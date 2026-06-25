# Learning Management System (LMS) Project Architecture & Data Flow

This document provides a highly detailed architecture description, data flow analysis, and structural diagrams of the LMS document processing and generation pipeline. It is designed for developers, architects, and management to understand every step, input/output, sequence, and component logic.

---

## 1. System Architecture Overview

The system consists of a **Flutter Frontend** (managed via Riverpod), a **FastAPI Backend Server**, local **JSON & Filesystem Storage**, and external **Model/Service Endpoints** for Large Language Model (LLM) and Text-to-Speech (TTS) operations.

```mermaid
graph TD
    subgraph Frontend ["Frontend (Flutter / Riverpod)"]
        UI["UI Pages & Portals (Dashboard, Document, Lesson, Slides, Scripts, Quiz, Video)"]
        RP["Riverpod State Providers (API Clients)"]
        UI --> RP
    end

    subgraph Backend ["Backend (FastAPI Server)"]
        API["FastAPI Endpoints (/api/...)"]
        PL["Pipeline Controllers (run_pipeline.py, run_full_pipeline_for_docs.py)"]
        EXT["Extractive Processors (pdfplumber, PyMuPDF)"]
        GEN["Slide/Video Engines (Pillow, FFmpeg)"]
        API --> PL
        PL --> EXT
        PL --> GEN
    end

    subgraph Storage ["Local Storage & Database"]
        DB["courses.json DB"]
        DIR_PDF["uploads/ (Source PDFs)"]
        DIR_ASSETS["assets/ (Images, Audio, Slides, Videos)"]
    end

    subgraph ModelEndpoints ["Model & Service Endpoints"]
        LLM_QWEN["Qwen/Qwen3-8B (http://35.238.33.238:8001)"]
        LLM_GEMMA["google/gemma-4-E4B-it (http://34.180.105.203:8002)"]
        TTS_F5["F5-TTS Endpoint (http://34.180.105.203:8005)"]
        TTS_G["Google Translate TTS (Fallback)"]
    end

    RP -->| "HTTP REST Requests" | API
    API -->| "Read/Write" | DB
    EXT -->| "Reads PDFs" | DIR_PDF
    GEN -->| "Writes media files" | DIR_ASSETS
    EXT -->| "Saves extracted images" | DIR_ASSETS

    PL -->| "LLM Prompts (Blueprint, Lessons, Refiner, Quiz, Image Map)" | LLM_QWEN
    PL -->| "LLM Prompts (Slide Planner, Script Gen)" | LLM_GEMMA
    PL -->| "TTS Request (ref_srk Voice)" | TTS_F5
    PL -->| "TTS Request (Fallback)" | TTS_G
```

---

## 2. End-to-End Data Pipeline Flow

The following chart outlines the sequential flow of data, beginning from the initial PDF document upload down to the final MP4 module compilation.

```mermaid
flowchart TD
    start([ "Start: User Uploads PDF" ]) --> upload[ "Upload PDF to backend" ]
    upload --> save_pdf[ "Save PDF to uploads/" ]
    
    subgraph Step1 ["Step 1: Course Blueprint Generation"]
        save_pdf --> extract_text[ "Extract text & metadata with pdfplumber" ]
        extract_text --> normalise_text[ "Normalise sentences & Number lines" ]
        normalise_text --> llm_blueprint["Call Qwen LLM for segmentation (3-6 modules)"]
        llm_blueprint --> align_headers[ "Adjust start_lines backward to catch headers" ]
        align_headers --> extract_imgs[ "Extract images & captions with PyMuPDF" ]
        extract_imgs --> assign_imgs[ "Map images to modules by line number/page" ]
        assign_imgs --> save_outline[ "Write course outline to courses.json" ]
    end

    subgraph Step2 ["Step 2: Lessons, Refinement & Image Mapping"]
        save_outline --> lesson_loop_start{ "Loop through Modules" }
        lesson_loop_start -->| "Module i" | llm_lessons["Call Qwen LLM for Lessons + Bullets"]
        llm_lessons --> clamp_bullets[ "Clamp long bullets & Number lessons" ]
        clamp_bullets --> feed_prior[ "Feed generated lesson titles as anchor for Module i+1" ]
        feed_prior --> lesson_loop_next{ "All Modules processed?" }
        lesson_loop_next -->| "No" | lesson_loop_start
        lesson_loop_next -->| "Yes" | refine_bullets["Call Qwen LLM for Holistic Bullet Refinement"]
        refine_bullets --> merge_bullets[ "Merge refined bullets back positionally" ]
        merge_bullets --> llm_img_map["Call Qwen LLM for Semantic Image-to-Bullet Mapping"]
        llm_img_map --> save_lessons[ "Update courses.json" ]
    end

    subgraph Step3 ["Step 3: MCQ Quiz Generation"]
        save_lessons --> quiz_loop_start{ "Loop through Modules" }
        quiz_loop_start -->| "If num_questions > 0" | llm_quiz["Call Qwen LLM for MCQ Questions"]
        llm_quiz --> save_quiz[ "Save quiz structure to courses.json" ]
        save_quiz --> quiz_loop_next{ "All Modules processed?" }
        quiz_loop_next -->| "No" | quiz_loop_start
        quiz_loop_next -->| "Yes" | end_step3([ "Quizzes saved" ])
    end

    subgraph Step4 ["Step 4: Slide Planning & HTML Compilation"]
        end_step3 --> slide_loop_start{ "Loop through Modules" }
        slide_loop_start -->| "Module i" | llm_slides["Call Gemma LLM for Slide Layout Types"]
        llm_slides --> map_topics[ "Map slide parent topics by bullet text overlap" ]
        map_topics --> map_slide_imgs[ "Map slide images by bullet text/caption overlap" ]
        map_slide_imgs --> compile_html_slides[ "Compile static HTML slideshow file" ]
        compile_html_slides --> slide_loop_next{ "All Modules processed?" }
        slide_loop_next -->| "No" | slide_loop_start
        slide_loop_next -->| "Yes" | end_step4([ "HTML slideshows compiled" ])
    end

    subgraph Step5 ["Step 5: Narration Scripts & TTS Speech Synthesis"]
        end_step4 --> script_loop_start{ "Loop through Modules" }
        script_loop_start -->| "Module i" | llm_scripts["Call Gemma LLM for narration script"]
        llm_scripts --> accumulate_script[ "Accumulate script for Module i+1 continuity" ]
        accumulate_script --> tts_loop_start{ "Loop through Slides" }
        tts_loop_start -->| "Slide j" | clean_script[ "Clean text for TTS engine" ]
        clean_script --> call_tts["Call F5-TTS or Fallback Google TTS"]
        call_tts --> save_wav[ "Save slide_j.wav audio file" ]
        save_wav --> tts_loop_next{ "All Slides processed?" }
        tts_loop_next -->| "No" | tts_loop_start
        tts_loop_next -->| "Yes" | script_loop_next{ "All Modules processed?" }
        script_loop_next -->| "No" | script_loop_start
        script_loop_next -->| "Yes" | compile_html_slides_narr[ "Re-compile HTML slides with audio paths" ]
    end

    subgraph Step6 ["Step 6: Video Compilation"]
        compile_html_slides_narr --> render_png[ "Render slide frames to 1920x1080 PNGs via Pillow" ]
        render_png --> ffmpeg_encode["Encode PNG + WAV into individual slide MP4s via FFmpeg"]
        ffmpeg_encode --> ffmpeg_concat["Concatenate slide MP4s into final module video MP4"]
        ffmpeg_concat --> save_video_path[ "Save video_path in courses.json" ]
    end

    save_video_path --> finish([ "End: Course Fully Generated" ])
```

---

## 3. Step-by-Step Execution Details

### Step 0: Document Upload
- **Trigger**: User selects a PDF file in the Flutter UI and uploads it.
- **Process**: The backend validates that it is a `.pdf` file, saves it to `backend/uploads/`, and returns confirmation.
- **Input**: Multipart PDF file.
- **Output**: JSON payload: `{"filename": "Test_Doc_2.pdf", "message": "File uploaded successfully"}`.

### Step 1: Course Blueprint Extraction (Outline)
- **Process**:
  1. **Text Extraction**: Uses `pdfplumber` to extract raw text page-by-page.
  2. **Metadata Parsing**: Programmatically parses the structured table on the first page of the PDF to extract course headers (Course Name, Description, Objective, Difficulty, Language, Target Audience, Course Type).
  3. **Sentence Normalisation**: Normalises whitespace and breaks the text into logical sentences.
  4. **Line Numbering**: Prefixes each content line with a `[LINE N]` tag.
  5. **Module Segmentation**: Sends the first 50,000 characters of numbered lines to the Qwen LLM (`Qwen/Qwen3-8B`) requesting a JSON schema with 3 to 6 modules and their starting line numbers.
  6. **Start Line Adjustment**: Backward-scans the text preceding the returned start lines to match headers (e.g., "Step X" or "Module Y") to prevent splitting headings from content.
  7. **Text Slicing**: Slices the original lines array dynamically using the start line indices.
  8. **Image Extraction**: PyMuPDF (`fitz`) extracts embedded image files, coordinates (`bbox`), pages, and closest text captions (or fallbacks). Saves images to `backend/assets/images/{course_id}/`.
  9. **Image-to-Module Mapping**: Assigns images to modules based on their caption line matching or page-ratio estimation. Replaces caption lines in the text with `[IMAGE: image_id]` tags.
- **Input**: PDF filename.
- **Output**: JSON structure written to `courses.json` representing the course metadata, module titles, texts, and embedded images.

### Step 2: Lesson Extraction, Bullet Refinement & Image Mapping
- **Process**:
  1. **Lesson Extraction (Sequential Loop)**:
     - Loops through each module in order.
     - Builds a prompt containing the module's text, title, and a list of all lesson titles generated in previous modules.
     - Calls Qwen LLM to extract 3-5 distinct lessons per module, each with outcome-focused titles and detailed fact-based bullet points.
     - Using prior lesson titles forces the LLM to anchor to a consistent style, terminology, and level of abstraction.
  2. **Holistic Bullet Refinement (Single Call)**:
     - Aggregates all lessons and bullets across the entire course.
     - Calls Qwen LLM with `BULLET_REFINEMENT_PROMPT`.
     - The LLM refines, consolidates, and splits bullet points to standardise lengths (~7 words) and maintain a consistent author voice.
  3. **Image-to-Lesson Mapping (Semantic Loop)**:
     - Loops through modules, extracting all available images and all refined bullets.
     - Calls Qwen LLM with `IMAGE_LESSON_MAPPING_PROMPT` to map image IDs to specific bullet indices.
     - Updates lesson structures in-place, and maps any unassigned images to Lesson 1 as a fallback.
- **Input**: `course_id`.
- **Output**: Updated course object in `courses.json` containing detailed lesson bullet trees and mapped images.

### Step 3: MCQ Quiz Generation
- **Process**:
  - Loops sequentially through modules. If a module has `num_questions` > 0, it formats a prompt with the course difficulty, module title, and text content.
  - Calls Qwen LLM with `QUIZ_GENERATION_PROMPT` to generate multiple-choice questions (A, B, C, D) with the correct answer key and detailed explanations.
- **Input**: `course_id`.
- **Output**: Updates the module's `quiz` JSON array inside `courses.json`.

### Step 4: Slide Deck Planning & HTML Slideshow Compilation
- **Process**:
  1. **Slide Planning (Sequential Loop)**:
     - Loops through modules, formatting lessons and bullets into JSON.
     - Calls Gemma-4 LLM (`google/gemma-4-E4B-it`) to structure lesson bullet points into visual slide schemas using layout types: `concept`, `steps`, `comparison`, `grid`, or `bullets`.
     - Maps slides to parent lesson topics based on text overlap.
     - Maps image IDs from lessons to slides based on overlap score with visual text elements.
  2. **HTML Slideshow Compilation**:
     - Compiles the structured slide schemas into static, responsive HTML slide decks located at `backend/assets/slides/{course_id}/module_{module_num}.html`.
     - Embeds custom Javascript controls (keyboard bindings, buttons) and `postMessage` listeners to sync state with the Flutter frontend container.
- **Input**: `course_id`.
- **Output**: Slide plans saved to `courses.json`; HTML slide decks written to disk.

### Step 5: Narration Scripts & Text-to-Speech (TTS) Speech Synthesis
- **Process**:
  1. **Narration Script Generation (Sequential Loop)**:
     - Loops through modules, sending raw module text and visual slide plans to Gemma-4 LLM.
     - Includes the accumulated spoken narration text from the previous module (`previous_script`) to ensure smooth transition continuity.
     - Saves text narration scripts for each slide.
  2. **Text-to-Speech Synthesis (Slide Loop)**:
     - Cleans XML/HTML tags and expands shorthand terms (e.g. "Ltd." to "Limited").
     - Calls F5-TTS endpoint with voice profile `ref_srk` (male narrator) and its corresponding reference audio and transcript.
     - Fallback: If the GPU server is offline, it splits text into <200 character chunks and falls back to Google Translate TTS, joining synthesized audio chunks.
     - Saves audio files to `backend/assets/audio/course_{course_id}/module_{module_number}/slide_{slide_num}.wav`.
  3. **Re-compiles Slides**: Regenerates the HTML slide files to insert absolute audio URLs and synchronized speaker notes.
- **Input**: `course_id`.
- **Output**: wav audio files saved on disk; updated slideshow files and JSON data.

### Step 6: Video Compilation
- **Process**:
  1. **Pillow Frame Rendering (Sequential Slide Loop)**:
     - Renders each slide into a 1920x1080 PNG image.
     - Renders text and visual templates matching slide layouts (`concept`, `steps`, `comparison`, `grid`, `bullets`).
     - Incorporates corporate style rules (PhillipCapital primary color `#00317A`, Barlow & Inter fonts, and the asymmetric "P"-shaped frame rounding with bottom-left overlay captions).
  2. **FFmpeg Slide-Clip Encoding (Sequential Slide Loop)**:
     - Combines the rendered PNG image with the WAV audio file to output a mini video clip (`clip_{idx}.mp4`).
     - Extracts the audio duration using `imageio-ffmpeg` to set the exact duration. Generates silent mono audio if audio is missing.
  3. **FFmpeg Concatenation**:
     - Writes a `concat.txt` file referencing all slide MP4 clips.
     - Concatenates them without re-encoding to produce a single final MP4 file under `backend/assets/videos/course_{course_id}/module_{module_number}.mp4`.
- **Input**: `course_id`, `module_number`.
- **Output**: Consolidated module MP4 video file on disk, updated `video_path` database property.

---

## 4. Analysis of Parallelism and Loops

### Parallelism Analysis
> [!IMPORTANT]
> **There is NO parallel execution in this backend pipeline.**
> All tasks are handled strictly in a serial, sequential manner.

The sequential architecture is mandatory due to critical design constraints:
1. **Context/Style Anchoring**: Steps like Lesson Generation rely on having access to *all* lesson titles generated in prior modules to prevent stylistic drift.
2. **Transition Continuity**: Script generation requires the narration scripts of the previous module (`previous_script`) to generate logical transition sentences.
3. **Hardware Resource Constraints**: Large Language Models (vLLM) and Text-to-Speech synthesis (GPU F5-TTS) are highly compute-intensive. Running queries in parallel would overload GPU endpoints, resulting in timeout failures (FastAPI timeout limit is 600s).
4. **Data Race Prevention**: The file-based JSON database (`courses.json`) is shared. Sequential writes prevent concurrent processes from overwriting each other's changes.

### Loop structures in code
The pipeline implements the following distinct loop iterations:

| Pipeline Step | Loop Type | Iteration Level | Purpose / Operation |
| :--- | :--- | :--- | :--- |
| **Step 1 (Blueprint)** | Sequential | PDF Pages | Extract text and detect tables. |
| | Sequential | PDF Images | Extract coordinates, pages, and captions using PyMuPDF. |
| **Step 2 (Lessons)** | Sequential | Modules | Call LLM to extract lessons while passing prior titles as context. |
| | Sequential | Modules | Run semantic matching to assign images to bullets. |
| **Step 3 (Quizzes)** | Sequential | Modules | Call LLM to generate MCQs if `num_questions > 0`. |
| **Step 4 (Slides)** | Sequential | Modules | Call LLM to plan layouts and output structured visual elements. |
| **Step 5 (Scripts/TTS)** | Sequential | Modules | Call LLM for slide script narration using transition context. |
| | Sequential | Slides (inner) | Clean text and call TTS API to generate `.wav` narration files. |
| **Step 6 (Video)** | Sequential | Slides | Render frames via Pillow; run FFmpeg to encode still PNG + WAV audio. |

---

## 5. Design Compliance & Styling Systems

All generated visual assets (static HTML slides and compiled MP4 video frames) are compiled using the **PhillipCapital Design System**:

*   **Color Palette**: Primary Blue (`#00317A`), Secondary Light Gray (`#EEEEEE`), Gray (`#AAAAAA`), Accent Cyan (`#17BCE2`), Orange (`#F78F20`), Green (`#14C496`), and Red (`#FF1515`).
*   **Typography**: *Barlow* is used for body content and list items. *Inter* is reserved for main headers and logos.
*   **UI Geometry ("P" shape)**: Image frames use asymmetric corner rounding. The top-right and bottom-left corners are rounded (radius 32), while the top-left and bottom-right corners remain sharp. Captions are overlaid on the lower-left angular side of the frame in a semi-transparent blue banner.
*   **Logo Rules**: The full "PhillipCapital" wordmark is always utilized. The isolated "P" letter is prohibited in accordance with brand rules.

---

## 6. Execution Call Count Reference

To help estimate compute requirements, here is the breakdown of API calls made for a course containing $M$ modules and $S$ total slides across all modules:

### Large Language Model (LLM) Calls

| Step | Operation | Target Model | API Calls |
| :--- | :--- | :--- | :--- |
| **Step 1** | Blueprint (Segmentation) | **Qwen3-8B** | $1$ call |
| **Step 2** | Lesson Extraction | **Qwen3-8B** | $M$ calls (1 per module) |
| **Step 2** | Bullet Refinement | **Qwen3-8B** | $1$ call (holistic course pass) |
| **Step 2** | Image Mapping | **Qwen3-8B** | $M_{img}$ calls (1 per module containing images) |
| **Step 3** | Quiz Generation | **Qwen3-8B** | $M_{quiz}$ calls (1 per module where `num_questions > 0`) |
| **Step 4** | Slide Planning | **Gemma-4** | $M$ calls (1 per module) |
| **Step 5** | Script Generation | **Gemma-4** | $M$ calls (1 per module) |

#### Call Counts Formula Summary:
*   **Total LLM Calls**: $2 + 3M + M_{img} + M_{quiz}$ (maximum of $2 + 5M$ calls if all modules contain images and quiz questions)
*   **Qwen Calls**: $2 + M + M_{img} + M_{quiz}$
*   **Gemma Calls**: $2M$

### Text-To-Speech (TTS) Calls

| Step | Operation | Target Engine | API Calls |
| :--- | :--- | :--- | :--- |
| **Step 5** | Speech Synthesis | **F5-TTS** (or fallback Google TTS) | $S$ calls (1 call per slide) |

#### Call Counts Formula Summary:
*   **Total TTS Calls**: $S$ calls
