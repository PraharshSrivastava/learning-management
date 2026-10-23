import pytest
from pydantic import ValidationError

from app.generation.blueprint import _normalize_labelled_modules
from app.schemas.generation.narration import batch_script_schema

LINES = [
    "Fire Safety and Evacuation for Branch Staff",
    "Practical guidance on preventing fires.",
    "Audience: All branch employees",
    "Module 1: Recognising Fire Hazards",
    "Check sockets daily.",
    "Module 2: Using a Fire Extinguisher",
    "Pull, aim, squeeze, sweep.",
]


def _module(number, title, start):
    return {"module_number": number, "title": title, "start_line": start}


def test_folds_title_page_preamble_into_first_labelled_module() -> None:
    modules = [
        _module(1, "Introduction to Fire Safety", 1),
        _module(2, "Module 1: Recognising Fire Hazards", 4),
        _module(3, "Module 2: Using a Fire Extinguisher", 6),
    ]

    _normalize_labelled_modules(modules, LINES)

    assert [(m["module_number"], m["title"], m["start_line"]) for m in modules] == [
        (1, "Module 1: Recognising Fire Hazards", 1),
        (2, "Module 2: Using a Fire Extinguisher", 6),
    ]


def test_trims_course_title_glued_onto_module_label() -> None:
    modules = [
        _module(1, "Fire Safety and Evacuation for Branch Staff / Module 1: Recognising Fire Hazards", 1),
        _module(2, "Module 2: Using a Fire Extinguisher", 6),
    ]

    _normalize_labelled_modules(modules, LINES)

    assert modules[0]["title"] == "Module 1: Recognising Fire Hazards"


def test_keeps_substantial_unlabelled_opening_module() -> None:
    lines = ["Overview " + "of the policy. " * 60, "Module 1: A", "Text.", "Module 2: B", "Text."]
    modules = [_module(1, "Overview", 1), _module(2, "Module 1: A", 2), _module(3, "Module 2: B", 4)]

    _normalize_labelled_modules(modules, lines)

    assert [m["title"] for m in modules] == ["Overview", "Module 1: A", "Module 2: B"]


def test_leaves_documents_without_module_labels_unchanged() -> None:
    modules = [_module(1, "Getting started", 1), _module(2, "Daily checks", 4)]

    _normalize_labelled_modules(modules, LINES)

    assert [m["title"] for m in modules] == ["Getting started", "Daily checks"]


def test_batch_scripts_carry_slide_anchor() -> None:
    schema = batch_script_schema(1)

    parsed = schema.model_validate(
        {"slides": [{"slide_number": 3, "slide_title": "Keeping Exits Clear", "script": "Keep exits clear."}]}
    )

    assert parsed.slides[0].slide_number == 3
    with pytest.raises(ValidationError):
        schema.model_validate({"slides": [{"script": "Unanchored narration."}]})


def test_uncaptioned_pdf_image_joins_module_holding_its_page() -> None:
    from app.generation.blueprint import assign_images_to_modules

    lines = ["Module 1: A", "Text one.", "Module 2: B", "Text two.", "Module 3: C", "Text three."]
    modules = [_module(1, "Module 1: A", 1), _module(2, "Module 2: B", 3), _module(3, "Module 3: C", 5)]
    image = {"image_id": "img_p1", "page": 1, "caption": "Image on page 1"}

    assign_images_to_modules([image], lines, modules, total_pages=2, line_pages=[1, 1, 2, 2, 2, 2])

    assert [m["images"] for m in modules] == [[image], [], []]
