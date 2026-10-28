# Captions timed from measured narration (no aligner)

## Goal

Locally rendered module videos get captions without the Qwen forced-aligner. Caption timing uses the Video Generator's method: measure the narration audio and split each measured span between caption lines by text length. Everything learners see stays as the LMS has it today:
- the same corporate player;
- the **CC button** to show or hide captions;
- captions in the bar **below** the video, not burned into the picture;
- the same `.vtt` and `.captions.json` files, checked by the player the same way.

The aligner stays optional. When it is configured, it still gives word-exact timing, and estimated captions can later be upgraded to aligned ones.

## How the Video Generator does it (reference only)

`website/backend/services/animation_audio.py` and `animation_captions.py` in the Video-Generator repo:

1. Each scene's narration is synthesized as **one TTS call per key point**. Each WAV's length is measured after the speed change, and points are joined with a fixed pause. Every point's start and end are therefore exact.
2. Each point's text is cut into caption chunks:
   - at sentence ends;
   - at most 2 lines of 42 characters;
   - a chunk never ends on a weak word like "the", "of" or "and".
3. Each chunk gets a share of the point's time **in proportion to its character count**. The minimum is 0.8 s, and a cue never overlaps the next one.
4. The cues are burned into the video (`.ass`), and an `.srt` is kept beside it.

We reuse steps 1–3 (the timing mechanism) and not step 4 (the presentation).

## How the LMS differs today

- TTS is **one call per slide** (`synthesize_speech_for_slide` in `backend/app/generation/tts.py`). The speed change (`TTS_SPEED`, `TTS_MAX_WORDS_PER_MINUTE`) happens before the WAV is saved, so the saved slide WAV is the final narration.
- Each slide clip is that WAV followed by `SLIDE_TRANSITION_PAUSE_SECONDS` of silence (`encode_slide_clip` in `backend/app/generation/video.py`). The real encoded clip lengths are measured and stored in `.source.json` as `clip_durations`.
- `generate_module_captions` in `backend/app/generation/captions.py` refuses to run unless `CAPTION_ALIGN_COMMAND` is set. As a result, local videos currently get no captions at all.

The exact timing points are therefore the **slide boundaries**, which come from the measured clip lengths. That is coarser than the Video Generator's per-point timing, because one slide can hold 20–60 s of speech. Phase 1 matches the Video Generator. Phase 2 adds sentence anchors from audible pauses, so long slides stay in step.

## Design

### Phase 1: same mechanism as the Video Generator

All of this is backend only, in `backend/app/generation/captions.py`. Nothing changes in the player or the employee app.

**1. Setting.** A new setting, `CAPTION_TIMING`:

| Value | Behaviour |
|---|---|
| `auto` (default) | Forced alignment if `CAPTION_ALIGN_COMMAND` is set; otherwise narration timing |
| `narration` | Always narration timing |
| `aligned` | Forced alignment only. Fails as today if the aligner is missing |
| `off` | No captions |

Add it to `settings.py`, `docker-compose.yml` and `.env.example`.

**2. Slide spans (exact).** Use the existing provenance checks in `generate_module_captions`:
- the video hash;
- each slide's script and audio hashes;
- `clip_durations`.

Slide *n* starts at the sum of the earlier clip durations. Its speech lasts the measured length of its narration WAV; the transition pause after it gets no caption.

**3. Trim silence at the edges (exact, cheap).** Find where speech starts and ends inside each slide WAV, using the loudness helpers already used for legacy videos (`_to_pcm`, `_envelope`). TTS often leaves 0.1–0.4 s of silence at either end. The Video Generator does not trim this, and trimming keeps the first line from appearing early.

**4. Caption chunks.** Build cues from the **written** script, so AML and FIU-IND appear as written, not as spoken. Reuse the LMS's current phrasing rules so captions look the same as aligned ones:
- break at sentence punctuation;
- balance long phrases at their most even word boundary, preferring a comma or colon (`_balanced_pieces`, about 78 characters ≈ 2 lines);
- add the Video Generator's rule that a cue never ends on a weak word ("the", "of", "to", "and" …).

`_balanced_pieces` currently splits on word timing (≤ 6 s). In narration mode it splits on text length only.

**5. Timing inside a slide.** Each cue gets a share of the slide's speech span in proportion to its length, as in the Video Generator. One improvement: length is measured in **spoken** characters, from `display_words`, which already maps each written word to its normalized spoken form. Expansions such as "FIU-IND" → "F I U India" or "₹5 crore" → "five crore rupees" therefore get the extra time they take to say. If a slide's text cannot be mapped, the written length is used.
- Minimum cue length is 0.8 s.
- A cue never overlaps the next.
- The last cue ends where the slide's speech ends.

**6. Output.** The same VTT and `.captions.json` as now, with `"method": "narration-timing"` (or `"forced-alignment"` when aligned). The player already ignores `method` and validates:
- the fingerprint;
- `vtt_sha256`;
- `cue_count`;
- the duration;
- the video size and Last-Modified.

So the CC button, the bottom caption bar and the integrity checks work unchanged.

**7. Where it runs.**
- **New videos:** `_generate_captions_if_available` in `video.py`, right after rendering, as now. It just stops failing when there is no aligner.
- **Old videos:** `backfill_module_captions` and `scripts/backfill_video_captions.py`. The legacy path already finds each slide inside the old video's soundtrack by loudness matching (`prepare_legacy_slides`), with no ML. Narration timing reuses those slide starts in place of the aligner call.
- **Video Generator videos:** skipped as today (a `video_service` run or an `.srt`), because their subtitles are already in the picture.

**8. Upgrading to aligned captions later.** Today an existing valid caption file is skipped. Change it so that when the aligner is configured and the existing `method` is `narration-timing`, the backfill regenerates the captions with forced alignment. Aligned captions are never replaced by estimated ones.

### Phase 2: sentence anchors from pauses (recommended)

TTS leaves short silences between sentences. Within each slide WAV:
1. Detect silent gaps of at least 0.25 s, using the same 10 ms loudness frames.
2. Match the gaps, in order, to sentence ends in the script, choosing for each sentence end the gap closest to its estimated time.
3. Accept a match only if it lies within ±1.5 s of the estimate.
4. Pin those sentence ends to the measured gap, then share time by character length only *between* anchors.

Long slides then stay in step much as the Video Generator's per-point timing does. Unmatched sentences fall back to Phase 1 timing, so nothing gets worse. This is a few dozen lines on top of Phase 1. It can ship together with Phase 1 or right after it.

### Not changing

- The player (`packages/shared/src/video/captionPlayer.js`, `HlsVideoPlayer.tsx`): the CC button, its menu, the caption bar below the video, styling and integrity checks.
- The caption file locations and access rules: `.vtt` and `.captions.json` beside the MP4, mapped to the course; internal files never served.
- The `.media.lock`, provenance and TTS cache rules, including the pace record from #43.
- The Video Generator flow and its burned-in subtitles.

## Accuracy to expect

| Part | Accuracy |
|---|---|
| Slide start and end | Exact (measured clip lengths) |
| First and last line of each slide | Exact once edges are trimmed |
| Sentences inside a slide, Phase 1 | Usually within ~0.5–1 s; worst on long slides with uneven pacing |
| Sentences inside a slide, Phase 2 | Within a few hundred ms wherever a pause is found |
| Individual words | Not timed. Cues are 1–2 line phrases, as in the Video Generator |

This is good enough for read-along captions. Word-exact timing still needs the aligner.

## Tests

Backend, in `backend/tests/test_captions.py`:
- **Settings:** `auto` uses narration timing when `CAPTION_ALIGN_COMMAND` is empty and alignment when it is set; `off` writes nothing.
- **Slide offsets** follow `clip_durations`, and transition pauses carry no cue.
- **Edge trimming:** a synthetic WAV with 0.3 s of leading silence starts its first cue at about 0.3 s.
- **Chunking:**
  - no cue is longer than 2×42 characters;
  - no cue ends on a weak word;
  - sentence breaks are respected;
  - AML and FIU-IND appear as written.
- **Spoken-length weighting:** an acronym-heavy cue gets more time than a plain one of equal written length.
- **Cue rules:** minimum 0.8 s, no overlaps, the last cue ends within the video, valid VTT.
- **Metadata:** `method` is `narration-timing`, and the hashes match what the player checks.
- **Legacy backfill** works without the aligner, using the slide starts from `prepare_legacy_slides`.
- **Upgrade:** with the aligner configured, a `narration-timing` caption is regenerated and an aligned one is skipped.
- **Video Generator videos** are still skipped.
- **Phase 2:** synthetic speech with known gaps pins sentence ends to them; gaps too far from the estimate are ignored.

Frontend: no code changes. Keep a player test that loads a `narration-timing` metadata file, to show that it is accepted.

## Docs

- Update the `captions.py` module docstring, which currently says "never estimate timing from word counts".
- Update `docs/video-captions-operations.md`: the new setting, the two timing methods and the upgrade path.
- Update `.env.example` comments.

## Rollout on the VM

1. Deploy as usual. There are no new packages, no aligner and no extra memory.
2. Leave `CAPTION_TIMING` at `auto`. With no aligner, narration timing is used.
3. Generate a short new test course. Check CC in the employee player at the start, middle and end of a long slide.
4. Backfill one old course: dry run, then `--apply`, using the commands already in the operations doc.
5. If the aligner is installed later, re-run the backfill to upgrade those captions to word-exact timing.

## Effort

- **Phase 1:** about a day including tests. It is backend only, mostly in `captions.py`, plus the setting and docs.
- **Phase 2:** about half a day more.
