"""Strict, versioned contracts for persistent training-document drafts.

The model emits content only. Identities, ownership, revisions and mutation scope
are assigned and checked by the application, never by the language model.
"""

from __future__ import annotations

import hashlib
import json
import unicodedata
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=20000)]
Title = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=240)]
Identity = Annotated[str, StringConstraints(pattern=r"^[a-zA-Z0-9_-]{1,100}$")]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, validate_assignment=True)


class DraftMetadata(StrictModel):
    courseName: str = Field(default="", max_length=240)
    courseDescription: str = Field(default="", max_length=4000)
    courseObjective: str = Field(default="", max_length=4000)
    courseDifficulty: str = Field(default="Easy", max_length=80)
    language: str = Field(default="English", max_length=80)
    targetAudience: str = Field(default="", max_length=1000)
    courseType: str = Field(default="Training guide", max_length=120)

    def outline_missing_fields(self, entry_mode: str) -> list[str]:
        required = ["courseName"]
        if entry_mode == "ai":
            required += ["targetAudience", "courseObjective"]
        return [name for name in required if not getattr(self, name).strip()]

    def missing_fields(self) -> list[str]:
        return [name for name, value in self.model_dump().items() if not value.strip()]


class WritingSettings(StrictModel):
    moduleCount: int = Field(default=4, ge=2, le=8)
    detailLevel: Literal["short", "standard", "detailed"] = "standard"
    tone: Title = "Clear and professional"
    writingFocus: Literal["balanced", "conceptual", "practical", "process"] = "balanced"
    includeScenarios: bool = True
    includeBadGood: bool = True
    includeTakeaways: bool = True
    includeMistakes: bool = True


class TextMark(StrictModel):
    start: int = Field(ge=0)
    end: int = Field(gt=0)
    type: Literal["bold", "italic", "link"]
    href: str | None = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def valid_mark(self):
        if self.end <= self.start:
            raise ValueError("Mark range must be nonempty")
        if self.type == "link":
            if not self.href or not self.href.startswith(("https://", "http://", "mailto:")):
                raise ValueError("Links require an allowed URL scheme")
        elif self.href is not None:
            raise ValueError("Only link marks have an href")
        return self


class SourceReference(StrictModel):
    sourceId: Identity
    spanId: Identity


class TextBlock(StrictModel):
    sourceReferences: list[SourceReference] = Field(default_factory=list, max_length=100)
    id: Identity
    type: Literal["paragraph", "heading", "scenario", "takeaway"] = "paragraph"
    text: str = Field(default="", max_length=20000)
    marks: list[TextMark] = Field(default_factory=list, max_length=200)
    level: int = Field(default=2, ge=1, le=3)

    @model_validator(mode="after")
    def valid_ranges(self):
        if any(mark.end > len(self.text) for mark in self.marks):
            raise ValueError("Formatting range exceeds block text")
        return self


class ListBlock(StrictModel):
    sourceReferences: list[SourceReference] = Field(default_factory=list, max_length=100)
    id: Identity
    type: Literal["list"] = "list"
    ordered: bool = False
    items: list[Text] = Field(min_length=1, max_length=100)


class TableBlock(StrictModel):
    sourceReferences: list[SourceReference] = Field(default_factory=list, max_length=100)
    id: Identity
    type: Literal["table"] = "table"
    rows: list[list[str]] = Field(min_length=1, max_length=100)

    @model_validator(mode="after")
    def rectangular(self):
        width = len(self.rows[0])
        if not 1 <= width <= 20 or any(len(row) != width for row in self.rows):
            raise ValueError("Table must have 1–20 consistently sized columns")
        if any(len(cell) > 4000 for row in self.rows for cell in row):
            raise ValueError("Table cell exceeds size limit")
        return self


class ImageBlock(StrictModel):
    sourceReferences: list[SourceReference] = Field(default_factory=list, max_length=100)
    id: Identity
    type: Literal["image"] = "image"
    assetId: Identity
    caption: str = Field(default="", max_length=2000)
    width: int = Field(default=60, ge=25, le=100)
    align: Literal["left", "center", "right"] = "left"


Block = Annotated[TextBlock | ListBlock | TableBlock | ImageBlock, Field(discriminator="type")]


class SourceSpan(StrictModel):
    id: Identity
    text: Text
    location: Title


class ExtractedSource(StrictModel):
    id: Identity
    documentId: str | None = None
    contentHash: str = Field(pattern=r"^[a-f0-9]{64}$")
    spans: list[SourceSpan] = Field(default_factory=list, max_length=20000)
    issues: list[str] = Field(default_factory=list, max_length=1000)
    acknowledged: bool = False


class DraftModule(StrictModel):
    id: Identity
    title: Title
    objective: str = Field(default="", max_length=2000)
    included: bool = True
    sections: list[Title] = Field(default_factory=list, max_length=20)
    blocks: list[Block] = Field(default_factory=list, max_length=1000)
    sourceReferences: list[SourceReference] = Field(default_factory=list, max_length=20000)
    status: Literal["empty", "ready", "generating", "failed"] = "empty"


class DraftContent(StrictModel):
    schemaVersion: Literal[1] = 1
    entryMode: Literal["existing", "ai", "blank"]
    metadata: DraftMetadata = Field(default_factory=DraftMetadata)
    settings: WritingSettings = Field(default_factory=WritingSettings)
    modules: list[DraftModule] = Field(default_factory=list, max_length=200)

    @model_validator(mode="after")
    def unique_ids(self):
        ids = [module.id for module in self.modules]
        ids += [block.id for module in self.modules for block in module.blocks]
        if len(ids) != len(set(ids)):
            raise ValueError("Module and block identities must be globally unique in a draft")
        return self


def fingerprint(value: BaseModel | dict | list | str) -> str:
    if isinstance(value, BaseModel):
        value = value.model_dump(mode="json")
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def outline_fingerprint(content: DraftContent) -> str:
    """Bodies do not change structure approval; metadata/settings do."""
    return fingerprint(
        {
            "metadata": content.metadata.model_dump(),
            "settings": content.settings.model_dump(),
            "sourceBlocks": [
                {"id": block.id, "references": [ref.model_dump() for ref in block.sourceReferences]}
                for module in content.modules
                for block in module.blocks
                if block.sourceReferences
            ],
            "modules": [
                {
                    key: module.model_dump()[key]
                    for key in (
                        "id",
                        "title",
                        "objective",
                        "included",
                        "sections",
                        "sourceReferences",
                    )
                }
                for module in content.modules
            ],
        }
    )


def module_text(module: DraftModule) -> str:
    parts = []
    for block in module.blocks:
        if isinstance(block, TextBlock):
            parts.append(block.text)
        elif isinstance(block, ListBlock):
            parts.append("\n".join(block.items))
        elif isinstance(block, TableBlock):
            parts.append("\n".join(" | ".join(row) for row in block.rows))
        elif block.caption:
            parts.append(block.caption)
    return "\n\n".join(parts).strip()


class DraftRecord(StrictModel):
    id: Identity
    revision: int = Field(ge=1)
    content: DraftContent
    approvedOutline: str | None = None
    createdAt: str
    updatedAt: str
    # Set on reads and saves: the course already created from this draft, if any.
    courseId: str | None = None


class SaveDraft(StrictModel):
    expectedRevision: int = Field(ge=1)
    content: DraftContent


class CopyDraft(StrictModel):
    content: DraftContent


class RevisionRequest(StrictModel):
    expectedRevision: int = Field(ge=1)


class RestoreDraft(RevisionRequest):
    restoreRevision: int = Field(ge=1)


class OperationRequest(RevisionRequest):
    task: Literal[
        "outline", "draft", "draft_module", "edit", "answer", "revise", "insert", "import"
    ]
    sourceImport: ImportRequest | None = None
    scope: Literal["selected", "module", "document"] = "selected"
    moduleId: Identity | None = None
    insertAfter: Identity | None = None
    instruction: str = Field(default="", max_length=4000)
    target: SelectionTarget | None = None
    key: Identity


class ImportRequest(RevisionRequest):
    referenceOnly: bool = False
    documentId: str | None = Field(default=None, max_length=100)
    text: str | None = Field(default=None, max_length=100000)

    @model_validator(mode="after")
    def one_source(self):
        if bool(self.documentId) == bool(self.text and self.text.strip()):
            raise ValueError("Provide one uploaded document or pasted text")
        return self


class SourceAcknowledgement(RevisionRequest):
    acknowledged: bool


# These schemas describe model content, deliberately without trusted IDs.
class OutlineModule(StrictModel):
    title: Title
    objective: Text
    sections: list[Title] = Field(min_length=1, max_length=20)


class OutlineResponse(StrictModel):
    modules: list[OutlineModule] = Field(min_length=2, max_length=8)

    @model_validator(mode="after")
    def distinct_titles(self):
        titles = [module.title.casefold() for module in self.modules]
        if len(titles) != len(set(titles)):
            raise ValueError("Outline module titles must be distinct")
        return self


class AcceptProposal(RevisionRequest):
    outline: OutlineResponse | None = None


class GeneratedTextBlock(StrictModel):
    type: Literal["paragraph", "heading", "scenario", "takeaway"]
    text: Text


class ModuleResponse(StrictModel):
    blocks: list[GeneratedTextBlock] = Field(min_length=1, max_length=100)
    sourceReferences: list[SourceReference] = Field(default_factory=list, max_length=100)


class EditResponse(StrictModel):
    replacementText: Text
    summary: Title
    sourceReferences: list[SourceReference] = Field(default_factory=list, max_length=100)


class AnswerResponse(StrictModel):
    answer: Text
    insufficientEvidence: bool
    sourceReferences: list[SourceReference] = Field(max_length=100)

    @model_validator(mode="after")
    def requires_evidence(self):
        if not self.insufficientEvidence and not self.sourceReferences:
            raise ValueError("A source answer requires evidence or insufficientEvidence=true")
        return self


class RevisionResponse(StrictModel):
    replacements: list[Text] = Field(min_length=1, max_length=20)
    summary: Title
    sourceReferences: list[SourceReference] = Field(default_factory=list, max_length=100)


class SelectionTarget(StrictModel):
    moduleId: Identity
    blockId: Identity
    start: int = Field(ge=0)
    end: int = Field(gt=0)
    textHash: str = Field(pattern=r"^[a-f0-9]{64}$")

    @model_validator(mode="after")
    def ordered(self):
        if self.end <= self.start:
            raise ValueError("Selection must be nonempty")
        return self


def validate_selection(content: DraftContent, target: SelectionTarget) -> str:
    module = next((m for m in content.modules if m.id == target.moduleId), None)
    block = next((b for b in module.blocks if b.id == target.blockId), None) if module else None
    if not isinstance(block, TextBlock) or target.end > len(block.text):
        raise ValueError("Selection is not within a supported text block")
    for boundary in (target.start, target.end):
        if 0 < boundary < len(block.text):
            next_char, previous = block.text[boundary], block.text[boundary - 1]
            if (
                unicodedata.category(next_char).startswith("M")
                or ord(next_char) in range(0x1F3FB, 0x1F400)
                or next_char == "\u200d"
                or previous == "\u200d"
                or unicodedata.combining(previous) == 9
            ):
                raise ValueError(
                    "Selection splits a combined character; select the whole character"
                )
            if 0x1F1E6 <= ord(next_char) <= 0x1F1FF:
                preceding = 0
                for char in reversed(block.text[:boundary]):
                    if not 0x1F1E6 <= ord(char) <= 0x1F1FF:
                        break
                    preceding += 1
                if preceding % 2:
                    raise ValueError("Selection splits a flag character")
    selected = block.text[target.start : target.end]
    if fingerprint(selected) != target.textHash:
        raise ValueError("Selection text changed")
    return selected


def utf16_to_codepoint(text: str, offset: int) -> int:
    """Convert browser/Dart UTF-16 offsets; reject half a surrogate pair."""
    if offset < 0:
        raise ValueError("Negative UTF-16 offset")
    units = 0
    for index, char in enumerate(text):
        if units == offset:
            return index
        units += 2 if ord(char) > 0xFFFF else 1
        if units > offset:
            raise ValueError("Offset splits a surrogate pair")
    if units == offset:
        return len(text)
    raise ValueError("UTF-16 offset exceeds text")


OperationRequest.model_rebuild()
