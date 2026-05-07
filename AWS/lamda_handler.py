import json
import os
import boto3
from boto3.dynamodb.conditions import Key
from botocore.exceptions import ClientError

REGION       = os.environ.get("AWS_REGION",        "us-east-1")
ENDPOINT_URL = os.environ.get("DYNAMODB_ENDPOINT", None)
S3_BUCKET    = os.environ.get("S3_BUCKET",         "musicly-images-nary2026")

_kw = dict(region_name=REGION)
if ENDPOINT_URL:
    _kw["endpoint_url"] = ENDPOINT_URL

dynamodb    = boto3.resource("dynamodb", **_kw)
users_table = dynamodb.Table("Users")
music_table = dynamodb.Table("Music")
sub_table   = dynamodb.Table("UserSubscriptions")
s3_client   = boto3.client("s3", region_name=REGION)

CORS_HEADERS = {
    "Content-Type":                 "application/json",
    "Access-Control-Allow-Origin":  "*",
    "Access-Control-Allow-Methods": "GET,POST,DELETE,OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type,Authorization",
}

def ok(body, status=200):
    return {
        "statusCode": status,
        "headers":    CORS_HEADERS,
        "body":       json.dumps(body, default=str),
    }

def err(msg, status=400):
    return ok({"error": msg}, status)


def presign_url(img_url, expires=3600):
    if not img_url:
        return ""
    try:
        if ".amazonaws.com/" in img_url:
            key = img_url.split(".amazonaws.com/", 1)[-1].split("?")[0]
        else:
            key = img_url.split("?")[0]
        return s3_client.generate_presigned_url(
            "get_object",
            Params={"Bucket": S3_BUCKET, "Key": key},
            ExpiresIn=expires,
        )
    except Exception:
        return img_url


def with_presigned(songs):
    for s in songs:
        if s.get("img_url"):
            s["img_url"] = presign_url(s["img_url"])
    return songs


def get_all_users():
    resp  = users_table.scan()
    items = resp.get("Items", [])
    while "LastEvaluatedKey" in resp:
        resp   = users_table.scan(ExclusiveStartKey=resp["LastEvaluatedKey"])
        items += resp.get("Items", [])
    return ok({"users": items, "count": len(items)})


def get_user_by_username(username):
    resp = users_table.get_item(Key={"username": username})
    item = resp.get("Item")
    if not item:
        return err(f"User '{username}' not found.", 404)
    return ok(item)


def get_user_by_email(email):
    resp  = users_table.query(
        IndexName="EmailIndex",
        KeyConditionExpression=Key("email").eq(email),
    )
    items = resp.get("Items", [])
    if not items:
        return err(f"No user found with email '{email}'.", 404)
    return ok(items[0])


def create_user(body):
    required = {"username", "email", "password_hash", "full_name"}
    missing  = required - body.keys()
    if missing:
        return err(f"Missing fields: {missing}")

    existing = users_table.query(
        IndexName="EmailIndex",
        KeyConditionExpression=Key("email").eq(body["email"]),
    ).get("Items", [])

    if existing:
        return err("The email already exists", 409)

    try:
        users_table.put_item(
            Item=body,
            ConditionExpression="attribute_not_exists(username)",
        )
        return ok({"message": f"User '{body['username']}' created."}, 201)
    except ClientError as e:
        if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
            return err(f"Username '{body['username']}' already exists.", 409)
        raise


def delete_user(username):
    resp = users_table.delete_item(
        Key={"username": username},
        ReturnValues="ALL_OLD",
    )
    if not resp.get("Attributes"):
        return err(f"User '{username}' not found.", 404)
    return ok({"message": f"User '{username}' deleted."})


def get_songs(params):
    artist = params.get("artist")
    album  = params.get("album")
    year   = params.get("year")

    if artist and year:
        resp  = music_table.query(
            IndexName="ArtistYearIndex",
            KeyConditionExpression=Key("artist").eq(artist) & Key("year").eq(year),
        )
        return ok({"songs": with_presigned(resp.get("Items", [])), "source": "LSI:ArtistYearIndex"})

    if artist:
        resp  = music_table.query(
            KeyConditionExpression=Key("artist").eq(artist),
        )
        return ok({"songs": with_presigned(resp.get("Items", [])), "source": "base_table:artist"})

    if album:
        resp  = music_table.query(
            IndexName="AlbumIndex",
            KeyConditionExpression=Key("album").eq(album),
        )
        return ok({"songs": with_presigned(resp.get("Items", [])), "source": "GSI:AlbumIndex"})

    if year:
        resp  = music_table.query(
            IndexName="YearIndex",
            KeyConditionExpression=Key("year").eq(year),
        )
        return ok({"songs": with_presigned(resp.get("Items", [])), "source": "GSI:YearIndex"})

    items = []
    resp  = music_table.scan()
    items += resp.get("Items", [])
    while "LastEvaluatedKey" in resp:
        resp   = music_table.scan(ExclusiveStartKey=resp["LastEvaluatedKey"])
        items += resp.get("Items", [])
    return ok({"songs": with_presigned(items), "count": len(items), "source": "scan:all"})


def get_song(artist, title_album):
    resp = music_table.get_item(Key={"artist": artist, "title_album": title_album})
    item = resp.get("Item")
    if not item:
        return err("Song not found.", 404)
    with_presigned([item])
    return ok(item)


def create_song(body):
    required = {"artist", "title", "album"}
    missing  = required - body.keys()
    if missing:
        return err(f"Missing fields: {missing}")
    if "title_album" not in body:
        body["title_album"] = f"{body['title']}#{body['album']}"
    try:
        music_table.put_item(
            Item=body,
            ConditionExpression="attribute_not_exists(artist)",
        )
        return ok({"message": "Song created.", "title_album": body["title_album"]}, 201)
    except ClientError as e:
        if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
            return err("Song already exists.", 409)
        raise


def delete_song(artist, title_album):
    resp = music_table.delete_item(
        Key={"artist": artist, "title_album": title_album},
        ReturnValues="ALL_OLD",
    )
    if not resp.get("Attributes"):
        return err("Song not found.", 404)
    return ok({"message": "Song deleted."})


def get_subscriptions(username):
    if not username:
        return err("Query parameter 'username' is required.")

    resp  = sub_table.query(
        KeyConditionExpression=Key("username").eq(username),
    )
    items = resp.get("Items", [])

    while "LastEvaluatedKey" in resp:
        resp   = sub_table.query(
            KeyConditionExpression=Key("username").eq(username),
            ExclusiveStartKey=resp["LastEvaluatedKey"],
        )
        items += resp.get("Items", [])

    for item in items:
        if not item.get("img_url") and item.get("artist") and item.get("title_album"):
            music_resp = music_table.get_item(
                Key={"artist": item["artist"], "title_album": item["title_album"]}
            )
            music_item = music_resp.get("Item", {})
            if music_item.get("img_url"):
                item["img_url"] = music_item["img_url"]

    return ok({"subscriptions": with_presigned(items), "count": len(items)})


def create_subscription(body):
    required = {"username", "title_album"}
    missing  = required - body.keys()
    if missing:
        return err(f"Missing fields: {missing}")

    if body.get("img_url") and ("X-Amz-Signature" in body["img_url"] or "AWSAccessKeyId" in body["img_url"]):
        body["img_url"] = body["img_url"].split("?")[0]

    sub_table.put_item(Item=body)
    return ok({"message": f"Subscribed to '{body.get('title', body['title_album'])}'."}, 201)


def delete_subscription(username, title_album):
    resp = sub_table.delete_item(
        Key={"username": username, "title_album": title_album},
        ReturnValues="ALL_OLD",
    )
    if not resp.get("Attributes"):
        return err("Subscription not found.", 404)
    return ok({"message": "Subscription removed."})


def lambda_handler(event, context):
    from urllib.parse import unquote
    method      = event.get("httpMethod", "GET").upper()
    resource    = event.get("resource", "")
    raw_params  = event.get("pathParameters") or {}
    path_params = {k: unquote(v) for k, v in raw_params.items()}
    qs_params   = event.get("queryStringParameters") or {}
    body_raw    = event.get("body") or "{}"

    if method == "OPTIONS":
        return ok({})

    try:
        body = json.loads(body_raw) if body_raw else {}
    except json.JSONDecodeError:
        return err("Invalid JSON body.", 400)

    if resource == "/users":
        if method == "GET":   return get_all_users()
        if method == "POST":  return create_user(body)

    if resource == "/users/by-email":
        if method == "GET":
            return get_user_by_email(qs_params.get("email", ""))

    if resource == "/users/{username}":
        username = path_params.get("username", "")
        if method == "GET":    return get_user_by_username(username)
        if method == "DELETE": return delete_user(username)

    if resource == "/songs":
        if method == "GET":  return get_songs(qs_params)
        if method == "POST": return create_song(body)

    if resource == "/songs/{artist}/{title_album}":
        artist      = path_params.get("artist", "")
        title_album = path_params.get("title_album", "")
        if method == "GET":    return get_song(artist, title_album)
        if method == "DELETE": return delete_song(artist, title_album)

    if resource == "/subscriptions":
        if method == "GET":
            return get_subscriptions(qs_params.get("username", ""))
        if method == "POST":
            return create_subscription(body)

    if resource == "/subscriptions/{username}/{title_album}":
        username    = path_params.get("username", "")
        title_album = path_params.get("title_album", "")
        if method == "DELETE":
            return delete_subscription(username, title_album)

    return err(f"No handler for {method} {resource}", 404)
