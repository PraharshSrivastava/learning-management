import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
DRAFT_COURSES_FILE = os.path.join(BASE_DIR, "courses_draft.json")
PUBLISHED_COURSES_FILE = os.path.join(BASE_DIR, "courses.json")
IMAGE_DIR = os.path.join(BASE_DIR, "assets", "images")

os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(IMAGE_DIR, exist_ok=True)
