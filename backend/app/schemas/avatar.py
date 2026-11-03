from pydantic import BaseModel, ConfigDict, model_validator

from app.core import storage


class WithAvatar(BaseModel):
    """Public avatar fields for anything with avatar_emoji / avatar_key columns."""

    model_config = ConfigDict(from_attributes=True)

    avatar_emoji: str | None = None
    avatar_url: str | None = None

    @model_validator(mode="before")
    @classmethod
    def _avatar_url(cls, data):
        # the stored S3 key becomes the URL browsers load
        key = getattr(data, "avatar_key", None)
        if key is not None:
            data = {name: getattr(data, name) for name in cls.model_fields if hasattr(data, name)}
            data["avatar_url"] = storage.public_url(key)
        return data
