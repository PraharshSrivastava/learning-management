from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.schemas.document_workflow import (
    AnswerResponse,
    DraftContent,
    DraftMetadata,
    DraftModule,
    ImageBlock,
    SelectionTarget,
    TableBlock,
    TextBlock,
    TextMark,
    fingerprint,
    outline_fingerprint,
    utf16_to_codepoint,
    validate_selection,
)


def draft() -> DraftContent:
    return DraftContent(
        entryMode="blank",
        modules=[
            DraftModule(
                id="module_1",
                title="Customer needs",
                blocks=[
                    TextBlock(id="text_1", text="Ask 😀 and listen."),
                    ImageBlock(id="image_1", assetId="owned_asset"),
                ],
            )
        ],
    )


def test_metadata_reports_every_empty_field_not_only_last_duplicate():
    assert DraftMetadata().missing_fields() == [
        "courseName",
        "courseDescription",
        "courseObjective",
        "targetAudience",
    ]


def test_outline_approval_survives_body_edit_but_not_reorder_or_settings():
    content = draft()
    before = outline_fingerprint(content)
    content.modules[0].blocks[0].text = "New explanation"
    assert outline_fingerprint(content) == before
    content.settings.moduleCount = 3
    assert outline_fingerprint(content) != before


def test_canonical_round_trip_preserves_images_and_formatting_order():
    content = draft()
    content.modules[0].blocks[0].marks = [TextMark(start=0, end=3, type="bold")]
    restored = DraftContent.model_validate_json(content.model_dump_json())
    assert restored == content
    assert restored.modules[0].blocks[1].assetId == "owned_asset"


def test_rejects_duplicate_module_or_block_identity():
    content = draft().model_dump()
    content["modules"][0]["blocks"][1]["id"] = "text_1"
    with pytest.raises(ValidationError):
        DraftContent.model_validate(content)


@pytest.mark.parametrize("href", ["javascript:alert(1)", "data:text/html,hi", "file:///private"])
def test_rejects_unsafe_link_marks(href):
    with pytest.raises(ValidationError):
        TextMark(start=0, end=2, type="link", href=href)


def test_rejects_out_of_bounds_formatting_and_ragged_table():
    with pytest.raises(ValidationError):
        TextBlock(id="b", text="short", marks=[TextMark(start=0, end=99, type="bold")])
    with pytest.raises(ValidationError):
        TableBlock(id="b", rows=[["a", "b"], ["c"]])


def test_target_is_bound_to_exact_text_and_block():
    content = draft()
    target = SelectionTarget(
        moduleId="module_1", blockId="text_1", start=0, end=3, textHash=fingerprint("Ask")
    )
    assert validate_selection(content, target) == "Ask"
    content.modules[0].blocks[0].text = "Changed paragraph"
    with pytest.raises(ValueError, match="changed"):
        validate_selection(content, target)


def test_image_is_not_a_text_edit_target():
    target = SelectionTarget(
        moduleId="module_1", blockId="image_1", start=0, end=3, textHash=fingerprint("Ask")
    )
    with pytest.raises(ValueError, match="supported text"):
        validate_selection(draft(), target)


@pytest.mark.parametrize("units,expected", [(0, 0), (4, 4), (6, 5), (17, 16)])
def test_browser_utf16_conversion_with_emoji(units, expected):
    assert utf16_to_codepoint("Ask 😀 and listen.", units) == expected


@pytest.mark.parametrize("units", [-1, 5, 99])
def test_rejects_invalid_or_split_utf16_offsets(units):
    with pytest.raises(ValueError):
        utf16_to_codepoint("Ask 😀 and listen.", units)


def test_source_question_requires_citation_or_explicit_missing_evidence():
    with pytest.raises(ValidationError):
        AnswerResponse(
            answer="Refunds take three days.", insufficientEvidence=False, sourceReferences=[]
        )
    assert AnswerResponse(
        answer="The source contains no refund deadline.",
        insufficientEvidence=True,
        sourceReferences=[],
    )
