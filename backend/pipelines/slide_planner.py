from core.database import get_all_courses, save_all_courses
import os
import json
import requests
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from enum import Enum

from pipelines.config import get_llm_endpoint, DRAFT_COURSES_FILE, safe_chat_completion
from pipelines.prompts import SLIDE_PLANNER_PROMPT
from core.io_utils import atomic_write_json


# -------------------------------------------------------
# Pydantic Schemas for Slide Plan
# -------------------------------------------------------
class SlideLayoutType(str, Enum):
    SPOTLIGHT = "spotlight"
    CONCEPT = "concept"
    STEPS = "steps"
    COMPARISON = "comparison"
    GRID = "grid"
    BULLETS = "bullets"

class SpotlightData(BaseModel):
    key_message: str = Field(description="A concise headline-style message that carries the slide's main idea.")
    supporting_points: List[str] = Field(default_factory=list, description="One to three short proof points or details that support the key message.")
    callout: Optional[str] = Field(default=None, description="Optional short implication, warning, or action the learner should remember.")

class ConceptData(BaseModel):
    core_term: str = Field(description="The key term or definition keyword being introduced.")
    definition: str = Field(description="The formal description or conceptual explanation.")
    key_takeaways: List[str] = Field(default_factory=list, description="A list of 0 to N concise key takeaways representing the 'so what?' of the concept.")

class StepItem(BaseModel):
    step_number: int = Field(description="Chronological index starting at 1.")
    title: str = Field(description="Short action phrase (2-4 words) for the step.")
    description: str = Field(description="Brief explanation of what occurs in this step.")

class StepsData(BaseModel):
    steps: List[StepItem] = Field(description="Strictly sequential or chronological steps in a process. DO NOT use this layout if the items are independent principles, general guidelines, or rules where order doesn't matter.")

class ComparisonData(BaseModel):
    left_column_title: str = Field(description="Title of the first item being compared.")
    left_column_points: List[str] = Field(description="Attributes or pros of the left column item.")
    right_column_title: str = Field(description="Title of the second item being compared.")
    right_column_points: List[str] = Field(description="Attributes or pros/cons of the right column item.")

class GridColumn(BaseModel):
    header: str = Field(description="The specific title/name of this individual pillar, category, or principle (e.g. 'Machine Learning' or 'Natural Language Processing'). Do NOT use generic repeated headings across columns like 'Technology', 'Pillar', 'Category', 'Section', or 'AI Type'.")
    content: str = Field(description="The details, facts, or explanation for this specific pillar. Do NOT repeat the pillar's name inside the content.")

class GridData(BaseModel):
    columns: List[GridColumn] = Field(description="A grid of distinct category columns (typically 3 to 4 pillars). Excellent for independent principles, categories, guidelines, or options where order does not matter.")

class SlidePlan(BaseModel):
    slide_title: str = Field(description="Specific, slide-focused child title (3-6 words) detailing the layout contents.")
    layout_type: SlideLayoutType = Field(description="The chosen visual design structure. Use 'spotlight' for a single high-value message, 'steps' only for sequential processes, and 'grid' or 'bullets' for independent guidelines or principles.")
    
    # Structural layout payloads
    spotlight_data: Optional[SpotlightData] = None
    concept_data: Optional[ConceptData] = None
    steps_data: Optional[StepsData] = None
    comparison_data: Optional[ComparisonData] = None
    grid_data: Optional[GridData] = None
    bullets_data: Optional[List[str]] = None

class ModuleSlidesSchema(BaseModel):
    slides: List[SlidePlan] = Field(description="Sequential list of planned slides forming the chapter presentation.")


def _slide_text_parts(slide: Dict[str, Any]) -> List[str]:
    """
    Flattens a slide's layout-specific content into a flat list of text
    fragments, for fuzzy text-overlap matching against lesson bullets and
    image captions. Shared by both the lesson-title matching pass and the
    image-to-slide mapping pass below, so a fix or a new layout type only
    needs to be added in one place instead of two.
    """
    parts = [slide.get("slide_title", "")]
    layout = slide.get("layout_type")
    if layout == "spotlight" and slide.get("spotlight_data"):
        sd = slide["spotlight_data"]
        parts.extend([sd.get("key_message", ""), sd.get("callout", "")])
        parts.extend(sd.get("supporting_points", []))
    elif layout == "concept" and slide.get("concept_data"):
        cd = slide["concept_data"]
        takeaways = cd.get("key_takeaways", [])
        if not takeaways and cd.get("key_takeaway"):
            takeaways = [cd["key_takeaway"]]
        parts.extend([cd.get("core_term", ""), cd.get("definition", "")] + takeaways)
    elif layout == "steps" and slide.get("steps_data"):
        for step in slide["steps_data"].get("steps", []):
            parts.extend([step.get("title", ""), step.get("description", "")])
    elif layout == "comparison" and slide.get("comparison_data"):
        cd = slide["comparison_data"]
        parts.extend([cd.get("left_column_title", ""), cd.get("right_column_title", "")])
        parts.extend(cd.get("left_column_points", []))
        parts.extend(cd.get("right_column_points", []))
    elif layout == "grid" and slide.get("grid_data"):
        for col in slide["grid_data"].get("columns", []):
            parts.extend([col.get("header", ""), col.get("content", "")])
    elif layout == "bullets" and slide.get("bullets_data"):
        parts.extend(slide.get("bullets_data", []))
    elif layout == "bullets" and slide.get("bullets"):
        for b in slide.get("bullets", []):
            parts.append(b if isinstance(b, str) else b.get("text", ""))
    return parts


# -------------------------------------------------------
# Core Generation Functions
# -------------------------------------------------------
def plan_slides_for_module(
    module: Dict[str, Any],
    difficulty: str = "Easy"
) -> Dict[str, Any]:
    """
    Calls the LLM to structure lessons and bullets into visual slides.
    Returns the updated module dict with a 'slides' list added.
    """
    lessons = module.get("lessons", [])
    module_title = module.get("title", "Untitled Module")
    
    if not lessons:
        print(f"  [SLIDE PLANNER] No lessons found for module '{module_title}' — skipping slide planning.")
        module["slides"] = []
        return module

    print(f"  [SLIDE PLANNER] Slicing lessons into slides for '{module_title}' ({len(lessons)} lessons)...")

    # Format lesson content for prompt context
    lessons_context = []
    for idx, lesson in enumerate(lessons):
        bullets_list = []
        for bullet in lesson.get("bullets", []):
            bullets_list.append(bullet.get("text", ""))

        lessons_context.append({
            "lesson_number": lesson.get("lesson_number", idx + 1),
            "lesson_title": lesson.get("lesson_title", ""),
            "bullets": bullets_list
        })

    user_message = (
        f"Generate presentation slides for the following chapter.\n\n"
        f"Chapter Title: \"{module_title}\"\n"
        f"Difficulty: {difficulty}\n\n"
        f"CHAPTER LESSONS & FACTS:\n"
        f"{json.dumps(lessons_context, indent=2)}\n"
    )

    base_url, model_name = get_llm_endpoint("slides")
    json_schema = ModuleSlidesSchema.model_json_schema()

    try:
        response = safe_chat_completion(
            base_url=base_url,
            model=model_name,
            messages=[
                {"role": "system", "content": SLIDE_PLANNER_PROMPT},
                {"role": "user", "content": user_message}
            ],
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "ModuleSlidesSchema",
                    "schema": json_schema
                }
            },
            temperature=0.15,
            default_max_tokens=4096
        )

        raw_content = response.choices[0].message.content
        parsed = ModuleSlidesSchema.model_validate_json(raw_content)
        
        # Merge slide objects
        slide_plans = parsed.model_dump()["slides"]
        
        # Map parent topics dynamically using fuzzy bullet text overlap
        for slide in slide_plans:
            slide["image_ids"] = [] # Reset LLM mapped images so we rely on stage 2 mapping
            assigned_eyebrow = f"Module: {module_title}"
            
            # Gather slide visual text content to compare against lesson bullets
            combined_slide_text = " ".join(_slide_text_parts(slide)).lower()
            best_overlap = -1
            matched_lesson_title = None
            
            for l_ctx in lessons_context:
                bullet_words = " ".join(l_ctx["bullets"]).lower()
                overlap = sum(1 for word in combined_slide_text.split() if len(word) > 3 and word in bullet_words)
                
                if overlap > best_overlap:
                    best_overlap = overlap
                    matched_lesson_title = l_ctx["lesson_title"]
            
            if matched_lesson_title:
                assigned_eyebrow = matched_lesson_title
            
            slide["parent_lesson_topic"] = assigned_eyebrow

        # Auto-assign images from lessons to the slides based on text overlap with bullet points
        for lesson in lessons:
            lesson_title = lesson.get("lesson_title")
            lesson_images = lesson.get("images", [])
            if not lesson_images:
                continue
                
            # Filter slides belonging to this lesson
            lesson_slides = [s for s in slide_plans if s.get("parent_lesson_topic") == lesson_title]
            if not lesson_slides:
                continue
                
            for img in lesson_images:
                img_id = img.get("image_id")
                mapped_bullet_text = img.get("mapped_bullet_text", "").lower()
                caption = img.get("caption", "").lower()
                
                best_slide = None
                best_score = -1
                
                for slide in lesson_slides:
                    # Gather slide text content to compare against bullet text and caption
                    combined_text = " ".join(_slide_text_parts(slide)).lower()
                    
                    score = 0
                    if mapped_bullet_text:
                        for word in mapped_bullet_text.split():
                            if len(word) > 3 and word in combined_text:
                                score += 1
                    if caption:
                        for word in caption.split():
                            if len(word) > 3 and word in combined_text:
                                score += 1
                                
                    if score > best_score:
                        best_score = score
                        best_slide = slide
                        
                if best_slide and best_score > 0:
                    if "image_ids" not in best_slide:
                        best_slide["image_ids"] = []
                    if img_id not in best_slide["image_ids"]:
                        best_slide["image_ids"].append(img_id)
                    print(f"    [AUTO IMAGE MAP] Assigned {img_id} to slide '{best_slide.get('slide_title')}' (score={best_score})")
                else:
                    # Fallback to the first slide of the lesson
                    fallback_slide = lesson_slides[0]
                    if "image_ids" not in fallback_slide:
                        fallback_slide["image_ids"] = []
                    if img_id not in fallback_slide["image_ids"]:
                        fallback_slide["image_ids"].append(img_id)
                    print(f"    [AUTO IMAGE MAP][FALLBACK] Assigned {img_id} to slide '{fallback_slide.get('slide_title')}'")

        module["slides"] = slide_plans
        print(f"    Successfully generated {len(slide_plans)} slides for module.")
        return module

    except Exception as e:
        print(f"    [ERROR] Failed to plan slides for module '{module_title}': {e}")
        # Fallback to 1-to-1 slides if planner crashes
        fallback_slides = []
        for idx, lesson in enumerate(lessons):
            bullets = [b.get("text", "") for b in lesson.get("bullets", [])]
            fallback_slides.append({
                "slide_title": lesson.get("lesson_title", "Summary"),
                "layout_type": "bullets",
                "image_ids": [img.get("image_id") for img in lesson.get("images", [])],
                "parent_lesson_topic": lesson.get("lesson_title", ""),
                "bullets_data": bullets
            })
        module["slides"] = fallback_slides
        return module


def generate_slides_for_course(course_id: str) -> Dict[str, Any]:
    """
    Loads courses.json, segments modules into slide decks, saves database, and returns course dict.
    """
    print(f"Generating slides database models for course {course_id}...")

    courses = get_all_courses('draft')

    course_idx = next((i for i, c in enumerate(courses) if c.get("id") == course_id), None)
    if course_idx is None:
        raise ValueError(f"Course '{course_id}' not found.")

    course = courses[course_idx]
    modules = course.get("modules", [])
    difficulty = course.get("course_difficulty", "Easy").strip()

    for i, module in enumerate(modules):
        # Plan slide layouts
        updated_module = plan_slides_for_module(module, difficulty)
        modules[i] = updated_module

    course["modules"] = modules

    # Load fresh courses list from disk to prevent race conditions during long LLM calls
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

    # Compile static HTML slide files
    try:
        from pipelines.slides_generator import compile_slides_for_course
        compile_slides_for_course(course_id)
    except Exception as slide_err:
        print(f"  [WARNING] Slides HTML compilation failed in slide planning: {slide_err}")

    print(f"Slide planning complete for course '{course.get('course_name')}'!")
    return course
