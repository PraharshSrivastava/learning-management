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
        body_class = "slide-body" if has_images else "slide-body no-image"

        html_content.append(f"""
        <!-- SLIDE {slide_idx + 1} -->
        <div class="slide" id="slide-{slide_idx}">
""")
        
        # Requirement 1 & 3: Do not write parent lesson title (eyebrow) in any layout,
        # and do not render the header/title block for concept layout.
        if layout_type_str != "concept":
            html_content.append(f"""            <div class="slide-header">
                <h1 class="slide-title">{_esc(slide_title)}</h1>
            </div>""")

        html_content.append(f"""            
            <div class="{body_class}">
                <div class="content-area">
""")

        # ----------------------------------------------------
        # Render Content Layouts
        # ----------------------------------------------------
        if layout_type_str == "concept" and slide.get("concept_data"):
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
                        <img src="{rel_img_path}" alt="{_esc(caption)}">
                        <div class="image-caption">{_esc(caption)}</div>
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
                            <img src="{rel_img_path}" alt="{_esc(caption)}">
                            <div class="image-caption">{_esc(caption)}</div>
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
