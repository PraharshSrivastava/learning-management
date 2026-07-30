"""Generate independently viewable HTML examples of every slide template."""

from pathlib import Path
import shutil

from pipelines.config import BASE_DIR
from pipelines.slides_generator import generate_html_slides_for_module


SAMPLES = {
    "cover": {
        "slide_title": "Building Reliable AI Workflows",
        "layout_type": "cover",
        "is_cover_slide": True,
        "course_name": "AI Workflow Fundamentals",
        "module_number": 1,
        "total_modules": 6,
    },
    "concept-v1": {
        "slide_title": "What is an AI workflow?",
        "layout_type": "concept",
        "template_variant": "v1",
        "concept_data": {
            "core_term": "AI workflow",
            "definition": "A repeatable process that combines a trigger, AI decision, and action to complete work consistently.",
            "key_takeaways": ["Repeatable", "Trigger-led", "Auditable"],
        },
    },
    "concept-v2": {
        "slide_title": "What is an AI workflow?",
        "layout_type": "concept",
        "template_variant": "v2",
        "concept_data": {
            "core_term": "AI workflow",
            "definition": "A repeatable process that combines a trigger, AI decision, and action to complete work consistently.",
            "key_takeaways": ["Repeatable", "Trigger-led", "Auditable"],
        },
    },
    "steps": {
        "slide_title": "A five-step workflow",
        "layout_type": "steps",
        "steps_data": {
            "steps": [
                {"title": "Trigger", "description": "A new request or event starts the workflow."},
                {"title": "Collect", "description": "Gather the relevant context and source data."},
                {"title": "Decide", "description": "Apply the AI instruction or business rule."},
                {"title": "Act", "description": "Send the output to the right system or person."},
                {"title": "Review", "description": "Track results and improve the workflow."},
            ]
        },
    },
    "comparison-v1": {
        "slide_title": "Manual work versus workflow automation",
        "layout_type": "comparison",
        "template_variant": "v1",
        "comparison_data": {
            "left_column_title": "Manual process",
            "left_column_points": ["One-off effort", "Inconsistent hand-offs", "Harder to audit"],
            "right_column_title": "AI workflow",
            "right_column_points": ["Repeatable execution", "Structured hand-offs", "Visible audit trail"],
        },
    },
    "comparison-v2": {
        "slide_title": "Manual work versus workflow automation",
        "layout_type": "comparison",
        "template_variant": "v2",
        "comparison_data": {
            "left_column_title": "Manual process",
            "left_column_points": ["One-off effort", "Inconsistent hand-offs", "Harder to audit"],
            "right_column_title": "AI workflow",
            "right_column_points": ["Repeatable execution", "Structured hand-offs", "Visible audit trail"],
        },
    },
    "grid-2": {
        "slide_title": "Two complementary workflow benefits",
        "layout_type": "grid",
        "grid_data": {"columns": [
            {"header": "Consistency", "points": ["Use the same decision logic every time."]},
            {"header": "Visibility", "points": ["Make each hand-off traceable and reviewable."]},
        ]},
    },
    "grid-3": {
        "slide_title": "Three building blocks",
        "layout_type": "grid",
        "grid_data": {"columns": [
            {"header": "Trigger", "points": ["Starts the workflow when a condition is met."]},
            {"header": "Decision", "points": ["Applies AI and business logic to the context."]},
            {"header": "Action", "points": ["Routes the result to the next system or person."]},
        ]},
    },
    "grid-4": {
        "slide_title": "Four controls for reliable automation",
        "layout_type": "grid",
        "grid_data": {"columns": [
            {"header": "Input", "points": ["Validate source data before processing."]},
            {"header": "Logic", "points": ["Apply clear and approved decision rules."]},
            {"header": "Review", "points": ["Escalate uncertain outcomes to a person."]},
            {"header": "Record", "points": ["Keep an auditable log of each run."]},
        ]},
    },
    "grid-5": {
        "slide_title": "Five workflow checkpoints",
        "layout_type": "grid",
        "grid_data": {"columns": [
            {"header": "Trigger", "points": ["Start only from an approved business event."]},
            {"header": "Context", "points": ["Collect the information required for a decision."]},
            {"header": "Decision", "points": ["Apply the approved AI instruction and rules."]},
            {"header": "Action", "points": ["Send the result to the correct destination."]},
            {"header": "Review", "points": ["Record outcomes and inspect exceptions."]},
        ]},
    },
    "grid-6": {
        "slide_title": "Six controls for reliable automation",
        "layout_type": "grid",
        "grid_data": {"columns": [
            {"header": "Input", "points": ["Validate source data."]},
            {"header": "Access", "points": ["Limit system permissions."]},
            {"header": "Logic", "points": ["Use approved instructions."]},
            {"header": "Review", "points": ["Escalate uncertainty."]},
            {"header": "Record", "points": ["Keep a run history."]},
            {"header": "Improve", "points": ["Measure outcomes over time."]},
        ]},
    },
    "bullets-v1": {
        "slide_title": "Workflow design principles",
        "layout_type": "bullets",
        "template_variant": "v1",
        "bullets": ["Start with a clear business trigger.", "Keep the AI decision bounded and explainable.", "Escalate exceptions to the correct owner."],
    },
    "bullets-v2": {
        "slide_title": "Workflow design principles",
        "layout_type": "bullets",
        "template_variant": "v2",
        "bullets": ["Start with a clear business trigger.", "Keep the AI decision bounded and explainable.", "Escalate exceptions to the correct owner."],
    },
}


def main() -> list[Path]:
    output_dir = Path(BASE_DIR) / "assets" / "slides" / "template_samples"
    output_dir.mkdir(parents=True, exist_ok=True)
    outputs = []
    for index, (name, slide) in enumerate(SAMPLES.items(), start=1):
        rendered = Path(generate_html_slides_for_module(
            "template_samples", index - 1, {"title": "Template samples", "images": [], "slides": [slide]}
        ))
        destination = output_dir / f"{name}.html"
        shutil.move(rendered, destination)
        outputs.append(destination)
    return outputs


if __name__ == "__main__":
    for output in main():
        print(output)
