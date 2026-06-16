import os
import re
import fitz  # PyMuPDF
from typing import List, Dict, Any
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
            best_caption = None
            min_dist = float('inf')
            
            for b in blocks:
                text_content = b[4].strip()
                if not text_content:
                    continue
                
                tx0, ty0, tx1, ty1 = b[0], b[1], b[2], b[3]
                
                # Check vertical distance from bottom of image to top of text
                dist = abs(ty0 - iy1)
                
                # Text block must be below or slightly overlapping the bottom of the image
                if ty0 > iy1 - 20:
                    # Check horizontal alignment/overlap
                    ix0, ix1 = bbox[0], bbox[2]
                    overlap = max(0, min(ix1, tx1) - max(ix0, tx0))
                    
                    # If they overlap horizontally or the text starts close to the image's x0
                    if overlap > 0 or (abs(tx0 - ix0) < 50):
                        if dist < min_dist and dist < 30:  # 30 points threshold
                            min_dist = dist
                            best_caption = text_content.split('\n')[0].strip()
            
            if best_caption:
                # Clean up newlines / whitespace in caption
                best_caption = " ".join(best_caption.split())
            else:
                # Fallback caption if none is found
                best_caption = f"Image on page {page_num + 1}"
            
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
                    "caption": best_caption,
                    "file_path": relative_path,
                    "page": page_num + 1,
                    "bbox": bbox
                })
                print(f"  Extracted image {xref} on page {page_num+1} with caption: \"{best_caption}\"")
            except Exception as e:
                print(f"  [WARNING] Failed to extract image with xref {xref} on page {page_num + 1}: {e}")
                
    return extracted


def find_matching_line(caption: str, original_lines: List[str]) -> int:
    """
    Finds the 1-based line index in original_lines that matches the caption.
    """
    clean_cap = re.sub(r'[^a-zA-Z0-9]', '', caption.lower())
    if not clean_cap:
        return -1
    
    # 1. Exact clean match
    for idx, line in enumerate(original_lines):
        clean_line = re.sub(r'[^a-zA-Z0-9]', '', line.lower())
        if clean_cap == clean_line:
            return idx + 1
            
    # 2. Fallback to substring matching
    for idx, line in enumerate(original_lines):
        clean_line = re.sub(r'[^a-zA-Z0-9]', '', line.lower())
        if len(clean_line) > 3 and clean_line in clean_cap:
            return idx + 1
        if len(clean_cap) > 3 and clean_cap in clean_line:
            return idx + 1
            
    return -1


def assign_images_to_modules(images: List[Dict[str, Any]], original_lines: List[str], modules: List[Dict[str, Any]], total_pages: int = 1) -> List[Dict[str, Any]]:
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
        line_num = find_matching_line(img["caption"], original_lines)
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
