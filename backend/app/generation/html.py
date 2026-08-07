"""Render course slide layouts and compile learner-facing HTML decks."""

from __future__ import annotations

import html
import os
from typing import Any, Dict, List

from app.core.logging import generation_logger
from app.core.providers import SLIDE_DIR
from app.repositories.courses import get_all_courses

logger = generation_logger(__name__)

def escape(value: object) -> str:
    return "" if value is None else html.escape(str(value), quote=True)

def brand_icon_path(slide_index: int, slot: int = 0) -> str:
    icon_number = 10 + ((slide_index + slot) % 14)
    return f"../../brand/icon-{icon_number}.svg"

def render_layout(
    slide: dict[str, Any],
    *,
    layout: str,
    is_cover: bool,
    is_variant_one: bool,
    module_number: int,
    slide_index: int,
) -> list[str]:
    if is_cover:
        return _render_cover(slide, module_number)
    if layout == "concept" and slide.get("concept_data"):
        return _render_concept(slide["concept_data"], slide_index)
    if layout == "steps" and slide.get("steps_data"):
        return _render_steps(slide["steps_data"], is_variant_one)
    if layout == "comparison" and slide.get("comparison_data"):
        return _render_comparison(slide["comparison_data"], is_variant_one)
    if layout == "grid" and slide.get("grid_data"):
        return _render_grid(slide["grid_data"], is_variant_one, slide_index)
    return _render_bullets(slide, is_variant_one)

def render_images(
    image_ids: list[str],
    images_by_id: dict[str, dict[str, Any]],
) -> list[str]:
    if not image_ids:
        return []
    parts = [
        f'<aside class="image-grid count-{min(len(image_ids), 3)}" '
        'aria-label="Course source images">'
    ]
    for image_id in image_ids[:3]:
        image = images_by_id.get(image_id)
        if not image:
            continue
        path = str(image.get("file_path", "")).replace("assets/", "../../")
        parts.append(f'<div class="image"><img src="{escape(path)}"></div>')
    parts.append("</aside>")
    return parts

def _render_cover(slide: dict[str, Any], module_number: int) -> list[str]:
    total_modules = slide.get("total_modules", "")
    current_module = slide.get("module_number", module_number)
    suffix = f" of {escape(total_modules)}" if total_modules else ""
    title = slide.get("slide_title") or slide.get("title", "Untitled")
    try:
        module_display = f"{int(current_module):02d}"
    except (TypeError, ValueError):
        module_display = escape(current_module)
    return [
        '<div class="module-cover">',
        f'<div class="module-cover-course">{escape(slide.get("course_name", ""))}</div>',
        '<div class="module-cover-brand">PhillipCapital'
        '<div class="module-cover-brand-tagline">Wealth. Across Chapters.</div></div>',
        '<div class="module-cover-orb" aria-hidden="true"></div>',
        '<div class="module-cover-swoosh" aria-hidden="true"></div>',
        f'<div class="module-cover-number" aria-hidden="true">{module_display}</div>',
        f"<h1>{escape(title)}</h1>",
        '<div class="module-cover-rule" aria-hidden="true"></div>',
        f'<div class="module-cover-kicker">Module {escape(current_module)}{suffix}</div>',
        "</div>",
    ]

def _render_concept(data: dict[str, Any], slide_index: int) -> list[str]:
    takeaways = _concept_takeaways(data)
    points = (
        '<div class="point-list">'
        + "".join(f'<div class="point">{escape(item)}</div>' for item in takeaways)
        + "</div>"
        if takeaways
        else ""
    )
    return [
        f'<section class="silver-panel {"no-points" if not takeaways else ""}" '
        f'style="--point-cols:{max(len(takeaways), 1)}">'
        f'<div class="panel-copy"><div class="panel-title">'
        f"{escape(data.get('core_term', ''))}</div>"
        f'<div class="panel-definition">{escape(data.get("definition", ""))}</div></div>'
        f'<div class="icon-tile"><img src="{brand_icon_path(slide_index)}" alt=""></div>'
        f"{points}</section>"
    ]

def _concept_takeaways(data: dict[str, Any]) -> list[str]:
    takeaways = data.get("key_takeaways", [])
    if not takeaways and data.get("key_takeaway"):
        takeaways = [data["key_takeaway"]]
    return [str(item).strip() for item in takeaways if str(item).strip()]

def _concept_density_class(slide: dict[str, Any], has_images: bool) -> str:
    data = slide.get("concept_data") or {}
    takeaways = _concept_takeaways(data)
    definition_words = len(str(data.get("definition", "")).split())

    if has_images:
        return ""
    if not takeaways:
        return " concept-sparse"
    if len(takeaways) < 3 and definition_words < 30:
        return " concept-focus"
    return " concept-balanced"

def _render_steps(data: dict[str, Any], is_variant_one: bool) -> list[str]:
    steps = list(data.get("steps", []))[:5]
    count = min(max(len(steps), 1), 5)
    if is_variant_one:
        parts = [f'<div class="steps-fit step-cards steps-{count}">']
        for index, step in enumerate(steps):
            parts.append(
                f'<section class="step-card"><div class="step-num">{index + 1:02d}</div>'
                f'<h3 class="step-title">{escape(step.get("title", ""))}</h3>'
                f'<p class="step-desc">{escape(step.get("description", ""))}</p></section>'
            )
    else:
        parts = [f'<div class="steps-fit step-bands steps-{count}" style="--steps:{count}">']
        for index, step in enumerate(steps):
            parts.append(
                f'<section class="step-band"><div class="band-num">{index + 1:02d}</div>'
                f'<div class="band-copy"><h3 class="band-title">'
                f"{escape(step.get('title', ''))}</h3>"
                f'<p class="band-desc">{escape(step.get("description", ""))}</p>'
                "</div></section>"
            )
    parts.append("</div>")
    return parts

def _render_comparison(data: dict[str, Any], is_variant_one: bool) -> list[str]:
    left = list(data.get("left_column_points", []))
    right = list(data.get("right_column_points", []))
    rows = min(max(len(left), len(right), 2), 4)
    left_title = escape(data.get("left_column_title", ""))
    right_title = escape(data.get("right_column_title", ""))
    if is_variant_one:
        parts = [
            f'<div class="comparison-fit rows-{rows} compare-matrix" style="--rows:{rows}">'
            f'<div class="compare-matrix-head"><div></div>'
            f'<div class="side-title">{left_title}</div>'
            f'<div class="side-title">{right_title}</div></div>'
        ]
        for index in range(rows):
            parts.append(
                f'<div class="compare-matrix-row"><div class="row-number">'
                f"{index + 1:02d}</div>"
                f'<div class="compare-cell">{escape(left[index]) if index < len(left) else "-"}</div>'
                f'<div class="compare-cell">{escape(right[index]) if index < len(right) else "-"}</div>'
                "</div>"
            )
        parts.append("</div>")
        return parts

    parts = [
        f'<div class="comparison-fit rows-{rows} compare-lanes" style="--rows:{rows}">'
        f'<section class="lane-panel left"><div class="lane-title">{left_title}</div>'
    ]
    parts.extend(
        f'<div class="lane-point">{escape(left[index]) if index < len(left) else "-"}</div>'
        for index in range(rows)
    )
    parts.append(
        '</section><div class="compare-spine"><div class="spine-vs">VS</div>'
        + "".join(f'<div class="spine-dot"><span>{index + 1}</span></div>' for index in range(rows))
        + f'</div><section class="lane-panel right"><div class="lane-title">{right_title}</div>'
    )
    parts.extend(
        f'<div class="lane-point">{escape(right[index]) if index < len(right) else "-"}</div>'
        for index in range(rows)
    )
    parts.append("</section></div>")
    return parts

def _render_grid(data: dict[str, Any], is_variant_one: bool, slide_index: int) -> list[str]:
    columns = list(data.get("columns", []))[:6]
    count = min(max(len(columns), 2), 6)
    variant = "insight-grid" if is_variant_one else "lane-grid"
    parts = [f'<div class="grid-fit"><div class="gallery-grid {variant} count-{count}">']
    for index, column in enumerate(columns):
        points = list(column.get("points") or [])
        if not points and column.get("content"):
            points = [column["content"]]
        points_html = (
            '<ul class="grid-points">'
            + "".join(f"<li>{escape(point)}</li>" for point in points if point)
            + "</ul>"
        )
        if is_variant_one:
            parts.append(
                f'<section class="insight-card"><div class="insight-num grid-icon-tile">'
                f'<img src="{brand_icon_path(slide_index, index)}" alt=""></div>'
                f"<h3>{escape(column.get('header', ''))}</h3>{points_html}</section>"
            )
        else:
            parts.append(
                f'<section class="lane-card"><div class="lane-num">'
                f'<img src="{brand_icon_path(slide_index, index)}" alt=""></div>'
                f'<div class="lane-copy"><h3>{escape(column.get("header", ""))}</h3>'
                f"{points_html}</div></section>"
            )
    parts.append("</div></div>")
    return parts

def _render_bullets(slide: dict[str, Any], is_variant_one: bool) -> list[str]:
    bullets = slide.get("bullets_data") or slide.get("bullets") or slide.get("content", [])
    bullets = [item for item in bullets if item and (isinstance(item, str) or item.get("text", ""))]
    count = min(max(len(bullets), 1), 5)
    list_class = "editorial-list" if is_variant_one else "numbered-list"
    item_class = "editorial-item" if is_variant_one else "numbered-item"
    index_class = "editorial-index" if is_variant_one else "numbered-index"
    text_class = "editorial-text" if is_variant_one else "numbered-text"
    parts = [
        f'<div class="bullet-fit items-{count}"><ol class="{list_class}" style="--items:{count}">'
    ]
    for index, item in enumerate(bullets):
        text = item if isinstance(item, str) else item.get("text", "")
        if text:
            parts.append(
                f'<li class="{item_class}"><div class="{index_class}">{index + 1:02d}</div>'
                f'<p class="{text_class}">{escape(text)}</p></li>'
            )
    parts.append("</ol></div>")
    return parts

def generate_html_slides_for_module(
    course_id: str, module_index: int, module: Dict[str, Any]
) -> str:
    """
    Renders planned slides for a single module into a static HTML slideshow using local templates.
    Saves it to generated-slide storage for the course and module.
    Returns the absolute path of the generated HTML file.
    """
    slides = module.get("slides", [])
    module_title = module.get("title", "Untitled Module")
    module_num = module_index + 1

    if not slides:
        logger.info(
            f"  [SLIDES GEN][WARNING] No slides planned for module {module_num} — skipping HTML compilation."
        )
        return None

    # Setup directories
    slides_dir = os.path.join(SLIDE_DIR, course_id)
    os.makedirs(slides_dir, exist_ok=True)
    output_path = os.path.join(slides_dir, f"module_{module_num}.html")

    # Map image metadata for easy lookup
    module_images = module.get("images", [])
    images_by_id = {img.get("image_id"): img for img in module_images}

    html_content = []

    # HTML Header
    html_content.append(f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{escape(module_title)} - Slideshow</title>
    <!-- Use local static CSS which will contain our new variations -->
    <link rel="stylesheet" href="../../slides.css">
    <link rel="stylesheet" href="../../layouts/cover.css">
    <link rel="stylesheet" href="../../layouts/concept.css">
    <link rel="stylesheet" href="../../layouts/comparison.css">
    <link rel="stylesheet" href="../../layouts/bullets.css">
    <link rel="stylesheet" href="../../layouts/steps.css">
    <link rel="stylesheet" href="../../layouts/grid.css">
    
    <!-- Fonts -->
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Barlow:wght@400;500;600;700&display=swap" rel="stylesheet">
</head>
<body>
    <div class="presentation-container">
""")

    # Render each slide
    for slide_idx, slide in enumerate(slides):
        slide_title = slide.get("slide_title") or slide.get("title", "Untitled")
        title_length = len(slide_title)
        title_size_class = (
            "brand-slide-title--long" if title_length > 48 else "brand-slide-title--standard"
        )
        layout_type = slide.get("layout_type", "bullets")
        layout_type_str = str(layout_type).lower().split(".")[-1]
        slide_imgs = slide.get("image_ids", [])

        # Production decks alternate variants. Template previews may explicitly
        # request one variant without adding filler slides.
        requested_variant = str(slide.get("template_variant", "")).lower()
        is_v1 = (
            requested_variant != "v2" if requested_variant in {"v1", "v2"} else (slide_idx % 2 == 0)
        )
        variant_class = "variant-v1" if is_v1 else "variant-v2"

        # Determine visual wrapper class based on image count
        img_count = len(slide_imgs)
        has_images = img_count > 0
        body_class = f"slide-body n-{img_count}" if has_images else "slide-body no-image"

        is_cover = layout_type_str == "cover" or slide.get("is_cover_slide")
        concept_template_class = (
            " statement"
            if layout_type_str == "concept" and is_v1
            else (" evidence" if layout_type_str == "concept" else "")
        )
        if layout_type_str == "concept" and slide.get("concept_data"):
            concept_template_class += _concept_density_class(slide, has_images)
        # The source-deck header holds the slide title; layouts must not repeat it.
        header_html = ""

        html_content.append(f"""
        <!-- SLIDE {slide_idx + 1} -->
        <div class="slide slide--{layout_type_str}{" slide--cover" if is_cover else ""} {variant_class}{concept_template_class}{" slide--with-images has-images" if has_images else " slide--text-only no-images"}" id="slide-{slide_idx}">
            <header class="brand-header">
                <div class="brand-slide-title {title_size_class}">{escape(slide_title)}</div>
                <div class="brand-lockup" aria-label="PhillipCapital Wealth. Across Chapters.">
                    <div class="brand-name">PhillipCapital</div>
                    <div class="brand-tagline">Wealth. Across Chapters.</div>
                </div>
            </header>
{header_html}
            <div class="{body_class} body">
                <div class="content-area">
""")

        html_content.extend(
            render_layout(
                slide,
                layout=layout_type_str,
                is_cover=bool(is_cover),
                is_variant_one=is_v1,
                module_number=module_num,
                slide_index=slide_idx,
            )
        )
        html_content.append("</div>")  # end content-area
        html_content.extend(render_images(slide_imgs, images_by_id))

        html_content.append(f"""
            </div>
            <footer class="brand-footer">
                <div class="footer-rule"></div>
                <span class="footer-page">{slide_idx + 1}</span>
            </footer>
        </div>
""")

    # HTML Footer & JS Script
    html_content.append("""
    </div>

    <script>
        let currentSlide = 0;
        const slides = document.querySelectorAll('.slide');

        function updateSlides() {
            slides.forEach((slide, idx) => {
                if (idx === currentSlide) {
                    slide.classList.add('active');
                } else {
                    slide.classList.remove('active');
                }
            });
            requestAnimationFrame(() => {
                fitSharedBodyText(slides[currentSlide]);
                if (document.fonts && document.fonts.ready) {
                    document.fonts.ready.then(() => fitSharedBodyText(slides[currentSlide]));
                }
            });
        }

        function fitSharedBodyText(slide) {
            if (!slide || slide.classList.contains('slide--cover')) return;
            let textSelector = '';
            let containerSelector = '';
            let minSize = 11;
            let maxSize = 24;

            if (slide.classList.contains('slide--grid')) {
                textSelector = '.grid-points li';
                containerSelector = '.insight-card, .lane-copy';
                minSize = slide.classList.contains('has-images') ? 10 : 11;
                maxSize = slide.classList.contains('has-images') ? 22 : 26;
            } else if (slide.classList.contains('slide--steps')) {
                textSelector = '.step-desc, .band-desc';
                containerSelector = '.step-card, .step-band';
                minSize = slide.classList.contains('has-images') ? 10 : 11;
                maxSize = slide.classList.contains('has-images') ? 18 : 22;
            } else if (slide.classList.contains('slide--comparison')) {
                textSelector = '.compare-cell, .lane-point';
                containerSelector = '.comparison-fit';
                minSize = slide.classList.contains('has-images') ? 10 : 11;
                maxSize = slide.classList.contains('has-images') ? 18 : 22;
            } else if (slide.classList.contains('slide--bullets')) {
                textSelector = '.editorial-text, .numbered-text';
                containerSelector = '.bullet-fit';
                minSize = slide.classList.contains('has-images') ? 12 : 14;
                maxSize = slide.classList.contains('has-images') ? 28 : 34;
            } else {
                return;
            }

            const textNodes = [...slide.querySelectorAll(textSelector)];
            const containers = [...slide.querySelectorAll(containerSelector)];
            if (!textNodes.length || !containers.length) return;

            const setSize = size => textNodes.forEach(node => { node.style.fontSize = `${size}px`; });
            const fits = size => {
                setSize(size);
                return containers.every(node => node.scrollHeight <= node.clientHeight + 1 && node.scrollWidth <= node.clientWidth + 1);
            };

            let low = minSize;
            let high = maxSize;
            let best = minSize;
            while (high - low > 0.2) {
                const middle = (low + high) / 2;
                if (fits(middle)) { best = middle; low = middle; }
                else { high = middle; }
            }
            setSize(Math.floor(best * 4) / 4);
            slide.dataset.sharedBodySize = String(Math.floor(best * 4) / 4);
        }

        function nextSlide() {
            if (currentSlide < slides.length - 1) {
                currentSlide++;
                updateSlides();
                // Send postMessage to notify Flutter parent container
                if (window.parent) {
                    window.parent.postMessage({ type: 'slide_changed', index: currentSlide }, '*');
                }
            }
        }

        function prevSlide() {
            if (currentSlide > 0) {
                currentSlide--;
                updateSlides();
                if (window.parent) {
                    window.parent.postMessage({ type: 'slide_changed', index: currentSlide }, '*');
                }
            }
        }

        function goToSlide(index) {
            if (index >= 0 && index < slides.length) {
                currentSlide = index;
                updateSlides();
            }
        }

        // Expose functions globally for dynamic webview injection
        window.nextSlide = nextSlide;
        window.prevSlide = prevSlide;
        window.goToSlide = goToSlide;

        // Key bindings
        document.addEventListener('keydown', (e) => {
            if (e.key === 'ArrowRight' || e.key === 'Space') {
                nextSlide();
            } else if (e.key === 'ArrowLeft') {
                prevSlide();
            }
        });

        // Message listener for remote slide navigation
        window.addEventListener('message', (event) => {
            if (event.data && event.data.type === 'go_to_slide') {
                goToSlide(event.data.index);
            }
        });

        // Initialize slideshow
        updateSlides();
    </script>
</body>
</html>
""")

    # Write HTML output
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(html_content))

    logger.info("slide_html_compiled path=%s", output_path)
    return output_path

def compile_slides_for_course(course_id: str) -> List[str]:
    """
    Reads persisted courses, generates slides, and compiles static HTML slide decks.
    """
    logger.info("course_html_compilation_started course_id=%s", course_id)

    courses = get_all_courses("draft")

    course_idx = next(
        (i for i, course in enumerate(courses) if course.get("course_id") == course_id),
        None,
    )
    if course_idx is None:
        raise ValueError(f"Course '{course_id}' not found.")

    course = courses[course_idx]
    modules = course.get("modules", [])

    html_files = []
    for i, module in enumerate(modules):
        file_path = generate_html_slides_for_module(course_id, i, module)
        if file_path:
            html_files.append(file_path)

    return html_files
