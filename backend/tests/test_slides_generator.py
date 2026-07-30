from pathlib import Path

from pipelines import slides_generator


def test_generated_grid_uses_gallery_layout_assets_and_styles(tmp_path, monkeypatch):
    monkeypatch.setattr(slides_generator, "BASE_DIR", str(tmp_path))
    module = {
        "title": "Reference-styled module",
        "images": [],
        "slides": [
            {
                "slide_title": "Reference grid",
                "layout_type": "grid",
                "grid_data": {
                    "columns": [
                        {"header": "First", "points": ["One point"]},
                        {"header": "Second", "points": ["Two points"]},
                    ]
                },
            }
        ],
    }

    output_path = slides_generator.generate_html_slides_for_module("course", 0, module)
    html = Path(output_path).read_text(encoding="utf-8")

    assert 'class="brand-name">PhillipCapital</div>' in html
    assert 'class="gallery-grid insight-grid count-2"' in html
    assert 'class="insight-icon" src="../../brand/icon-10.svg"' in html
    assert '<li>One point</li>' in html
