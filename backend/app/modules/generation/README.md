# Generation module

PDF -> course pipeline: blueprint, slides, narration, captions, video.

## Files

| File | What it does |
| --- | --- |
| `api.py` | Generation-stage and background-job endpoints. |
| `generation_queue.py` | Process-local FIFO queue for generation work. |
| `jobs.py` | Bounded job manager with durable state and optional subprocess execution. |
| `jobs_repository.py` | Persistence for generation worker lifecycle state. |
| `pipeline/` | Course-generation stages and orchestration entry points. |
| `pipeline/blueprint.py` | Extract course blueprints, metadata, modules, and source images from uploaded PDFs. |
| `pipeline/captions.py` | Captions for locally rendered module videos, timed one of two ways (``CAPTION_TIMING``). |
| `pipeline/html.py` | Render course slide layouts and compile learner-facing HTML decks. |
| `pipeline/notes.py` | Generate and persist concise learner-facing module notes. |
| `pipeline/parallel.py` | Small helpers for bounded parallel generation stages. |
| `pipeline/prompts.py` | Prompt templates loaded from Markdown files. |
| `pipeline/quiz.py` | Generate and validate module quizzes. |
| `pipeline/runtime.py` | Coordinate generation state, retries, recovery, orchestration, and publishing. |
| `pipeline/scripts.py` | Generate and persist slide narration scripts. |
| `pipeline/slides.py` | Plan, lay out, validate, and persist course slides. |
| `pipeline/thumbnails.py` | Plan, generate, store, and identify course thumbnails. |
| `pipeline/tts.py` | Synthesize, validate, and persist slide narration audio. |
| `pipeline/tts_normalization.py` | Normalize narration text before sending it to TTS. |
| `pipeline/video.py` | Capture HTML slides, encode narration clips, and persist module videos. |
| `pipeline/video_engine.py` | Per-course choice between the Video Generator ("Video Engine") and standard generation. |
| `pipeline/video_service.py` | Produce module videos through the external Video Generator service. |
| `schemas/` | Generation-state and background-job contracts. |
| `schemas/blueprint.py` | LLM and pipeline contracts for document blueprint extraction. |
| `schemas/narration.py` | LLM contracts for slide narration. |
| `schemas/notes.py` | LLM contract for learner notes. |
| `schemas/providers.py` | Typed external-provider request contracts. |
| `schemas/quiz.py` | LLM contracts for generated module quizzes. |
| `schemas/slides.py` | LLM contracts for slide planning and art direction. |
| `service.py` | Course-generation use cases independent of FastAPI routing. |

## HTTP routes

| Method | Path |
| --- | --- |
| POST | `/api/courses/{course_id}/continue-generation` |
| POST | `/api/courses/{course_id}/generate-full-course` |
| POST | `/api/courses/{course_id}/generate-quiz` |
| POST | `/api/courses/{course_id}/generate-scripts` |
| POST | `/api/courses/{course_id}/generate-slides` |
| POST | `/api/courses/{course_id}/generation-jobs` |
| POST | `/api/courses/{course_id}/generation-jobs/continue` |
| POST | `/api/courses/{course_id}/modules/{module_number}/generate-video` |
| POST | `/api/courses/{course_id}/modules/{module_number}/video-jobs` |
| GET | `/api/generation-jobs/{job_id}` |
| GET | `/api/generation/config` |

## Tables created here

None in this folder. Its tables are created by `app/db/schema.py`.

See [docs/ARCHITECTURE.md](../../../../docs/ARCHITECTURE.md) for how modules fit together.
