"""
backend/app/utils/file_validator.py
------------------------------------
File validation: size limits, allowed extensions, magic number checks.
Returns file type so the correct extraction path is chosen.
"""

import os
from pathlib import Path
from typing import Literal
from fastapi import HTTPException, UploadFile

from app.core.config import MAX_FILE_SIZE_MB, ALLOWED_EXTENSIONS

# Magic bytes for format verification
MAGIC_BYTES: dict[bytes, str] = {
    b"\xff\xd8\xff":        "image",   # JPEG
    b"\x89PNG\r\n":         "image",   # PNG
    b"%PDF":                "pdf",     # PDF
    b"PK\x03\x04":          "excel",   # XLSX (zip-based)
}

FileType = Literal["image", "pdf", "excel", "csv"]


def detect_file_type(filename: str, header: bytes) -> FileType:
    """Detect file type from magic bytes + extension."""
    for magic, ftype in MAGIC_BYTES.items():
        if header.startswith(magic):
            return ftype  

    ext = Path(filename).suffix.lower()
    if ext == ".csv":
        return "csv"
    if ext in (".xlsx", ".xls"):
        return "excel"
    if ext in (".jpg", ".jpeg", ".png"):
        return "image"
    if ext == ".pdf":
        return "pdf"

    raise HTTPException(
        status_code=415,
        detail=f"Unsupported file type: {ext}. Allowed: {', '.join(ALLOWED_EXTENSIONS)}"
    )


async def validate_and_save(upload: UploadFile, dest_dir: Path) -> tuple[Path, FileType]:
    """
    Validate an uploaded file (size, extension, magic bytes)
    and save it to dest_dir. Returns (saved_path, file_type).
    """
    ext = Path(upload.filename or "file").suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=415,
            detail=f"File '{upload.filename}': extension '{ext}' not allowed. "
                   f"Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}"
        )

    content = await upload.read()

    # Size check
    size_mb = len(content) / (1024 * 1024)
    if size_mb > MAX_FILE_SIZE_MB:
        raise HTTPException(
            status_code=413,
            detail=f"File '{upload.filename}' is {size_mb:.1f} MB. "
                   f"Maximum allowed: {MAX_FILE_SIZE_MB} MB."
        )

    # Magic byte check
    file_type = detect_file_type(upload.filename or "file", content[:8])

    # Save
    dest_dir.mkdir(parents=True, exist_ok=True)
    safe_name  = Path(upload.filename or "upload").name
    saved_path = dest_dir / safe_name

    # Avoid overwrite collisions
    counter = 1
    while saved_path.exists():
        stem   = Path(upload.filename or "upload").stem
        saved_path = dest_dir / f"{stem}_{counter}{ext}"
        counter += 1

    saved_path.write_bytes(content)
    return saved_path, file_type
