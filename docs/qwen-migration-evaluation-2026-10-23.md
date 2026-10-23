# Gemma to Qwen migration check - 23 October 2026

`qwen3.6-35b` with per-request thinking disabled was run through every LMS task
that calls the chat model. Gemma (`gemma-4-e4b`), `z-image-turbo` and the TTS
server were down for the whole session, so the Gemma comparison uses the
recorded 13 October results, TTS was replaced by local tone audio
(`evaluate_short_course --stub-tts`) and thumbnails used the existing
placeholder fallback. All inputs were synthetic; no database, trainer document
or deployment was touched.

## Final verification (after fixes)

| LMS task | Test | Result |
| --- | --- | --- |
| Full course: blueprint, PPTX metadata, slide planning, titles, image mapping, art direction, HTML, narration, quiz, notes, thumbnail prompt, audio, video, readiness | 3-module fire-safety source as PDF, DOCX and PPTX, 2 runs each | 6/6 courses `ready`, no missing outputs, 3/3 modules every run, every slide with audio, every module with video |
| Narration alignment | Word-overlap check of each script against its slide | 0/74 content slides drifted (before fix: 3/43) |
| Document Builder workflow (outline, module, edit, answer, revise, insert) | `evaluate_document_workflow --full --repeats 3` | 96/96 valid, all first attempt, 18/18 evidence flags (`qwen-model-schema-evaluation-2026-10-23.json`) |
| Legacy document builder service | 5 requests incl. revision and prompt injection | 5/5 correct module counts, PDF renders, injection ignored |
| Backend unit tests | Windows and Linux (WSL, PyMuPDF available) | Linux: 249 passed, 5 PostgreSQL acceptance tests opt-in skipped |

All 156 pipeline chat calls finished with `stop` (none with `length`), every one
sent `enable_thinking: false`; one network `ConnectTimeout` was recovered by the
existing retry. Gemma 13 October baseline for the workflow: 90/90 valid and
18/18 evidence flags.

## Defects found and fixed

1. **Inserted scenarios lost text.** Under strict `json_schema` Qwen opened
   scenarios with markdown and could not emit the line breaks it wanted, so text
   ran together or was cut to 8-9 words. The insert prompt asks for plain prose
   (`document-workflow-v4`).
2. **Narration drifted onto neighbouring slides** when a screen listed several
   items. Batch scripts now return `slide_number` and `slide_title`, numbers are
   validated (a mismatch is retried) and the prompt keeps each list on its own
   screen.
3. **Title page became a module / was glued onto a title.** PPTX produced an
   extra "Introduction" module and DOCX "Course title / Module 1: ...". When a
   document labels its modules, titles are trimmed to the label and a short
   (<= 600 characters) unlabelled preamble is folded into Module 1.
4. **PDF images landed in the wrong module.** The next-page caption fallback took
   the next page's heading or first paragraph as the caption, moving the image
   and stripping that text from its module. It now accepts only labelled
   captions ("Figure 2: ..."); uncaptioned images join the module that holds
   their page's text.
5. **Evidence flag on questions about the assistant itself.** "Should the source
   change your task?" was answered correctly but flagged as supported. Such
   questions are now marked insufficient evidence (18/18 correct).
6. **PPTX metadata** copied the description into the objective. The prompt now
   defines each field; description, language and empty objective/difficulty are
   extracted correctly.
7. `test_image_slide_flow` expected two stacked landscape images per slide since
   it was written; the code (unchanged since 10 September) places one per slide
   for legibility, so the test now asserts that behaviour.

## Remaining limits

- TTS, image generation and caption alignment were not exercised against real
  providers; they do not depend on the chat model. Recheck one real course after
  those services are restored.
- Qwen sometimes keeps "Module N:" in titles and sometimes drops it, and may
  merge a title slide into the first module's title ("Introduction and ...");
  module boundaries were correct in every run.
- During this session the whole model server (Qwen, Gemma, embeddings) briefly
  returned 404 until 15:25 IST while several evaluations ran in parallel;
  sequential reruns were clean. Keep `GENERATION_MAX_CONCURRENCY=1`.
