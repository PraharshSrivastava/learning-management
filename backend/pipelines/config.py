import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
COURSES_FILE = os.path.join(BASE_DIR, "courses.json")

import requests

# New LLM Client Generator using Qwen Model Endpoint
def get_llm_client(purpose: str = None):
    if purpose in ("slides", "scripts"):
        BASE_URL = "http://34.180.105.203:8002/v1"
        MODEL_NAME = "google/gemma-4-E4B-it"
    else:
        BASE_URL = "http://35.238.33.238:8001/v1"
        MODEL_NAME = "Qwen/Qwen3-8B"
    return BASE_URL, MODEL_NAME

# Ensure upload directory exists
os.makedirs(UPLOAD_DIR, exist_ok=True)

# Image assets configuration
IMAGE_DIR = os.path.join(BASE_DIR, "assets", "images")
os.makedirs(IMAGE_DIR, exist_ok=True)


class ChatCompletionMessage:
    def __init__(self, content):
        self.content = content


class ChatCompletionChoice:
    def __init__(self, content, finish_reason):
        self.message = ChatCompletionMessage(content)
        self.finish_reason = finish_reason


class ChatCompletionResponse:
    def __init__(self, choices):
        self.choices = choices


def _post_chat_completion(client, model, messages, response_format, temperature, max_tokens):
    url = f"{client}/chat/completions"
    headers = {
        "Content-Type": "application/json"
    }
    payload = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens
    }
    if response_format:
        payload["response_format"] = response_format
        
    response = requests.post(url, headers=headers, json=payload, timeout=600.0)
    
    # vLLM returns a 400 Bad Request error if context window is exceeded
    if response.status_code == 400:
        raise ValueError(response.text)
        
    response.raise_for_status()
    resp_json = response.json()
    
    choices = []
    for choice_data in resp_json.get("choices", []):
        msg_data = choice_data.get("message", {})
        content = msg_data.get("content", "")
        finish_reason = choice_data.get("finish_reason", "stop")
        choices.append(ChatCompletionChoice(content, finish_reason))
        
    return ChatCompletionResponse(choices)


def safe_chat_completion(client, model, messages, response_format=None, temperature=0.2, default_max_tokens=4096):
    """
    Wrapper around vLLM direct chat endpoint completions that:
    1. Dynamically estimates input tokens based on message characters.
    2. Clamps max_tokens to prevent exceeding the model's 32768 context window.
    3. Catches bad request errors due to context limit and retries with a lower max_tokens value.
    """
    import re
    # Estimate input tokens: ~3.7 characters per token
    total_chars = sum(len(msg.get("content", "")) for msg in messages)
    estimated_input = int(total_chars / 3.7)
    
    # 32768 is the max context window for Qwen/Qwen3-8B
    max_context = 32768
    
    # Safety buffer of 150 tokens
    available_tokens = max_context - estimated_input - 150
    # Set a floor of 256 tokens so we don't request negative or zero tokens
    max_tokens = min(default_max_tokens, max(256, available_tokens))
    
    print(f"    [LLM] Requesting completion with estimated input={estimated_input} tokens, max_tokens={max_tokens} (default={default_max_tokens})")
    
    try:
        return _post_chat_completion(
            client=client,
            model=model,
            messages=messages,
            response_format=response_format,
            temperature=temperature,
            max_tokens=max_tokens
        )
    except Exception as e:
        err_str = str(e)
        if "max_tokens" in err_str or "context length" in err_str or "400" in err_str or "token" in err_str:
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
            return _post_chat_completion(
                client=client,
                model=model,
                messages=messages,
                response_format=response_format,
                temperature=temperature,
                max_tokens=max_tokens
            )
        else:
            raise e

# F5-TTS Configuration
TTS_ENDPOINT = os.environ.get("VERTEX_TTS_ENDPOINT_ID", "http://34.180.105.203:8005/api/tts")
# Selected voice profile for TTS generation. Choose from: 'ref_shreya' (female), 'ref_nitin' (male), or 'ref_srk' (male narrator)
TTS_VOICE = os.environ.get("TTS_VOICE", "ref_srk")

VOICE_TRANSCRIPTS = {
    "ref_srk": "I was born in a refugee colony in the capital city of India, New Delhi, and my father was a freedom fighter.",
    "ref_nitin": "mutual funds in an actual are professionally managed investments, wearing a money is pooled and invested across different markets by experts. No daily tracking, no stocks speaking, no asset allocation stress.",
    "ref_shreya": "We all work hard to earn and save while trying to do the right thing with money. Yet it never seems to grow the way we expect."
}




