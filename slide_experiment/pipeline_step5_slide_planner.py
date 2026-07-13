import os
import sys
import json
from pydantic import BaseModel, Field
from typing import List

# Ensure backend imports work
BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from local_db import get_all_courses, save_all_courses
from pipelines.config import safe_chat_completion, get_llm_endpoint

class SlidePlan(BaseModel):
    title: str = Field(description="Title of the slide")
    content: List[str] = Field(description="The reframed bullets or paragraphs that belong on this slide")

class ModuleSlidesSchema(BaseModel):
    chain_of_thought: str = Field(description="Step 1: Look at the module bullets as a whole. Step 2: Evaluate each individual bullet. If a bullet is a definition, give it its own slide. Arrange all other bullets into slides of 3, 4, or 5 ensuring subtopics don't spill over to next/previous slides.")
    slides: List[SlidePlan] = Field(description="The final arranged slides")

class SlideTitle(BaseModel):
    title: str = Field(description="A clean, highly descriptive, standalone title for the slide based ONLY on its contents. DO NOT use prefixes like 'Module 1:' or 'Lesson 2:'.")

class SlideTitlesSchema(BaseModel):
    titles: List[SlideTitle] = Field(description="List of titles corresponding to the input slides in the exact same order.")

class ImageMapping(BaseModel):
    image_id: str
    bullet_index: int  # 1-based index across all slides in this module

class ImageMappingResult(BaseModel):
    mappings: List[ImageMapping]

IMAGE_SLIDE_MAPPING_PROMPT = """You are an instructional designer mapping images to bullet points within a presentation module.

You will receive:
1. A list of slides in the module, where each slide has a title and a list of numbered bullet points.
2. A list of images with their captions (the descriptions of the images).

Your task is to map each image to the single bullet point that is most semantically relevant to the image content/caption.

CRITICAL REQUIREMENTS:
- You MUST output exactly one mapping for every single image in the provided list.
- For each image, you must output a mapping containing the image_id and the bullet_index (the 1-based sequential bullet number across the entire module).
- Choose the bullet point that discusses or is most closely related to the image caption.

Return a JSON object matching the ImageMappingResult schema.
"""

def run_step5_slide_planner(course_id: str):
    print(f"[STEP 5] Running Slide Planner (Chain of Thought) for {course_id}")
    
    courses = get_all_courses()
    course_idx = next((i for i, c in enumerate(courses) if c.get("id") == course_id), None)
    
    if course_idx is None:
        raise ValueError(f"Course '{course_id}' not found.")

    course = courses[course_idx]
    modules = course.get("modules", [])
    
    base_url, model_name = get_llm_endpoint("slides")
    json_schema = ModuleSlidesSchema.model_json_schema()

    for module in modules:
        module_title = module.get("title", f"Module {module.get('module_number', '1')}")
        text_input = module.get("text", "")
        if not text_input:
            module["planned_slides"] = []
            continue

        prompt = f"""
You are an expert Instructional Designer and Presentation Architect.
Your task is to organize raw instructional bullets into a logical, high-impact slide presentation.

### INPUT DATA
{text_input}

### INSTRUCTIONS & CHAIN OF THOUGHT
You must follow this exact logical progression in your `chain_of_thought` field before generating the slides:
1. **Module Analysis**: Read the bullets as a whole to understand the overarching theme.
2. **Bullet Evaluation**: Evaluate each bullet individually. 
3. **Definition Isolation**: Identify any bullets that represent a core definition or a major standalone concept. These MUST be isolated onto their own dedicated slide.
4. **Subtopic Grouping**: Group all remaining bullets strictly by subtopic.
5. **Slide Sizing**: Arrange the grouped bullets into slides of 3, 4, or 5 bullets per slide. CRITICAL: Conceptual cohesion is your highest priority. You are permitted to output 1 or 2 bullets on a slide ONLY IF forcing it to 3 bullets would require merging two completely unrelated concepts.
6. **No Spillage Rule**: ALL bullets belonging to a specific subtopic must be contained on a single slide. A subtopic must NEVER spill over to the next or previous slide.

### SLIDE CONTENT RULES
- **Reframing**: You are encouraged to reframe, restructure, and rewrite the bullets for maximum clarity and presentation impact. Do not just copy/paste.
- **Completeness**: You must preserve 100% of the factual information from the raw bullets.
- **Formatting**: Output crisp, single-level bullets. Do not use nested bullets or special characters (like '•') inside the text.

Output a JSON object containing your `chain_of_thought` and the final array of `slides`.
"""
        try:
            print(f"\n    -> Calling LLM for Module {module.get('module_number')}...")
            print("\n=== EXACT TEXT BEING SENT TO LLM ===")
            print(prompt)
            print("====================================\n")
            
            response = safe_chat_completion(
                base_url=base_url,
                model=model_name,
                messages=[
                    {"role": "system", "content": "You are a logical presentation designer."},
                    {"role": "user", "content": prompt}
                ],
                response_format={
                    "type": "json_schema",
                    "json_schema": {
                        "name": "ModuleSlidesSchema",
                        "schema": json_schema,
                        "strict": True
                    }
                },
                temperature=0.2,
                default_max_tokens=4096
            )
            
            raw_content = response.choices[0].message.content
            parsed = ModuleSlidesSchema.model_validate_json(raw_content)
            
            # --- SECOND LLM CALL: SYNTHESIZE TITLES ---
            if parsed.slides:
                print(f"    -> Calling LLM to synthesize titles for {len(parsed.slides)} slides...")
                titles_prompt = "Here is a list of slides containing grouped bullets. For each slide, generate a clean, highly descriptive, standalone title based ONLY on the bullets within that slide.\n\nCRITICAL RULE: DO NOT use prefixes like 'Module 1:', 'Lesson 2:', or 'Slide 3:' in your generated titles.\n\n"
                
                for i, slide in enumerate(parsed.slides):
                    titles_prompt += f"Slide {i+1}:\n"
                    for b in slide.content:
                        titles_prompt += f"- {b}\n"
                    titles_prompt += "\n"
                    
                print("\n=== EXACT TEXT BEING SENT TO 2ND LLM (TITLES) ===")
                print(titles_prompt)
                print("=================================================\n")
                
                titles_response = safe_chat_completion(
                    base_url=base_url,
                    model=model_name,
                    messages=[
                        {"role": "system", "content": "You are an expert copywriter."},
                        {"role": "user", "content": titles_prompt}
                    ],
                    response_format={
                        "type": "json_schema",
                        "json_schema": {
                            "name": "SlideTitlesSchema",
                            "schema": SlideTitlesSchema.model_json_schema(),
                            "strict": True
                        }
                    },
                    temperature=0.2,
                    default_max_tokens=2048
                )
                
                titles_raw = titles_response.choices[0].message.content
                titles_parsed = SlideTitlesSchema.model_validate_json(titles_raw)
                
                # Merge the titles back in
                for i, slide in enumerate(parsed.slides):
                    if i < len(titles_parsed.titles):
                        slide.title = titles_parsed.titles[i].title
            
            # Save the raw dicts
            planned_slides = parsed.model_dump()["slides"]
            module["chain_of_thought"] = parsed.chain_of_thought
            
            # --- 3rd LLM Call: Map Images ---
            images = module.get("images", [])
            if images and planned_slides:
                # Initialize images list for each slide
                for slide in planned_slides:
                    slide["images"] = []
                    
                print(f"\n    -> Calling LLM (Image Mapper) for Module {module.get('module_number')}...")
                
                # Build lessons/slides string
                slides_str = ""
                bullet_to_slide = {}
                bullet_counter = 1
                
                for s_idx, slide in enumerate(planned_slides):
                    slides_str += f"Slide {s_idx + 1}: {slide.get('title')}\n"
                    bullets = slide.get("content", [])
                    for b in bullets:
                        slides_str += f"  - Bullet {bullet_counter}: {b}\n"
                        bullet_to_slide[bullet_counter] = s_idx
                        bullet_counter += 1
                    if not bullets:
                        slides_str += "  - (No bullets)\n"
                    slides_str += "\n"
                
                # Build images string
                images_str = ""
                for img in images:
                    images_str += f"Image ID: {img.get('image_id')}\n"
                    images_str += f"Caption: {img.get('caption')}\n\n"
                    
                mapping_prompt = f"SLIDES:\n{slides_str}\n\nIMAGES:\n{images_str}"
                
                print("\n=== EXACT TEXT BEING SENT TO 3RD LLM (IMAGE MAPPER) ===")
                print(mapping_prompt)
                print("========================================================\n")
                
                mapping_response = safe_chat_completion(
                    base_url=base_url,
                    model=model_name,
                    messages=[
                        {"role": "system", "content": IMAGE_SLIDE_MAPPING_PROMPT},
                        {"role": "user", "content": mapping_prompt}
                    ],
                    response_format={
                        "type": "json_schema",
                        "json_schema": {
                            "name": "ImageMappingResult",
                            "schema": ImageMappingResult.model_json_schema(),
                            "strict": True
                        }
                    },
                    temperature=0.1,
                    default_max_tokens=1024
                )
                
                mapping_raw = mapping_response.choices[0].message.content
                mapping_parsed = ImageMappingResult.model_validate_json(mapping_raw)
                
                # Attach images to slides based on mapped bullet
                mapped_ids = set()
                for mapping in mapping_parsed.mappings:
                    s_idx = bullet_to_slide.get(mapping.bullet_index, 0)
                    if 0 <= s_idx < len(planned_slides):
                        img_meta = next((img for img in images if img.get("image_id") == mapping.image_id), None)
                        if img_meta:
                            planned_slides[s_idx]["images"].append(img_meta)
                            mapped_ids.add(mapping.image_id)
                
                # Fallback unmapped images to slide 1
                for img in images:
                    if img.get("image_id") not in mapped_ids:
                        planned_slides[0]["images"].append(img)
                        print(f"      [FALLBACK] Mapped unassigned image {img.get('image_id')} to Slide 1")

            module["planned_slides"] = planned_slides
            
        except Exception as e:
            print(f"Error planning slides for module {module.get('module_number')}: {e}")
            module["planned_slides"] = []
            module["chain_of_thought"] = str(e)

    course["modules"] = modules
    courses[course_idx] = course
    save_all_courses(courses)

    return course

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        run_step5_slide_planner(sys.argv[1])
    else:
        print("Provide course_id")
