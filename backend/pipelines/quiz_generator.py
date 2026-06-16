import os
import json
from pydantic import BaseModel
from typing import List, Dict, Any

from pipelines.config import get_llm_client, COURSES_FILE
from pipelines.prompts import QUIZ_GENERATION_PROMPT


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

    if not os.path.exists(COURSES_FILE):
        raise FileNotFoundError("Courses database not found.")

    with open(COURSES_FILE, 'r', encoding='utf-8') as f:
        courses = json.load(f)

    course_idx = next((i for i, c in enumerate(courses) if c.get("id") == course_id), None)
    if course_idx is None:
        raise ValueError(f"Course '{course_id}' not found.")

    course = courses[course_idx]
    modules = course.get("modules", [])
    difficulty = course.get("course_difficulty", "Easy").strip()

    if not modules:
        raise ValueError("This course has no modules. Save a blueprint first.")

    client, model_name = get_llm_client()
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

        try:
            response = client.chat.completions.create(
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
                max_tokens=4096,
            )

            raw_content = response.choices[0].message.content
            parsed = ModuleQuiz.model_validate_json(raw_content)
            
            # Save the quiz structure directly under module['quiz']
            module["quiz"] = parsed.model_dump()
            print(f"    Successfully generated {len(parsed.questions)} questions.")

        except Exception as e:
            print(f"    [ERROR] Failed to generate quiz for module '{module_title}': {e}")
            # Do not crash the entire course quiz generation on a single module failure
            if "quiz" not in module:
                module["quiz"] = {"questions": []}

    course["modules"] = modules
    courses[course_idx] = course

    with open(COURSES_FILE, 'w', encoding='utf-8') as f:
        json.dump(courses, f, indent=2, ensure_ascii=False)

    print(f"Quiz generation complete for course '{course.get('course_name')}'!")
    return course
