import pytest
from pydantic import ValidationError

from app.modules.generation.pipeline.blueprint import _normalize_labelled_modules
from app.modules.generation.schemas.narration import batch_script_schema

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

    _normalize_labelled_modules(modules, ["Welcome", "Why checks matter", "Short intro", "Daily checks", "Walk the floor"])

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
    from app.modules.generation.pipeline.blueprint import assign_images_to_modules

    lines = ["Module 1: A", "Text one.", "Module 2: B", "Text two.", "Module 3: C", "Text three."]
    modules = [_module(1, "Module 1: A", 1), _module(2, "Module 2: B", 3), _module(3, "Module 3: C", 5)]
    image = {"image_id": "img_p1", "page": 1, "caption": "Image on page 1"}

    assign_images_to_modules([image], lines, modules, total_pages=2, line_pages=[1, 1, 2, 2, 2, 2])

    assert [m["images"] for m in modules] == [[image], [], []]


def test_folds_preamble_when_llm_drops_labels_from_titles() -> None:
    modules = [
        _module(1, "Introduction to Fire Safety", 1),
        _module(2, "Recognising Fire Hazards", 4),
        _module(3, "Using a Fire Extinguisher", 6),
    ]

    _normalize_labelled_modules(modules, LINES)

    assert [(m["title"], m["start_line"]) for m in modules] == [
        ("Module 1: Recognising Fire Hazards", 1),
        ("Module 2: Using a Fire Extinguisher", 6),
    ]


def test_keeps_opening_module_that_holds_labelled_content() -> None:
    modules = [_module(1, "Introduction and hazards", 1), _module(2, "Using a Fire Extinguisher", 6)]

    _normalize_labelled_modules(modules, LINES)

    assert [m["start_line"] for m in modules] == [1, 6]


def test_retitles_module_named_after_the_course_with_its_label() -> None:
    lines = ["Fire Safety Course", "Module 1: Hazards", "Check sockets.", "Module 2: Extinguishers", "Pull the pin."]
    modules = [_module(1, "Fire Safety Course", 1), _module(2, "Extinguishers", 4)]

    _normalize_labelled_modules(modules, lines)

    assert [m["title"] for m in modules] == ["Module 1: Hazards", "Module 2: Extinguishers"]


GUIDE_LINES = [
    "Module 1: Why Saving Alone Is Not Enough",
    "Most of us are taught to save.",
    "Key takeaway: saving alone loses value.",
    "Module 2: The Power of Compounding",
    "Compounding means earning returns on returns.",
    "Key takeaway: start early.",
    "Module 3: Asset Classes",
    "Equity, debt, gold and real estate.",
    "Key takeaway: each asset has a role.",
]


def test_labelled_document_is_split_exactly_at_its_headings() -> None:
    from app.modules.generation.pipeline.blueprint import modules_from_labels

    modules = modules_from_labels(GUIDE_LINES)

    assert [(m["module_number"], m["title"], m["start_line"]) for m in modules] == [
        (1, "Module 1: Why Saving Alone Is Not Enough", 1),
        (2, "Module 2: The Power of Compounding", 4),
        (3, "Module 3: Asset Classes", 7),
    ]


def test_labelled_document_skips_the_llm(monkeypatch) -> None:
    from app.modules.generation.pipeline import blueprint

    def fail(*args, **kwargs):
        raise AssertionError("the LLM must not be asked to split a labelled document")

    monkeypatch.setattr(blueprint, "safe_chat_completion", fail)

    modules = blueprint.extract_modules_with_llm(GUIDE_LINES)

    assert [m["start_line"] for m in modules] == [1, 4, 7]


def test_short_preamble_joins_the_first_labelled_module() -> None:
    from app.modules.generation.pipeline.blueprint import modules_from_labels

    modules = modules_from_labels(["Fire Safety Course", "For branch staff."] + GUIDE_LINES)

    assert [m["start_line"] for m in modules] == [1, 6, 9]


def test_labels_fall_back_to_the_llm_when_they_are_not_a_clean_sequence() -> None:
    from app.modules.generation.pipeline.blueprint import modules_from_labels

    two_labels = GUIDE_LINES[:6]
    gap = [line.replace("Module 3", "Module 4") for line in GUIDE_LINES]
    table_of_contents = ["Module 1: A", "Module 2: B", "Module 3: C"] + GUIDE_LINES
    nested = ["Chapter 1: Basics", "Unit 1: Saving", "Text.", "Unit 2: Spending", "Text.", "Chapter 2: More", "Text."]
    long_opening = ["Overview " + "of the policy. " * 60] + GUIDE_LINES
    sentence = GUIDE_LINES[:6] + ["Module 3 " + "covers asset classes in depth and more " * 5]

    for lines in (two_labels, gap, table_of_contents, nested, long_opening, sentence):
        assert modules_from_labels(lines) is None


def test_bare_label_line_takes_the_next_line_as_its_title() -> None:
    from app.modules.generation.pipeline.blueprint import modules_from_labels

    lines = ["Module 1.", "Intro", "Text.", "Module 2.", "Rules", "Text.", "Module 3:", "Review", "Text."]

    assert [m["title"] for m in modules_from_labels(lines)] == [
        "Module 1: Intro",
        "Module 2: Rules",
        "Module 3: Review",
    ]


def test_header_adjustment_keeps_a_module_that_starts_on_its_label() -> None:
    from app.modules.generation.pipeline.blueprint import adjust_start_lines_for_headers

    # The previous module ends with a short line that shares words with the next title,
    # which the fuzzy header match used to pull into the next module.
    lines = [
        "Module 1: Saving",
        "Text about saving.",
        "Compounding is powerful.",
        "Module 2: The Power of Compounding",
        "More text.",
    ]
    modules = [_module(1, lines[0], 1), _module(2, lines[3], 4)]

    adjust_start_lines_for_headers(modules, lines)

    assert modules[1]["start_line"] == 4
