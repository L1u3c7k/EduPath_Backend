import io
import logging
import uuid

import httpx
from PIL import Image, ImageOps
from supabase import ClientOptions, create_client, Client

from src.config import settings

logger = logging.getLogger(__name__)

# Single client instance reused across all requests (handles HTTP pooling)
supabase_client: Client = create_client(
    settings.SUPABASE_URL,
    settings.SUPABASE_KEY,
    options=ClientOptions(storage_client_timeout=60),
)


def public_image_url(filename: str | None) -> str | None:
    if not filename:
        return None
    if filename.startswith(("http://", "https://")):
        return filename
    base = settings.SUPABASE_URL.rstrip("/")
    return (
        f"{base}/storage/v1/object/public/"
        f"{settings.SUPABASE_BUCKET}/{filename.lstrip('/')}"
    )


def _object_path(filename: str) -> str:
    prefix = (
        f"{settings.SUPABASE_URL.rstrip('/')}/storage/v1/object/public/"
        f"{settings.SUPABASE_BUCKET}/"
    )
    if filename.startswith(prefix):
        return filename[len(prefix) :]
    if filename.startswith(("http://", "https://")):
        return filename.rsplit("/", 1)[-1]
    return filename


def process_profile_image(content: bytes, user_id: str | None = None) -> str:
    """
    Process an image in memory (orient, resize, convert to JPEG) 
    and upload it to Supabase Storage.
    """
    if not content:
        raise ValueError("Empty image file")

    # 1. Process image in memory
    with Image.open(io.BytesIO(content)) as original:
        img = ImageOps.exif_transpose(original)
        img = ImageOps.fit(img, (300, 300), method=Image.Resampling.LANCZOS)

        # Convert palette/transparency to standard RGB JPEG format
        if img.mode != "RGB":
            img = img.convert("RGB")

        filename = f"{uuid.uuid4().hex}.jpg"
        path = f"{user_id}/{filename}" if user_id else filename

        buffer = io.BytesIO()
        img.save(buffer, format="JPEG", quality=85, optimize=True)
        file_bytes = buffer.getvalue()

    # 2. Upload using shared storage client
    storage = supabase_client.storage.from_(settings.SUPABASE_BUCKET)

    last_error: Exception | None = None
    for attempt in range(2):
        try:
            storage.upload(
                path=path,
                file=file_bytes,
                file_options={
                    "content-type": "image/jpeg",
                    "upsert": "true",
                },
            )
            return path
        except (httpx.TimeoutException, httpx.TransportError, Exception) as err:
            last_error = err
            logger.warning("Storage upload attempt %s failed: %s", attempt + 1, err)

    if last_error:
        raise last_error
    raise RuntimeError("Storage upload failed unexpectedly")


def delete_profile_image(filename: str | None) -> None:
    """Delete a profile image from Supabase Storage."""
    if not filename:
        return

    path = _object_path(filename)
    try:
        supabase_client.storage.from_(settings.SUPABASE_BUCKET).remove([path])
    except Exception:
        logger.exception("Failed to delete profile image %s", path)