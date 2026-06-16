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
    )
    return client, ENDPOINT_ID

# Ensure upload directory exists
os.makedirs(UPLOAD_DIR, exist_ok=True)

# Image assets configuration
IMAGE_DIR = os.path.join(BASE_DIR, "assets", "images")
os.makedirs(IMAGE_DIR, exist_ok=True)

