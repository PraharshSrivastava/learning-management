import os
import sys
from pydantic import BaseModel, Field
from typing import List, Optional

# Ensure backend imports work
BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from local_db import get_all_courses, save_all_courses
from pipelines.config import safe_chat_completion, get_llm_endpoint

# --- Schema Definitions for Layouts ---

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
    slides: List[ArtDirectorSlidePlan] = Field(description="The enhanced slides with assigned layouts and structured data, in the exact same order as the input slides.")

def run_step6_art_director(course_id: str):
    print(f"[STEP 6] Running Art Director (Layout Selection) for {course_id}")
    
    courses = get_all_courses()
    course_idx = next((i for i, c in enumerate(courses) if c.get("id") == course_id), None)
    
    if course_idx is None:
        raise ValueError(f"Course '{course_id}' not found.")

    course = courses[course_idx]
    modules = course.get("modules", [])
    
    base_url, model_name = get_llm_endpoint("slides")
    json_schema = ArtDirectorResponse.model_json_schema()

    for module in modules:
        planned_slides = module.get("planned_slides", [])
        if not planned_slides:
            continue

        print(f"\n    -> Calling Art Director LLM for Module {module.get('module_number', '1')}...")
        
        # Construct the input prompt from the planned slides
        slides_text = ""
        for idx, slide in enumerate(planned_slides):
            slides_text += f"Slide {idx + 1}:\n"
            slides_text += f"Title: {slide.get('title')}\n"
            slides_text += "Bullets:\n"
            for b in slide.get("content", []):
                slides_text += f" - {b}\n"
            slides_text += "\n"
        
        prompt = f"""
You are an expert Presentation Art Director.
You have been given a series of slides containing titles and bullet points.
Your job is to transform these generic bullets into visually engaging layouts by assigning each slide a `layout_type` and structuring the content to fit that layout.

### AVAILABLE LAYOUTS:
1. **concept**: Best for defining a core term or explaining a central idea. Requires a `core_term`, `definition`, and `key_takeaways`.
2. **steps**: Best for sequential processes, timelines, or ordered phases. Requires a list of `steps` (title + description).
3. **comparison**: Best for pros/cons, before/after, or contrasting two distinct concepts. Requires left/right headers and points.
4. **grid**: Best for independent pillars, features, or 2-4 items of equal weight that aren't necessarily a sequence. Requires a list of `columns` (header + content).
5. **bullets**: The standard fallback layout. Use this if the content doesn't fit the other specific layouts. Just requires a list of `bullets`.

### INPUT SLIDES:
{slides_text}

### INSTRUCTIONS:
- Analyze the semantic meaning of each slide's bullets.
- Choose the SINGLE best `layout_type` for each slide.
- Extract, rephrase, or restructure the text from the input bullets to perfectly fit the chosen layout's schema.
- NEVER lose information. Ensure all the core facts from the input bullets are represented in the chosen layout.
- You must output the slides in the exact same order as the input.

Return a JSON object matching the `ArtDirectorResponse` schema.
"""
        try:
            print("\n=== EXACT TEXT BEING SENT TO ART DIRECTOR LLM ===")
            print(prompt)
            print("=================================================\n")
            
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
            
            # Merge the layout data back into the planned_slides
            for i, enhanced_slide in enumerate(parsed.slides):
                if i < len(planned_slides):
                    # Keep the original title and images, but add the layout data
                    planned_slides[i]["layout_type"] = enhanced_slide.layout_type
                    
                    # Fix keys for slides_generator.py compatibility
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
                        # Replace content with potentially refined bullets from the LLM
                        planned_slides[i]["bullets_data"] = enhanced_slide.bullets
                        planned_slides[i]["content"] = enhanced_slide.bullets
                        planned_slides[i]["bullets"] = enhanced_slide.bullets

            module["planned_slides"] = planned_slides
            module["slides"] = planned_slides # Required by generate_html_slides_for_module
            
        except Exception as e:
            print(f"Error in Art Director step for module {module.get('module_number')}: {e}")

    course["modules"] = modules
    courses[course_idx] = course
    save_all_courses(courses)

    return course

if __name__ == "__main__":
    if len(sys.argv) > 1:
        run_step6_art_director(sys.argv[1])
    else:
        print("Provide course_id")
