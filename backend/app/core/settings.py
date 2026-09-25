"""Validated application settings loaded from the process environment."""

from __future__ import annotations

import os
from email.utils import getaddresses
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, Field, field_validator, model_validator

_BACKEND_DIR = Path(__file__).resolve().parents[2]


def is_single_mailbox(value: str | None) -> bool:
    """Accept one plain mailbox, never a display name or address list."""
    if not value or value != value.strip() or value.count("@") != 1:
        return False
    if any(char.isspace() or ord(char) < 32 or ord(char) == 127 for char in value):
        return False
    parsed = getaddresses([value])
    return len(parsed) == 1 and parsed[0] == ("", value)


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
    llm_api_key: str | None = None
    llm_model_name: str = "gemma-4-e4b"
    llm_context_window: int = Field(default=100000, ge=256)
    llm_max_input_tokens: int = Field(default=87000, ge=256)
    llm_max_output_tokens: int = Field(default=12000, ge=256)

    langfuse_enabled: bool = False
    langfuse_host: str | None = None
    langfuse_public_key: str | None = None
    langfuse_secret_key: str | None = None
    langfuse_environment: str = "development"
    langfuse_release: str | None = None
    langfuse_capture_content: bool = False
    langfuse_capture_max_chars: int = Field(default=12000, ge=100, le=100000)
    langfuse_timeout_seconds: int = Field(default=5, ge=1, le=60)

    tts_endpoint: str = "http://35.238.33.238:8081"
    tts_voice: str = "priyanka"
    tts_temperature: float = Field(default=0.6, ge=0, le=2)
    tts_speed: float = Field(default=0.9, gt=0)
    slide_transition_pause_seconds: float = Field(default=1.0, ge=0)
    thumbnail_endpoint: str = "http://35.238.33.238:4000/v1/images/generations"
    thumbnail_model: str = "z-image-turbo"
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
    directory_sync_time: str = "09:10"
    directory_sync_timezone: str = "Asia/Kolkata"
    email_delivery_mode: str = "disabled"
    email_scheduler_enabled: bool = True
    email_scheduler_interval_seconds: float = Field(default=300, gt=0)
    email_worker_batch_size: int = Field(default=25, ge=1, le=200)
    email_max_attempts: int = Field(default=5, ge=1, le=20)
    email_retry_delay_seconds: float = Field(default=300, gt=0)
    email_lock_timeout_seconds: float = Field(default=600, gt=0)
    email_due_soon_days: int = Field(default=2, ge=1, le=30)
    email_assignment_reminder_days: int = Field(default=5, ge=1, le=90)
    email_overdue_repeat_days: int = Field(default=2, ge=1, le=30)
    email_notification_timezone: str = "Asia/Kolkata"
    email_digest_send_time: str = "09:00"
    email_due_soon_digest_interval_hours: int = Field(default=24, ge=1, le=168)
    email_completion_digest_interval_hours: int = Field(default=24, ge=1, le=168)
    email_test_mode: bool = False
    email_test_assignment_reminder_minutes: int = Field(default=5, ge=1, le=1440)
    email_test_due_soon_window_minutes: int = Field(default=7, ge=1, le=1440)
    email_test_overdue_repeat_minutes: int = Field(default=5, ge=1, le=1440)
    email_test_digest_delay_minutes: int = Field(default=1, ge=1, le=60)
    email_subject_prefix: str = ""
    email_recipient_allowlist: tuple[str, ...] = ()
    email_from_email: str | None = None
    email_from_name: str = "Learning Management System"
    smtp_host: str | None = None
    smtp_port: int = Field(default=587, ge=1, le=65535)
    smtp_username: str | None = None
    smtp_password: str | None = None
    smtp_use_starttls: bool = True
    smtp_use_ssl: bool = False
    smtp_timeout_seconds: float = Field(default=30, gt=0)
    lms_public_url: str | None = None
    lms_employee_public_url: str | None = None
    lms_trainer_public_url: str | None = None

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

    @field_validator("email_recipient_allowlist", mode="before")
    @classmethod
    def split_email_allowlist(cls, value: object) -> tuple[str, ...]:
        if value is None:
            return ()
        if isinstance(value, str):
            return tuple(email.strip().lower() for email in value.split(",") if email.strip())
        if isinstance(value, (list, tuple, set)):
            return tuple(str(email).strip().lower() for email in value if str(email).strip())
        return ()

    @model_validator(mode="after")
    def validate_production_contract(self) -> "Settings":
        email_errors = []
        if self.email_delivery_mode not in {"log", "smtp", "disabled"}:
            email_errors.append("EMAIL_DELIVERY_MODE must be log, smtp, or disabled")
        if self.smtp_use_ssl and self.smtp_use_starttls:
            email_errors.append("SMTP_USE_SSL and SMTP_USE_STARTTLS cannot both be true")
        if bool(self.smtp_username) != bool(self.smtp_password):
            email_errors.append("SMTP_USERNAME and SMTP_PASSWORD must be configured together")
        if self.email_from_email and not is_single_mailbox(self.email_from_email):
            email_errors.append("EMAIL_FROM_EMAIL must be a valid email address")
        if self.email_delivery_mode == "smtp":
            if not self.smtp_host:
                email_errors.append("SMTP_HOST is required in smtp mode")
            if not self.email_from_email:
                email_errors.append("EMAIL_FROM_EMAIL is required in smtp mode")
            if not (self.smtp_use_starttls or self.smtp_use_ssl):
                email_errors.append("SMTP mode requires SMTP_USE_STARTTLS or SMTP_USE_SSL")
        invalid_allowlist = [
            email for email in self.email_recipient_allowlist if not is_single_mailbox(email)
        ]
        if invalid_allowlist:
            email_errors.append("EMAIL_RECIPIENT_ALLOWLIST contains an invalid email address")
        if self.email_test_mode:
            if not self.email_recipient_allowlist:
                email_errors.append("EMAIL_RECIPIENT_ALLOWLIST is required in test mode")
            if not self.email_subject_prefix.strip():
                email_errors.append("EMAIL_SUBJECT_PREFIX is required in test mode")
        try:
            ZoneInfo(self.email_notification_timezone)
        except ZoneInfoNotFoundError:
            email_errors.append("EMAIL_NOTIFICATION_TIMEZONE must be a valid IANA timezone")
        try:
            digest_hour, digest_minute = (
                int(part) for part in self.email_digest_send_time.split(":", 1)
            )
            if not (0 <= digest_hour <= 23 and 0 <= digest_minute <= 59):
                raise ValueError
        except (AttributeError, TypeError, ValueError):
            email_errors.append("EMAIL_DIGEST_SEND_TIME must use 24-hour HH:MM format")
        if email_errors:
            raise ValueError("Invalid email configuration: " + ", ".join(email_errors))

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
                "llm_api_key": values.get("LLM_API_KEY") or values.get("LITELLM_API_KEY") or None,
                "llm_model_name": values.get("LLM_MODEL_NAME", "gemma-4-e4b"),
                "llm_context_window": values.get("LLM_CONTEXT_WINDOW", "100000"),
                "llm_max_input_tokens": values.get("LLM_MAX_INPUT_TOKENS", "87000"),
                "llm_max_output_tokens": values.get("LLM_MAX_OUTPUT_TOKENS", "12000"),
                "langfuse_enabled": values.get("LANGFUSE_ENABLED", "false"),
                "langfuse_host": values.get("LANGFUSE_BASE_URL")
                or values.get("LANGFUSE_HOST")
                or None,
                "langfuse_public_key": values.get("LANGFUSE_PUBLIC_KEY") or None,
                "langfuse_secret_key": values.get("LANGFUSE_SECRET_KEY") or None,
                "langfuse_environment": values.get("LANGFUSE_ENVIRONMENT", "development"),
                "langfuse_release": values.get("LANGFUSE_RELEASE") or None,
                "langfuse_capture_content": values.get("LANGFUSE_CAPTURE_CONTENT", "false"),
                "langfuse_capture_max_chars": values.get(
                    "LANGFUSE_CAPTURE_MAX_CHARS",
                    "12000",
                ),
                "langfuse_timeout_seconds": values.get("LANGFUSE_TIMEOUT_SECONDS", "5"),
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
                "thumbnail_model": values.get("COURSE_THUMBNAIL_MODEL", "z-image-turbo"),
                "thumbnail_api_key": values.get("COURSE_THUMBNAIL_API_KEY")
                or values.get("LLM_API_KEY")
                or values.get("LITELLM_API_KEY")
                or None,
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
                "directory_sync_time": values.get("DIRECTORY_SYNC_TIME", "09:10"),
                "directory_sync_timezone": values.get("DIRECTORY_SYNC_TIMEZONE", "Asia/Kolkata"),
                "email_delivery_mode": values.get("EMAIL_DELIVERY_MODE", "disabled"),
                "email_scheduler_enabled": values.get("EMAIL_SCHEDULER_ENABLED", "true"),
                "email_scheduler_interval_seconds": values.get(
                    "EMAIL_SCHEDULER_INTERVAL_SECONDS",
                    "300",
                ),
                "email_worker_batch_size": values.get("EMAIL_WORKER_BATCH_SIZE", "25"),
                "email_max_attempts": values.get("EMAIL_MAX_ATTEMPTS", "5"),
                "email_retry_delay_seconds": values.get("EMAIL_RETRY_DELAY_SECONDS", "300"),
                "email_lock_timeout_seconds": values.get("EMAIL_LOCK_TIMEOUT_SECONDS", "600"),
                "email_due_soon_days": values.get("EMAIL_DUE_SOON_DAYS", "2"),
                "email_assignment_reminder_days": values.get(
                    "EMAIL_ASSIGNMENT_REMINDER_DAYS",
                    "5",
                ),
                "email_overdue_repeat_days": values.get(
                    "EMAIL_OVERDUE_REPEAT_DAYS",
                    "2",
                ),
                "email_notification_timezone": values.get(
                    "EMAIL_NOTIFICATION_TIMEZONE", "Asia/Kolkata"
                ),
                "email_digest_send_time": values.get("EMAIL_DIGEST_SEND_TIME", "09:00"),
                "email_due_soon_digest_interval_hours": values.get(
                    "EMAIL_DUE_SOON_DIGEST_INTERVAL_HOURS", "24"
                ),
                "email_completion_digest_interval_hours": values.get(
                    "EMAIL_COMPLETION_DIGEST_INTERVAL_HOURS", "24"
                ),
                "email_test_mode": values.get("EMAIL_TEST_MODE", "false"),
                "email_test_assignment_reminder_minutes": values.get(
                    "EMAIL_TEST_ASSIGNMENT_REMINDER_MINUTES", "5"
                ),
                "email_test_due_soon_window_minutes": values.get(
                    "EMAIL_TEST_DUE_SOON_WINDOW_MINUTES", "7"
                ),
                "email_test_overdue_repeat_minutes": values.get(
                    "EMAIL_TEST_OVERDUE_REPEAT_MINUTES", "5"
                ),
                "email_test_digest_delay_minutes": values.get(
                    "EMAIL_TEST_DIGEST_DELAY_MINUTES", "1"
                ),
                "email_subject_prefix": values.get("EMAIL_SUBJECT_PREFIX", ""),
                "email_recipient_allowlist": values.get("EMAIL_RECIPIENT_ALLOWLIST", ""),
                "email_from_email": values.get("EMAIL_FROM_EMAIL") or None,
                "email_from_name": values.get("EMAIL_FROM_NAME", "Learning Management System"),
                "smtp_host": values.get("SMTP_HOST") or None,
                "smtp_port": values.get("SMTP_PORT", "587"),
                "smtp_username": values.get("SMTP_USERNAME") or None,
                "smtp_password": values.get("SMTP_PASSWORD") or None,
                "smtp_use_starttls": values.get("SMTP_USE_STARTTLS", "true"),
                "smtp_use_ssl": values.get("SMTP_USE_SSL", "false"),
                "smtp_timeout_seconds": values.get("SMTP_TIMEOUT_SECONDS", "30"),
                "lms_public_url": values.get("LMS_PUBLIC_URL") or None,
                "lms_employee_public_url": values.get("LMS_EMPLOYEE_PUBLIC_URL") or None,
                "lms_trainer_public_url": values.get("LMS_TRAINER_PUBLIC_URL") or None,
            }
        )


settings = Settings.from_environment()
