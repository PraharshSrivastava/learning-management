"""Validated application settings loaded from the process environment."""

from __future__ import annotations

import os
from pathlib import Path

from pydantic import BaseModel, Field, field_validator, model_validator

_BACKEND_DIR = Path(__file__).resolve().parents[2]


def _load_dotenv_values(path: Path) -> dict[str, str]:
    """Read a small, dependency-free `.env` file; shell variables take precedence."""
    values = dict(os.environ)
    if not path.is_file():
        return values

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].strip()
        key, separator, value = line.partition("=")
        if not separator or not key.strip():
            continue
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        values.setdefault(key.strip(), value)
    return values


class Settings(BaseModel):
    """Runtime configuration shared by the API and generation pipeline."""

    app_env: str = "development"
    log_level: str = "INFO"
    backend_dir: Path = _BACKEND_DIR
    db_path: Path = _BACKEND_DIR / "storage" / "lms.db"
    storage_dir: Path = _BACKEND_DIR / "storage"
    generated_dir: Path = _BACKEND_DIR / "storage" / "generated"
    upload_dir: Path = _BACKEND_DIR / "storage" / "uploads"
    image_dir: Path = _BACKEND_DIR / "storage" / "generated" / "images"
    audio_dir: Path = _BACKEND_DIR / "storage" / "generated" / "audio"
    slide_dir: Path = _BACKEND_DIR / "storage" / "generated" / "slides"
    video_dir: Path = _BACKEND_DIR / "storage" / "generated" / "videos"
    static_dir: Path = _BACKEND_DIR / "app" / "static"
    template_dir: Path = _BACKEND_DIR / "app" / "templates" / "slides"
    prompt_dir: Path = _BACKEND_DIR / "app" / "prompts"
    cors_allowed_origins: tuple[str, ...] = (
        "http://localhost:3000",
        "http://localhost:8080",
    )

    llm_base_url: str = "http://35.238.33.238:4000/v1"
    llm_api_key: str | None = "sk-test-litellm-gateway"
    llm_model_name: str = "gemma-4-e4b"
    llm_context_window: int = Field(default=8128, ge=256)

    tts_endpoint: str = "http://35.238.33.238:8081"
    tts_voice: str = "sana"
    tts_temperature: float = Field(default=0.6, ge=0, le=2)
    tts_speed: float = Field(default=0.9, gt=0)
    slide_transition_pause_seconds: float = Field(default=1.0, ge=0)
    thumbnail_endpoint: str = "http://35.238.33.238:4000/v1/images/generations"
    thumbnail_model: str = "ernie-image"
    thumbnail_api_key: str | None = None
    thumbnail_connect_timeout: float = Field(default=60, gt=0)
    thumbnail_read_timeout: float = Field(default=180, gt=0)
    thumbnails_enabled: bool = True
    generation_max_concurrency: int = Field(default=1, ge=1, le=8)

    @field_validator("cors_allowed_origins", mode="before")
    @classmethod
    def split_origins(cls, value: object) -> tuple[str, ...]:
        if isinstance(value, str):
            origins = tuple(origin.strip() for origin in value.split(",") if origin.strip())
            return origins or ("http://localhost:3000", "http://localhost:8080")
        if isinstance(value, (list, tuple)):
            return tuple(str(origin).strip() for origin in value if str(origin).strip()) or (
                "http://localhost:3000",
                "http://localhost:8080",
            )
        return ("http://localhost:3000", "http://localhost:8080")

    @model_validator(mode="after")
    def validate_production_contract(self) -> "Settings":
        if self.app_env.lower() != "production":
            return self
        missing = []
        if not self.llm_api_key:
            missing.append("LLM_API_KEY")
        if "*" in self.cors_allowed_origins:
            missing.append("CORS_ALLOWED_ORIGINS (explicit origins required)")
        if not self.llm_base_url:
            missing.append("LLM_BASE_URL")
        if not self.tts_endpoint:
            missing.append("TTS_ENDPOINT")
        if missing:
            raise ValueError("Incomplete production configuration: " + ", ".join(missing))
        return self

    @classmethod
    def from_environment(cls) -> "Settings":
        values = _load_dotenv_values(_BACKEND_DIR / ".env")
        backend_dir = Path(values.get("LMS_BACKEND_DIR", _BACKEND_DIR)).resolve()
        storage_dir = Path(values.get("LMS_STORAGE_DIR", backend_dir / "storage")).resolve()
        generated_dir = Path(values.get("LMS_GENERATED_DIR", storage_dir / "generated")).resolve()
        static_dir = Path(values.get("LMS_STATIC_DIR", backend_dir / "app" / "static")).resolve()
        template_dir = Path(
            values.get("LMS_TEMPLATE_DIR", backend_dir / "app" / "templates" / "slides")
        ).resolve()
        prompt_dir = Path(values.get("LMS_PROMPTS_DIR", backend_dir / "app" / "prompts")).resolve()
        return cls.model_validate(
            {
                "app_env": values.get("APP_ENV", "development"),
                "log_level": values.get("LOG_LEVEL", "INFO"),
                "backend_dir": backend_dir,
                "db_path": Path(
                    values.get("LMS_DB_PATH", backend_dir / "storage" / "lms.db")
                ).resolve(),
                "storage_dir": storage_dir,
                "generated_dir": generated_dir,
                "upload_dir": Path(values.get("LMS_UPLOAD_DIR", storage_dir / "uploads")).resolve(),
                "image_dir": Path(values.get("LMS_IMAGE_DIR", generated_dir / "images")).resolve(),
                "audio_dir": Path(values.get("LMS_AUDIO_DIR", generated_dir / "audio")).resolve(),
                "slide_dir": Path(values.get("LMS_SLIDE_DIR", generated_dir / "slides")).resolve(),
                "video_dir": Path(values.get("LMS_VIDEO_DIR", generated_dir / "videos")).resolve(),
                "static_dir": static_dir,
                "template_dir": template_dir,
                "prompt_dir": prompt_dir,
                "cors_allowed_origins": values.get(
                    "CORS_ALLOWED_ORIGINS",
                    "http://localhost:3000,http://localhost:8080",
                ),
                "llm_base_url": values.get("LLM_BASE_URL", "http://35.238.33.238:4000/v1"),
                "llm_api_key": values.get("LLM_API_KEY")
                or values.get("LITELLM_API_KEY")
                or "sk-test-litellm-gateway",
                "llm_model_name": values.get("LLM_MODEL_NAME", "gemma-4-e4b"),
                "llm_context_window": values.get("LLM_CONTEXT_WINDOW", "8128"),
                "tts_endpoint": values.get(
                    "TTS_ENDPOINT",
                    "http://35.238.33.238:8081",
                ),
                "tts_voice": values.get("TTS_VOICE", "sana"),
                "tts_temperature": values.get("TTS_TEMPERATURE", "0.6"),
                "tts_speed": values.get("TTS_SPEED", "0.9"),
                "slide_transition_pause_seconds": values.get(
                    "SLIDE_TRANSITION_PAUSE_SECONDS", "1.0"
                ),
                "thumbnail_endpoint": values.get(
                    "COURSE_THUMBNAIL_ENDPOINT",
                    "http://35.238.33.238:4000/v1/images/generations",
                ),
                "thumbnail_model": values.get("COURSE_THUMBNAIL_MODEL", "ernie-image"),
                "thumbnail_api_key": values.get("COURSE_THUMBNAIL_API_KEY")
                or values.get("LLM_API_KEY")
                or values.get("LITELLM_API_KEY")
                or "sk-test-litellm-gateway",
                "thumbnail_connect_timeout": values.get(
                    "COURSE_THUMBNAIL_CONNECT_TIMEOUT",
                    "60",
                ),
                "thumbnail_read_timeout": values.get(
                    "COURSE_THUMBNAIL_READ_TIMEOUT",
                    "180",
                ),
                "thumbnails_enabled": values.get("COURSE_THUMBNAILS_ENABLED", "true"),
                "generation_max_concurrency": values.get("GENERATION_MAX_CONCURRENCY", "1"),
            }
        )


settings = Settings.from_environment()
