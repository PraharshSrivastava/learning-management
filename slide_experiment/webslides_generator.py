import os
import sys
import html
from typing import Dict, Any, List

# Ensure backend imports work
BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from pipelines.config import BASE_DIR

def _esc(value) -> str:
    if value is None:
        return ""
    return html.escape(str(value), quote=True)

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
    <link rel="stylesheet" href="/api/slides.css">
    
    <!-- Fonts -->
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Barlow:wght@400;500;600;700&family=Inter:wght@600;700;800&display=swap" rel="stylesheet">
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
        
        # Decide variation: Even indices get V1, Odd indices get V2
        is_v1 = (slide_idx % 2 == 0)

        # Determine visual wrapper class based on image count
        img_count = len(slide_imgs)
        has_images = img_count > 0
        body_class = f"slide-body n-{img_count}" if has_images else "slide-body no-image"

        header_html = f"""
            <div class="slide-header">
                <div class="eyebrow">{_esc(eyebrow)}</div>
                <h1 class="slide-title">{_esc(slide_title)}</h1>
            </div>
""" if layout_type_str != "concept" else ""

        html_content.append(f"""
        <!-- SLIDE {slide_idx + 1} -->
        <div class="slide" id="slide-{slide_idx}">
{header_html}            
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
            takeaways = [t.strip() for t in takeaways if t and t.strip()]
            
            if is_v1:
                takeaways_html = ""
                if takeaways:
                    pills = "".join([f'<div class="takeaway-pill">{_esc(t)}</div>' for t in takeaways])
                    takeaways_html = f'<div class="takeaways">{pills}</div>'
                
                html_content.append(f"""
                    <div class="concept-v1">
                        <div class="term">{_esc(data.get("core_term", ""))}</div>
                        <div class="def">{_esc(data.get("definition", ""))}</div>
                        {takeaways_html}
                    </div>
""")
            else:
                takeaways_html = ""
                if takeaways:
                    pills = "".join([f'<div class="takeaways-text">{_esc(t)}</div>' for t in takeaways])
                    takeaways_html = f'<div class="takeaways">{pills}</div>'
                
                html_content.append(f"""
                    <div class="concept-v2">
                        <div class="term">{_esc(data.get("core_term", ""))}</div>
                        <div class="def">{_esc(data.get("definition", ""))}</div>
                        {takeaways_html}
                    </div>
""")

        elif layout_type_str == "steps" and slide.get("steps_data"):
            data = slide["steps_data"]
            steps = data.get("steps", [])
            
            if is_v1:
                html_content.append('<div class="steps-v1">')
                for i, step in enumerate(steps):
                    html_content.append(f"""
                        <div class="step-v1-card">
                            <div class="step-v1-num">{i+1}</div>
                            <h3>{_esc(step.get("title", ""))}</h3>
                            <p>{_esc(step.get("description", ""))}</p>
                        </div>
""")
                html_content.append('</div>')
            else:
                html_content.append('<div class="steps-v2">')
                colors = ["var(--accent-blue)", "var(--accent-indigo)", "var(--accent-purple)", "var(--accent-teal)"]
                for i, step in enumerate(steps):
                    color = colors[i % len(colors)]
                    html_content.append(f"""
                        <div class="step-v2-row" style="border-left-color: {color};">
                            <div class="step-v2-num">{i+1:02d}</div>
                            <div class="step-v2-content">
                                <h3>{_esc(step.get("title", ""))}</h3>
                                <p>{_esc(step.get("description", ""))}</p>
                            </div>
                        </div>
""")
                html_content.append('</div>')

        elif layout_type_str == "comparison" and slide.get("comparison_data"):
            data = slide["comparison_data"]
            
            if is_v1:
                html_content.append('<div class="comp-v1">')
                # Left
                html_content.append(f"""
                    <div class="comp-v1-card left">
                        <h2 style="font-size: 24px; text-align: center; margin-bottom: 16px;">{_esc(data.get("left_column_title", ""))}</h2>
                        <ul class="comp-list">
""")
                for pt in data.get("left_column_points", []):
                    html_content.append(f'<li>{_esc(pt)}</li>')
                html_content.append('</ul></div>')
                
                # VS
                html_content.append('<div class="vs-circle">VS</div>')
                
                # Right
                html_content.append(f"""
                    <div class="comp-v1-card right">
                        <h2 style="font-size: 24px; text-align: center; margin-bottom: 16px;">{_esc(data.get("right_column_title", ""))}</h2>
                        <ul class="comp-list">
""")
                for pt in data.get("right_column_points", []):
                    html_content.append(f'<li>{_esc(pt)}</li>')
                html_content.append('</ul></div></div>')
            else:
                html_content.append(f"""
                    <div class="comp-v2">
                        <div class="comp-v2-row header">
                            <div class="comp-v2-col">{_esc(data.get("left_column_title", ""))}</div>
                            <div class="comp-v2-col">{_esc(data.get("right_column_title", ""))}</div>
                        </div>
""")
                left_pts = data.get("left_column_points", [])
                right_pts = data.get("right_column_points", [])
                max_pts = max(len(left_pts), len(right_pts))
                
                for i in range(max_pts):
                    l_pt = _esc(left_pts[i]) if i < len(left_pts) else "-"
                    r_pt = _esc(right_pts[i]) if i < len(right_pts) else "-"
                    html_content.append(f"""
                        <div class="comp-v2-row">
                            <div class="comp-v2-col">{l_pt}</div>
                            <div class="comp-v2-col">{r_pt}</div>
                        </div>
""")
                html_content.append('</div>')

        elif layout_type_str == "grid" and slide.get("grid_data"):
            data = slide["grid_data"]
            cols = data.get("columns", [])
            
            if is_v1 or len(cols) != 3:
                # Standard Bento
                html_content.append('<div class="grid-v1">')
                colors = ["var(--accent-blue)", "var(--accent-indigo)", "var(--accent-purple)", "var(--accent-teal)"]
                for i, col in enumerate(cols):
                    color = colors[i % len(colors)]
                    html_content.append(f"""
                        <div class="grid-v1-card" style="border-bottom: 4px solid {color};">
                            <h3>{_esc(col.get("header", ""))}</h3>
                            <p>{_esc(col.get("content", ""))}</p>
                        </div>
""")
                html_content.append('</div>')
            else:
                # Asymmetric Hero (works best with 3 items)
                html_content.append('<div class="grid-v2">')
                for i, col in enumerate(cols):
                    if i == 0:
                        html_content.append(f"""
                            <div class="grid-v2-card grid-v2-hero">
                                <h3>{_esc(col.get("header", ""))}</h3>
                                <p>{_esc(col.get("content", ""))}</p>
                            </div>
""")
                    else:
                        html_content.append(f"""
                            <div class="grid-v2-card">
                                <h3>{_esc(col.get("header", ""))}</h3>
                                <p>{_esc(col.get("content", ""))}</p>
                            </div>
""")
                html_content.append('</div>')
                
        else:
            # Fallback to standard bullets
            bullets = slide.get("bullets_data")
            if not bullets:
                bullets = slide.get("bullets", [])
                
            if is_v1:
                html_content.append('<ul class="bullets-v1">')
                for b in bullets:
                    b_text = b if isinstance(b, str) else b.get("text", "")
                    if b_text:
                        html_content.append(f'<li>{_esc(b_text)}</li>')
                html_content.append('</ul>')
            else:
                html_content.append('<ul class="bullets-v2">')
                for i, b in enumerate(bullets):
                    b_text = b if isinstance(b, str) else b.get("text", "")
                    if b_text:
                        html_content.append(f"""
                            <li>
                                <div class="bullets-v2-num">{i+1:02d}</div>
                                <div class="bullets-v2-text">{_esc(b_text)}</div>
                            </li>
""")
                html_content.append('</ul>')

        html_content.append('</div>') # end content-area

        # ----------------------------------------------------
        # Render Visual Asset Area
        # ----------------------------------------------------
        if has_images:
            html_content.append(f'<div class="visual-area n-{min(img_count, 3)}">')
            for img_id in slide_imgs[:3]: # Cap at 3 for layout safety
                img_meta = images_by_id.get(img_id)
                if img_meta:
                    raw_path = img_meta.get("file_path", "")
                    rel_img_path = raw_path.replace("assets/", "/api/")
                    # The app.py serves images at /api/images/course_id/filename
                    # but wait, static/slides.css assumes standard paths. Let's just use /api/images/course_id/filename.
                    img_filename = os.path.basename(raw_path)
                    html_content.append(f"""
                        <div class="img-frame">
                            <img src="/api/images/{course_id}/{img_filename}">
                        </div>
""")
            html_content.append('</div>')

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
            }
        }

        function prevSlide() {
            if (currentSlide > 0) {
                currentSlide--;
                updateSlides();
            }
        }

        document.addEventListener('keydown', (e) => {
            if (e.key === 'ArrowRight' || e.key === 'Space') nextSlide();
            else if (e.key === 'ArrowLeft') prevSlide();
        });

        updateSlides();
    </script>
</body>
</html>
""")

    # Write HTML output
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write("\n".join(html_content))

    print(f"  [SLIDES GEN] Slide html file compiled successfully via Local Pipeline: {output_path}")
    return output_path
