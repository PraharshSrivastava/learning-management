# Learning Management System

An internal LMS for turning uploaded training PDFs into structured courses with
trainer authoring tools, employee learning views, quizzes, generated slide decks,
narration audio, and module videos.

## Project Structure

```text
backend/             FastAPI API, generation pipeline, PostgreSQL-backed storage
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
```

Important backend paths:

```text
backend/app/api/          HTTP routes
backend/app/services/     business workflows
backend/app/repositories/ PostgreSQL persistence layer
backend/app/generation/   course generation stages
backend/app/templates/    slide HTML/CSS templates
backend/app/static/       public brand assets
backend/scripts/          generation subprocess entrypoint
backend/storage/          uploads and generated media
```

The generation job manager currently launches one course pipeline through:

```powershell
.\.venv\Scripts\python.exe -m scripts.run_pipeline --course-id <course_id>
```

Do not remove `backend/scripts/run_pipeline.py` while the current job manager is
still in use.

## Docker Deployment

The root Compose stack is the deployment shape for the current app:

```text
postgres           PostgreSQL database
backend            FastAPI API and generation pipeline
frontend           trainer/admin Flutter web app
employee_frontend  employee Flutter web app
```

Create host persistence directories on the VM:

```bash
sudo mkdir -p /opt/lms/postgres /opt/lms/storage /opt/lms/backups
```

Create the deployment env file:

```bash
cp .env.example .env
nano .env
```

Set real secrets and VM/domain origins in `.env`, especially:

```text
POSTGRES_PASSWORD
CORS_ALLOWED_ORIGINS
LLM_BASE_URL
LLM_API_KEY
TTS_ENDPOINT
COURSE_THUMBNAIL_ENDPOINT
```

Start or update the deployment:

```bash
docker compose up -d --build
```

Default deployed ports match the existing VM branch:

```text
Backend health:   http://<vm-host>:3060/health
Trainer app:      http://<vm-host>:6969
Employee app:     http://<vm-host>:6970
```

Port map:

```text
3060 -> backend container port 8000
6969 -> trainer frontend container port 80
6970 -> employee frontend container port 80
127.0.0.1:5432 -> postgres container port 5432
```

PostgreSQL is bound to `127.0.0.1` on the VM host, not to the public network
interface. This keeps the database reachable for host-local maintenance while
preventing direct external access to the database port. Backend-to-database
traffic inside Docker uses the private service name `postgres:5432`.

Compose persists data in explicit host folders:

```text
/opt/lms/postgres    PostgreSQL rows
/opt/lms/storage     uploads and generated audio/images/slides/videos
/opt/lms/backups     backup output location
```

Rebuilding containers does not erase those host folders. Do not delete them
unless you intentionally want to reset production data.

Check status and logs:

```bash
docker compose ps
docker compose logs -f backend
```

Back up PostgreSQL and storage on the VM:

```bash
stamp=$(date +%Y%m%d_%H%M%S)
docker compose exec -T postgres pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB" > "/opt/lms/backups/lms_${stamp}.sql"
tar -czf "/opt/lms/backups/storage_${stamp}.tar.gz" -C /opt/lms storage
```

Stop services without deleting data:

```bash
docker compose stop
```

Do not remove `/opt/lms/postgres` or `/opt/lms/storage` unless you intentionally
want to erase production data.

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

That `8000` port is for direct terminal development only, for example when the
backend is started with `uvicorn app.main:app --reload --port 8000`. Docker/VM
deployment exposes the backend on host port `3060`.

For the Docker deployment, frontend builds use same-origin `/api` and `/assets`
through nginx, so no VM-specific backend URL is baked into the Flutter build.

## Environment

For Docker deployment, copy the root `.env.example` to `.env` and set real
values. The root template is the only committed env template. Direct terminal
runs may still use private local env files such as `backend/.env`,
`frontend/.env`, and `employee_frontend/.env`.

Key settings:

```text
APP_ENV
LOG_LEVEL
CORS_ALLOWED_ORIGINS
DATABASE_URL
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

Generated uploads, audio, images, slides, and videos live under `/app/storage`
inside the backend container and `/opt/lms/storage` on the VM host. Structured
application data lives in PostgreSQL. SQLite is no longer supported.

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

Remaining hardening items after the VM Docker rollout:

1. Add versioned database migrations.
2. Run API and generation worker as separate services.
3. Make the global generation queue durable across multi-process deployments.
4. Store secrets in deployment secret management.
5. Serve HTTPS through a reverse proxy.
6. Lock CORS to real frontend URLs.
7. Add API, database, provider, and worker health checks.
8. Add upload size/type limits and API rate limits.
9. Add structured logs, alerts, backups, and queue/stage monitoring.

## Replacing `feat/docker`

The `feat/docker` branch is the old deployed Docker shape. It persists SQLite and
old asset folders. Replace it from the current code after testing this Compose
deployment; do not merge the old branch into the current app.

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
