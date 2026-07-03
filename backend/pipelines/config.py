import os
from core.config import BASE_DIR, UPLOAD_DIR, DRAFT_COURSES_FILE, PUBLISHED_COURSES_FILE, IMAGE_DIR

import requests

# LLM Endpoint Resolver — returns (base_url, model_name) for the given
# purpose. NOTE: this does NOT return a client object (e.g. not an OpenAI
# SDK client instance) — it returns a raw base-URL string and model-name
# string, which callers pass into safe_chat_completion() to make a direct
# HTTP request. Renamed from the old get_llm_client() to avoid implying
# this returns an actual client instance.
def get_llm_endpoint(purpose: str = None):
    if purpose in ("slides", "scripts", "quiz"):
        BASE_URL = "http://34.180.105.203:8002/v1"
        MODEL_NAME = "google/gemma-4-E4B-it"
    else:
        BASE_URL = "http://35.238.33.238:8001/v1"
        MODEL_NAME = "Qwen/Qwen3-8B"
    return BASE_URL, MODEL_NAME


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


def _post_chat_completion(base_url, model, messages, response_format, temperature, max_tokens):
    url = f"{base_url}/chat/completions"
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


def safe_chat_completion(base_url, model, messages, response_format=None, temperature=0.2, default_max_tokens=4096):
    """
    Wrapper around vLLM direct chat endpoint completions that:
    1. Dynamically estimates input tokens based on message characters.
    2. Clamps max_tokens to prevent exceeding the model's 32768 context window.
    3. Catches bad request errors due to context limit and retries with a lower max_tokens value.
    """
    import re
    total_chars = sum(len(msg.get("content", "")) for msg in messages)
    estimated_input = int(total_chars / 3.7)
    
    max_context = 32768
    available_tokens = max_context - estimated_input - 150
    max_tokens = min(default_max_tokens, max(256, available_tokens))
    
    print(f"    [LLM] Requesting completion with estimated input={estimated_input} tokens, max_tokens={max_tokens} (default={default_max_tokens})")
    
    try:
        return _post_chat_completion(
            base_url=base_url,
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
            
            match = re.search(r"request has (\d+) input tokens", err_str)
            if match:
                actual_input = int(match.group(1))
                max_tokens = max(256, max_context - actual_input - 100)
            else:
                max_tokens = 512
                
            print(f"    [INFO] Retrying with max_tokens={max_tokens}")
            return _post_chat_completion(
                base_url=base_url,
                model=model,
                messages=messages,
                response_format=response_format,
                temperature=temperature,
                max_tokens=max_tokens
            )
        else:
            raise e

TTS_ENDPOINT = os.environ.get("VERTEX_TTS_ENDPOINT_ID", "http://35.238.33.238:8081")
TTS_VOICE = os.environ.get("TTS_VOICE", "ref_srk")

VOICE_TRANSCRIPTS = {
    "ref_srk": "I was born in a refugee colony in the capital city of India, New Delhi, and my father was a freedom fighter.",
    "ref_nitin": "mutual funds in an actual are professionally managed investments, wearing a money is pooled and invested across different markets by experts. No daily tracking, no stocks speaking, no asset allocation stress.",
    "ref_shreya": "We all work hard to earn and save while trying to do the right thing with money. Yet it never seems to grow the way we expect."
}
