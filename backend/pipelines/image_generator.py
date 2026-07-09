import os
import json
import uuid
import time
import multiprocessing
import subprocess
from pydantic import BaseModel, Field

os.environ["TORCH_CUDNN_SDPA_ENABLED"] = "0"

from core.database import get_all_courses, save_all_courses
from pipelines.config import get_llm_endpoint, safe_chat_completion, BASE_DIR
from pipelines.prompts import IMAGE_GENERATION_SYSTEM_PROMPT

FLUX_IMAGES_DIR = os.path.join(BASE_DIR, "assets", "images", "generated")

class ImagePromptSchema(BaseModel):
    suggested_image_prompt: str = Field(description="A highly descriptive prompt for an AI image generator (e.g. Flux) to create an abstract or literal visual representation of the slide's core message. Make it cinematic and textless.")

def get_nvidia_gpus():
    try:
        cmd = "nvidia-smi --query-gpu=index,memory.free,memory.total --format=csv,noheader,nounits"
        output = subprocess.check_output(cmd, shell=True, text=True)
        gpus = []
        for line in output.strip().split('\n'):
            if line.strip():
                parts = [x.strip() for x in line.split(',')]
                idx = int(parts[0])
                free_mb = float(parts[1])
                total_mb = float(parts[2])
                gpus.append({'index': idx, 'free_mb': free_mb, 'total_mb': total_mb})
        return gpus
    except Exception as e:
        return [{'index': 0, 'free_mb': 24000.0, 'total_mb': 24000.0}]

def flux_worker(gpu_idx, task_queue, results_queue, model_id, steps, guidance, max_seq_len):
    os.environ["CUDA_VISIBLE_DEVICES"] = str(gpu_idx)
    
    # Default to Vertex AI (HTTP) in the backend to avoid massive local PyTorch downloads
    if os.environ.get("USE_VERTEX_AI", "1") == "1":
        print(f"      [Vertex Worker GPU {gpu_idx}] Generating via Cloud Vertex AI API...")
        try:
            from pipelines.vertex_inference import generate_image_vertex
            endpoint_id = os.environ.get("VERTEX_FLUX_ENDPOINT_ID", "http://35.238.33.238:8002/generate")
            
            while True:
                if task_queue.empty():
                    break
                try:
                    task = task_queue.get_nowait()
                except Exception:
                    break
                module_idx, slide_idx, prompt, output_path = task
                start_time = time.time()
                
                success = generate_image_vertex(
                    prompt=prompt,
                    output_path=output_path,
                    endpoint_id=endpoint_id
                )
                
                if success:
                    duration = time.time() - start_time
                    print(f"      [Vertex Worker] Saved: {output_path} (Took {duration:.2f}s)")
                    results_queue.put((module_idx, slide_idx, output_path))
        except Exception as e:
            print(f"Error in Vertex AI worker: {e}")
        return

    from diffusers import FluxPipeline
    import torch
    
    # Force disable cuDNN SDPA backend at runtime (use math/flash attention instead)
    torch.backends.cudnn.allow_tf32 = True
    if hasattr(torch.backends.cuda, 'enable_cudnn_sdp'):
        torch.backends.cuda.enable_cudnn_sdp(False)
    if hasattr(torch.backends.cuda, 'enable_flash_sdp'):
        torch.backends.cuda.enable_flash_sdp(True)
    if hasattr(torch.backends.cuda, 'enable_math_sdp'):
        torch.backends.cuda.enable_math_sdp(True)
    
    try:
        print(f"      [Flux Worker GPU {gpu_idx}] Loading {model_id} from local cache...")
        
        # Load from HF Hub cache
        pipe = FluxPipeline.from_pretrained(
            model_id, 
            torch_dtype=torch.bfloat16
        )
        
        pipe.to("cuda")
        print(f"      [Flux Worker GPU {gpu_idx}] Model loaded successfully. Processing queue...")
        
        while True:
            if task_queue.empty():
                break
            try:
                task = task_queue.get_nowait()
            except Exception:
                break
                
            module_idx, slide_idx, prompt, output_path = task
            start_time = time.time()
            print(f"      [Flux Worker GPU {gpu_idx}] Generating Module {module_idx+1} Slide {slide_idx+1}...")
            
            with torch.inference_mode():
                image = pipe(
                    prompt=prompt,
                    guidance_scale=guidance,  
                    num_inference_steps=steps,  
                    max_sequence_length=max_seq_len,
                    width=1024,
                    height=1024
                ).images[0]
                
            image.save(output_path)
            duration = time.time() - start_time
            print(f"      [Flux Worker GPU {gpu_idx}] Saved: {output_path} (Took {duration:.2f}s)")
            results_queue.put((module_idx, slide_idx, output_path))
            
        del pipe
        torch.cuda.empty_cache()
    except Exception as e:
        print(f"Error in Flux worker on GPU {gpu_idx}: {e}")

def generate_prompt_for_slide(slide: dict) -> str:
    title = slide.get("slide_title", "Concept")
    
    content = ""
    layout = str(slide.get("layout_type", "bullets")).lower().split(".")[-1]
    if layout == "concept" and slide.get("concept_data"):
        cd = slide["concept_data"]
        content = f"Term: {cd.get('core_term', '')}. Definition: {cd.get('definition', '')}"
    else:
        bullets = slide.get("bullets_data")
        if not bullets:
            bullets = slide.get("bullets", [])
        if bullets:
            content = " ".join([b if isinstance(b, str) else b.get("text", "") for b in bullets])
            
    # Pass the actual slide context to the LLM
    prompt = f"Slide Title: {title}\n\nSlide Content/Bullets: {content}\n\nBased on this slide content, decide on an appropriate visual metaphor or illustration, and write the optimized FLUX image generation prompt for it."
    
    base_url, model = get_llm_endpoint("slides")
    try:
        response = safe_chat_completion(
            base_url=base_url,
            model=model,
            messages=[
                {"role": "system", "content": IMAGE_GENERATION_SYSTEM_PROMPT},
                {"role": "user", "content": prompt}
            ],
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "ImagePromptSchema",
                    "schema": ImagePromptSchema.model_json_schema(),
                    "strict": True
                }
            },
            temperature=0.2
        )
        parsed = ImagePromptSchema.model_validate_json(response.choices[0].message.content)
        return parsed.suggested_image_prompt
    except Exception as e:
        print(f"      [LLM] Error generating prompt for slide '{title}': {e}")
        return f"Abstract representation of {title}"

def enrich_sparse_slides_with_flux(course_id: str):
    print(f"\n[STEP 4.5] Enriching sparse slides with Flux generated images for course {course_id}...")
    
    courses = get_all_courses('draft')
    course_idx = next((i for i, c in enumerate(courses) if c.get("id") == course_id), None)
    if course_idx is None:
        raise ValueError(f"Course '{course_id}' not found.")
        
    course = courses[course_idx]
    modules = course.get("modules", [])
    
    os.makedirs(FLUX_IMAGES_DIR, exist_ok=True)
    
    task_queue = multiprocessing.Queue()
    results_queue = multiprocessing.Queue()
    tasks_count = 0
    
    # 1. Identify sparse slides and generate LLM prompts
    print("  [Enrichment] Scanning modules for sparse slides (<= 2 bullets or concept layout) lacking images...")
    for m_idx, module in enumerate(modules):
        slides = module.get("slides", [])
        for s_idx, slide in enumerate(slides):
            # Check if it has an image mapped
            if slide.get("image_ids") and len(slide["image_ids"]) > 0:
                continue
                
            # Check if sparse
            is_sparse = False
            layout = str(slide.get("layout_type")).lower().split(".")[-1]
            
            if layout == "bullets":
                bullets = slide.get("bullets_data")
                if not bullets:
                    bullets = slide.get("bullets", [])
                if len(bullets) == 1 or len(bullets) == 2:
                    is_sparse = True
                    
            if is_sparse:
                print(f"    -> Flagging Module {m_idx+1} Slide {s_idx+1} ('{slide.get('slide_title')}') for enrichment.")
                raw_prompt = generate_prompt_for_slide(slide)
                
                # The LLM prompt now handles all formatting and textless rules
                flux_prompt = raw_prompt
                print(f"      [LLM] Generated Flux prompt: {flux_prompt}")
                
                img_uuid = str(uuid.uuid4())[:8]
                output_path = os.path.abspath(os.path.join(FLUX_IMAGES_DIR, f"flux_scene_{img_uuid}.png"))
                
                task_queue.put((m_idx, s_idx, flux_prompt, output_path))
                tasks_count += 1
                
    if tasks_count == 0:
        print("  [Enrichment] No sparse slides requiring enrichment found. Skipping Flux generation.")
        return True

    # 2. Configure Flux
    model_id = "black-forest-labs/FLUX.1-schnell"
    steps = 4
    guidance = 0.0
    max_seq_len = 256
    vram_requirement = 16000.0  # 16 GB for Schnell
    
    gpus = get_nvidia_gpus()
    available_gpus = [gpu['index'] for gpu in gpus if gpu['free_mb'] >= vram_requirement]
    
    if not available_gpus:
        best_gpu = max(gpus, key=lambda x: x['free_mb'])
        available_gpus = [best_gpu['index']]
        print(f"  [Parallel Engine] Warning: Under VRAM constraint. Allocating single fallback worker to GPU {best_gpu['index']} ({best_gpu['free_mb']:.1f} MB free).")
    else:
        print(f"  [Parallel Engine] Allocating Flux workers to GPUs: {available_gpus}...")

    # 3. Spawn workers
    processes = []
    try:
        multiprocessing.set_start_method('spawn', force=True)
    except RuntimeError:
        pass
        
    for gpu_idx in available_gpus:
        p = multiprocessing.Process(
            target=flux_worker,
            args=(gpu_idx, task_queue, results_queue, model_id, steps, guidance, max_seq_len)
        )
        p.start()
        processes.append(p)
        
    for p in processes:
        p.join()
        
    # 4. Bind generated images back to slides
    generated_updates = 0
    while not results_queue.empty():
        m_idx, s_idx, output_path = results_queue.get()
        if os.path.exists(output_path):
            img_id = f"flux_img_{uuid.uuid4().hex[:8]}"
            rel_path = f"assets/images/generated/{os.path.basename(output_path)}"
            
            module = modules[m_idx]
            if "images" not in module:
                module["images"] = []
                
            module["images"].append({
                "image_id": img_id,
                "file_path": rel_path,
                "caption": "AI Generated Visualization",
                "mapped_bullet_text": ""
            })
            
            slide = module["slides"][s_idx]
            if "image_ids" not in slide:
                slide["image_ids"] = []
            slide["image_ids"].append(img_id)
            generated_updates += 1

    if generated_updates > 0:
        course["modules"] = modules
        courses[course_idx] = course
        save_all_courses(courses, "draft")
        print(f"  [Enrichment] Successfully enriched {generated_updates} sparse slides with AI images.")
        
    return True

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        enrich_sparse_slides_with_flux(sys.argv[1])
    else:
        print("Provide course_id")
