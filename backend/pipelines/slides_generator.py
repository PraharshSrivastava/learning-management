from core.database import get_all_courses, save_all_courses
import os
import json
import html
from typing import Dict, Any, List

from pipelines.config import BASE_DIR, DRAFT_COURSES_FILE


def _esc(value) -> str:
    """
    HTML-escapes any interpolated content before embedding it in generated
    slide HTML. Necessary because slide text originates from LLM-extracted
    PDF content, which may contain characters like <, >, &, or quotes that
    would otherwise break the HTML structure or allow injected markup.
    """
    if value is None:
        return ""
    return html.escape(str(value), quote=True)


def _brand_icon_path(slide_index: int, slot: int = 0) -> str:
    """Returns one of the line icons extracted from the approved PPT deck."""
    icon_number = 10 + ((slide_index + slot) % 14)
    return f"../../brand/icon-{icon_number}.svg"


def _grid_icon_html(slide_index: int, slot: int = 0) -> str:
    """Wraps a source-deck icon in the exact gradient icon frame treatment."""
    return (
        '<span class="grid-icon-frame">'
        f'<img class="grid-icon" src="{_brand_icon_path(slide_index, slot)}" alt="">'
        '</span>'
    )


def _step_icon_html(slide_index: int, slot: int = 0) -> str:
    """Uses the same approved icon tile on the restored card-grid step layout."""
    return (
        '<span class="step-icon-frame">'
        f'<img class="step-icon" src="{_brand_icon_path(slide_index, slot)}" alt="">'
        '</span>'
    )


def _feature_icon_html(frame_class: str, icon_class: str, slide_index: int, slot: int = 0) -> str:
    """Creates a non-overlapping, source-style icon tile for content cards."""
    return (
        f'<span class="{frame_class}">'
        f'<img class="{icon_class}" src="{_brand_icon_path(slide_index, slot)}" alt="">'
        '</span>'
    )

def generate_html_slides_for_module(
    course_id: str,
    module_index: int,
    module: Dict[str, Any]
) -> str:
    """
    Renders planned slides for a single module into a static HTML slideshow using local templates.
    Saves it to backend/assets/slides/{course_id}/module_{module_index + 1}.html.
    Returns the absolute path of the generated HTML file.
    """
    slides = module.get("slides", [])
    module_title = module.get("title", "Untitled Module")
    module_num = module_index + 1

    if not slides:
        print(f"  [SLIDES GEN][WARNING] No slides planned for module {module_num} — skipping HTML compilation.")
        return None

    # Setup directories
    slides_dir = os.path.join(BASE_DIR, "assets", "slides", course_id)
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
    <title>{_esc(module_title)} - Slideshow</title>
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
        title_size_class = "brand-slide-title--long" if title_length > 48 else "brand-slide-title--standard"
        eyebrow = slide.get("parent_lesson_topic", f"Module {module_num}")
        layout_type = slide.get("layout_type", "bullets")
        layout_type_str = str(layout_type).lower().split(".")[-1]
        slide_imgs = slide.get("image_ids", [])
        
        # Production decks alternate variants. Template previews may explicitly
        # request one variant without adding filler slides.
        requested_variant = str(slide.get("template_variant", "")).lower()
        is_v1 = requested_variant != "v2" if requested_variant in {"v1", "v2"} else (slide_idx % 2 == 0)
        variant_class = "variant-v1" if is_v1 else "variant-v2"

        # Determine visual wrapper class based on image count
        img_count = len(slide_imgs)
        has_images = img_count > 0
        body_class = f"slide-body n-{img_count}" if has_images else "slide-body no-image"

        is_cover = layout_type_str == "cover" or slide.get("is_cover_slide")
        concept_template_class = " statement" if layout_type_str == "concept" and is_v1 else (" evidence" if layout_type_str == "concept" else "")
        # The source-deck header holds the slide title; layouts must not repeat it.
        header_html = ""

        html_content.append(f"""
        <!-- SLIDE {slide_idx + 1} -->
        <div class="slide slide--{layout_type_str}{' slide--cover' if is_cover else ''} {variant_class}{concept_template_class}{' slide--with-images has-images' if has_images else ' slide--text-only no-images'}" id="slide-{slide_idx}">
            <header class="brand-header">
                <div class="brand-slide-title {title_size_class}">{_esc(slide_title)}</div>
                <div class="brand-lockup" aria-label="PhillipCapital Wealth. Across Chapters.">
                    <div class="brand-name">PhillipCapital</div>
                    <div class="brand-tagline">Wealth. Across Chapters.</div>
                </div>
            </header>
{header_html}
            <div class="{body_class} body">
                <div class="content-area">
""")

        # ----------------------------------------------------
        # Render Content Layouts
        # ----------------------------------------------------
        if is_cover:
            course_name = slide.get("course_name", "")
            total_modules = slide.get("total_modules", "")
            cover_module_num = slide.get("module_number", module_num)
            html_content.append(f"""
                    <div class="module-cover">
                        <div class="module-cover-course">{_esc(course_name)}</div>
                        <div class="module-cover-kicker">Module {_esc(cover_module_num)}{f" of {_esc(total_modules)}" if total_modules else ""}</div>
                        <h1>{_esc(slide_title)}</h1>
                        <div class="module-cover-rule"></div>
                    </div>
""")

        elif layout_type_str == "concept" and slide.get("concept_data"):
            data = slide["concept_data"]
            takeaways = data.get("key_takeaways", [])
            if not takeaways and data.get("key_takeaway"):
                takeaways = [data["key_takeaway"]]
            takeaways = [t.strip() for t in takeaways if t and t.strip()]
            
            points_html = '<div class="point-list">' + ''.join(f'<div class="point">{_esc(t)}</div>' for t in takeaways) + '</div>' if takeaways else ''
            html_content.append(f'<section class="silver-panel {"no-points" if not takeaways else ""}" style="--point-cols:{max(len(takeaways), 1)}"><div class="panel-copy"><div class="panel-title">{_esc(data.get("core_term", ""))}</div><div class="panel-definition">{_esc(data.get("definition", ""))}</div></div><div class="icon-tile"><img src="{_brand_icon_path(slide_idx)}" alt=""></div>{points_html}</section>')

        elif layout_type_str == "steps" and slide.get("steps_data"):
            data = slide["steps_data"]
            steps = data.get("steps", [])
            step_count = min(max(len(steps), 1), 5)
            if is_v1:
                html_content.append(f'<div class="steps-fit step-cards steps-{step_count}">')
                for i, step in enumerate(steps[:5]):
                    html_content.append(f'<section class="step-card"><div class="step-num">{i+1:02d}</div><h3 class="step-title">{_esc(step.get("title", ""))}</h3><p class="step-desc">{_esc(step.get("description", ""))}</p></section>')
            else:
                html_content.append(f'<div class="steps-fit step-bands steps-{step_count}" style="--steps:{step_count}">')
                for i, step in enumerate(steps[:5]):
                    html_content.append(f'<section class="step-band"><div class="band-num">{i+1:02d}</div><div class="band-copy"><h3 class="band-title">{_esc(step.get("title", ""))}</h3><p class="band-desc">{_esc(step.get("description", ""))}</p></div></section>')
            html_content.append('</div>')

        elif layout_type_str == "comparison" and slide.get("comparison_data"):
            data = slide["comparison_data"]
            
            left_pts, right_pts = data.get("left_column_points", []), data.get("right_column_points", [])
            rows = min(max(len(left_pts), len(right_pts), 2), 4)
            left_title, right_title = _esc(data.get("left_column_title", "")), _esc(data.get("right_column_title", ""))
            if is_v1:
                html_content.append(f'<div class="comparison-fit rows-{rows} compare-matrix" style="--rows:{rows}"><div class="compare-matrix-head"><div></div><div class="side-title">{left_title}</div><div class="side-title">{right_title}</div></div>')
                for i in range(rows): html_content.append(f'<div class="compare-matrix-row"><div class="row-number">{i+1:02d}</div><div class="compare-cell">{_esc(left_pts[i]) if i < len(left_pts) else "-"}</div><div class="compare-cell">{_esc(right_pts[i]) if i < len(right_pts) else "-"}</div></div>')
                html_content.append('</div>')
            else:
                html_content.append(f'<div class="comparison-fit rows-{rows} compare-lanes" style="--rows:{rows}"><section class="lane-panel left"><div class="lane-title">{left_title}</div>')
                for i in range(rows): html_content.append(f'<div class="lane-point">{_esc(left_pts[i]) if i < len(left_pts) else "-"}</div>')
                html_content.append('</section><div class="compare-spine"><div class="spine-vs">VS</div>' + ''.join(f'<div class="spine-dot"><span>{i+1}</span></div>' for i in range(rows)) + f'</div><section class="lane-panel right"><div class="lane-title">{right_title}</div>')
                for i in range(rows): html_content.append(f'<div class="lane-point">{_esc(right_pts[i]) if i < len(right_pts) else "-"}</div>')
                html_content.append('</section></div>')

        elif layout_type_str == "grid" and slide.get("grid_data"):
            data = slide["grid_data"]
            cols = data.get("columns", [])
            column_count = min(max(len(cols), 2), 6)
            density_class = f"count-{column_count}"

            def grid_points_html(column: dict) -> str:
                points = column.get("points") or []
                if not points and column.get("content"):
                    points = [column["content"]]
                return '<ul class="grid-points">' + ''.join(f'<li>{_esc(point)}</li>' for point in points if point) + '</ul>'
            
            grid_variant = "insight-grid" if is_v1 else "lane-grid"
            html_content.append(f'<div class="grid-fit"><div class="gallery-grid {grid_variant} {density_class}">')
            for i, col in enumerate(cols[:6]):
                if is_v1:
                    html_content.append(f'<section class="insight-card"><div class="insight-num">{i+1:02d}</div><img class="insight-icon" src="{_brand_icon_path(slide_idx, i)}" alt=""><h3>{_esc(col.get("header", ""))}</h3>{grid_points_html(col)}</section>')
                else:
                    html_content.append(f'<section class="lane-card"><div class="lane-num">{i+1:02d}</div><div class="lane-copy"><h3>{_esc(col.get("header", ""))}</h3>{grid_points_html(col)}</div></section>')
            html_content.append('</div></div>')
                
        else:
            # Fallback to standard bullets
            bullets = slide.get("bullets_data")
            if not bullets:
                bullets = slide.get("bullets")
            if not bullets:
                bullets = slide.get("content", [])
            bullets = [b for b in bullets if b and (isinstance(b, str) or b.get("text", ""))]
            bullet_count = min(max(len(bullets), 1), 5)
                
            if is_v1:
                html_content.append(f'<div class="bullet-fit items-{bullet_count}"><ol class="editorial-list" style="--items:{bullet_count}">')
                for i, b in enumerate(bullets):
                    b_text = b if isinstance(b, str) else b.get("text", "")
                    if b_text:
                        html_content.append(f'<li class="editorial-item"><div class="editorial-index">{i+1:02d}</div><p class="editorial-text">{_esc(b_text)}</p></li>')
                html_content.append('</ol></div>')
            else:
                html_content.append(f'<div class="bullet-fit items-{bullet_count}"><ol class="numbered-list" style="--items:{bullet_count}">')
                for i, b in enumerate(bullets):
                    b_text = b if isinstance(b, str) else b.get("text", "")
                    if b_text:
                        html_content.append(f"""
                            <li class="numbered-item">
                                <div class="numbered-index">{i+1:02d}</div>
                                <p class="numbered-text">{_esc(b_text)}</p>
                            </li>
""")
                html_content.append('</ol></div>')

        html_content.append('</div>') # end content-area

        # ----------------------------------------------------
        # Render Visual Asset Area
        # ----------------------------------------------------
        if has_images:
            html_content.append(f'<aside class="image-grid count-{min(img_count, 3)}" aria-label="Course source images">')
            for img_id in slide_imgs[:3]: # Cap at 3 for layout safety
                img_meta = images_by_id.get(img_id)
                if img_meta:
                    raw_path = img_meta.get("file_path", "")
                    rel_img_path = raw_path.replace("assets/", "../../")
                    html_content.append(f"""
                        <div class="image">
                            <img src="{rel_img_path}">
                        </div>
""")
            html_content.append('</aside>')

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
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write("\n".join(html_content))

    print(f"  [SLIDES GEN] Slide html file compiled successfully: {output_path}")
    return output_path


def compile_slides_for_course(course_id: str) -> List[str]:
    """
    Reads courses.json, generates slides, and compiles them into static html slide decks.
    """
    print(f"Compiling HTML Slide decks for course {course_id}...")

    courses = get_all_courses('draft')

    course_idx = next((i for i, c in enumerate(courses) if c.get("id") == course_id), None)
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
