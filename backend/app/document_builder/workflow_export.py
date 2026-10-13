"""Canonical PDF export and approved-revision adapter into existing courses."""

from io import BytesIO
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5
from xml.sax.saxutils import escape

from app.core.exceptions import ConflictError
from app.core.settings import settings
from app.core.storage import public_asset_url
from app.document_builder.pdf_builder import REQUIRED_METADATA_FIELDS
from app.generation.runtime import complete_generation, mark_stage, now_iso
from app.repositories.courses import CourseRepository
from app.repositories.database import advisory_lock
from app.schemas.document_workflow import (
    ImageBlock,
    ListBlock,
    TextBlock,
    fingerprint,
    module_text,
    outline_fingerprint,
)
from app.services.uploads import UploadService


def owned_path(resource):
    path = Path(resource["path"]).resolve()
    if (
        not path.is_relative_to((settings.derived_document_dir / "builder").resolve())
        or not path.is_file()
    ):
        raise ValueError("Owned source asset is unavailable")
    return path


class WorkflowExport:
    def __init__(self, drafts, courses=None):
        self.drafts = drafts
        self.courses = courses or CourseRepository()

    def pdf(self, draft_id, owner, expected):
        draft = self.drafts.get(draft_id, owner)
        if draft.revision != expected:
            raise ConflictError("Save the latest document before preview")
        if draft.content.metadata.missing_fields():
            raise ValueError("Complete course details before export")
        if draft.content.metadata.language.casefold() != "english":
            raise ValueError(
                "This release supports English PDF export; other language fonts are not validated"
            )
        assets = {r["id"]: r for r in self.drafts.resources(draft_id, owner, "asset")}
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.platypus import (
            Image,
            PageBreak,
            Paragraph,
            SimpleDocTemplate,
            Spacer,
            Table,
            TableStyle,
        )

        styles = getSampleStyleSheet()
        styles["BodyText"].fontSize = 11
        styles["BodyText"].leading = 16
        output = BytesIO()
        document = SimpleDocTemplate(
            output,
            pagesize=A4,
            leftMargin=48,
            rightMargin=48,
            topMargin=48,
            bottomMargin=48,
            title=draft.content.metadata.courseName,
        )
        story = [
            Paragraph(escape(draft.content.metadata.courseName), styles["Title"]),
            Spacer(1, 18),
        ]
        rows = [
            [
                Paragraph(escape(label), styles["BodyText"]),
                Paragraph(escape(str(getattr(draft.content.metadata, key))), styles["BodyText"]),
            ]
            for key, label in REQUIRED_METADATA_FIELDS
        ]
        metadata_table = Table(rows, colWidths=[150, 349])
        metadata_table.setStyle(
            TableStyle(
                [("VALIGN", (0, 0), (-1, -1), "TOP"), ("BOTTOMPADDING", (0, 0), (-1, -1), 12)]
            )
        )
        story.extend([metadata_table, PageBreak()])
        included = [m for m in draft.content.modules if m.included]

        def formatted(block):
            points = sorted(
                {0, len(block.text), *(m.start for m in block.marks), *(m.end for m in block.marks)}
            )
            parts = []
            for start, end in zip(points, points[1:]):
                value = escape(block.text[start:end]).replace("\n", "<br/>")
                for mark in block.marks:
                    if mark.start <= start and mark.end >= end:
                        if mark.type == "bold":
                            value = "<b>" + value + "</b>"
                        elif mark.type == "italic":
                            value = "<i>" + value + "</i>"
                        else:
                            value = (
                                '<link href="'
                                + escape(mark.href, {'"': "&quot;"})
                                + '">'
                                + value
                                + "</link>"
                            )
                parts.append(value)
            return "".join(parts)

        for number, module in enumerate(included, 1):
            heading = f"Module {number}: {module.title}"
            story.append(Paragraph(escape(heading), styles["Heading1"]))
            for block in module.blocks:
                if isinstance(block, ImageBlock):
                    asset = assets.get(block.assetId)
                    if not asset:
                        raise ValueError("Document image is unavailable")
                    from PIL import Image as PILImage

                    path = owned_path(asset)
                    with PILImage.open(path) as source:
                        width, height = source.size
                    shown_width = min(499 * block.width / 100, 499, 500 * width / height)
                    image = Image(str(path), width=shown_width, height=shown_width * height / width)
                    image.hAlign = block.align.upper()
                    story.extend(
                        [image, Paragraph(escape(block.caption), styles["Italic"]), Spacer(1, 10)]
                    )
                elif isinstance(block, TextBlock):
                    style = styles["Heading2"] if block.type == "heading" else styles["BodyText"]
                    story.extend([Paragraph(formatted(block), style), Spacer(1, 10)])
                elif isinstance(block, ListBlock):
                    for index, item in enumerate(block.items, 1):
                        story.append(
                            Paragraph(
                                f"{index}. " + escape(item)
                                if block.ordered
                                else "• " + escape(item),
                                styles["BodyText"],
                            )
                        )
                    story.append(Spacer(1, 10))
                else:
                    table = Table(
                        [
                            [Paragraph(escape(cell), styles["BodyText"]) for cell in row]
                            for row in block.rows
                        ],
                        colWidths=[499 / len(block.rows[0])] * len(block.rows[0]),
                        repeatRows=1,
                    )
                    table.setStyle(
                        TableStyle(
                            [
                                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                            ]
                        )
                    )
                    story.extend([table, Spacer(1, 10)])
        if not included:
            raise ValueError("Include at least one module")
        document.build(story)
        return output.getvalue()

    def create_course(self, draft_id, owner, expected):
        # Revision-derived identity makes retries deterministic without changing
        # existing filename-based callers or generated-course lifecycle behavior.
        course_id = "course_" + uuid5(NAMESPACE_URL, f"builder:{owner}:{draft_id}:{expected}").hex
        with advisory_lock("builder-handoff:" + draft_id):
            draft = self.drafts.get(draft_id, owner)
            if draft.revision != expected:
                raise ConflictError("Draft changed; review before creating a course")
            existing = self.courses.get_draft_for_trainer(course_id, owner)
            if existing:
                return existing
            content = draft.content
            if draft.approvedOutline != outline_fingerprint(content):
                raise ConflictError("Approve the current outline before creating a course")
            included = [module for module in content.modules if module.included]
            if (
                content.metadata.missing_fields()
                or not included
                or any(
                    not any(
                        block.type != "image"
                        and module_text(
                            type(module)(id=module.id, title=module.title, blocks=[block])
                        ).strip()
                        for block in module.blocks
                    )
                    for module in included
                )
            ):
                raise ValueError(
                    "Complete course details and every included module before creating a course"
                )
            self.drafts.validate_resources(draft_id, owner, content)
            exported = UploadService(settings.upload_dir).save_document(
                f"builder-{draft_id}-r{expected}-source.pdf",
                BytesIO(self.pdf(draft_id, owner, expected)),
                owner,
            )
            metadata = content.metadata
            course = {
                "course_id": course_id,
                "trainer_id": owner,
                "document_id": exported.document_id,
                "course_name": metadata.courseName,
                "course_description": metadata.courseDescription,
                "course_objective": metadata.courseObjective,
                "course_difficulty": metadata.courseDifficulty,
                "language": metadata.language,
                "target_audience": metadata.targetAudience,
                "created_at": now_iso(),
                "modules": [],
                "images": [],
                "document_builder": {
                    "draft_id": draft_id,
                    "revision": expected,
                    "content_hash": fingerprint(content),
                    "origin": "accepted_revision",
                },
            }
            assets = {r["id"]: r for r in self.drafts.resources(draft_id, owner, "asset")}
            from PIL import Image

            for number, module in enumerate(included, 1):
                images, texts = [], []
                for block in module.blocks:
                    if isinstance(block, ImageBlock):
                        asset = assets[block.assetId]
                        destination = (
                            settings.image_dir / f"builder_{course_id}_{block.assetId}.png"
                        )
                        destination.parent.mkdir(parents=True, exist_ok=True)
                        destination.write_bytes(owned_path(asset).read_bytes())
                        with Image.open(destination) as image:
                            width, height = image.size
                        record = {
                            "image_id": block.assetId,
                            "path": str(destination),
                            "url": public_asset_url("images", destination.name),
                            "caption": block.caption,
                            "width": width,
                            "height": height,
                            "orientation": "landscape" if width >= height else "portrait",
                        }
                        images.append(record)
                        course["images"].append(record)
                        texts.append(f"[IMAGE: {block.assetId}]\n{block.caption}")
                    else:
                        texts.append(
                            module_text(
                                type(module)(id=module.id, title=module.title, blocks=[block])
                            )
                        )
                course["modules"].append(
                    {
                        "module_number": number,
                        "title": module.title,
                        "source_text": "\n\n".join(texts),
                        "num_questions": 3,
                        "images": images,
                    }
                )
            mark_stage(course, "blueprint", "completed")
            complete_generation(course, 0)
            self.courses.save_draft(course)
            return self.courses.get_draft_for_trainer(course_id, owner)
