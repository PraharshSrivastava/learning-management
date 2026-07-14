from core.database import get_all_courses, save_all_courses
import os
import sys
import json
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any

from pipelines.config import safe_chat_completion, get_llm_endpoint
from pipelines.prompts import (
    MODULE_SLIDE_PLANNER_PROMPT,
    SLIDE_TITLES_PROMPT,
    IMAGE_SLIDE_MAPPING_PROMPT,
    ART_DIRECTOR_PROMPT
)

# --- Step 5 Schemas ---
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


# --- Step 6 Schemas ---
class ConceptLayoutData(BaseModel):
    core_term: str = Field(description="The main concept or term being defined.")
    definition: str = Field(description="The definition or explanation of the core term.")
    key_takeaways: List[str] = Field(description="1 to 3 key takeaways or essential points about this concept.")

class StepItem(BaseModel):
    title: str = Field(description="Short title for the step.")
    description: str = Field(description="Description of the step.")

class StepsLayoutData(BaseModel):
    steps: List[StepItem] = Field(description="List of sequential steps. Must have 2 to 5 steps.")

class ComparisonLayoutData(BaseModel):
    left_column_title: str = Field(description="Header for the left column (e.g., 'Pros', 'Before', 'Entity A').")
    left_column_points: List[str] = Field(description="List of bullet points for the left column.")
    right_column_title: str = Field(description="Header for the right column (e.g., 'Cons', 'After', 'Entity B').")
    right_column_points: List[str] = Field(description="List of bullet points for the right column.")

class GridColumnItem(BaseModel):
    header: str = Field(description="Header for this grid item.")
    content: str = Field(description="Text content/description for this grid item.")

class GridLayoutData(BaseModel):
    columns: List[GridColumnItem] = Field(description="List of independent pillars or categories. Must have 2 to 4 columns.")

class ArtDirectorSlidePlan(BaseModel):
    layout_type: str = Field(description="Must be one of: 'concept', 'steps', 'comparison', 'grid', or 'bullets'. Choose the most fitting visual layout for the provided slide content.")
    concept_data: Optional[ConceptLayoutData] = Field(None, description="Provide if layout_type is 'concept'.")
    steps_data: Optional[StepsLayoutData] = Field(None, description="Provide if layout_type is 'steps'.")
    comparison_data: Optional[ComparisonLayoutData] = Field(None, description="Provide if layout_type is 'comparison'.")
    grid_data: Optional[GridLayoutData] = Field(None, description="Provide if layout_type is 'grid'.")
    bullets: Optional[List[str]] = Field(None, description="Provide if layout_type is 'bullets'. A list of standard bullet points.")

class ArtDirectorResponse(BaseModel):
    chain_of_thought: str = Field(description="Step 1: Slide Analysis. Step 2: Relationship Evaluation. Step 3: Layout Selection.")
    slides: List[ArtDirectorSlidePlan] = Field(description="The enhanced slides with assigned layouts and structured data, in the exact same order as the input slides.")

def plan_slides_for_module(module: dict, base_url: str, model_name: str) -> dict:
    """
    Step 5 logic: Groups bullets into slides, maps images, and generates titles.
    """
    module_title = module.get("title", f"Module {module.get('module_number', '1')}")
    text_input = module.get("text", "")
    if not text_input:
        module["planned_slides"] = []
        return module

    json_schema = ModuleSlidesSchema.model_json_schema()
    
    prompt = MODULE_SLIDE_PLANNER_PROMPT.format(text_input=text_input)
    try:
        print(f"\n    -> Calling LLM for Module {module.get('module_number')}...")
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
            titles_prompt = SLIDE_TITLES_PROMPT
            
            for i, slide in enumerate(parsed.slides):
                titles_prompt += f"Slide {i+1}:\n"
                for b in slide.content:
                    titles_prompt += f"- {b}\n"
                titles_prompt += "\n"
                
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
            
            for i, slide in enumerate(parsed.slides):
                if i < len(titles_parsed.titles):
                    slide.title = titles_parsed.titles[i].title
        
        planned_slides = parsed.model_dump()["slides"]
        module["chain_of_thought"] = parsed.chain_of_thought
        
        # --- 3rd LLM Call: Map Images ---
        images = module.get("images", [])
        if images and planned_slides:
            for slide in planned_slides:
                slide["images"] = []
                
            print(f"\n    -> Calling LLM (Image Mapper) for Module {module.get('module_number')}...")
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
            
            images_str = ""
            for img in images:
                images_str += f"Image ID: {img.get('image_id')}\n"
                images_str += f"Caption: {img.get('caption')}\n\n"
                
            mapping_prompt = f"SLIDES:\n{slides_str}\n\nIMAGES:\n{images_str}"
            
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
            
            mapped_ids = set()
            for mapping in mapping_parsed.mappings:
                s_idx = bullet_to_slide.get(mapping.bullet_index, 0)
                if 0 <= s_idx < len(planned_slides):
                    img_meta = next((img for img in images if img.get("image_id") == mapping.image_id), None)
                    if img_meta:
                        planned_slides[s_idx]["images"].append(img_meta)
                        mapped_ids.add(mapping.image_id)
            
            for img in images:
                if img.get("image_id") not in mapped_ids:
                    planned_slides[0]["images"].append(img)
                    print(f"      [FALLBACK] Mapped unassigned image {img.get('image_id')} to Slide 1")

        module["planned_slides"] = planned_slides
        
    except Exception as e:
        print(f"Error planning slides for module {module.get('module_number')}: {e}")
        module["planned_slides"] = []
        module["chain_of_thought"] = str(e)

    return module


def assign_layouts_to_module(module: dict, base_url: str, model_name: str) -> dict:
    """
    Step 6 logic: Assigns layouts (concept, steps, etc.) to the planned slides.
    """
    planned_slides = module.get("planned_slides", [])
    if not planned_slides:
        module["slides"] = []
        return module

    print(f"\n    -> Calling Art Director LLM for Module {module.get('module_number', '1')}...")
    
    slides_text = ""
    for idx, slide in enumerate(planned_slides):
        slides_text += f"Slide {idx + 1}:\n"
        slides_text += f"Title: {slide.get('title')}\n"
        slides_text += "Bullets:\n"
        for b in slide.get("content", []):
            slides_text += f" - {b}\n"
        slides_text += "\n"
    
    prompt = ART_DIRECTOR_PROMPT.format(slides_text=slides_text)
    try:
        json_schema = ArtDirectorResponse.model_json_schema()
        response = safe_chat_completion(
            base_url=base_url,
            model=model_name,
            messages=[
                {"role": "system", "content": "You are a creative and analytical presentation art director."},
                {"role": "user", "content": prompt}
            ],
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "ArtDirectorResponse",
                    "schema": json_schema,
                    "strict": True
                }
            },
            temperature=0.2,
            default_max_tokens=4096
        )
        
        raw_content = response.choices[0].message.content
        parsed = ArtDirectorResponse.model_validate_json(raw_content)
        
        for i, enhanced_slide in enumerate(parsed.slides):
            if i < len(planned_slides):
                planned_slides[i]["layout_type"] = enhanced_slide.layout_type
                
                planned_slides[i]["slide_title"] = planned_slides[i].get("title", "")
                if "images" in planned_slides[i]:
                    planned_slides[i]["image_ids"] = [img.get("image_id") for img in planned_slides[i]["images"] if img.get("image_id")]
                
                if enhanced_slide.concept_data:
                    planned_slides[i]["concept_data"] = enhanced_slide.concept_data.model_dump()
                if enhanced_slide.steps_data:
                    planned_slides[i]["steps_data"] = enhanced_slide.steps_data.model_dump()
                if enhanced_slide.comparison_data:
                    planned_slides[i]["comparison_data"] = enhanced_slide.comparison_data.model_dump()
                if enhanced_slide.grid_data:
                    planned_slides[i]["grid_data"] = enhanced_slide.grid_data.model_dump()
                if enhanced_slide.bullets:
                    planned_slides[i]["bullets_data"] = enhanced_slide.bullets
                    planned_slides[i]["content"] = enhanced_slide.bullets
                    planned_slides[i]["bullets"] = enhanced_slide.bullets

        module["slides"] = planned_slides
        
    except Exception as e:
        print(f"Error in Art Director step for module {module.get('module_number')}: {e}")
        module["slides"] = planned_slides

    return module


def generate_slides_for_course(course_id: str) -> Dict[str, Any]:
    """
    Main entrypoint: Loads courses.json, segments modules into slide decks via the experimental 
    multi-step LLM approach, saves database, and returns course dict.
    """
    print(f"Generating slides database models for course {course_id}...")

    courses = get_all_courses('draft')

    course_idx = next((i for i, c in enumerate(courses) if c.get("id") == course_id), None)
    if course_idx is None:
        raise ValueError(f"Course '{course_id}' not found.")

    course = courses[course_idx]
    modules = course.get("modules", [])

    base_url, model_name = get_llm_endpoint("slides")

    import copy
    
    for i, module in enumerate(modules):
        MAX_RETRIES = 3
        best_module_state = module
        is_valid = False
        
        for attempt in range(MAX_RETRIES):
            mod_copy = copy.deepcopy(module)
            print(f"--- Processing Module {mod_copy.get('module_number')} (Attempt {attempt+1}/{MAX_RETRIES}) ---")
            mod_copy = plan_slides_for_module(mod_copy, base_url, model_name)
            mod_copy = assign_layouts_to_module(mod_copy, base_url, model_name)
            
            is_valid = True
            planned_slides = mod_copy.get("planned_slides", [])
            
            for slide in planned_slides:
                content = slide.get("content", [])
                layout = slide.get("layout_type", "")
                
                if len(content) == 0:
                    is_valid = False
                    print(f"Validation failed: Empty slide (0 bullets) detected in module {mod_copy.get('module_number')}")
                    break
                if len(content) == 1 and layout not in ["concept", "comparison"]:
                    is_valid = False
                    print(f"Validation failed: Single bullet on a '{layout}' layout in module {mod_copy.get('module_number')}")
                    break
                    
                # New strict structural validations
                if layout == "concept" and not slide.get("concept_data"):
                    is_valid = False
                    print(f"Validation failed: Missing concept_data for concept layout in module {mod_copy.get('module_number')}")
                    break
                if layout == "steps" and not slide.get("steps_data"):
                    is_valid = False
                    print(f"Validation failed: Missing steps_data for steps layout in module {mod_copy.get('module_number')}")
                    break
                if layout == "comparison" and not slide.get("comparison_data"):
                    is_valid = False
                    print(f"Validation failed: Missing comparison_data for comparison layout in module {mod_copy.get('module_number')}")
                    break
                if layout == "grid" and not slide.get("grid_data"):
                    is_valid = False
                    print(f"Validation failed: Missing grid_data for grid layout in module {mod_copy.get('module_number')}")
                    break
            
            best_module_state = mod_copy
            if is_valid:
                print(f"Validation successful for module {mod_copy.get('module_number')}!")
                break
            else:
                if attempt < MAX_RETRIES - 1:
                    print(f"Retrying slide generation for module {mod_copy.get('module_number')}...")
        
        # If it still fails after max retries, force a fix
        if not is_valid:
            print(f"Max retries reached for module {best_module_state.get('module_number')}. Applying fallback fixes.")
            fixed_slides = []
            for slide in best_module_state.get("planned_slides", []):
                content = slide.get("content", [])
                layout = slide.get("layout_type", "")
                
                if len(content) == 0:
                    print(f"  -> Dropping empty slide: '{slide.get('title')}'")
                    continue
                elif len(content) == 1 and layout not in ["concept", "comparison"]:
                    print(f"  -> Forcing 'concept' layout on single-bullet slide: '{slide.get('title')}' (was '{layout}').")
                    slide["layout_type"] = "concept"
                    if "concept_data" not in slide or not slide["concept_data"]:
                        slide["concept_data"] = {
                            "core_term": slide.get("title", "Key Concept"),
                            "definition": content[0],
                            "key_takeaways": []
                        }
                    fixed_slides.append(slide)
                else:
                    fixed_slides.append(slide)
                    
            best_module_state["planned_slides"] = fixed_slides

        modules[i] = best_module_state

    course["modules"] = modules

    try:
        fresh_courses = get_all_courses('draft')
    except Exception:
        fresh_courses = []

    fresh_idx = next((i for i, c in enumerate(fresh_courses) if c.get("id") == course_id), None)
    if fresh_idx is not None:
        fresh_courses[fresh_idx] = course
    else:
        fresh_courses.append(course)

    save_all_courses(fresh_courses, "draft")

    print(f"Slide planning complete for course '{course.get('course_name')}'!")
    return course
