import os
import base64
from io import BytesIO
from PIL import Image

# Vertex AI SDKs
try:
    from google.cloud import aiplatform
    from vertexai.generative_models import GenerativeModel
except ImportError:
    pass

def init_vertex_ai(location: str = None):
    project_id = os.environ.get("GCP_PROJECT_ID")
    if not location:
        location = os.environ.get("GCP_LOCATION", "us-central1")
    if project_id:
        # Try local gcloud credentials only if the SDK actually exists on disk
        gcloud_path = "/home/Aryan/google-cloud-sdk/bin/gcloud"
        if os.path.exists(gcloud_path):
            try:
                import subprocess
                from google.oauth2.credentials import Credentials
                token = subprocess.check_output([gcloud_path, "auth", "print-access-token"], text=True).strip()
                credentials = Credentials(token=token)
                aiplatform.init(project=project_id, location=location, credentials=credentials, api_endpoint=f"{location}-aiplatform.googleapis.com")
                return
            except Exception as e:
                print(f"[Vertex Init] Local gcloud credential failed, falling back to ADC: {e}")
        # In Cloud Run / Docker: use Application Default Credentials (service account)
        aiplatform.init(project=project_id, location=location, api_endpoint=f"{location}-aiplatform.googleapis.com")


def generate_text_vertex(prompt: str, endpoint_id: str = None, max_tokens: int = 700) -> str:
    if not endpoint_id:
        raise ValueError("Vertex Endpoint ID or HTTP API URL is required for Gemma text generation.")
        
    if endpoint_id.startswith("http://") or endpoint_id.startswith("https://"):
        import requests
        headers = {
            "Content-Type": "application/json"
        }
        # Estimate prompt tokens (safely assuming 3 characters per token)
        estimated_prompt_tokens = len(prompt) // 3
        # Strict context window cap of 8192 for the VM LLM endpoint
        max_allowed = 8192 - estimated_prompt_tokens - 40
        if max_allowed < 100:
            max_allowed = 100  # absolute minimum to prevent failure
        actual_max_tokens = min(max_tokens, max_allowed)
        
        payload = {
            "model": "google/gemma-4-E4B-it",
            "messages": [
                {"role": "user", "content": prompt}
            ],
            "response_format": {"type": "json_object"},
            "max_tokens": actual_max_tokens,
            "temperature": 0.0
        }
        
        print(f"      [HTTP LLM Worker] Sending request to VM endpoint: {endpoint_id}...")
        try:
            response = requests.post(endpoint_id, json=payload, headers=headers)
            if response.status_code == 200:
                res_json = response.json()
                if "choices" in res_json and len(res_json["choices"]) > 0:
                    choice = res_json["choices"][0]
                    if "message" in choice and "content" in choice["message"]:
                        return choice["message"]["content"]
                raise ValueError(f"Unexpected response format from VM LLM: {response.text}")
            else:
                raise ValueError(f"VM LLM endpoint error: {response.status_code} - {response.text}")
        except Exception as e:
            print(f"Connection error to VM LLM: {e}")
            raise e

    location = None
    if "locations/" in endpoint_id:
        try:
            parts = endpoint_id.split("/")
            location = parts[parts.index("locations") + 1]
        except Exception:
            pass
    init_vertex_ai(location=location)
    
    endpoint = aiplatform.Endpoint(endpoint_id)
    
    # Ensure Gemma 2 Instruct format is applied if the prompt is raw text
    if "<start_of_turn>" not in prompt:
        prompt = f"<start_of_turn>user\n{prompt}<end_of_turn>\n<start_of_turn>model\n"
        
    # Estimate prompt tokens (safely assuming 3 characters per token)
    estimated_prompt_tokens = len(prompt) // 3
    # Strict context window cap of 2048 for Model Garden endpoint
    max_allowed = 2048 - estimated_prompt_tokens - 40
    if max_allowed < 100:
        max_allowed = 100  # absolute minimum to prevent failure
    actual_max_tokens = min(max_tokens, max_allowed)
    
    instances = [{"prompt": prompt, "max_tokens": actual_max_tokens}]
    use_dedicated = getattr(endpoint.gca_resource, "dedicated_endpoint_enabled", False)
    response = endpoint.predict(instances=instances, use_dedicated_endpoint=use_dedicated)
    
    if not response or not hasattr(response, "predictions") or not response.predictions:
        raise ValueError("[Error] Model Garden Gemma endpoint returned empty/null predictions. Fallbacks are disabled to ensure strictly open source model usage.")

    # Google Model Garden sometimes wraps the output in "Prompt:\n...Output:\n..."
    out_str = response.predictions[0]
    if isinstance(out_str, str) and "Output:\n" in out_str:
        out_str = out_str.split("Output:\n")[-1]
        
    return out_str

def generate_image_vertex(prompt: str, output_path: str, endpoint_id: str = None):
    location = None
    if endpoint_id and "locations/" in endpoint_id:
        try:
            parts = endpoint_id.split("/")
            location = parts[parts.index("locations") + 1]
        except Exception:
            pass
    init_vertex_ai(location=location)
    
    # If deploying FLUX.1 via Model Garden endpoint or Custom VM HTTP URL
    if endpoint_id:
        import requests as req_lib
        
        # --- Try Custom HTTP URL directly (e.g. your VM) ---
        if endpoint_id.startswith("http://") or endpoint_id.startswith("https://"):
            print(f"[Flux Debug] Calling custom HTTP URL: {endpoint_id}")
            try:
                resp = req_lib.post(
                    endpoint_id,
                    json={"prompt": prompt},
                    timeout=1200
                )
                print(f"[Flux Debug] HTTP status: {resp.status_code}")
                resp.raise_for_status()
                data = resp.json()
                predictions = data.get("predictions", [])
                if predictions:
                    pred = predictions[0]
                    img_b64 = None
                    if isinstance(pred, dict):
                        img_b64 = pred.get("image_b64", pred)
                    elif isinstance(pred, list) and len(pred) > 0:
                        img_b64 = pred[0]
                    else:
                        img_b64 = pred
                        
                    if isinstance(img_b64, dict):
                        img_b64 = list(img_b64.values())[0]
                    img_data = base64.b64decode(img_b64)
                    image = Image.open(BytesIO(img_data))
                    image.save(output_path)
                    print(f"[Flux Debug] Saved image via custom HTTP -> {output_path}")
                    return True
            except Exception as e:
                print(f"[Flux Debug] Custom HTTP call failed: {e}")
                return False

        endpoint = aiplatform.Endpoint(endpoint_id)
        instances = [{"prompt": prompt}]

        # --- Try dedicated endpoint DNS directly via HTTP (most reliable) ---
        dedicated_dns = None
        try:
            dedicated_dns = endpoint.gca_resource.dedicated_endpoint_dns
            print(f"[Flux Debug] dedicated_endpoint_dns = {dedicated_dns}")
        except Exception as e:
            print(f"[Flux Debug] Could not get dedicated_endpoint_dns: {e}")

        if dedicated_dns:
            try:
                from google.auth import default as ga_default
                from google.auth.transport.requests import Request as GARequest
                creds, _ = ga_default(scopes=["https://www.googleapis.com/auth/cloud-platform"])
                creds.refresh(GARequest())
                predict_url = f"https://{dedicated_dns}/v1/{endpoint_id}:predict"
                print(f"[Flux Debug] Calling dedicated URL: {predict_url}")
                resp = req_lib.post(
                    predict_url,
                    json={"instances": instances},
                    headers={"Authorization": f"Bearer {creds.token}", "Content-Type": "application/json"},
                    timeout=600
                )
                print(f"[Flux Debug] HTTP status: {resp.status_code}")
                resp.raise_for_status()
                data = resp.json()
                predictions = data.get("predictions", [])
                print(f"[Flux Debug] predictions count: {len(predictions)}")
                if predictions:
                    pred = predictions[0]
                    img_b64 = pred[0] if isinstance(pred, list) else pred
                    img_data = base64.b64decode(img_b64)
                    image = Image.open(BytesIO(img_data))
                    image.save(output_path)
                    print(f"[Flux Debug] Saved image via dedicated HTTP -> {output_path}")
                    return True
            except Exception as e:
                print(f"[Flux Debug] Dedicated HTTP call failed: {e}, falling back to SDK")

        # --- Fallback: SDK with use_dedicated_endpoint=True ---
        print(f"[Flux Debug] Trying SDK predict with use_dedicated_endpoint=True")
        response = endpoint.predict(instances=instances, use_dedicated_endpoint=True)
        print(f"[Flux Debug] SDK predictions count: {len(response.predictions) if response.predictions else 0}")
        if response and hasattr(response, "predictions") and response.predictions:
            pred = response.predictions[0]
            img_b64 = None
            if isinstance(pred, dict):
                for key in ("image_b64", "output", "images", "image", "b64_json", "generated_image"):
                    if key in pred:
                        val = pred[key]
                        img_b64 = val[0] if isinstance(val, list) else val
                        break
            elif isinstance(pred, str):
                img_b64 = pred
            if img_b64:
                img_data = base64.b64decode(img_b64)
                image = Image.open(BytesIO(img_data))
                image.save(output_path)
                return True

        print(f"[Flux Debug] All methods failed. Full response: {response}")
        raise ValueError("[Error] FLUX endpoint returned empty/null predictions. Fallbacks are disabled to ensure strictly open source model usage.")

    raise ValueError("Vertex Endpoint ID is required for FLUX image generation to ensure strictly open source model usage.")


def generate_audio_vertex(text: str, ref_audio_path: str, ref_text: str, output_path: str, endpoint_id: str, speed: str = "1.0"):
    """Calls a custom Vertex AI Endpoint or HTTP API running F5-TTS."""
    if not endpoint_id:
        raise ValueError("VERTEX_TTS_ENDPOINT_ID is required for offloaded audio generation.")
        
    if endpoint_id.startswith("http://") or endpoint_id.startswith("https://"):
        import requests
        print(f"      [HTTP Worker] Sending TTS request to custom HTTP API: {endpoint_id}...")
        
        # New API Logic (supports the new 8081 endpoint)
        if "/clone" in endpoint_id or ":8081" in endpoint_id:
            base_url = endpoint_id.replace("/clone", "").rstrip("/")
            voice_name = os.path.basename(ref_audio_path).split('.')[0]
            
            # 1. Upload voice reference (ignoring 409 if already exists, or just fire and forget)
            import subprocess
            import tempfile
            
            try:
                # Fire and forget upload using curl
                cmd_upload = [
                    "curl", "-X", "POST", f"{base_url}/voices",
                    "-F", f"audio=@{ref_audio_path}",
                    "-F", f"name={voice_name}",
                    "-F", f"transcript={ref_text}",
                    "-s"
                ]
                subprocess.run(cmd_upload, timeout=10, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except Exception as e:
                print(f"Failed to upload voice {voice_name}: {e}")
                
            # 2. Generate Cloned Audio (with retries for intermittent 503s)
            import time
            import json
            for attempt in range(8):
                try:
                    payload = json.dumps({
                        "voice_name": voice_name,
                        "text": text,
                        "language": "English",
                        "temperature": 0.6,
                        "top_p": 0.95,
                        "top_k": 50
                    })
                    
                    cmd_clone = [
                        "curl", "-X", "POST", f"{base_url}/clone",
                        "-H", "Content-Type: application/json",
                        "-d", payload,
                        "--output", output_path,
                        "-s", "-w", "%{http_code}"
                    ]
                    
                    result = subprocess.run(cmd_clone, capture_output=True, text=True, timeout=1200)
                    http_code = result.stdout.strip()
                    
                    if http_code == "200":
                        # Verify the file is valid and not 0 bytes
                        if os.path.exists(output_path) and os.path.getsize(output_path) > 1000:
                            return True
                        else:
                            print(f"HTTP TTS Error (Attempt {attempt+1}): Returned 200 but file is empty or corrupted.")
                    else:
                        print(f"HTTP TTS Error (Attempt {attempt+1}): {http_code}")
                except subprocess.TimeoutExpired:
                    print(f"HTTP TTS Timeout Error (Attempt {attempt+1}): Server froze for 1200 seconds (20 mins). Retrying...")
                except Exception as e:
                    print(f"HTTP TTS Connection Error (Attempt {attempt+1}): {e}")
                    
                if attempt < 7:
                    time.sleep(3)
                    
            print(f"Failed to generate TTS after 3 attempts for text: {text[:30]}...")
            return False
        else:
            # Legacy logic
            data = {
                "gen_text": text,
                "ref_text": ref_text,
                "speed": speed
            }
            try:
                with open(ref_audio_path, "rb") as f_ref:
                    files = {
                        "ref_audio": (os.path.basename(ref_audio_path), f_ref, "audio/wav")
                    }
                    response = requests.post(endpoint_id, data=data, files=files, timeout=300)
                if response.status_code == 200:
                    with open(output_path, "wb") as f_out:
                        f_out.write(response.content)
                    return True
                else:
                    print(f"HTTP TTS Error: {response.status_code} - {response.text}")
                    return False
            except Exception as e:
                print(f"HTTP TTS Connection Error: {e}")
                return False

    location = None
    if endpoint_id and "locations/" in endpoint_id:
        try:
            parts = endpoint_id.split("/")
            location = parts[parts.index("locations") + 1]
        except Exception:
            pass
    init_vertex_ai(location=location)
    endpoint = aiplatform.Endpoint(endpoint_id)
    
    with open(ref_audio_path, "rb") as f:
        ref_audio_b64 = base64.b64encode(f.read()).decode("utf-8")
        
    instances = [{
        "text": text,
        "ref_audio_b64": ref_audio_b64,
        "ref_text": ref_text,
        "speed": speed
    }]
    
    print(f"      [Vertex Worker] Sending TTS request to custom endpoint: {endpoint_id}...")
    use_dedicated = getattr(endpoint.gca_resource, "dedicated_endpoint_enabled", False)
    response = endpoint.predict(instances=instances, use_dedicated_endpoint=use_dedicated)
    
    if response and hasattr(response, "predictions") and response.predictions and "audio_b64" in response.predictions[0]:
        audio_data = base64.b64decode(response.predictions[0]["audio_b64"])
        with open(output_path, "wb") as f:
            f.write(audio_data)
        return True
    return False

def generate_video_vertex(video_path: str, audio_path: str, output_path: str, endpoint_id: str):
    """Calls a custom Vertex AI Endpoint or HTTP URL running LatentSync."""
    if not endpoint_id:
        raise ValueError("VERTEX_SYNC_ENDPOINT_ID is required for offloaded video syncing.")
        
    with open(video_path, "rb") as f:
        video_b64 = base64.b64encode(f.read()).decode("utf-8")
    with open(audio_path, "rb") as f:
        audio_b64 = base64.b64encode(f.read()).decode("utf-8")
        
    print(f"      [Vertex Worker] Sending LatentSync request to custom endpoint: {endpoint_id}...")
    
    if endpoint_id.startswith("http://") or endpoint_id.startswith("https://"):
        import requests as req_lib
        payload = {
            "video_b64": video_b64,
            "audio_b64": audio_b64,
            "inference_steps": 20,
            "guidance_scale": 1.5
        }
        try:
            resp = req_lib.post(endpoint_id, json=payload, timeout=1200)
            resp.raise_for_status()
            data = resp.json()
            predictions = data.get("predictions", [])
            
            video_b64_out = None
            if predictions and ("video_b64" in predictions[0] or "synced_video_b64" in predictions[0]):
                key = "video_b64" if "video_b64" in predictions[0] else "synced_video_b64"
                video_b64_out = predictions[0][key]
            else:
                video_b64_out = data.get("video_b64", data.get("synced_video_b64"))
                
            if video_b64_out:
                video_data = base64.b64decode(video_b64_out)
                with open(output_path, "wb") as f:
                    f.write(video_data)
                return True
            else:
                print(f"[LatentSync] Invalid response format from VM: {str(data)[:200]}")
                return False
        except Exception as e:
            print(f"[LatentSync] HTTP request failed: {e}")
            return False
    else:
        # Fallback to standard Vertex AI SDK
        location = None
        if "locations/" in endpoint_id:
            try:
                parts = endpoint_id.split("/")
                location = parts[parts.index("locations") + 1]
            except Exception:
                pass
        init_vertex_ai(location=location)
        endpoint = aiplatform.Endpoint(endpoint_id)
        
        instances = [{
            "video_b64": video_b64,
            "audio_b64": audio_b64
        }]
        
        # This might require a larger timeout for long videos!
        use_dedicated = getattr(endpoint.gca_resource, "dedicated_endpoint_enabled", False)
        response = endpoint.predict(instances=instances, use_dedicated_endpoint=use_dedicated)
        
        if "synced_video_b64" in response.predictions[0] or "video_b64" in response.predictions[0]:
            key = "video_b64" if "video_b64" in response.predictions[0] else "synced_video_b64"
            video_data = base64.b64decode(response.predictions[0][key])
            with open(output_path, "wb") as f:
                f.write(video_data)
            return True
        return False
