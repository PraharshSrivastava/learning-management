import json
import os
import subprocess
import time
import urllib.request
from pathlib import Path

from playwright.sync_api import expect, sync_playwright


ROOT_DIR = Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT_DIR / "backend"
EMPLOYEE_FRONTEND_DIR = ROOT_DIR / "employee_frontend"
PYTHON = BACKEND_DIR / ".venv" / "Scripts" / "python.exe"
FLUTTER = Path(r"C:\Users\LPUSER\flutter\bin\flutter.bat")
BACKEND_PORT = 8000
FRONTEND_PORT = 8121


PUBLISHED_COURSE = {
    "id": "e2e-course-1",
    "course_id": "e2e-course-1",
    "title": "E2E Employee Course",
    "course_description": "Course seeded for employee browser smoke testing.",
    "modules": [
        {
            "module_number": 1,
            "title": "Module 1",
            "video_url": "/assets/videos/e2e.mp4",
            "quiz": [
                {
                    "question": "What is this test?",
                    "options": ["Smoke", "Load", "Unit", "Manual"],
                    "correct": "A",
                    "explanation": "It checks the browser flow.",
                }
            ],
            "pass_mark": 0.67,
        }
    ],
    "images": [],
}


def _wait_for_url(url, timeout=90):
    deadline = time.time() + timeout
    last_error = None
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=2) as response:
                if response.status < 500:
                    return
        except Exception as exc:
            last_error = exc
        time.sleep(1)
    raise RuntimeError(f"Timed out waiting for {url}: {last_error}")


def _terminate(process):
    if process and process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=10)


def _seed_database(database_url):
    env = os.environ.copy()
    env["DATABASE_URL"] = database_url
    seed_code = (
        "import json;"
        "from app.repositories.schema import init_db;"
        "from app.repositories.courses import save_all_courses;"
        "init_db();"
        f"save_all_courses([json.loads({json.dumps(json.dumps(PUBLISHED_COURSE))})], 'published')"
    )
    subprocess.run(
        [str(PYTHON), "-c", seed_code],
        cwd=BACKEND_DIR,
        env=env,
        check=True,
    )


def main():
    if not PYTHON.exists():
        raise RuntimeError(f"Backend Python not found at {PYTHON}")
    if not FLUTTER.exists():
        raise RuntimeError(f"Flutter not found at {FLUTTER}")
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL is required for the employee E2E smoke test.")

    backend_process = None
    frontend_process = None
    _seed_database(database_url)

    env = os.environ.copy()
    env["DATABASE_URL"] = database_url
    env["DART_DISABLE_ANALYTICS"] = "true"

    backend_process = subprocess.Popen(
        [
            str(PYTHON),
            "-m",
            "uvicorn",
            "app.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(BACKEND_PORT),
        ],
        cwd=BACKEND_DIR,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )

    try:
        _wait_for_url(f"http://127.0.0.1:{BACKEND_PORT}/health", timeout=45)

        subprocess.run(
            [str(FLUTTER), "build", "web", "--no-pub"],
            cwd=EMPLOYEE_FRONTEND_DIR,
            env=env,
            check=True,
        )

        frontend_process = subprocess.Popen(
            [
                str(PYTHON),
                "-m",
                "http.server",
                str(FRONTEND_PORT),
                "--bind",
                "127.0.0.1",
            ],
            cwd=EMPLOYEE_FRONTEND_DIR / "build" / "web",
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )

        _wait_for_url(f"http://127.0.0.1:{FRONTEND_PORT}", timeout=120)

        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            page = browser.new_page(viewport={"width": 1440, "height": 950})
            page.on("console", lambda message: print(f"[browser:{message.type}] {message.text}"))
            page.on("requestfailed", lambda request: print(
                f"[requestfailed] {request.url}: {request.failure}"
            ))
            with page.expect_response(
                lambda response: response.url.endswith("/api/employees")
                and response.status == 200,
                timeout=90000,
            ):
                page.goto(f"http://127.0.0.1:{FRONTEND_PORT}")

            expect(page).to_have_title("PhillipCapital Employee LMS", timeout=90000)

            with page.expect_response(
                lambda response: response.url.endswith("/api/auth/local/employee-login")
                and response.status == 200,
                timeout=90000,
            ), page.expect_response(
                lambda response: response.url.endswith("/api/me/courses")
                and response.status == 200,
                timeout=90000,
            ) as courses_info:
                page.mouse.click(220, 335)

            courses_response = courses_info.value
            courses = courses_response.json()
            assert any(
                course.get("course_id") == PUBLISHED_COURSE["course_id"]
                for course in courses
            ), courses
            browser.close()

        print("Employee frontend E2E smoke test passed.")
    finally:
        _terminate(frontend_process)
        _terminate(backend_process)


if __name__ == "__main__":
    main()
