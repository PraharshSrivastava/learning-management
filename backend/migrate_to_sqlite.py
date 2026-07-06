import os
import json
from core.database import save_all_courses, save_progress
from core.config import DRAFT_COURSES_FILE, PUBLISHED_COURSES_FILE, EMPLOYEE_PROGRESS_FILE

def migrate():
    print("Starting migration to SQLite...")
    
    # 1. Migrate Draft Courses
    if os.path.exists(DRAFT_COURSES_FILE):
        try:
            with open(DRAFT_COURSES_FILE, 'r', encoding='utf-8') as f:
                drafts = json.load(f)
                if drafts:
                    save_all_courses(drafts, "draft")
                    print(f"Migrated {len(drafts)} draft courses.")
        except Exception as e:
            print(f"Failed to migrate drafts: {e}")
            
    # 2. Migrate Published Courses
    if os.path.exists(PUBLISHED_COURSES_FILE):
        try:
            with open(PUBLISHED_COURSES_FILE, 'r', encoding='utf-8') as f:
                published = json.load(f)
                if published:
                    save_all_courses(published, "published")
                    print(f"Migrated {len(published)} published courses.")
        except Exception as e:
            print(f"Failed to migrate published: {e}")

    # 3. Migrate Employee Progress
    if os.path.exists(EMPLOYEE_PROGRESS_FILE):
        try:
            with open(EMPLOYEE_PROGRESS_FILE, 'r', encoding='utf-8') as f:
                progress = json.load(f)
                count = 0
                for course_id, data in progress.items():
                    save_progress(course_id, data)
                    count += 1
                if count > 0:
                    print(f"Migrated progress for {count} courses.")
        except Exception as e:
            print(f"Failed to migrate progress: {e}")

    print("Migration complete!")

if __name__ == "__main__":
    migrate()
