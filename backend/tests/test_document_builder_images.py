"""Builder images must use the same asset contract as extracted document images."""

from contextlib import nullcontext
from types import SimpleNamespace

from PIL import Image

from app.document_builder import workflow_export
from app.generation.html import render_image_slide
from app.schemas.document_workflow import (
    DraftContent,
    DraftMetadata,
    DraftModule,
    ImageBlock,
    TextBlock,
)

pytest_plugins = ["test_document_draft_repository"]


def test_png_reaches_pdf_blueprint_and_video_slide_with_canonical_path(repo, monkeypatch, tmp_path):
    monkeypatch.setattr(workflow_export.settings, "derived_document_dir", tmp_path / "derived")
    monkeypatch.setattr(workflow_export.settings, "image_dir", tmp_path / "images")
    monkeypatch.setattr(workflow_export, "advisory_lock", lambda *a: nullcontext())
    draft = repo.create(
        "owner",
        DraftContent(
            entryMode="ai",
            metadata=DraftMetadata(
                courseName="Listening",
                courseDescription="Service skills",
                courseObjective="Listen carefully",
                targetAudience="New staff",
            ),
            modules=[
                DraftModule(
                    id="m",
                    title="Listening",
                    blocks=[
                        TextBlock(id="b", text="Listen first."),
                        ImageBlock(id="i", assetId="asset", caption="An attentive listener"),
                    ],
                )
            ],
        ),
    )
    source = tmp_path / "derived" / "builder" / draft.id / "manual" / "asset.png"
    source.parent.mkdir(parents=True)
    Image.new("RGB", (240, 120), "navy").save(source)
    repo.put_resource(
        draft.id, "owner", "asset", "asset", {"path": str(source), "mime": "image/png"}
    )
    approved = repo.approve(draft.id, "owner", 1)

    class Upload:
        def __init__(self, *args):
            pass

        def save_document(self, name, stream, owner):
            assert stream.read().startswith(b"%PDF")
            return SimpleNamespace(document_id="source-document")

    monkeypatch.setattr(workflow_export, "UploadService", Upload)
    saved = {}
    courses = SimpleNamespace(
        get_draft_for_trainer=lambda cid, owner: saved.get(cid),
        save_draft=lambda c: saved.update({c["course_id"]: c}),
    )
    course = workflow_export.WorkflowExport(repo, courses).create_course(
        draft.id, "owner", approved.revision
    )
    record = course["modules"][0]["images"][0]
    assert record == course["images"][0]
    assert record["file_path"].startswith("assets/images/builder_")
    assert record["file_path"].endswith(".png")
    destination = tmp_path / "images" / record["file_path"].split("/")[-1]
    assert destination.read_bytes() == source.read_bytes()
    html = "".join(
        render_image_slide(
            {"images": [record], "image_layout": "landscape"}, {record["image_id"]: record}
        )
    )
    assert f'src="{record["file_path"].replace("assets/", "../../")}"' in html
    assert 'src=""' not in html
    assert record["caption"] in html
