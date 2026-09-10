from __future__ import annotations

from app.generation.html import render_image_slide
from app.generation.slides import _expand_mapped_image_slides


def _image(image_id: str, orientation: str, caption: str = "Source caption") -> dict:
    return {
        "image_id": image_id,
        "caption": caption,
        "file_path": f"assets/images/course/{image_id}.png",
        "orientation": orientation,
    }


def test_expands_mapped_images_after_content_slide() -> None:
    module = {
        "module_number": 1,
        "slides": [
            {
                "title": "Risk profile",
                "slide_title": "Risk profile",
                "layout_type": "bullets",
                "content": ["Match risk to client needs."],
                "images": [_image("img_1", "portrait")],
                "image_ids": ["img_1"],
            },
            {
                "title": "Next topic",
                "slide_title": "Next topic",
                "layout_type": "bullets",
                "content": ["Continue."],
                "images": [],
            },
        ],
    }

    expanded = _expand_mapped_image_slides(module)["slides"]

    assert [slide["layout_type"] for slide in expanded] == ["bullets", "image", "bullets"]
    assert expanded[0]["image_ids"] == []
    assert expanded[0]["images"] == []
    assert expanded[0]["mapped_image_ids"] == ["img_1"]
    assert expanded[1]["is_image_slide"] is True
    assert expanded[1]["source_slide_title"] == "Risk profile"
    assert expanded[1]["image_ids"] == ["img_1"]


def test_groups_three_vertical_images_on_one_image_slide() -> None:
    module = {
        "module_number": 1,
        "slides": [
            {
                "title": "Documents",
                "slide_title": "Documents",
                "layout_type": "bullets",
                "content": ["Review three forms."],
                "images": [
                    _image("img_1", "portrait"),
                    _image("img_2", "square"),
                    _image("img_3", "portrait"),
                ],
            }
        ],
    }

    expanded = _expand_mapped_image_slides(module)["slides"]

    assert len(expanded) == 2
    assert expanded[1]["image_layout"] == "vertical"
    assert expanded[1]["image_ids"] == ["img_1", "img_2", "img_3"]


def test_splits_third_landscape_image_to_separate_slide() -> None:
    module = {
        "module_number": 1,
        "slides": [
            {
                "title": "Charts",
                "slide_title": "Charts",
                "layout_type": "bullets",
                "content": ["Compare charts."],
                "images": [
                    _image("img_1", "landscape"),
                    _image("img_2", "landscape"),
                    _image("img_3", "landscape"),
                ],
            }
        ],
    }

    expanded = _expand_mapped_image_slides(module)["slides"]

    assert len(expanded) == 3
    assert expanded[1]["image_layout"] == "landscape"
    assert expanded[1]["image_ids"] == ["img_1", "img_2"]
    assert expanded[2]["image_layout"] == "landscape"
    assert expanded[2]["image_ids"] == ["img_3"]


def test_image_slide_renderer_has_no_visible_caption_or_title() -> None:
    slide = {
        "layout_type": "image",
        "is_image_slide": True,
        "image_layout": "vertical",
        "slide_title": "",
        "images": [_image("img_1", "portrait", "Hidden caption")],
    }

    html = "".join(render_image_slide(slide, {}))

    assert "image-slide-stage--vertical" in html
    assert "../../images/course/img_1.png" in html
    assert "Hidden caption" in html
    assert "<figcaption" not in html
    assert "brand-slide-title" not in html
