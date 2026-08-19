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
    database_url: str | None = None
    storage_dir: Path = _BACKEND_DIR / "storage"
    generated_dir: Path = _BACKEND_DIR / "storage" / "generated"
    upload_dir: Path = _BACKEND_DIR / "storage" / "uploads"
    derived_document_dir: Path = _BACKEND_DIR / "storage" / "derived_documents"
    image_dir: Path = _BACKEND_DIR / "storage" / "generated" / "images"
    audio_dir: Path = _BACKEND_DIR / "storage" / "generated" / "audio"
    slide_dir: Path = _BACKEND_DIR / "storage" / "generated" / "slides"
    video_dir: Path = _BACKEND_DIR / "storage" / "generated" / "videos"
    static_dir: Path = _BACKEND_DIR / "app" / "static"
    template_dir: Path = _BACKEND_DIR / "app" / "templates" / "slides"
    prompt_dir: Path = _BACKEND_DIR / "app" / "prompts"
    libreoffice_executable: str = "soffice"
    document_conversion_timeout_seconds: float = Field(default=180, gt=0)
    cors_allowed_origins: tuple[str, ...] = (
        "http://localhost:3000",
        "http://localhost:8080",
    )

    llm_base_url: str = "http://35.238.33.238:4000/v1"
    llm_api_key: str | None = "sk-test-litellm-gateway"
    llm_model_name: str = "qwen3.6-35b"
    llm_enable_thinking: bool = False
    llm_context_window: int = Field(default=128000, ge=256)
    llm_max_input_tokens: int = Field(default=100000, ge=256)
    llm_max_output_tokens: int = Field(default=28000, ge=256)

    tts_endpoint: str = "http://35.238.33.238:8081"
    tts_voice: str = "priyanka"
    tts_temperature: float = Field(default=0.6, ge=0, le=2)
    tts_speed: float = Field(default=0.9, gt=0)
    slide_transition_pause_seconds: float = Field(default=1.0, ge=0)
    thumbnail_endpoint: str = "http://35.238.33.238:4000/v1/images/generations"
    thumbnail_model: str = "ernie-image"
    thumbnail_api_key: str | None = None
    thumbnail_connect_timeout: float = Field(default=60, gt=0)
    thumbnail_read_timeout: float = Field(default=500, gt=0)
    thumbnails_enabled: bool = True
    generation_max_concurrency: int = Field(default=1, ge=1, le=8)
    hub_launch_secret: str | None = None
    hub_trainer_app_key: str = "lms-trainer"
    hub_employee_app_key: str = "lms-employee"
    hub_trainer_cookie_name: str = "lms_trainer_hub"
    hub_employee_cookie_name: str = "lms_employee_hub"
    hub_launch_session_seconds: int = Field(default=28800, ge=60)
    hub_launch_dev_mode: bool = False
    hub_cookie_secure: bool = False
    directory_exports_base_url: str | None = None
    directory_exports_api_key: str | None = None
    directory_sync_admin_key: str | None = None
    directory_sync_timeout_seconds: float = Field(default=30, gt=0)
    directory_sync_page_limit: int = Field(default=100, ge=1, le=500)
    directory_sync_enabled: bool = False
    directory_sync_interval_hours: float = Field(default=24, gt=0)
    directory_sync_initial_delay_seconds: float = Field(default=0, ge=0)

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
        if not self.database_url:
            missing.append("DATABASE_URL")
        if "*" in self.cors_allowed_origins:
            missing.append("CORS_ALLOWED_ORIGINS (explicit origins required)")
        if not self.llm_base_url:
            missing.append("LLM_BASE_URL")
        if not self.tts_endpoint:
            missing.append("TTS_ENDPOINT")
        if not self.hub_launch_dev_mode:
            if not self.hub_launch_secret:
                missing.append("HUB_LAUNCH_SECRET")
            if not self.hub_trainer_app_key:
                missing.append("HUB_TRAINER_APP_KEY")
            if not self.hub_employee_app_key:
                missing.append("HUB_EMPLOYEE_APP_KEY")
        if self.directory_sync_enabled:
            if not self.directory_exports_base_url:
                missing.append("DIRECTORY_EXPORTS_BASE_URL")
            if not self.directory_exports_api_key:
                missing.append("DIRECTORY_EXPORTS_API_KEY")
            if not self.directory_sync_admin_key:
                missing.append("DIRECTORY_SYNC_ADMIN_KEY")
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
                "database_url": values.get("DATABASE_URL") or None,
                "storage_dir": storage_dir,
                "generated_dir": generated_dir,
                "upload_dir": Path(values.get("LMS_UPLOAD_DIR", storage_dir / "uploads")).resolve(),
                "derived_document_dir": Path(
                    values.get(
                        "LMS_DERIVED_DOCUMENT_DIR",
                        storage_dir / "derived_documents",
                    )
                ).resolve(),
                "image_dir": Path(values.get("LMS_IMAGE_DIR", generated_dir / "images")).resolve(),
                "audio_dir": Path(values.get("LMS_AUDIO_DIR", generated_dir / "audio")).resolve(),
                "slide_dir": Path(values.get("LMS_SLIDE_DIR", generated_dir / "slides")).resolve(),
                "video_dir": Path(values.get("LMS_VIDEO_DIR", generated_dir / "videos")).resolve(),
                "static_dir": static_dir,
                "template_dir": template_dir,
                "prompt_dir": prompt_dir,
                "libreoffice_executable": values.get("LIBREOFFICE_EXECUTABLE", "soffice"),
                "document_conversion_timeout_seconds": values.get(
                    "DOCUMENT_CONVERSION_TIMEOUT_SECONDS", "180"
                ),
                "cors_allowed_origins": values.get(
                    "CORS_ALLOWED_ORIGINS",
                    "http://localhost:3000,http://localhost:8080",
                ),
                "llm_base_url": values.get("LLM_BASE_URL", "http://35.238.33.238:4000/v1"),
                "llm_api_key": values.get("LLM_API_KEY")
                or values.get("LITELLM_API_KEY")
                or "sk-test-litellm-gateway",
                "llm_model_name": values.get("LLM_MODEL_NAME", "qwen3.6-35b"),
                "llm_enable_thinking": values.get("LLM_ENABLE_THINKING", "false"),
                "llm_context_window": values.get("LLM_CONTEXT_WINDOW", "128000"),
                "llm_max_input_tokens": values.get("LLM_MAX_INPUT_TOKENS", "100000"),
                "llm_max_output_tokens": values.get("LLM_MAX_OUTPUT_TOKENS", "28000"),
                "tts_endpoint": values.get(
                    "TTS_ENDPOINT",
                    "http://35.238.33.238:8081",
                ),
                "tts_voice": values.get("TTS_VOICE", "priyanka"),
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
                    "500",
                ),
                "thumbnails_enabled": values.get("COURSE_THUMBNAILS_ENABLED", "true"),
                "generation_max_concurrency": values.get("GENERATION_MAX_CONCURRENCY", "1"),
                "hub_launch_secret": values.get("HUB_LAUNCH_SECRET") or None,
                "hub_trainer_app_key": values.get("HUB_TRAINER_APP_KEY", "lms-trainer"),
                "hub_employee_app_key": values.get("HUB_EMPLOYEE_APP_KEY", "lms-employee"),
                "hub_trainer_cookie_name": values.get(
                    "HUB_TRAINER_COOKIE_NAME",
                    "lms_trainer_hub",
                ),
                "hub_employee_cookie_name": values.get(
                    "HUB_EMPLOYEE_COOKIE_NAME",
                    "lms_employee_hub",
                ),
                "hub_launch_session_seconds": values.get(
                    "HUB_LAUNCH_SESSION_SECONDS",
                    "28800",
                ),
                "hub_launch_dev_mode": values.get("HUB_LAUNCH_DEV_MODE", "false"),
                "hub_cookie_secure": values.get("HUB_COOKIE_SECURE", "false"),
                "directory_exports_base_url": values.get("DIRECTORY_EXPORTS_BASE_URL") or None,
                "directory_exports_api_key": values.get("DIRECTORY_EXPORTS_API_KEY") or None,
                "directory_sync_admin_key": values.get("DIRECTORY_SYNC_ADMIN_KEY") or None,
                "directory_sync_timeout_seconds": values.get(
                    "DIRECTORY_SYNC_TIMEOUT_SECONDS",
                    "30",
                ),
                "directory_sync_page_limit": values.get("DIRECTORY_SYNC_PAGE_LIMIT", "100"),
                "directory_sync_enabled": values.get("DIRECTORY_SYNC_ENABLED", "false"),
                "directory_sync_interval_hours": values.get(
                    "DIRECTORY_SYNC_INTERVAL_HOURS",
                    "24",
                ),
                "directory_sync_initial_delay_seconds": values.get(
                    "DIRECTORY_SYNC_INITIAL_DELAY_SECONDS",
                    "0",
                ),
            }
        )


settings = Settings.from_environment()
