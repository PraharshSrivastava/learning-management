import os
from core.config import BASE_DIR, UPLOAD_DIR, DRAFT_COURSES_FILE, PUBLISHED_COURSES_FILE, IMAGE_DIR

import requests
import time
from pipelines.pipeline_runtime import retry

LITELLM_BASE_URL = "http://35.238.33.238:4000/v1"
LITELLM_API_KEY = "sk-test-litellm-gateway"
CHAT_MODEL_NAME = "gemma-4-e4b"
# The LiteLLM route for this model advertises an 8,128-token combined
# prompt-and-completion window.
CHAT_MODEL_CONTEXT_WINDOW = 8128

# LLM Endpoint Resolver — returns (base_url, model_name) for the given
# purpose. NOTE: this does NOT return a client object (e.g. not an OpenAI
# SDK client instance) — it returns a raw base-URL string and model-name
# string, which callers pass into safe_chat_completion() to make a direct
# HTTP request. Renamed from the old get_llm_client() to avoid implying
# this returns an actual client instance.
def get_llm_endpoint(purpose: str = None):
    return LITELLM_BASE_URL, CHAT_MODEL_NAME


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
    llm_api_key = os.environ.get("LLM_API_KEY") or os.environ.get("LITELLM_API_KEY") or LITELLM_API_KEY
    if llm_api_key:
        headers["Authorization"] = f"Bearer {llm_api_key}"
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


def safe_chat_completion(base_url, model, messages, response_format=None, temperature=0.2, default_max_tokens=4096,
                         course_id="unknown", stage="llm", module_number=None, attempts=3):
    """
    Wrapper around vLLM direct chat endpoint completions that:
    1. Dynamically estimates input tokens based on message characters.
    2. Clamps max_tokens to prevent exceeding the configured model context window.
    3. Catches bad request errors due to context limit and retries with a lower max_tokens value.
    """
    import re
    total_chars = sum(len(msg.get("content", "")) for msg in messages)
    # The provider counts the JSON response schema too. This estimate mirrors
    # its observed tokenisation more closely and reserves 100 tokens for it.
    estimated_input = int(total_chars / 6.0) + 100
    
    max_context = CHAT_MODEL_CONTEXT_WINDOW
    available_tokens = max_context - estimated_input - 150
    max_tokens = min(default_max_tokens, max(256, available_tokens))
    
    print(f"    [LLM] Requesting completion stage={stage} input={estimated_input} max_tokens={max_tokens} attempts={attempts}")

    def request_once():
        nonlocal max_tokens
        try:
            return _post_chat_completion(base_url, model, messages, response_format, temperature, max_tokens)
        except Exception as exc:
            err_str = str(exc)
            if "max_tokens" in err_str or "context length" in err_str or "token" in err_str:
                match = re.search(r"(?:request has|prompt contains at least) (\d+) input tokens", err_str)
                if match:
                    max_tokens = max(256, max_context - int(match.group(1)) - 100)
                    print(f"    [LLM] Retrying immediately with max_tokens={max_tokens}")
                    return _post_chat_completion(
                        base_url, model, messages, response_format, temperature, max_tokens
                    )
                max_tokens = 512
                print(f"    [LLM] Clamped max_tokens to {max_tokens} for next attempt")
            raise

    return retry(
        request_once, course_id=course_id, stage=stage, attempts=attempts, module_number=module_number,
    )

TTS_ENDPOINT = os.environ.get("VERTEX_TTS_ENDPOINT_ID", "https://7ly2ceze0uzno9-8081.proxy.runpod.net")
TTS_VOICE = os.environ.get("TTS_VOICE", "Ryan")
TTS_SPEED = float(os.environ.get("TTS_SPEED", "0.9"))
# The generated narration is intentionally 0.9x.  Player controls expose this
# mastered pace as the learner-facing 1x baseline.
SLIDE_TRANSITION_PAUSE_SECONDS = float(os.environ.get("SLIDE_TRANSITION_PAUSE_SECONDS", "1.0"))

VOICE_TRANSCRIPTS = {
    "ref_tejas": "hello my name is Tejas and I am interning at Phillip Capital in the AI labs department.",
    "ref_srk": "I was born in a refugee colony in the capital city of India, New Delhi, and my father was a freedom fighter.",
    "ref_nitin": "mutual funds in an actual are professionally managed investments, wearing a money is pooled and invested across different markets by experts. No daily tracking, no stocks speaking, no asset allocation stress.",
    "ref_shreya": "We all work hard to earn and save while trying to do the right thing with money. Yet it never seems to grow the way we expect."
}
