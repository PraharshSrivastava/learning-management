"""Small LibreOffice helper for converting Office docs to PDF."""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

from app.core.logging import generation_logger
from app.core.settings import settings

logger = generation_logger(__name__)


class DocumentConversionError(RuntimeError):
    """Raised when an Office document cannot be converted to PDF."""


def _resolve_libreoffice() -> str:
    for candidate in (
        settings.libreoffice_executable,
        "soffice",
        "libreoffice",
        r"C:\Program Files\LibreOffice\program\soffice.exe",
        r"C:\Program Files (x86)\LibreOffice\program\soffice.exe",
    ):
        resolved = shutil.which(candidate) or candidate
        if Path(resolved).is_file():
            return str(resolved)
    raise DocumentConversionError("LibreOffice is required to convert DOCX/PPTX files to PDF.")


def convert_office_to_pdf(source_path: Path, output_pdf: Path) -> Path:
    source = source_path.resolve()
    target = output_pdf.resolve()
    if not source.is_file():
        raise FileNotFoundError(f"Source document not found at {source}")
    if source.suffix.lower() not in {".docx", ".pptx"}:
        raise DocumentConversionError(f"Cannot convert {source.suffix} to PDF.")
    if target.is_file() and target.stat().st_mtime_ns >= source.stat().st_mtime_ns:
        return target

    target.parent.mkdir(parents=True, exist_ok=True)
    executable = _resolve_libreoffice()
    with tempfile.TemporaryDirectory(prefix="convert-", dir=target.parent) as temp_name:
        temp_dir = Path(temp_name)
        output_dir = temp_dir / "output"
        profile_dir = temp_dir / "profile"
        output_dir.mkdir()
        profile_dir.mkdir()
        command = [
            executable,
            "--headless",
            "--nologo",
            "--nodefault",
            "--nofirststartwizard",
            f"-env:UserInstallation={profile_dir.resolve().as_uri()}",
            "--convert-to",
            "pdf",
            "--outdir",
            str(output_dir),
            str(source),
        ]
        logger.info("document_pdf_conversion_started source=%s", source)
        try:
            completed = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=settings.document_conversion_timeout_seconds,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise DocumentConversionError("Document conversion timed out.") from exc
        except OSError as exc:
            raise DocumentConversionError(f"Failed to start LibreOffice: {exc}") from exc

        converted = output_dir / f"{source.stem}.pdf"
        if completed.returncode != 0 or not converted.is_file():
            detail = (completed.stderr or completed.stdout or "unknown error").strip()
            raise DocumentConversionError(f"LibreOffice conversion failed: {detail}")
        shutil.copyfile(converted, target)
        logger.info("document_pdf_conversion_completed source=%s target=%s", source, target)
        return target
