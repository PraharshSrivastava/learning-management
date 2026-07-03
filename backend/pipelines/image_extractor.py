import os
import re
import fitz  # PyMuPDF
from typing import List, Dict, Any, Set
from pipelines.config import IMAGE_DIR

def extract_images_from_pdf(pdf_path: str, course_id: str) -> List[Dict[str, Any]]:
    """
    Opens the PDF with PyMuPDF, extracts embedded images and their captions (the text block
    immediately below the image), saves the image files to assets, and returns the metadata.
    """
    print(f"Extracting images from PDF: {pdf_path}")
    doc = fitz.open(pdf_path)
    extracted = []
    
    # Create directory for course images
    course_image_dir = os.path.join(IMAGE_DIR, course_id)
    os.makedirs(course_image_dir, exist_ok=True)
    
    total_pages = len(doc)
    
    for page_num in range(total_pages):
        page = doc[page_num]
        
        # Get image positions
        images_info = page.get_image_info(xrefs=True)
        # Get text blocks sorted by coordinate order
        blocks = page.get_text("blocks")
        
        for img_idx, img in enumerate(images_info):
            xref = img['xref']
            bbox = img['bbox']  # (x0, y0, x1, y1)
            iy1 = bbox[3]  # bottom of image
            
            # Find candidate captions (the closest text block below the image)
            best_caption_raw = None
            min_dist = float('inf')
            
            for b in blocks:
                text_content = b[4].strip()
                if not text_content:
                    continue
                
                tx0, ty0, tx1, ty1 = b[0], b[1], b[2], b[3]
                
                # Check vertical distance from bottom of image to top of text
                dist = abs(ty0 - iy1)
                
                # Check if it starts with a caption prefix
                is_caption_format = bool(re.match(r'^\s*(figure|fig|img|image|caption|chart)\b', text_content, re.IGNORECASE))
                
                # Text block must be below or slightly overlapping the bottom of the image, OR be a caption format ending below the image
                if ty0 > iy1 - 20 or (is_caption_format and ty1 > iy1 - 20):
                    # Check horizontal alignment/overlap
                    ix0, ix1 = bbox[0], bbox[2]
                    overlap = max(0, min(ix1, tx1) - max(ix0, tx0))
                    
                    # If they overlap horizontally or the text starts close to the image's x0
                    if overlap > 0 or (abs(tx0 - ix0) < 50):
                        effective_dist = 0 if is_caption_format else dist
                        if effective_dist < min_dist:
                            min_dist = effective_dist
                            # Split by paragraph double newlines and join lines in space-separated form
                            paragraphs = [p for p in re.split(r'\n\s*\n', text_content) if p.strip()]
                            best_caption_raw = " ".join(paragraphs[0].split()) if paragraphs else text_content
            
            # Fallback: search top of next page if image is near bottom of the page
            if not best_caption_raw and (page.rect.height - iy1 < 150) and (page_num + 1 < total_pages):
                next_page = doc[page_num + 1]
                next_blocks = next_page.get_text("blocks")
                min_next_page_ty0 = float('inf')
                
                for b in next_blocks:
                    text_content = b[4].strip()
                    if not text_content:
                        continue
                    
                    tx0, ty0, tx1, ty1 = b[0], b[1], b[2], b[3]
                    
                    if ty0 < 150:
                        ix0, ix1 = bbox[0], bbox[2]
                        overlap = max(0, min(ix1, tx1) - max(ix0, tx0))
                        
                        if overlap > 0 or (abs(tx0 - ix0) < 50):
                            if ty0 < min_next_page_ty0:
                                min_next_page_ty0 = ty0
                                paragraphs = re.split(r'\n\s*\n', text_content)
                                best_caption_raw = " ".join(paragraphs[0].split())
                                print(f"    [NEXT PAGE CAPTION] Found wrapped caption at top of page {page_num + 2}: \"{best_caption_raw}\"")
                                
            if not best_caption_raw:
                best_caption_raw = f"Image on page {page_num + 1}"
                caption_content = best_caption_raw
            else:
                # Parse prefix (e.g. Figure 9: Cosine Similarity -> content="Cosine Similarity")
                prefix_pattern = re.compile(r'^\s*(figure|fig|img|image|caption|chart)\s*\d*[:.-]?\s*(.*)', re.IGNORECASE)
                match = prefix_pattern.match(best_caption_raw)
                if match:
                    caption_content = match.group(2).strip()
                else:
                    caption_content = best_caption_raw
            
            # Extract and save the image
            try:
                base_image = doc.extract_image(xref)
                image_bytes = base_image["image"]
                image_ext = base_image["ext"]
                
                img_filename = f"page_{page_num + 1}_img_{img_idx + 1}_{xref}.{image_ext}"
                img_filepath = os.path.join(course_image_dir, img_filename)
                
                with open(img_filepath, "wb") as f:
                    f.write(image_bytes)
                
                # Relative path to backend (BASE_DIR) directory
                relative_path = f"assets/images/{course_id}/{img_filename}"
                
                extracted.append({
                    "image_id": f"img_{xref}",
                    "caption": caption_content,
                    "raw_caption": best_caption_raw,
                    "file_path": relative_path,
                    "page": page_num + 1,
                    "bbox": bbox
                })
                print(f"  Extracted image {xref} on page {page_num+1} with caption: \"{caption_content}\"")
            except Exception as e:
                print(f"  [WARNING] Failed to extract image with xref {xref} on page {page_num + 1}: {e}")
                
    return extracted


def parse_caption_prefix(text: str):
    """
    Parses a caption string to extract the prefix type, figure number, and the caption body.
    Example:
      "Figure 9: ChatGPT" -> ("figure", "9", "ChatGPT")
      "Fig 1.2 - Diagram" -> ("fig", "1.2", "Diagram")
      "ChatGPT" -> (None, None, "ChatGPT")
    """
    pattern = re.compile(
        r'^\s*(figure|fig|img|image|caption|chart)\s*(\d+(?:[\.-]\d+)*)?\s*[:.\-]?\s*(.*)', 
        re.IGNORECASE
    )
    match = pattern.match(text)
    if match:
        prefix_type = match.group(1).lower()
        num = match.group(2)
        body = match.group(3).strip()
        return prefix_type, num, body
    return None, None, text.strip()


def find_matching_line(caption: str, original_lines: List[str], line_pages: List[int] = None, image_page: int = None, raw_caption: str = None) -> int:
    """
    Finds the 1-based line index in original_lines that matches the caption.
    If line_pages and image_page are provided, restricts the search to target pages.
    """
    match_target = raw_caption if raw_caption else caption
    target_prefix, target_num, target_body = parse_caption_prefix(match_target)
    clean_target_body = re.sub(r'[^a-zA-Z0-9]', '', target_body.lower())
    if not clean_target_body:
        return -1
    
    # 1. Exact clean match with prefix alignment
    for idx, line in enumerate(original_lines):
        if line_pages and image_page and line_pages[idx] not in (image_page, image_page + 1):
            continue
            
        cand_prefix, cand_num, cand_body = parse_caption_prefix(line)
        clean_cand_body = re.sub(r'[^a-zA-Z0-9]', '', cand_body.lower())
        
        if target_prefix is not None:
            if cand_prefix is None:
                continue
            if target_num is not None and cand_num is not None and target_num != cand_num:
                continue
            if clean_target_body == clean_cand_body:
                return idx + 1
        else:
            if cand_prefix is not None:
                continue
            if clean_target_body == clean_cand_body:
                return idx + 1
            
    # 2. Fallback to substring matching with prefix alignment
    for idx, line in enumerate(original_lines):
        if line_pages and image_page and line_pages[idx] not in (image_page, image_page + 1):
            continue
            
        cand_prefix, cand_num, cand_body = parse_caption_prefix(line)
        clean_cand_body = re.sub(r'[^a-zA-Z0-9]', '', cand_body.lower())
        
        if target_prefix is not None:
            if cand_prefix is None:
                continue
            if target_num is not None and cand_num is not None and target_num != cand_num:
                continue
            if len(clean_cand_body) > 3 and clean_cand_body in clean_target_body:
                return idx + 1
            if len(clean_target_body) > 3 and clean_target_body in clean_cand_body:
                return idx + 1
        else:
            if cand_prefix is not None:
                continue
            if len(clean_cand_body) > 3 and clean_cand_body in clean_target_body:
                return idx + 1
            if len(clean_target_body) > 3 and clean_target_body in clean_cand_body:
                return idx + 1
            
    return -1


def get_caption_lines(caption: str, start_line_num: int, original_lines: List[str], raw_caption: str = None) -> Set[int]:
    """
    Given an image caption (or raw caption) and the 1-based start line number where it matches,
    reconstructs multi-line captions by consuming consecutive lines in original_lines
    until the full cleaned caption is covered.
    Returns a set of 1-based line numbers containing the caption.
    """
    match_target = raw_caption if raw_caption else caption
    clean_cap = re.sub(r'[^a-zA-Z0-9]', '', match_target.lower())
    if not clean_cap or start_line_num < 1 or start_line_num > len(original_lines):
        return set()
        
    caption_line_indices = set()
    current_idx = start_line_num - 1
    accumulated_cleaned = ""
    
    # We loop and accumulate cleaned text from consecutive lines
    while current_idx < len(original_lines) and len(accumulated_cleaned) < len(clean_cap):
        line = original_lines[current_idx]
        clean_line = re.sub(r'[^a-zA-Z0-9]', '', line.lower())
        if clean_line:
            # If adding this line matches or is a prefix/substring of the remaining clean_cap
            remaining_cap = clean_cap[len(accumulated_cleaned):]
            if clean_line in remaining_cap or remaining_cap in clean_line:
                accumulated_cleaned += clean_line
                caption_line_indices.add(current_idx + 1)
            else:
                # If it doesn't match/fit, stop (we hit non-caption content)
                break
        else:
            # If the line is empty (whitespace/formatting), still include it as part of the caption lines
            caption_line_indices.add(current_idx + 1)
        current_idx += 1
        
    return caption_line_indices


def assign_images_to_modules(images: List[Dict[str, Any]], original_lines: List[str], modules: List[Dict[str, Any]], total_pages: int = 1, line_pages: List[int] = None) -> List[Dict[str, Any]]:
    """
    Assigns each image to the module containing its corresponding line.
    If matching fails, falls back to a page-ratio estimation.
    """
    total_lines = len(original_lines)
    num_modules = len(modules)
    
    # Initialize/compute end_lines and image lists for each module
    for idx, module in enumerate(modules):
        start_line = module["start_line"]
        if idx + 1 < num_modules:
            end_line = modules[idx + 1]["start_line"] - 1
        else:
            end_line = total_lines
        module["end_line"] = end_line
        if "images" not in module:
            module["images"] = []
            
    for img in images:
        line_num = find_matching_line(
            img["caption"], 
            original_lines, 
            line_pages=line_pages, 
            image_page=img.get("page"), 
            raw_caption=img.get("raw_caption")
        )
        assigned = False
        
        if line_num != -1:
            for module in modules:
                if module["start_line"] <= line_num <= module["end_line"]:
                    # Avoid duplicates
                    if not any(existing["image_id"] == img["image_id"] for existing in module["images"]):
                        module["images"].append(img)
                    assigned = True
                    print(f"  Assigned image {img['image_id']} to Module '{module['title']}' (matched to line {line_num})")
                    
                    # Inject inline image tag into the module's text
                    module_lines = module.get("text", "").split('\n')
                    rel_idx = line_num - module["start_line"]
                    if 0 <= rel_idx < len(module_lines):
                        module_lines[rel_idx] = f"[IMAGE: {img['image_id']}] {module_lines[rel_idx]}"
                        module["text"] = '\n'.join(module_lines)
                        print(f"    Injected inline marker [IMAGE: {img['image_id']}] at relative line {rel_idx} of module '{module['title']}'")
                    break
        
        # Fallback: estimate module by page number distribution
        if not assigned and num_modules > 0:
            page = img.get("page", 1)
            estimated_idx = min(num_modules - 1, int(((page - 1) / max(1, total_pages)) * num_modules))
            module = modules[estimated_idx]
            if not any(existing["image_id"] == img["image_id"] for existing in module["images"]):
                module["images"].append(img)
            print(f"  [FALLBACK] Assigned image {img['image_id']} to Module '{module['title']}' based on page {page}/{total_pages}")
            
    # Clean up temporary 'end_line' fields to keep schema clean
    for module in modules:
        module.pop("end_line", None)
        
    return modules
