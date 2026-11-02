"""Object storage (S3, or MinIO in development).

Files are written under keys like ``avatars/orgs/<id>/<uuid>.png`` and read
by browsers from ``MEDIA_BASE_URL/<key>``: the Vite proxy in development,
a public bucket or CDN in production.
"""

from functools import lru_cache

import json

import boto3
from botocore.client import BaseClient
from botocore.exceptions import ClientError

from app.core.config import settings


@lru_cache
def _client() -> BaseClient:
    return boto3.client(
        "s3",
        endpoint_url=settings.AWS_ENDPOINT_URL,
        region_name=settings.AWS_REGION,
    )


@lru_cache
def _ensure_bucket() -> None:
    # Only the local MinIO starts empty; real buckets come with the infra.
    if not settings.AWS_ENDPOINT_URL:
        return
    bucket = settings.S3_BUCKET_MEDIA
    try:
        _client().head_bucket(Bucket=bucket)
    except ClientError:
        _client().create_bucket(Bucket=bucket)
    # browsers load avatars straight from the bucket, so they must be public
    _client().put_bucket_policy(
        Bucket=bucket,
        Policy=json.dumps({
            "Version": "2012-10-17",
            "Statement": [{
                "Effect": "Allow",
                "Principal": "*",
                "Action": "s3:GetObject",
                "Resource": f"arn:aws:s3:::{bucket}/avatars/*",
            }],
        }),
    )


def put_object(key: str, data: bytes, content_type: str) -> None:
    _ensure_bucket()
    _client().put_object(
        Bucket=settings.S3_BUCKET_MEDIA,
        Key=key,
        Body=data,
        ContentType=content_type,
        CacheControl="public, max-age=31536000, immutable",  # keys are never reused
    )


def delete_object(key: str) -> None:
    _client().delete_object(Bucket=settings.S3_BUCKET_MEDIA, Key=key)


def public_url(key: str) -> str:
    return f"{settings.MEDIA_BASE_URL.rstrip('/')}/{key}"
