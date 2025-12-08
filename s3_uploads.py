import boto3
import requests
import mimetypes
import uuid
import os
from flask import current_app

def upload_image_to_s3(file_or_url):
    """
    Accepts either:
    - a file upload (jpg/png)
    - a string URL of an image

    Returns a public S3 URL.
    """
    s3 = boto3.client(
        "s3",
        aws_access_key_id=current_app.config["AWS_ACCESS_KEY_ID"],
        aws_secret_access_key=current_app.config["AWS_SECRET_ACCESS_KEY"],
        region_name=current_app.config["AWS_REGION"],
    )

    bucket = current_app.config["AWS_S3_BUCKET"]

    # image URL
    if isinstance(file_or_url, str):
        response = requests.get(file_or_url)
        if response.status_code != 200:
            raise ValueError("Could not download image URL")
        file_bytes = response.content
        content_type = response.headers.get("Content-Type", "image/jpeg")

    # JPG, PNG, etc.
    else:
        file_bytes = file_or_url.read()
        content_type = file_or_url.mimetype or "image/jpeg"

    # Build filename
    extension = mimetypes.guess_extension(content_type) or ".jpg"
    filename = f"uploads/{uuid.uuid4()}{extension}"

    s3.put_object(
        Bucket=bucket,
        Key=filename,
        Body=file_bytes,
        ContentType=content_type,
        ACL="public-read"
    )

    return f"https://{bucket}.s3.amazonaws.com/{filename}"
