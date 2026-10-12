"""
backend/app/utils/file_validator.py
------------------------------------
File validation: size limits, allowed extensions, magic number checks.
"""

from pathlib import Path
from fastapi import HTTPException, UploadFile

from app.core.config import MAX_FILE_SIZE_MB, ALLOWED_EXTENSIONS

# Magic bytes of the binary spreadsheet formats
MAGIC_BYTES: dict[str, bytes] = {
    ".xlsx": b"PK\x03\x04",                          # Office Open XML (zip)
    ".xls":  b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1",    # legacy Excel (OLE2)
}


def _verify_content(filename: str, ext: str, header: bytes) -> None:
    """Reject files whose content doesn't match their extension (e.g. a renamed image)."""
    magic = MAGIC_BYTES.get(ext)
    if magic is not None:
        if not header.startswith(magic):
            raise HTTPException(
                status_code=415,
                detail=f"File '{filename}' does not look like a valid {ext} spreadsheet.",
            )
        return

    # CSV: must be plain text
    if b"\x00" in header:
        raise HTTPException(
            status_code=415,
            detail=f"File '{filename}' does not look like a valid CSV (binary content found).",
        )


async def validate_and_save(upload: UploadFile, dest_dir: Path) -> Path:
    """
    Validate an uploaded file (extension, size, magic bytes)
    and save it to dest_dir. Returns the saved path.
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

    _verify_content(upload.filename or "file", ext, content[:512])

    # Save
    dest_dir.mkdir(parents=True, exist_ok=True)
    safe_name  = Path(upload.filename or "upload").name
    saved_path = dest_dir / safe_name

    # Avoid overwrite collisions
    counter = 1
    while saved_path.exists():
        stem   = Path(safe_name).stem
        saved_path = dest_dir / f"{stem}_{counter}{ext}"
        counter += 1

    saved_path.write_bytes(content)
    return saved_path
