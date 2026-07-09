from core.database import get_all_courses, save_all_courses
import os
import re
import json
import tempfile
import subprocess
from PIL import Image, ImageDraw, ImageFont
import imageio_ffmpeg
from pathlib import Path
from core.io_utils import atomic_write_json

from pipelines.config import BASE_DIR, DRAFT_COURSES_FILE
VIDEO_DIR = os.path.join(BASE_DIR, "assets", "videos")

# Colors from PhillipCapital Design System
PRIMARY_BLUE = (0, 49, 122)      # #00317A
LIGHT_GRAY = (238, 238, 238)     # #EEEEEE
GRAY = (170, 170, 170)           # #AAAAAA
TEXT_BLACK = (0, 0, 0)           # #000000
ACCENT_BLUE = (0, 128, 255)      # #0080FF
ACCENT_CYAN = (23, 188, 226)     # #17BCE2
ACCENT_ORANGE = (247, 143, 32)   # #F78F20
ACCENT_GREEN = (20, 196, 150)    # #14C496
ACCENT_RED = (255, 21, 21)       # #FF1515

# Safe font loader — checks a bundled-fonts directory first (recommended:
# place metric-compatible .ttf files, e.g. Liberation Sans, under
# backend/assets/fonts/ named arial.ttf and arialbd.ttf), then falls back
# to common per-OS system font locations, and only uses PIL's low-quality
# default font as a last resort — with a visible warning so this never
# fails silently again.
_FONT_SEARCH_DIRS = [
    os.path.join(BASE_DIR, "assets", "fonts"),
    "C:\\Windows\\Fonts",
    "/usr/share/fonts/truetype/dejavu",
    "/usr/share/fonts/truetype/liberation",
    "/usr/share/fonts/truetype/msttcorefonts",
    "/System/Library/Fonts",
    "/System/Library/Fonts/Supplemental",
]

def load_font(font_name="arial.ttf", size=24):
    for font_dir in _FONT_SEARCH_DIRS:
        font_path = os.path.join(font_dir, font_name)
        if os.path.exists(font_path):
            try:
                return ImageFont.truetype(font_path, size)
            except Exception:
                pass
    print(f"    [WARNING] Font '{font_name}' not found in any known location "
          f"({_FONT_SEARCH_DIRS}). Falling back to PIL's low-quality default "
          f"font. Bundle a real .ttf file under backend/assets/fonts/{font_name} to fix this.")
    return ImageFont.load_default()

def get_text_width(text, font, draw=None):
    if draw and hasattr(draw, 'textlength'):
        return draw.textlength(text, font=font)
    try:
        return font.getbbox(text)[2] - font.getbbox(text)[0]
    except AttributeError:
        return font.getsize(text)[0]

def get_text_height(text, font):
    try:
        return font.getbbox(text)[3] - font.getbbox(text)[1]
    except AttributeError:
        return font.getsize(text)[1]

def wrap_text(text, font, max_width, draw):
    words = text.split()
    lines = []
    current_line = []
    for word in words:
        test_line = ' '.join(current_line + [word])
        w = get_text_width(test_line, font, draw)
        if w <= max_width:
            current_line.append(word)
        else:
            if current_line:
                lines.append(' '.join(current_line))
            current_line = [word]
    if current_line:
        lines.append(' '.join(current_line))
    return '\n'.join(lines)

def draw_multiline_text(draw, text, x, y, font, fill, max_width, line_spacing=1.3):
    wrapped = wrap_text(text, font, max_width, draw)
    lines = wrapped.split('\n')
    curr_y = y
    h = get_text_height("Ag", font)
    for line in lines:
        draw.text((x, curr_y), line, font=font, fill=fill)
        curr_y += int(h * line_spacing)
    return curr_y

def round_corners_p_shape(img, radius):
    """
    Creates a mask with top-right and bottom-left corners rounded,
    while leaving top-left and bottom-right sharp to reflect the "P" brand geometry.
    """
    mask = Image.new('L', img.size, 255)
    draw = ImageDraw.Draw(mask)
    w, h = img.size
    
    # Mask top-right corner
    draw.rectangle([w - radius, 0, w, radius], fill=0)
    draw.pieslice([w - 2 * radius, 0, w, 2 * radius], 270, 360, fill=255)
    
    # Mask bottom-left corner
    draw.rectangle([0, h - radius, radius, h], fill=0)
    draw.pieslice([0, h - 2 * radius, 2 * radius, h], 90, 180, fill=255)
    
    result = img.copy()
    result.putalpha(mask)
    return result

def draw_slide_image(draw, bg_image, image_meta, x, y, max_w, max_h):
    """
    Loads, scales, applies 'P'-shape rounding, and draws a slide visual asset.
    """
    raw_path = image_meta.get("file_path", "")
    abs_path = os.path.join(BASE_DIR, raw_path)
    if not os.path.exists(abs_path):
        return
    
    try:
        img = Image.open(abs_path)
        # Keep aspect ratio
        img.thumbnail((max_w, max_h))
        
        # Apply the P-shape geometry mask (radius 32)
        radius = min(32, img.size[0] // 4, img.size[1] // 4)
        rounded_img = round_corners_p_shape(img, radius)
        
        # Paste onto background
        bg_image.paste(rounded_img, (x, y), rounded_img)
        
        # Draw translucent blue caption banner on the lower-left side of the frame
        # (Caption rendering has been removed as per requirements)
            
    except Exception as e:
        print(f"Error drawing slide image: {e}")

def get_audio_duration(audio_path):
    """
    Uses the bundled imageio-ffmpeg executable to get details of the audio.
    """
    if not audio_path or not os.path.exists(audio_path):
        return 5.0
        
    ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
    try:
        result = subprocess.run([ffmpeg_exe, "-i", audio_path], capture_output=True, text=True, errors='ignore')
        match = re.search(r"Duration:\s*(\d+):(\d+):(\d+\.\d+)", result.stderr)
        if match:
            hours = int(match.group(1))
            minutes = int(match.group(2))
            seconds = float(match.group(3))
            return hours * 3600 + minutes * 60 + seconds
    except Exception as e:
        print(f"Error getting audio duration: {e}")
    return 5.0

def draw_concept_layout(draw, slide, text_w, fonts):
    data = slide.get("concept_data", {})
    term = data.get("core_term", "Concept")
    definition = data.get("definition", "")
    takeaways = data.get("key_takeaways", [])
    if not takeaways and data.get("key_takeaway"):
        takeaways = [data["key_takeaway"]]
        
    # Draw cyan vertical border line
    draw.rectangle([100, 200, 112, 450], fill=ACCENT_CYAN)
    
    # Core term
    draw.text((140, 200), term, font=fonts["title"], fill=PRIMARY_BLUE)
    
    # Definition
    draw_multiline_text(draw, definition, 140, 280, fonts["body_large"], TEXT_BLACK, text_w - 40)
    
    # Key takeaways banner box (Light Gray with Blue left border)
    if takeaways:
        box_y = 500
        box_w = text_w
        box_h = 300
        
        # Gray background box
        draw.rectangle([100, box_y, 100 + box_w, box_y + box_h], fill=LIGHT_GRAY)
        # Primary Blue left border
        draw.rectangle([100, box_y, 108, box_y + box_h], fill=PRIMARY_BLUE)
        
        draw.text((130, box_y + 20), "Key Takeaways:", font=fonts["subtitle"], fill=PRIMARY_BLUE)
        
        curr_y = box_y + 80
        for t in takeaways:
            if not t.strip():
                continue
            bullet_sym = "▪ "
            draw.text((130, curr_y), bullet_sym, font=fonts["body"], fill=PRIMARY_BLUE)
            curr_y = draw_multiline_text(draw, t, 160, curr_y, fonts["body"], TEXT_BLACK, box_w - 90) + 10

def draw_steps_layout(draw, slide, text_w, fonts):
    data = slide.get("steps_data", {})
    steps = data.get("steps", [])
    
    if not steps:
        return
        
    card_margin = 20
    num_steps = len(steps)
    step_w = int((text_w - (card_margin * (num_steps - 1))) / num_steps)
    
    for idx, step in enumerate(steps):
        card_x = 100 + idx * (step_w + card_margin)
        card_y = 250
        card_h = 500
        
        # Step card container (Light gray background)
        draw.rectangle([card_x, card_y, card_x + step_w, card_y + card_h], fill=LIGHT_GRAY)
        # Blue top border
        draw.rectangle([card_x, card_y, card_x + step_w, card_y + 8], fill=PRIMARY_BLUE)
        
        # Step number
        step_num = f"STEP {step.get('step_number', idx + 1)}"
        draw.text((card_x + 15, card_y + 25), step_num, font=fonts["body_small"], fill=ACCENT_CYAN)
        
        # Step title
        title_y = draw_multiline_text(
            draw, 
            step.get("title", ""), 
            card_x + 15, 
            card_y + 55, 
            fonts["body_large_bold"], 
            PRIMARY_BLUE, 
            step_w - 30
        )
        
        # Step description
        draw_multiline_text(
            draw, 
            step.get("description", ""), 
            card_x + 15, 
            title_y + 15, 
            fonts["body"], 
            TEXT_BLACK, 
            step_w - 30
        )
        
        # Draw connections
        if idx < num_steps - 1:
            arrow_x = card_x + step_w + 2
            arrow_y = card_y + (card_h // 2) - 10
            draw.text((arrow_x, arrow_y), "→", font=fonts["subtitle"], fill=GRAY)

def draw_comparison_layout(draw, slide, text_w, fonts):
    data = slide.get("comparison_data", {})
    col_w = int((text_w - 40) / 2)
    
    # Left column: Accent Blue
    col1_x = 100
    col1_y = 220
    draw.rectangle([col1_x, col1_y, col1_x + col_w, col1_y + 600], fill=(255, 255, 255), outline=LIGHT_GRAY, width=2)
    draw.rectangle([col1_x, col1_y, col1_x + col_w, col1_y + 8], fill=ACCENT_BLUE)
    
    title_left = data.get("left_column_title", "")
    draw.text((col1_x + 20, col1_y + 25), title_left, font=fonts["body_large_bold"], fill=PRIMARY_BLUE)
    
    curr_y = col1_y + 90
    for pt in data.get("left_column_points", []):
        draw.text((col1_x + 20, curr_y), "•", font=fonts["subtitle"], fill=ACCENT_CYAN)
        curr_y = draw_multiline_text(draw, pt, col1_x + 45, curr_y, fonts["body"], TEXT_BLACK, col_w - 65) + 15

    # Right column: Accent Orange
    col2_x = 100 + col_w + 40
    col2_y = 220
    draw.rectangle([col2_x, col2_y, col2_x + col_w, col2_y + 600], fill=(255, 255, 255), outline=LIGHT_GRAY, width=2)
    draw.rectangle([col2_x, col2_y, col2_x + col_w, col2_y + 8], fill=ACCENT_ORANGE)
    
    title_right = data.get("right_column_title", "")
    draw.text((col2_x + 20, col2_y + 25), title_right, font=fonts["body_large_bold"], fill=PRIMARY_BLUE)
    
    curr_y = col2_y + 90
    for pt in data.get("right_column_points", []):
        draw.text((col2_x + 20, curr_y), "•", font=fonts["subtitle"], fill=ACCENT_ORANGE)
        curr_y = draw_multiline_text(draw, pt, col2_x + 45, curr_y, fonts["body"], TEXT_BLACK, col_w - 65) + 15

def draw_grid_layout(draw, slide, text_w, fonts):
    data = slide.get("grid_data", {})
    columns = data.get("columns", [])
    if not columns:
        return
        
    num_cols = len(columns)
    margin = 25
    col_w = int((text_w - (margin * (num_cols - 1))) / num_cols)
    
    for idx, col in enumerate(columns):
        card_x = 100 + idx * (col_w + margin)
        card_y = 240
        card_h = 520
        
        # Grid Card
        draw.rectangle([card_x, card_y, card_x + col_w, card_y + card_h], fill=LIGHT_GRAY)
        # Bottom Green Border
        draw.rectangle([card_x, card_y + card_h - 8, card_x + col_w, card_y + card_h], fill=ACCENT_GREEN)
        
        # Header
        header_y = draw_multiline_text(
            draw, 
            col.get("header", ""), 
            card_x + 20, 
            card_y + 25, 
            fonts["body_large_bold"], 
            PRIMARY_BLUE, 
            col_w - 40
        )
        
        # Content
        draw_multiline_text(
            draw, 
            col.get("content", ""), 
            card_x + 20, 
            header_y + 20, 
            fonts["body"], 
            TEXT_BLACK, 
            col_w - 40
        )

def draw_bullets_layout(draw, slide, text_w, fonts):
    bullets = slide.get("bullets_data")
    if not bullets:
        bullets = slide.get("bullets", [])
        
    curr_y = 220
    for b in bullets:
        b_text = b if isinstance(b, str) else b.get("text", "")
        if not b_text.strip():
            continue
            
        # Draw solid square bullet
        draw.rectangle([100, curr_y + 8, 114, curr_y + 22], fill=PRIMARY_BLUE)
        curr_y = draw_multiline_text(draw, b_text, 140, curr_y, fonts["subtitle"], TEXT_BLACK, text_w - 40) + 30

def render_slide_image(slide, images_by_id, output_path):
    """
    Renders a planned slide to a 1920x1080 visual image asset.
    """
    # Create canvas
    img = Image.new('RGB', (1920, 1080), (255, 255, 255))
    draw = ImageDraw.Draw(img)
    
    # Load fonts
    fonts = {
        "logo": load_font("arialbd.ttf", 36),
        "title": load_font("arialbd.ttf", 46),
        "subtitle": load_font("arialbd.ttf", 30),
        "body_large_bold": load_font("arialbd.ttf", 26),
        "body_large": load_font("arial.ttf", 26),
        "body": load_font("arial.ttf", 22),
        "body_small": load_font("arialbd.ttf", 16)
    }
    
    # Draw logo at top-left
    logo_path = os.path.join(BASE_DIR, "assets", "logo.png")
    logo_drawn = False
    if os.path.exists(logo_path):
        try:
            logo = Image.open(logo_path)
            logo.thumbnail((250, 60))
            img.paste(logo, (100, 45), logo if logo.mode == 'RGBA' else None)
            logo_drawn = True
        except Exception as e:
            print(f"Error loading logo png: {e}")
            
    if not logo_drawn:
        draw.text((100, 45), "PHILLIPCAPITAL", font=fonts["logo"], fill=PRIMARY_BLUE)
        
    layout_type = slide.get("layout_type", "bullets").lower()
    
    # Layout sizes
    has_images = len(slide.get("image_ids", [])) > 0
    text_width = 1000 if has_images else 1720
    
    # Render layout specific content
    if layout_type == "concept":
        draw_concept_layout(draw, slide, text_width, fonts)
    else:
        # Standard header block for other layouts
        slide_title = slide.get("slide_title", "Summary")
        draw.text((100, 115), slide_title, font=fonts["title"], fill=PRIMARY_BLUE)
        draw.rectangle([100, 190, 1820, 192], fill=LIGHT_GRAY)
        
        if layout_type == "steps":
            draw_steps_layout(draw, slide, text_width, fonts)
        elif layout_type == "comparison":
            draw_comparison_layout(draw, slide, text_width, fonts)
        elif layout_type == "grid":
            draw_grid_layout(draw, slide, text_width, fonts)
        else:
            draw_bullets_layout(draw, slide, text_width, fonts)
            
    # Render image visual space (if mapped)
    if has_images:
        img_id = slide["image_ids"][0]
        img_meta = images_by_id.get(img_id)
        if img_meta:
            draw_slide_image(draw, img, img_meta, 1160, 200, 660, 600)
            
    # Save the rendered frame
    img.save(output_path, "PNG")

def generate_video_for_module(course_id: str, module_number: int) -> str:
    """
    Renders slides to PNG, merges with slide speech clips,
    concatenates clips together, and exports the final MP4 slideshow video.
    """
    courses = get_all_courses('draft')
        
    course = next((c for c in courses if c.get("id") == course_id), None)
    if not course:
        raise ValueError(f"Course '{course_id}' not found.")
        
    modules = course.get("modules", [])
    if module_number < 1 or module_number > len(modules):
        raise ValueError(f"Module number {module_number} out of range.")
        
    module = modules[module_number - 1]
    slides = module.get("slides", [])
    
    if not slides:
        raise ValueError(f"Module {module_number} has no slides generated yet. Generate slides first.")
        
    # Compile HTML slides to ensure they exist
    from pipelines.slides_generator import compile_slides_for_course
    try:
        compile_slides_for_course(course_id)
    except Exception as e:
        print(f"  [WARNING] Slide compilation failed: {e}")

    html_file_path = os.path.join(BASE_DIR, "assets", "slides", course_id, f"module_{module_number}.html")
    if not os.path.exists(html_file_path):
        raise FileNotFoundError(f"HTML slides file not found at {html_file_path}")

    # Establish local folder structures
    course_video_dir = os.path.join(VIDEO_DIR, f"course_{course_id}")
    os.makedirs(course_video_dir, exist_ok=True)
    final_output_path = os.path.join(course_video_dir, f"module_{module_number}.mp4")
    
    temp_clips = []
    ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
    
    with tempfile.TemporaryDirectory() as temp_dir:
        print(f"Generating video chunks in temp path: {temp_dir}")
        
        # Render HTML slides via Playwright Chromium screenshots
        print(f"Screenshotting HTML slides for module {module_number} using Playwright...")
        from playwright.sync_api import sync_playwright
        
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 1280, "height": 720})
            
            file_url = Path(html_file_path).resolve().as_uri()
            page.goto(file_url)
            
            # Wait for images and web fonts to fully load
            page.wait_for_load_state("networkidle")
            page.evaluate("document.fonts.ready")
            
            # Inject CSS to disable animations during capture
            page.add_style_tag(content=".slide { animation: none !important; transition: none !important; }")
            
            for idx in range(len(slides)):
                slide_img_path = os.path.join(temp_dir, f"slide_{idx}.png")
                page.evaluate(f"window.goToSlide({idx})")
                page.screenshot(path=slide_img_path)
                
            browser.close()
        
        for idx, slide in enumerate(slides):
            slide_img_path = os.path.join(temp_dir, f"slide_{idx}.png")
            # 2. Get audio path & duration
            audio_rel_path = slide.get("audio_path", "")
            audio_abs_path = os.path.join(BASE_DIR, audio_rel_path) if audio_rel_path else ""
            
            duration = get_audio_duration(audio_abs_path)
            
            # 3. Create video chunk
            clip_path = os.path.join(temp_dir, f"clip_{idx}.mp4")
            
            # If audio exists, encode slide frame + audio to video chunk
            if audio_abs_path and os.path.exists(audio_abs_path):
                cmd = [
                    ffmpeg_exe, "-y",
                    "-loop", "1", "-i", slide_img_path,
                    "-i", audio_abs_path,
                    "-c:v", "libx264",
                    "-tune", "stillimage",
                    "-c:a", "aac",
                    "-b:a", "192k",
                    "-pix_fmt", "yuv420p",
                    "-t", str(duration),
                    clip_path
                ]
            else:
                # Fallback to silent video chunk if narration audio is missing
                cmd = [
                    ffmpeg_exe, "-y",
                    "-loop", "1", "-i", slide_img_path,
                    "-f", "lavfi", "-i", "anullsrc=channel_layout=mono:sample_rate=44100",
                    "-c:v", "libx264",
                    "-tune", "stillimage",
                    "-c:a", "aac",
                    "-t", str(duration),
                    "-pix_fmt", "yuv420p",
                    clip_path
                ]
                
            print(f"Encoding clip {idx} with duration={duration}...")
            result = subprocess.run(cmd, capture_output=True, text=True, errors='ignore')
            if result.returncode != 0:
                raise RuntimeError(f"FFmpeg failed encoding slide {idx}: {result.stderr}")
                
            temp_clips.append(clip_path)
            
        # 4. Concatenate all slide clips together
        print("Concatenating all clips...")
        txt_path = os.path.join(temp_dir, "concat.txt")
        with open(txt_path, "w", encoding="utf-8") as f:
            for clip in temp_clips:
                norm_path = clip.replace("\\", "/")
                f.write(f"file '{norm_path}'\n")
                
        cmd = [
            ffmpeg_exe, "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", txt_path,
            "-c", "copy",
            final_output_path
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, errors='ignore')
        if result.returncode != 0:
            raise RuntimeError(f"FFmpeg concatenation failed: {result.stderr}")
            
    print(f"Module video generated successfully: {final_output_path}")
    
    # Save the video path in courses.json database
    fresh_courses = get_all_courses('draft')
    fresh_idx = next((i for i, c in enumerate(fresh_courses) if c.get("id") == course_id), None)
    if fresh_idx is not None:
        fresh_courses[fresh_idx]["modules"][module_number - 1]["video_path"] = f"assets/videos/course_{course_id}/module_{module_number}.mp4"
        save_all_courses(fresh_courses, "draft")
            
    # Return relative URL path
    return f"assets/videos/course_{course_id}/module_{module_number}.mp4"
