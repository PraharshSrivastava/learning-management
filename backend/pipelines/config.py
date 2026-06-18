import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
COURSES_FILE = os.path.join(BASE_DIR, "courses.json")

# New LLM Client Generator using Google Vertex AI Endpoint
def get_llm_client():
    import google.auth
    import google.auth.transport.requests
    from openai import OpenAI
    
    credentials, _ = google.auth.default(
        scopes=["https://www.googleapis.com/auth/cloud-platform"]
    )
    credentials.refresh(google.auth.transport.requests.Request())
    
    PROJECT_ID = "648401835410"
    LOCATION = "asia-northeast3"
    ENDPOINT_ID = "mg-endpoint-7503e251-1953-479a-9f35-797328944525"
    
    BASE_URL = (
        f"https://{ENDPOINT_ID}.{LOCATION}-{PROJECT_ID}.prediction.vertexai.goog"
        f"/v1/projects/{PROJECT_ID}/locations/{LOCATION}/endpoints/{ENDPOINT_ID}"
    )
    
    client = OpenAI(
        base_url=BASE_URL,
        api_key=credentials.token,
        timeout=600.0,
    )
    return client, ENDPOINT_ID

# Ensure upload directory exists
os.makedirs(UPLOAD_DIR, exist_ok=True)

# Image assets configuration
IMAGE_DIR = os.path.join(BASE_DIR, "assets", "images")
os.makedirs(IMAGE_DIR, exist_ok=True)


def safe_chat_completion(client, model, messages, response_format=None, temperature=0.2, default_max_tokens=4096):
    """
    Wrapper around client.chat.completions.create that:
    1. Dynamically estimates input tokens based on message characters.
    2. Clamps max_tokens to prevent exceeding the model's 8192 context window.
    3. Catches 400 bad request errors due to context limit and retries with a lower max_tokens value.
    """
    import re
    # Estimate input tokens: ~3.7 characters per token
    total_chars = sum(len(msg.get("content", "")) for msg in messages)
    estimated_input = int(total_chars / 3.7)
    
    # 8192 is the max context window
    max_context = 8192
    
    # Safety buffer of 150 tokens
    available_tokens = max_context - estimated_input - 150
    # Set a floor of 256 tokens so we don't request negative or zero tokens
    max_tokens = min(default_max_tokens, max(256, available_tokens))
    
    print(f"    [LLM] Requesting completion with estimated input={estimated_input} tokens, max_tokens={max_tokens} (default={default_max_tokens})")
    
    try:
        return client.chat.completions.create(
            model=model,
            messages=messages,
            response_format=response_format,
            temperature=temperature,
            max_tokens=max_tokens
        )
    except Exception as e:
        err_str = str(e)
        if "max_tokens" in err_str or "context length" in err_str or "400" in err_str:
            print(f"    [WARNING] LLM call failed with context/token limit error: {e}. Retrying with clamped max_tokens...")
            
            # Try to parse actual input tokens from the error message
            match = re.search(r"request has (\d+) input tokens", err_str)
            if match:
                actual_input = int(match.group(1))
                max_tokens = max(256, max_context - actual_input - 100)
            else:
                # Fallback to a safe low default
                max_tokens = 512
                
            print(f"    [INFO] Retrying with max_tokens={max_tokens}")
            return client.chat.completions.create(
                model=model,
                messages=messages,
                response_format=response_format,
                temperature=temperature,
                max_tokens=max_tokens
            )
        else:
            raise e


