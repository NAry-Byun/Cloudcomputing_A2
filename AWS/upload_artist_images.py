import os
import json
import mimetypes
from urllib.parse import urlparse

import boto3
import requests
from botocore.exceptions import ClientError

AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")
BUCKET_NAME = os.environ.get("S3_BUCKET_NAME", "musicly-images")
SONGS_FILE = os.environ.get("SONGS_FILE", "2026a2_songs.json")
OUTPUT_FILE = os.environ.get("OUTPUT_FILE", "2026a2_songs_with_s3.json")

s3 = boto3.client("s3", region_name=AWS_REGION)

def slugify(text):
    text = text.strip().lower()
    return "".join(c if c.isalnum() else "-" for c in text).strip("-")

def guess_extension(url, content_type=None):
    path = urlparse(url).path
    ext = os.path.splitext(path)[1].lower()
    if ext in [".jpg", ".jpeg", ".png", ".webp", ".gif"]:
        return ext
    if content_type:
        guessed = mimetypes.guess_extension(content_type.split(";")[0].strip())
        if guessed:
            return guessed
    return ".jpg"

def ensure_bucket_exists():
    try:
        s3.head_bucket(Bucket=BUCKET_NAME)
        print(f"Bucket '{BUCKET_NAME}' already exists.")
    except ClientError:
        print(f"Creating bucket '{BUCKET_NAME}'...")
        if AWS_REGION == "us-east-1":
            s3.create_bucket(Bucket=BUCKET_NAME)
        else:
            s3.create_bucket(
                Bucket=BUCKET_NAME,
                CreateBucketConfiguration={"LocationConstraint": AWS_REGION},
            )
        print("Bucket created.")

def make_s3_url(bucket, region, key):
    return f"https://{bucket}.s3.{region}.amazonaws.com/{key}"

def main():
    ensure_bucket_exists()

    with open(SONGS_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    songs = data.get("songs", [])
    if not songs:
        print("No songs found in JSON.")
        return

    seen_urls = {}
    uploaded_count = 0

    for song in songs:
        image_url = song.get("img_url", "").strip()
        artist = song.get("artist", "").strip() or "unknown-artist"

        if not image_url:
            song["img_url"] = ""
            continue

        if image_url in seen_urls:
            song["img_url"] = seen_urls[image_url]
            continue

        try:
            print(f"Downloading image for: {artist}")
            response = requests.get(image_url, timeout=20)
            response.raise_for_status()

            content_type = response.headers.get("Content-Type", "image/jpeg")
            ext = guess_extension(image_url, content_type)
            object_key = f"artists/{slugify(artist)}{ext}"

            s3.put_object(
                Bucket=BUCKET_NAME,
                Key=object_key,
                Body=response.content,
                ContentType=content_type,
            )

            s3_url = make_s3_url(BUCKET_NAME, AWS_REGION, object_key)
            song["img_url"] = s3_url
            seen_urls[image_url] = s3_url
            uploaded_count += 1

            print(f"Uploaded to S3: {s3_url}")

        except Exception as e:
            print(f"Failed for {artist}: {e}")
            song["img_url"] = ""

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump({"songs": songs}, f, indent=2, ensure_ascii=False)

    print(f"\nDone. {uploaded_count} unique images uploaded.")
    print(f"Updated JSON saved as: {OUTPUT_FILE}")

if __name__ == "__main__":
    main()
