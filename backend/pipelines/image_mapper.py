import requests
from pydantic import BaseModel
from typing import List, Dict, Any
from pipelines.config import get_llm_client
from pipelines.prompts import IMAGE_SLIDE_MAPPING_PROMPT

class ImageMapping(BaseModel):
    image_id: str
    slide_index: int  # 1-based index in the flat list of slides for this module

class ImageMappingResult(BaseModel):
    mappings: List[ImageMapping]

def map_images_to_slides(course: Dict[str, Any]) -> Dict[str, Any]:
    """
    Backward-compatible pass-through. Image mapping is now handled inline during lesson generation.
    """
    print("  [IMAGE MAPPER] Images are already mapped inline. Skipping post-generation mapping.")
    return course
