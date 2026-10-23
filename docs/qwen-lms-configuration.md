# Qwen in LMS

Use the following values in the root deployment `.env` (or the backend process
environment). Keep the API key in the existing `LLM_API_KEY` setting.

```dotenv
LLM_BASE_URL=http://35.238.33.238:4000/v1
LLM_MODEL_NAME=qwen3.6-35b
LLM_ENABLE_THINKING=false
```

Rebuild and recreate the backend to install the client change and load the values:

```sh
docker compose up -d --build --no-deps --force-recreate backend
```

For direct backend execution, restart the backend with those environment values.
The backend also reads `backend/.env`; the root `.env` is used by Docker Compose.

The client sends `chat_template_kwargs: {"enable_thinking": false}` on LMS chat
requests, including document workflow requests. No shared proxy or model-server
default is changed, so News Filtering can retain its reasoning settings.
Leave `LLM_ENABLE_THINKING` empty to preserve the provider default, or set `true`
to explicitly enable thinking. The deployed provider must support this option;
it was accepted by the supplied Qwen endpoint during compatibility checks.

If `DOCUMENT_BUILDER_MODEL` is explicitly set, review it as well: the workflow
uses that model instead of `LLM_MODEL_NAME`, with the same LMS thinking setting.
Validate a complete synthetic course after deployment before using real courses.

## Default and rollback (2026-10-23)

`qwen3.6-35b` with `LLM_ENABLE_THINKING=false` is now the default in
`settings.py`, `docker-compose.yml` and `.env.example`. Thinking must stay
disabled: with thinking on, short `max_tokens` budgets (for example narration)
can end with `finish_reason=length` and null content. To roll back, set
`LLM_MODEL_NAME=gemma-4-e4b` and leave `LLM_ENABLE_THINKING` empty, then recreate
the backend.
