from core.database import get_all_courses, save_all_courses
import os
import json
from pydantic import BaseModel
from typing import List, Dict, Any

from pipelines.config import get_llm_endpoint, DRAFT_COURSES_FILE, safe_chat_completion
from pipelines.prompts import QUIZ_GENERATION_PROMPT
from core.io_utils import atomic_write_json

QUIZ_GENERATION_RETRIES = 3


# -------------------------------------------------------
# Pydantic Schemas for Quiz Structure
# -------------------------------------------------------
class MCQOption(BaseModel):
    key: str  # "A", "B", "C", or "D"
    text: str


class MCQQuestion(BaseModel):
    question_text: str
    options: List[MCQOption]
    correct_option: str  # "A", "B", "C", or "D"
    explanation: str


class ModuleQuiz(BaseModel):
    questions: List[MCQQuestion]


# -------------------------------------------------------
# Core Generation function
# -------------------------------------------------------
def generate_quiz_for_course(course_id: str) -> Dict[str, Any]:
    """
    Generates quizzes for each module in a course if `num_questions` is > 0.
    Updates the course database in courses.json and returns the updated course dictionary.
    """
    print(f"Generating quizzes for course {course_id}...")

    courses = get_all_courses('draft')

    course_idx = next((i for i, c in enumerate(courses) if c.get("id") == course_id), None)
    if course_idx is None:
        raise ValueError(f"Course '{course_id}' not found.")

    course = courses[course_idx]
    modules = course.get("modules", [])
    difficulty = course.get("course_difficulty", "Easy").strip()

    if not modules:
        raise ValueError("This course has no modules. Save a blueprint first.")

    base_url, model_name = get_llm_endpoint("quiz")
    json_schema = ModuleQuiz.model_json_schema()

    for i, module in enumerate(modules):
        try:
            num_q = int(module.get("num_questions", 0))
        except (ValueError, TypeError):
            num_q = 0

        module_title = module.get("title", f"Module {i + 1}")
        module_text = module.get("text", "")

        if num_q <= 0:
            print(f"  Module '{module_title}' has num_questions={num_q}. Skipping quiz generation.")
            # Clear any legacy quiz if count was set to 0
            module.pop("quiz", None)
            continue

        if not module_text.strip():
            print(f"  [WARNING] Module '{module_title}' has no text content. Skipping.")
            module.pop("quiz", None)
            continue

        print(f"  Generating quiz for Module '{module_title}' ({num_q} questions, difficulty={difficulty})...")

        user_message = (
            f"Generate a quiz with exactly {num_q} multiple choice questions.\n\n"
            f"Difficulty Level: {difficulty}\n"
            f"Module Title: \"{module_title}\"\n\n"
            f"MODULE CONTENT:\n"
            f"{module_text}\n"
        )

        last_error = None
        for attempt in range(QUIZ_GENERATION_RETRIES + 1):
            try:
                if attempt > 0:
                    print(
                        f"    [RETRY] Retrying quiz generation for module "
                        f"'{module_title}' ({attempt}/{QUIZ_GENERATION_RETRIES})..."
                    )

                response = safe_chat_completion(
                    base_url=base_url,
                    model=model_name,
                    messages=[
                        {"role": "system", "content": QUIZ_GENERATION_PROMPT},
                        {"role": "user", "content": user_message},
                    ],
                    response_format={
                        "type": "json_schema",
                        "json_schema": {
                            "name": "ModuleQuiz",
                            "schema": json_schema,
                        },
                    },
                    temperature=0.2,
                    default_max_tokens=4096,
                )

                raw_content = response.choices[0].message.content
                parsed = ModuleQuiz.model_validate_json(raw_content)

                module["quiz"] = parsed.model_dump()
                module.pop("quiz_generation_error", None)
                print(f"    Successfully generated {len(parsed.questions)} questions.")
                break

            except Exception as e:
                last_error = e
                print(
                    f"    [ERROR] Quiz generation attempt "
                    f"{attempt + 1}/{QUIZ_GENERATION_RETRIES + 1} failed for "
                    f"module '{module_title}': {e}"
                )
        else:
            print(
                f"    [ERROR] Failed to generate quiz for module '{module_title}' "
                f"after {QUIZ_GENERATION_RETRIES + 1} attempts."
            )
            module["quiz"] = {"questions": []}
            module["quiz_generation_error"] = str(last_error) if last_error else "Unknown quiz generation error"

    course["modules"] = modules
    courses[course_idx] = course

    save_all_courses(courses, "draft")

    print(f"Quiz generation complete for course '{course.get('course_name')}'!")
    return course
