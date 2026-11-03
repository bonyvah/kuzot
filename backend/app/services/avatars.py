"""Avatars for organizations and workspaces: an emoji or an uploaded image.

A record holds at most one of the two; setting one clears the other.
"""

import logging
import uuid

from fastapi import HTTPException, UploadFile, status
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import storage
from app.models.competitor import Competitor
from app.models.organization import Organization
from app.models.user import User
from app.models.workspace import Workspace

log = logging.getLogger(__name__)

MAX_IMAGE_BYTES = 2 * 1024 * 1024
MAX_EMOJI_CHARS = 16  # room for ZWJ sequences, flags and skin tones

# Detected from the file's first bytes, never from the client's content type.
# SVG is deliberately absent: it can carry scripts.
_SIGNATURES: list[tuple[bytes, int, str, str]] = [
    (b"\x89PNG\r\n\x1a\n", 0, "image/png", "png"),
    (b"\xff\xd8\xff", 0, "image/jpeg", "jpg"),
    (b"GIF87a", 0, "image/gif", "gif"),
    (b"GIF89a", 0, "image/gif", "gif"),
    (b"WEBP", 8, "image/webp", "webp"),
]

Avatarable = Organization | Workspace | Competitor | User


def validate_emoji(value: str) -> str:
    emoji = value.strip()
    if (
        not emoji
        or len(emoji) > MAX_EMOJI_CHARS
        or any(ch.isspace() or ch.isascii() for ch in emoji)
    ):
        raise ValueError("Pick a single emoji")
    return emoji


def _sniff(data: bytes) -> tuple[str, str]:
    for magic, offset, content_type, ext in _SIGNATURES:
        if data[offset : offset + len(magic)] == magic:
            if ext == "webp" and data[:4] != b"RIFF":
                continue
            return content_type, ext
    raise HTTPException(
        status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
        detail="Upload a PNG, JPEG, WebP or GIF image",
    )


async def _drop_image(record: Avatarable) -> None:
    key, record.avatar_key = record.avatar_key, None
    if key:
        try:
            await run_in_threadpool(storage.delete_object, key)
        except Exception:
            # an orphaned file is harmless; failing the request isn't worth it
            log.warning("Could not delete avatar %s", key, exc_info=True)


async def set_emoji(db: AsyncSession, record: Avatarable, emoji: str) -> Avatarable:
    await _drop_image(record)
    record.avatar_emoji = emoji
    await db.commit()
    await db.refresh(record)
    return record


async def set_image(
    db: AsyncSession, record: Avatarable, upload: UploadFile, prefix: str
) -> Avatarable:
    data = await upload.read(MAX_IMAGE_BYTES + 1)
    if len(data) > MAX_IMAGE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail="Images must be 2 MB or smaller",
        )
    content_type, ext = _sniff(data)

    # a fresh key per upload, so cached old images never shadow new ones
    key = f"avatars/{prefix}/{record.id}/{uuid.uuid4().hex}.{ext}"
    try:
        await run_in_threadpool(storage.put_object, key, data, content_type)
    except Exception:
        log.exception("Could not upload avatar %s", key)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Image storage is unavailable, try again shortly",
        )

    await _drop_image(record)
    record.avatar_key = key
    record.avatar_emoji = None
    await db.commit()
    await db.refresh(record)
    return record


async def clear(db: AsyncSession, record: Avatarable) -> Avatarable:
    await _drop_image(record)
    record.avatar_emoji = None
    await db.commit()
    await db.refresh(record)
    return record


async def delete_files(record: Avatarable) -> None:
    """Remove a record's stored image before the record itself is deleted."""
    await _drop_image(record)


async def delete_workspace_files(workspace: Workspace) -> None:
    """A workspace's image and its competitors' (they're deleted with it)."""
    for competitor in workspace.competitors:
        await _drop_image(competitor)
    await _drop_image(workspace)
