import os
import sys

# Ensure backend imports work
BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from pipelines.run_pipeline import generate_course_outline

def run_step1_extract_blueprint(filename: str):
    print(f"[STEP 1] Generating blueprint for {filename}")
    outline = generate_course_outline(filename)
    return outline
