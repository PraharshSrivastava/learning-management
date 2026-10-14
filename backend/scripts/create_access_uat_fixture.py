"""Create only a new isolated local-demo schema for four-role browser verification."""

import argparse
import subprocess
from uuid import NAMESPACE_URL, uuid4, uuid5

from psycopg.types.json import Jsonb

from app.core.settings import settings
from app.generation.thumbnails import course_thumbnail_signature
from app.repositories import database, schema
from app.repositories.access_migrations import apply_access_migrations
from app.repositories.lms_access import identity_key


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--with-media', action='store_true', help='Generate a synthetic two-second local clip and thumbnail for browser UAT')
    args = parser.parse_args()
    with database.get_connection() as db:
        if db.execute("SELECT current_database() AS name").fetchone()["name"] != "lms_performance_demo":
            raise RuntimeError("UAT fixture refuses any database other than the isolated local demo")
        name = "access_uat_" + uuid4().hex
        db.execute(f'CREATE SCHEMA "{name}"')
        db.execute(f'SET LOCAL search_path TO "{name}"')
        schema._create_tables(db.cursor())
        apply_access_migrations(db)
        people = [("kiran", "Demo Kiran · Admin Trainer", "Finance"),
                  ("karneeshkar", "Demo Karneeshkar · Trainer", "Operations"),
                  ("meera", "Demo Meera · HOD", "HR"),
                  ("neha", "Demo Neha · Observer", "Legal"),
                  ("combined", "Demo Combined · HOD + Observer", "HR"),
                  ("priya", "Demo Priya · Employee", "Finance"),
                  ("arjun", "Demo Arjun · Employee", "Operations"),
                  ("ravi", "Demo Ravi · Employee", "Finance")]
        for number, (person, label, department) in enumerate(people, 990001):
            employee_id = "uat-" + person
            directory_uuid = str(uuid5(NAMESPACE_URL, "lms-access-uat:" + person))
            db.execute("""INSERT INTO employees(employee_id,name,job_title,department,directory_uuid,hub_user_id,email,synced_at)
                VALUES (?, ?, 'Demo employee', ?, ?, ?, ?, localtimestamp::text)""",
                (employee_id, label, department, directory_uuid, number, person + '@example.invalid'))
            if person in ("kiran", "karneeshkar"):
                db.execute("INSERT INTO trainers(trainer_id,name,directory_uuid,email) VALUES (?, ?, ?, ?)",
                    (employee_id, label, directory_uuid, person + '@example.invalid'))
        for course_id, owner, title, status in [("uat-excel", "uat-karneeshkar", "Excel Basics", "published"),
                ("uat-compliance", "uat-kiran", "Compliance Essentials", "published"),
                ("uat-draft", "uat-karneeshkar", "Draft: Communication Skills", "draft")]:
            db.execute("INSERT INTO courses(course_id,trainer_id,course_name,status,course_description,course_objective) VALUES (?, ?, ?, ?, 'Isolated dummy course for access verification', 'Learn and demonstrate the module objectives')", (course_id, owner, title, status))
            db.execute("INSERT INTO course_modules(module_id,course_id,module_number,title,source_text,num_questions) VALUES (?, ?, 1, 'Introduction', 'Dummy source content: Kiran may inspect this text but only the original creator can edit it.', 0)", (course_id + '-m1', course_id))
            if status != 'published':
                continue
            db.execute("INSERT INTO assignment_rules(course_id,published_at,include_filters_json) VALUES (?, localtimestamp::text, ?)", (course_id, Jsonb({"include_all": False, "employee_ids": ["uat-priya", "uat-arjun", "uat-ravi"]})))
            for person in ("priya", "arjun", "ravi"):
                db.execute("INSERT INTO course_assignments(assignment_id,course_id,employee_id,assigned_at,deadline,status) VALUES (?, ?, ?, localtimestamp::text, (localtimestamp+ interval '7 days')::text, 'pending')", (course_id + '-' + person, course_id, "uat-" + person))
        if args.with_media:
            import imageio_ffmpeg
            # Only synthetic color bars, no uploads, source documents or generation providers.
            settings.video_dir.mkdir(parents=True, exist_ok=True)
            settings.image_dir.mkdir(parents=True, exist_ok=True)
            for course_id in ('uat-excel', 'uat-compliance'):
                video = settings.video_dir / (name + '-' + course_id + '.mp4')
                image = settings.image_dir / (name + '-' + course_id + '.png')
                subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), '-y', '-f', 'lavfi', '-i', 'color=c=navy:s=640x360:d=2', '-c:v', 'libx264', '-pix_fmt', 'yuv420p', str(video)], check=True, capture_output=True)
                subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), '-y', '-i', str(video), '-frames:v', '1', str(image)], check=True, capture_output=True)
                course = dict(db.execute('SELECT * FROM courses WHERE course_id = ?', (course_id,)).fetchone())
                db.execute('UPDATE courses SET thumbnail_path = ?, metadata_json = ? WHERE course_id = ?', ('assets/images/' + image.name, Jsonb({'thumbnail_prompt_hash': course_thumbnail_signature(course)}), course_id))
                db.execute('UPDATE course_modules SET video_path = ? WHERE course_id = ?', ('assets/videos/' + video.name, course_id))
        admin = db.execute("SELECT * FROM employees WHERE employee_id='uat-kiran'").fetchone()
        db.execute("INSERT INTO lms_authoring_roles(employee_id,role,identity_key,granted_by) VALUES ('uat-kiran','admin_trainer',?,'isolated-uat-fixture')", (identity_key(admin),))
        db.execute("INSERT INTO lms_access_versions VALUES ('uat-kiran',1)")
        db.execute("INSERT INTO lms_departments VALUES ('uat-finance','fixture-finance','Finance','directory',TRUE), ('uat-operations','fixture-operations','Operations','directory',TRUE)")
        for hod in ("uat-meera", "uat-combined"):
            row = db.execute("SELECT * FROM employees WHERE employee_id=?", (hod,)).fetchone()
            db.execute("INSERT INTO hod_department_access(hod_employee_id,identity_key,department_id,source,source_key) VALUES (?,?,'uat-finance','directory','isolated-fixture-only')", (hod, identity_key(row)))
        for observer in ("uat-neha", "uat-combined"):
            row = db.execute("SELECT * FROM employees WHERE employee_id=?", (observer,)).fetchone()
            db.execute("INSERT INTO course_observer_grants(course_id,observer_employee_id,identity_key,active,granted_by_trainer_id) VALUES ('uat-excel',?,?,TRUE,'uat-karneeshkar')", (observer, identity_key(row)))
            for phase in ('active', 'pending'):
                db.execute("INSERT INTO course_observer_departments VALUES ('uat-excel',?,?, 'uat-operations')", (observer, phase))
        db.commit()
        print(name)


if __name__ == '__main__':
    main()
