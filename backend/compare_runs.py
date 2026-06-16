import os
import sys
import io
import json
import time
import re
import traceback
import shutil

# Force UTF-8 encoding for stdout to handle unicode characters gracefully on Windows
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# Ensure backend root is in search path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

import pipelines.config as config
from pipelines.config import COURSES_FILE

# Global storage for captured LLM calls
captured_llm_calls = []

class WrappedCompletions:
    def __init__(self, original_completions, pdf_name):
        self.original_completions = original_completions
        self.pdf_name = pdf_name

    def create(self, *args, **kwargs):
        call_id = len(captured_llm_calls) + 1
        messages = kwargs.get("messages", [])
        
        # Format input messages for logging
        system_msg = next((m["content"] for m in messages if m["role"] == "system"), "")
        user_msg = next((m["content"] for m in messages if m["role"] == "user"), "")
        
        call_info = {
            "id": call_id,
            "pdf": self.pdf_name,
            "caller": traceback.format_stack()[-2].split('\n')[0].strip(),
            "model": kwargs.get("model"),
            "system_prompt": system_msg,
            "user_prompt": user_msg,
            "temperature": kwargs.get("temperature"),
            "max_tokens": kwargs.get("max_tokens")
        }
        
        print(f"    [LLM CALL {call_id}] Calling API for {self.pdf_name} (Caller: {call_info['caller'].split('.')[-1]})")
        
        # Invoke actual LLM
        response = self.original_completions.create(*args, **kwargs)
        
        # Capture outputs
        call_info["response_content"] = response.choices[0].message.content
        call_info["finish_reason"] = response.choices[0].finish_reason
        
        captured_llm_calls.append(call_info)
        return response

class WrappedChat:
    def __init__(self, original_chat, pdf_name):
        self.completions = WrappedCompletions(original_chat.completions, pdf_name)

class WrappedClient:
    def __init__(self, original_client, pdf_name):
        self.chat = WrappedChat(original_client.chat, pdf_name)


def main():
    print("======================================================================")
    print("STARTING BACKEND PIPELINE COMPARISON RUN")
    print("======================================================================")
    
    # 1. Back up courses.json
    courses_backup = None
    if os.path.exists(COURSES_FILE):
        print("Backing up courses.json...")
        with open(COURSES_FILE, 'r', encoding='utf-8') as f:
            courses_backup = f.read()
    else:
        print("No existing courses.json found.")
        
    # Retrieve the real un-patched LLM client generator
    real_get_llm_client = config.get_llm_client
    
    try:
        results = {}
        
        for pdf_name in ["AI_test.pdf", "AI_test_img.pdf"]:
            print(f"\n----------------------------------------------------------------------")
            print(f"RUNNING PIPELINE FOR: {pdf_name}")
            print(f"----------------------------------------------------------------------")
            
            # Setup LLM interceptor for this specific PDF run
            def make_patched_get_llm_client(name):
                def patched_get_llm_client():
                    client, model_name = real_get_llm_client()
                    return WrappedClient(client, name), model_name
                return patched_get_llm_client
                
            current_patch = make_patched_get_llm_client(pdf_name)
            
            # Patch config
            config.get_llm_client = current_patch
            # Patch all imported modules to use the patched function
            import pipelines.blueprint_extractor as bp
            bp.get_llm_client = current_patch
            import pipelines.lesson_extractor as le
            le.get_llm_client = current_patch
            import pipelines.bullet_refiner as br
            br.get_llm_client = current_patch
            import pipelines.image_mapper as im
            im.get_llm_client = current_patch
            import pipelines.script_generator as sg
            sg.get_llm_client = current_patch
            
            # Step 1: Blueprint Module Slicing
            from pipelines.run_pipeline import generate_course_outline
            outline = generate_course_outline(pdf_name)
            course_id = outline["id"]
            
            # Step 2: Lesson Generation & Bullet Refinement & Image-to-Slide Mapping
            from pipelines.run_pipeline import generate_lessons_for_course
            course_with_lessons = generate_lessons_for_course(course_id)
            
            # Step 3: Script Generation
            from pipelines.run_pipeline import generate_scripts_for_course
            final_course = generate_scripts_for_course(course_id)
            
            # Retrieve final state of this course from COURSES_FILE
            with open(COURSES_FILE, 'r', encoding='utf-8') as f:
                current_courses = json.load(f)
            course_data = next((c for c in current_courses if c.get("id") == course_id), None)
            
            results[pdf_name] = {
                "course_id": course_id,
                "course_data": course_data
            }
            
            print(f"Finished pipeline for: {pdf_name}")
            
        # 2. Write captured logs to file
        comparison_data = {
            "runs": results,
            "llm_calls": captured_llm_calls
        }
        
        report_path = os.path.join(BASE_DIR, "run_comparison_results.json")
        with open(report_path, 'w', encoding='utf-8') as f:
            json.dump(comparison_data, f, indent=2, ensure_ascii=False)
            
        print(f"\nRaw comparison results saved to: {report_path}")
        
        # 3. Analyze and Print comparison report
        print_analysis(results)
        
    finally:
        # Restore courses.json
        if courses_backup is not None:
            print("\nRestoring original courses.json...")
            with open(COURSES_FILE, 'w', encoding='utf-8') as f:
                f.write(courses_backup)
        elif os.path.exists(COURSES_FILE):
            print("\nRemoving temporary courses.json...")
            os.remove(COURSES_FILE)


def print_analysis(results):
    ai_test = results.get("AI_test.pdf", {}).get("course_data", {})
    ai_test_img = results.get("AI_test_img.pdf", {}).get("course_data", {})
    
    if not ai_test or not ai_test_img:
        print("\n[ERROR] Missing course data for comparison analysis.")
        return
        
    print("\n======================================================================")
    print("DETAILED SIDE-BY-SIDE PIPELINE COMPARISON REPORT")
    print("======================================================================")
    
    print("\n--- METADATA COMPARISON ---")
    fields = ["course_name", "course_description", "course_objective", "course_difficulty", "language", "target_audience", "course_type"]
    for field in fields:
        val_test = ai_test.get(field, "")
        val_img = ai_test_img.get(field, "")
        print(f"{field:20} | AI_test: {val_test[:40]:40} | AI_test_img: {val_img[:40]}")
        if val_test != val_img:
            print(f"{'':20} | * DIFFERENCE DETECTED in metadata field '{field}'!")
            
    print("\n--- MODULE EXTRACTION (BLUEPRINT) COMPARISON ---")
    mods_test = ai_test.get("modules", [])
    mods_img = ai_test_img.get("modules", [])
    
    print(f"Total modules extracted | AI_test: {len(mods_test):<3} | AI_test_img: {len(mods_img)}")
    
    # Side-by-side modules
    max_mods = max(len(mods_test), len(mods_img))
    for i in range(max_mods):
        m_test = mods_test[i] if i < len(mods_test) else {}
        m_img = mods_img[i] if i < len(mods_img) else {}
        
        title_test = m_test.get("title", "N/A")
        sl_test = m_test.get("start_line", "N/A")
        text_len_test = len(m_test.get("text", ""))
        
        title_img = m_img.get("title", "N/A")
        sl_img = m_img.get("start_line", "N/A")
        text_len_img = len(m_img.get("text", ""))
        
        print(f"Module {i+1}:")
        print(f"  AI_test    : Title: {title_test:30} | Start line: {sl_test:<4} | Text length: {text_len_test} chars")
        print(f"  AI_test_img: Title: {title_img:30} | Start line: {sl_img:<4} | Text length: {text_len_img} chars")
        
        # Check text diff / caption removal
        images_img = m_img.get("images", [])
        if images_img:
            print(f"  AI_test_img module extracted {len(images_img)} images:")
            for img in images_img:
                print(f"    - Image ID: {img.get('image_id')}, Caption: \"{img.get('caption')}\"")
                
    print("\n--- LESSONS & SLIDES & BULLETS COMPARISON ---")
    for i in range(min(len(mods_test), len(mods_img))):
        m_test = mods_test[i]
        m_img = mods_img[i]
        print(f"\nModule {i+1} ('{m_test.get('title')}' vs '{m_img.get('title')}'):")
        
        less_test = m_test.get("lessons", [])
        less_img = m_img.get("lessons", [])
        print(f"  Lessons count | AI_test: {len(less_test):<3} | AI_test_img: {len(less_img)}")
        
        max_less = max(len(less_test), len(less_img))
        for j in range(max_less):
            l_test = less_test[j] if j < len(less_test) else {}
            l_img = less_img[j] if j < len(less_img) else {}
            
            lt_test = l_test.get("lesson_title", "N/A")
            s_test_cnt = len(l_test.get("slides", []))
            b_test_cnt = sum(len(s.get("bullets", [])) for s in l_test.get("slides", []))
            
            lt_img = l_img.get("lesson_title", "N/A")
            s_img_cnt = len(l_img.get("slides", []))
            b_img_cnt = sum(len(s.get("bullets", [])) for s in l_img.get("slides", []))
            
            print(f"    Lesson {j+1}:")
            print(f"      AI_test    : Title: {lt_test:40} | Slides: {s_test_cnt:<3} | Bullets: {b_test_cnt}")
            print(f"      AI_test_img: Title: {lt_img:40} | Slides: {s_img_cnt:<3} | Bullets: {b_img_cnt}")
            
            # Print slide titles and check slide assignments/bullets
            if l_test:
                print(f"      AI_test Slides:")
                for s in l_test.get("slides", []):
                    print(f"        - Slide {s.get('slide_number')}: {s.get('slide_title')} ({len(s.get('bullets', []))} bullets)")
            if l_img:
                print(f"      AI_test_img Slides:")
                for s in l_img.get("slides", []):
                    s_images = s.get("images", [])
                    img_str = f" [Images: {[img.get('image_id') for img in s_images]}]" if s_images else ""
                    print(f"        - Slide {s.get('slide_number')}: {s.get('slide_title')} ({len(s.get('bullets', []))} bullets){img_str}")
                    
    print("\n--- LLM COMPLETIONS COUNT ---")
    calls_test = [c for c in captured_llm_calls if c["pdf"] == "AI_test.pdf"]
    calls_img = [c for c in captured_llm_calls if c["pdf"] == "AI_test_img.pdf"]
    print(f"Total LLM API Calls | AI_test: {len(calls_test):<3} | AI_test_img: {len(calls_img)}")
    
    print("\nDetailed list of API Calls by caller:")
    for idx, c in enumerate(captured_llm_calls):
        caller_short = c["caller"].split(".")[-1].split(" ")[0]
        p_len = len(c["user_prompt"])
        r_len = len(c["response_content"])
        print(f"  Call {c['id']:2}: PDF: {c['pdf']:15} | Caller: {caller_short:25} | Prompt size: {p_len:6,} | Response size: {r_len:6,}")


if __name__ == "__main__":
    main()
