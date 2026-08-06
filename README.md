# Learning Management System

An internal LMS for turning uploaded training PDFs into structured courses with
trainer authoring tools, employee learning views, quizzes, generated slide decks,
narration audio, and module videos.

## Project Structure

```text
backend/             FastAPI API, generation pipeline, SQLite storage
frontend/            Flutter trainer/admin web app
employee_frontend/   Flutter employee learning web app
```

The backend owns course generation and persistence. The trainer frontend uploads
documents, manages courses, assigns training, and reviews performance. The
employee frontend lets learners view assigned courses, watch module videos, and
complete quiz/progress flows.

## Backend

Runtime entrypoint:

```powershell
cd backend
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

Install dependencies from a clean environment:

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m playwright install chromium
Copy-Item .env.example .env
```

Important backend paths:

```text
backend/app/api/          HTTP routes
backend/app/services/     business workflows
backend/app/repositories/ SQLite persistence layer
backend/app/generation/   course generation stages
backend/app/templates/    slide HTML/CSS templates
backend/app/static/       public brand assets
backend/scripts/          generation subprocess entrypoint
backend/storage/          local DB, uploads, and generated media
```

The generation job manager currently launches one course pipeline through:

```powershell
.\.venv\Scripts\python.exe -m scripts.run_pipeline --course-id <course_id>
```

Do not remove `backend/scripts/run_pipeline.py` while the current job manager is
still in use.

## Frontends

Trainer app:

```powershell
cd frontend
flutter pub get
flutter run -d chrome
```

Employee app:

```powershell
cd employee_frontend
flutter pub get
flutter run -d chrome
```

Both Flutter apps read `API_BASE_URL` through `flutter_dotenv`. In local
development they fall back to:

```text
http://localhost:8000
```

For deployment, build each frontend with the real backend URL configured.

## Environment

Copy `backend/.env.example` to `backend/.env` and set real values for the
provider endpoints and keys.

Key settings:

```text
APP_ENV
LOG_LEVEL
CORS_ALLOWED_ORIGINS
LLM_BASE_URL
LLM_API_KEY
LLM_MODEL_NAME
TTS_ENDPOINT
TTS_VOICE
COURSE_THUMBNAIL_ENDPOINT
COURSE_THUMBNAIL_API_KEY
GENERATION_MAX_CONCURRENCY
LMS_STORAGE_DIR
```

Generated uploads, audio, images, slides, videos, and the SQLite database live
under `backend/storage` by default.

## Generation Pipeline

Course generation is checkpointed and resumable. The main stages are:

1. Create course blueprint from the uploaded PDF.
2. Generate thumbnail, notes, quizzes, and slides.
3. Compile slide HTML.
4. Generate narration scripts.
5. Synthesize slide audio with TTS.
6. Render module videos with Playwright screenshots and FFmpeg.
7. Publish/sync completed course state.

Within a course, several stages use controlled parallelism:

```text
Wave 1: thumbnail, quiz, notes, and slide generation can run in parallel
TTS: up to 3 slides at a time
Video: capped module-level parallelism
```

The video stage captures generated HTML slides as PNG frames, combines each frame
with its narration WAV file, and concatenates slide clips into final MP4 module
videos.

## Static Assets

Only selected generated/public asset folders are mounted by the backend:

```text
/assets/audio
/assets/brand
/assets/images
/assets/layouts
/assets/slides
/assets/videos
```

Uploaded PDFs, prompts, templates, private storage files, and non-mounted
directories are not exposed as static assets.

## Current Production Notes

The project is still in local/VM-preparation shape. Before production rollout,
the key planned upgrades are:

1. Move persistence from SQLite to PostgreSQL.
2. Add versioned database migrations.
3. Run API and generation worker as separate services.
4. Use one durable global generation queue.
5. Store secrets in deployment secret management.
6. Serve HTTPS through a reverse proxy.
7. Lock CORS to real frontend URLs.
8. Add API, database, provider, and worker health checks.
9. Add upload size/type limits and API rate limits.
10. Add structured logs, alerts, backups, and queue/stage monitoring.

## Verification

Basic backend checks:

```powershell
cd backend
.\.venv\Scripts\python.exe -m scripts.run_pipeline --help
.\.venv\Scripts\python.exe -m ruff check app scripts
```

Frontend checks:

```powershell
cd frontend
flutter analyze

cd ..\employee_frontend
flutter analyze
```
