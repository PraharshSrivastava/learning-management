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

ICON_ALIASES = {
    "approval": "check",
    "approved": "check",
    "benefit": "check",
    "compliance": "shield",
    "customer": "user",
    "deadline": "time",
    "document": "file",
    "documents": "file",
    "email": "message",
    "escalate": "alert",
    "finance": "payment",
    "goal": "target",
    "idea": "lightbulb",
    "kpi": "chart",
    "learning": "book",
    "money": "payment",
    "payment": "payment",
    "process": "route",
    "report": "chart",
    "review": "search",
    "risk": "alert",
    "security": "shield",
    "time": "time",
}

ICON_PATHS = {
    "alert": '<path d="M12 3 2 20h20L12 3Z"/><path d="M12 9v4"/><path d="M12 17h.01"/>',
    "book": '<path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/><path d="M4 4.5A2.5 2.5 0 0 1 6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5Z"/>',
    "chart": '<path d="M4 19V5"/><path d="M4 19h16"/><path d="M8 16v-5"/><path d="M12 16V8"/><path d="M16 16v-3"/>',
    "check": '<path d="M20 6 9 17l-5-5"/>',
    "data": '<ellipse cx="12" cy="5" rx="7" ry="3"/><path d="M5 5v6c0 1.7 3.1 3 7 3s7-1.3 7-3V5"/><path d="M5 11v6c0 1.7 3.1 3 7 3s7-1.3 7-3v-6"/>',
    "file": '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8Z"/><path d="M14 2v6h6"/><path d="M8 13h8"/><path d="M8 17h5"/>',
    "lightbulb": '<path d="M9 18h6"/><path d="M10 22h4"/><path d="M8.5 14.5A6 6 0 1 1 15.5 14.5c-.8.6-1.5 1.4-1.5 2.5h-4c0-1.1-.7-1.9-1.5-2.5Z"/>',
    "message": '<path d="M21 15a4 4 0 0 1-4 4H8l-5 3V7a4 4 0 0 1 4-4h10a4 4 0 0 1 4 4Z"/>',
    "payment": '<rect x="3" y="5" width="18" height="14" rx="2"/><path d="M3 10h18"/><path d="M7 15h4"/>',
    "route": '<circle cx="6" cy="6" r="3"/><circle cx="18" cy="18" r="3"/><path d="M9 6h4a5 5 0 0 1 0 10h-1"/>',
    "search": '<circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/>',
    "shield": '<path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10Z"/><path d="m9 12 2 2 4-4"/>',
    "target": '<circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="5"/><circle cx="12" cy="12" r="1"/>',
    "time": '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
    "user": '<circle cx="12" cy="8" r="4"/><path d="M4 21a8 8 0 0 1 16 0"/>',
}

def _icon_name(keyword) -> str:
    key = str(keyword or "").strip().lower().replace("_", "-")
    return ICON_ALIASES.get(key, key if key in ICON_PATHS else "target")

def _icon_svg(keyword, class_name="slide-icon") -> str:
    icon = _icon_name(keyword)
    return (
        f'<svg class="{class_name}" viewBox="0 0 24 24" aria-hidden="true" '
        f'fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
        f'{ICON_PATHS[icon]}</svg>'
    )

def generate_html_slides_for_module(
    course_id: str,
    module_index: int,
    module: Dict[str, Any]
) -> str:
    """
    Renders planned slides for a single module into a static HTML slideshow.
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
    <link rel="stylesheet" href="../../slides.css">
</head>
<body>
    <div class="presentation-container">
""")

    # Render each slide
    for slide_idx, slide in enumerate(slides):
        slide_title = slide.get("slide_title", "Summary")
        eyebrow = slide.get("parent_lesson_topic", f"Module {module_num}")
        layout_type = slide.get("layout_type", "bullets")
        layout_type_str = str(layout_type).lower().split(".")[-1]
        slide_imgs = slide.get("image_ids", [])

        # Determine visual wrapper class
        has_images = len(slide_imgs) > 0
        body_class = f"slide-body layout-{layout_type_str}"
        if not has_images:
            body_class += " no-image"

        html_content.append(f"""
        <!-- SLIDE {slide_idx + 1} -->
        <div class="slide slide-{layout_type_str}" id="slide-{slide_idx}">
""")
        
        # Render the header/title block for all layouts.
        html_content.append(f"""            <div class="slide-header">
                <div class="eyebrow">{_esc(eyebrow)}</div>
                <h1 class="slide-title">{_esc(slide_title)}</h1>
            </div>""")

        html_content.append(f"""            
            <div class="{body_class}">
                <div class="content-area">
""")

        # ----------------------------------------------------
        # Render Content Layouts
        # ----------------------------------------------------
        if layout_type_str == "spotlight" and slide.get("spotlight_data"):
            data = slide["spotlight_data"]
            supporting_points = [
                point.strip()
                for point in data.get("supporting_points", [])
                if point and point.strip()
            ]
            callout = data.get("callout")

            html_content.append(f"""
                    <div class="spotlight-container">
                        <p class="spotlight-kicker">Key message</p>
                        <h2 class="spotlight-message">{_esc(data.get("key_message", ""))}</h2>
""")
            if supporting_points:
                html_content.append('                        <div class="spotlight-points">')
                for point in supporting_points[:3]:
                    html_content.append(f'                            <div class="spotlight-point">{_esc(point)}</div>')
                html_content.append('                        </div>')
            if callout and callout.strip():
                html_content.append(f'                        <div class="spotlight-callout">{_esc(callout)}</div>')
            html_content.append("""                    </div>
""")
        elif layout_type_str == "flow" and slide.get("flow_data"):
            data = slide["flow_data"]
            flow_type = str(data.get("flow_type", "horizontal")).lower()
            html_content.append(f'                    <div class="flow-container flow-{_esc(flow_type)}">')
            for node in data.get("nodes", []):
                html_content.append(f"""
                        <div class="flow-node">
                            <div class="flow-icon">{_icon_svg(node.get("icon_keyword") or "route")}</div>
                            <h3>{_esc(node.get("title", ""))}</h3>
                            <p>{_esc(node.get("description", ""))}</p>
                        </div>
""")
            html_content.append('                    </div>')
        elif layout_type_str == "decision_tree" and slide.get("decision_tree_data"):
            data = slide["decision_tree_data"]
            html_content.append(f"""
                    <div class="decision-container">
                        <div class="decision-question">
                            {_icon_svg("target", "decision-icon")}
                            <h2>{_esc(data.get("question", ""))}</h2>
                        </div>
                        <div class="decision-branches">
""")
            for branch in data.get("branches", []):
                html_content.append(f"""
                            <div class="decision-branch">
                                <div class="branch-label">{_esc(branch.get("label", ""))}</div>
                                <div class="branch-icon">{_icon_svg(branch.get("icon_keyword") or branch.get("label") or "check")}</div>
                                <p>{_esc(branch.get("outcome", ""))}</p>
                            </div>
""")
            html_content.append("""                        </div>
                    </div>
""")
        elif layout_type_str == "metric" and slide.get("metric_data"):
            data = slide["metric_data"]
            html_content.append(f"""
                    <div class="metric-container">
                        <div class="metric-icon">{_icon_svg(data.get("icon_keyword") or "chart")}</div>
                        <div class="metric-value">{_esc(data.get("metric_value", ""))}</div>
                        <h2 class="metric-label">{_esc(data.get("metric_label", ""))}</h2>
                        <p class="metric-context">{_esc(data.get("context", ""))}</p>
                    </div>
""")
        elif layout_type_str == "icon_grid" and slide.get("icon_grid_data"):
            data = slide["icon_grid_data"]
            html_content.append('                    <div class="icon-grid-container">')
            for item in data.get("items", []):
                html_content.append(f"""
                        <div class="icon-card">
                            <div class="icon-card-symbol">{_icon_svg(item.get("icon_keyword"))}</div>
                            <h3>{_esc(item.get("title", ""))}</h3>
                            <p>{_esc(item.get("content", ""))}</p>
                        </div>
""")
            html_content.append('                    </div>')
        elif layout_type_str == "concept" and slide.get("concept_data"):
            data = slide["concept_data"]
            takeaways = data.get("key_takeaways", [])
            if not takeaways and data.get("key_takeaway"):
                takeaways = [data["key_takeaway"]]
            
            # Filter empty values
            takeaways = [t.strip() for t in takeaways if t and t.strip()]
            
            takeaways_html = ""
            if takeaways:
                if len(takeaways) == 1:
                    takeaways_html = f"""                        <div class="takeaway-banner">
                            <strong>Key Takeaway:</strong> {_esc(takeaways[0])}
                        </div>"""
                else:
                    bullets_li = "\n".join([f"                            <li style='margin-bottom: 0.25rem;'>{_esc(t)}</li>" for t in takeaways])
                    takeaways_html = f"""                        <div class="takeaway-banner">
                            <strong>Key Takeaways:</strong>
                            <ul class="takeaway-list" style="margin-top: 0.5rem; padding-left: 1.25rem; list-style-type: square; line-height: 1.4;">
{bullets_li}
                            </ul>
                        </div>"""

            html_content.append(f"""
                    <div class="concept-container">
                        <div class="concept-definition">
                            <h2 class="concept-term">{_esc(data.get("core_term", ""))}</h2>
                            <p class="concept-desc">{_esc(data.get("definition", ""))}</p>
                        </div>
{takeaways_html}
                    </div>
""")
        elif layout_type_str == "steps" and slide.get("steps_data"):
            data = slide["steps_data"]
            html_content.append('                    <div class="steps-container">')
            html_content.append('                        <div class="timeline-row">')
            for step in data.get("steps", []):
                html_content.append(f"""
                            <div class="timeline-step">
                                <h3 class="step-title">{_esc(step.get("title", ""))}</h3>
                                <p class="step-desc">{_esc(step.get("description", ""))}</p>
                            </div>
""")
            html_content.append('                        </div>')
            html_content.append('                    </div>')
        elif layout_type_str == "comparison" and slide.get("comparison_data"):
            data = slide["comparison_data"]
            html_content.append(f"""
                    <div class="comparison-container">
                        <div class="comparison-column left-col">
                            <h2 class="column-header">{_esc(data.get("left_column_title", ""))}</h2>
                            <ul class="column-list">
""")
            for point in data.get("left_column_points", []):
                html_content.append(f'                                <li>{_esc(point)}</li>')
            html_content.append(f"""
                            </ul>
                        </div>
                        <div class="comparison-column right-col">
                            <h2 class="column-header">{_esc(data.get("right_column_title", ""))}</h2>
                            <ul class="column-list">
""")
            for point in data.get("right_column_points", []):
                html_content.append(f'                                <li>{_esc(point)}</li>')
            html_content.append(f"""
                            </ul>
                        </div>
                    </div>
""")
        elif layout_type_str == "grid" and slide.get("grid_data"):
            data = slide["grid_data"]
            html_content.append('                    <div class="grid-container">')
            for col in data.get("columns", []):
                html_content.append(f"""
                        <div class="grid-card">
                            <h3 class="card-header">{_esc(col.get("header", ""))}</h3>
                            <p class="card-content">{_esc(col.get("content", ""))}</p>
                        </div>
""")
            html_content.append('                    </div>')
        else:
            # Fallback to standard bullet list
            bullets = slide.get("bullets_data")
            if not bullets:
                # If no direct bullets data, extract from facts list fallback
                bullets = slide.get("bullets", [])
            
            html_content.append('                    <div class="bullets-container">')
            html_content.append('                        <ul class="bullet-list">')
            for b in bullets:
                b_text = b if isinstance(b, str) else b.get("text", "")
                if b_text:
                    html_content.append(f'                            <li>{_esc(b_text)}</li>')
            html_content.append('                        </ul>')
            html_content.append('                    </div>')

        html_content.append("""
                </div>
""")

        # ----------------------------------------------------
        # Render Visual Asset Area (0 to N images)
        # ----------------------------------------------------
        if has_images:
            html_content.append('                <div class="visual-area">')
            if len(slide_imgs) == 1:
                img_id = slide_imgs[0]
                img_meta = images_by_id.get(img_id)
                if img_meta:
                    raw_path = img_meta.get("file_path", "")
                    # Convert static prefix to relative slideshow path
                    rel_img_path = raw_path.replace("assets/", "../../")
                    caption = img_meta.get("caption", "")
                    html_content.append(f"""
                    <div class="p-shape-frame">
                        <img src="{_esc(rel_img_path)}" alt="{_esc(caption or slide_title)}">
                    </div>
""")
            else:
                # Render a grid of images
                html_content.append('                    <div class="visual-grid">')
                for img_id in slide_imgs:
                    img_meta = images_by_id.get(img_id)
                    if img_meta:
                        raw_path = img_meta.get("file_path", "")
                        rel_img_path = raw_path.replace("assets/", "../../")
                        caption = img_meta.get("caption", "")
                        html_content.append(f"""
                        <div class="p-shape-frame">
                            <img src="{_esc(rel_img_path)}" alt="{_esc(caption or slide_title)}">
                        </div>
""")
                html_content.append('                    </div>')
            html_content.append('                </div>')

        html_content.append("""
            </div>
        </div>
""")

    # HTML Footer & JS Script
    html_content.append("""
        <!-- Slide Controls Overlay -->
        <div class="controls-overlay">
            <button class="control-btn prev-btn" onclick="prevSlide()">&larr;</button>
            <span class="slide-number"></span>
            <button class="control-btn next-btn" onclick="nextSlide()">&rarr;</button>
        </div>
    </div>

    <script>
        let currentSlide = 0;
        const slides = document.querySelectorAll('.slide');
        const prevBtn = document.querySelector('.prev-btn');
        const nextBtn = document.querySelector('.next-btn');
        const slideNumDisplay = document.querySelector('.slide-number');

        function updateSlides() {
            slides.forEach((slide, idx) => {
                if (idx === currentSlide) {
                    slide.classList.add('active');
                } else {
                    slide.classList.remove('active');
                }
            });
            prevBtn.disabled = currentSlide === 0;
            nextBtn.disabled = currentSlide === slides.length - 1;
            slideNumDisplay.textContent = `${currentSlide + 1} / ${slides.length}`;
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
