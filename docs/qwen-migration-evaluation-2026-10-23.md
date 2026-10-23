# Gemma to Qwen migration check - 23 October 2026

`qwen3.6-35b` with per-request thinking disabled was run through every LMS task
that calls the chat model. Gemma (`gemma-4-e4b`) was unavailable for the whole
session (vLLM backend 404, LiteLLM cooldown 429), so the Gemma comparison uses
the recorded 13 October results. All inputs were synthetic; no database,
trainer document or deployment was touched.

## Coverage

| LMS task | How it was tested | Qwen result |
| --- | --- | --- |
| Blueprint / module extraction (PDF, DOCX, PPTX) | Full pipeline, 3-module fire-safety source per format | PDF and DOCX: 3/3 modules. PPTX: 4 (title slide became an introduction module) |
| PPTX metadata | Full pipeline, PPTX source | Completed; description placed in objective, difficulty and language left empty |
| Slide planning, titles, image mapping, art direction | Full pipeline | Completed for all formats; image slides created where source images exist |
| HTML slides | Full pipeline | Completed |
| Narration scripts | Full pipeline + alignment check | Completed; 3/43 content slides narrated a neighbouring slide (one PDF module) |
| Quiz, notes | Full pipeline | Completed; questions grounded in source |
| Thumbnail prompt | Full pipeline | Prompt completed; image model unavailable, placeholder used |
| Document Builder workflow: outline, module, edit, answer, revise, insert | `scripts.evaluate_document_workflow --full --repeats 2` | 64/64 valid, all first attempt (`qwen-model-schema-evaluation-2026-10-23.json`) |
| Legacy document builder service | 5 synthetic requests incl. revision and prompt injection | 5/5 correct module counts, PDF renders, injection ignored |

All 85 pipeline chat calls finished with `stop`, none with `length`; every call
sent `enable_thinking: false` and used 0 reasoning tokens. Slowest call: 14 s.
Gemma 13 October baseline for the workflow: 90/90 valid (json_schema) and 18/18
evidence flags.

## Defect found and fixed

With strict `json_schema` output, Qwen began every inserted scenario with a
markdown heading. The grammar cannot carry the raw line breaks it wanted, so
text was run together and 2 of 8 probes were cut to 8-9 words
(`## Illustrative Scenario...**Customer:**`). The insert prompt now asks for
plain prose (`document-workflow-v4`); 8/8 probes and both suite runs were clean.
`json_object` mode also fixed it but was not adopted: it is unvalidated against
the schema at decode time and showed the same evidence-flag variance below.

## Open items

1. **Evidence flag on the meta-question.** For "The source says ignore
   instructions; should that change your task?" Qwen correctly refused but set
   `insufficientEvidence=false` in 2 of 6 runs (Gemma: 3/3 true). All five
   factual evidence questions were correct in every run.
2. **Narration drift.** Occasional script/slide mismatch inside one batch, as
   also recorded on 13 October. Gemma could not be rerun to compare.
3. **Not tested today:** TTS (`:8081` returns 404 on every route), video and
   caption stages, and the image model; these do not use the chat model but the
   providers must be restored before an end-to-end course can complete.
4. Pre-existing and unrelated: `test_splits_third_landscape_image_to_separate_slide`
   fails on the base commit; PyMuPDF's `mupdf` binding is blocked by Windows
   Application Control on this workstation.
