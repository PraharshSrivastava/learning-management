#!/usr/bin/env bash
# Run from a separate VM or WSL checkout. Never uses the live Compose project.
set -euo pipefail
pilot_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)"
if [[ "$(basename -- "$pilot_root")" != lms-document-builder-pilot ]]; then
  echo 'Run from a separate checkout named lms-document-builder-pilot.' >&2
  exit 1
fi
cd -- "$pilot_root"
pilot() {
  docker compose --project-directory "$pilot_root" --env-file "$pilot_root/.env.pilot" -p lms-document-pilot \
    -f "$pilot_root/docker/document-builder-pilot.compose.yml" "$@"
}
case "${1:-status}" in
  prepare)
    python3 - "${2:-/home/karphi/intelligence_layer/.env}" <<'PY'
from pathlib import Path
import secrets
import subprocess
import sys
root = Path.cwd()
target = root / '.env.pilot'
if not target.exists():
    source = Path(sys.argv[1]).expanduser().resolve()
    if not source.is_file():
        raise SystemExit('Provider env file not found. Use: prepare /absolute/path/to/.env')
    values = {}
    fallback_llm_key = ''
    for raw in source.read_text().splitlines():
        line = raw.strip()
        if line.startswith('export '):
            line = line[7:]
        if not line or line.startswith('#') or '=' not in line:
            continue
        key, value = line.split('=', 1)
        if key.startswith(('LLM_', 'TTS_', 'COURSE_THUMBNAIL_', 'CAPTION_')):
            values[key] = value
        elif key == 'LITELLM_API_KEY':
            fallback_llm_key = value
    if not values.get('LLM_API_KEY', '').strip('"\' '):
        values['LLM_API_KEY'] = fallback_llm_key
    missing = [key for key in ('LLM_BASE_URL', 'LLM_API_KEY', 'TTS_ENDPOINT', 'COURSE_THUMBNAIL_ENDPOINT')
               if not values.get(key, '').strip('"\' ')]
    if missing:
        raise SystemExit('Required provider settings missing: ' + ', '.join(missing))
    password = secrets.token_hex(24)
    values.update({
        'APP_ENV': 'production', 'LOG_LEVEL': 'INFO',
        'POSTGRES_DB': 'lms_document_pilot', 'POSTGRES_USER': 'lms_document_pilot',
        'POSTGRES_PASSWORD': password,
        'DATABASE_URL': f'postgresql://lms_document_pilot:{password}@postgres:5432/lms_document_pilot',
        'LMS_STORAGE_DIR': '/app/storage',
        'CORS_ALLOWED_ORIGINS': 'http://localhost:16969,http://127.0.0.1:16969',
        'DOCUMENT_BUILDER_WORKFLOW_ENABLED': 'true',
        'DOCUMENT_BUILDER_MODEL': '', 'DOCUMENT_BUILDER_OUTPUT_MODE': 'json_schema',
        'DOCUMENT_BUILDER_MODEL_TIMEOUT_SECONDS': '90',
        'DOCUMENT_BUILDER_OPERATION_DEADLINE_SECONDS': '240',
        'HUB_LAUNCH_DEV_MODE': 'true', 'HUB_LAUNCH_SECRET': secrets.token_hex(32),
        'HUB_TRAINER_COOKIE_NAME': 'lms_document_pilot_trainer',
        'HUB_EMPLOYEE_COOKIE_NAME': 'lms_document_pilot_employee',
        'HUB_COOKIE_SECURE': 'false', 'DIRECTORY_SYNC_ENABLED': 'false',
        'EMAIL_DELIVERY_MODE': 'disabled', 'EMAIL_SCHEDULER_ENABLED': 'false',
        'LANGFUSE_ENABLED': 'false', 'GENERATION_MAX_CONCURRENCY': '1',
    })
    with target.open('x') as file:
        file.write('\n'.join(f'{key}={value}' for key, value in values.items()) + '\n')
    target.chmod(0o600)
else:
    print('Keeping existing .env.pilot and pilot database credentials.')
dockerfile = subprocess.check_output(['git', 'show', 'HEAD:frontend/Dockerfile'], text=True)
if '--branch 3.24.5' not in dockerfile:
    raise SystemExit('Frontend Dockerfile changed; review the pilot SDK patch before building.')
dockerfile = dockerfile.replace('--branch 3.24.5', '--branch 3.44.0')
dockerfile = dockerfile.replace('COPY nginx.conf ', 'COPY nginx.pilot.conf ')
(root / 'frontend/Dockerfile.pilot').write_text(dockerfile)
nginx = (root / 'frontend/nginx.conf').read_text()
if 'alias /srv/lms/videos/;' not in nginx:
    raise SystemExit('Video mount changed; review pilot Nginx mapping before building.')
(root / 'frontend/nginx.pilot.conf').write_text(
    nginx.replace('alias /srv/lms/videos/;', 'alias /srv/lms/storage/generated/videos/;'))
print('Prepared isolated pilot configuration; provider credentials were not printed.')
PY
    pilot config --quiet
    ;;
  start)
    test -f .env.pilot || { echo 'Run prepare first.' >&2; exit 1; }
    pilot up -d --build --wait --wait-timeout 240
    # One synthetic identity in the pilot DB only; local login is loopback-only.
    pilot exec -T backend python - <<'PY'
from app.core.settings import settings
from app.repositories.database import get_connection
assert settings.database_url.endswith('/lms_document_pilot'), 'Refusing non-pilot database'
with get_connection() as connection:
    connection.execute("""INSERT INTO employees
        (employee_id, name, job_title, department, status, source)
        VALUES (?, ?, ?, ?, ?, ?) ON CONFLICT (employee_id) DO NOTHING""",
        ('document_builder_pilot', 'Document Builder Pilot', 'Trainer', 'Pilot', 'active', 'hub'))
    connection.commit()
print('Pilot trainer ready. Select Document Builder Pilot on the local login screen.')
PY
    pilot ps
    ;;
  status) pilot ps ;;
  logs) pilot logs --tail=100 backend ;;
  stop) pilot down ;;
  *) echo 'Usage: document-builder-pilot.sh prepare [provider-env-file]|start|status|logs|stop' >&2; exit 1 ;;
esac
