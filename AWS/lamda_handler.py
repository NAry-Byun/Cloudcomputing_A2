import json
import os
import boto3
from boto3.dynamodb.conditions import Key
from botocore.exceptions import ClientError
 
# ── Config ────────────────────────────────────────────────────────────────────
REGION       = os.environ.get("AWS_REGION",        "us-east-1")
ENDPOINT_URL = os.environ.get("DYNAMODB_ENDPOINT", None)
 
_kw = dict(region_name=REGION)
if ENDPOINT_URL:
    _kw["endpoint_url"] = ENDPOINT_URL
 
dynamodb       = boto3.resource("dynamodb", **_kw)
users_table    = dynamodb.Table("Users")
music_table    = dynamodb.Table("Music")
sub_table      = dynamodb.Table("UserSubscriptions")   # ← NEW
 
 
# ── CORS + response helpers ───────────────────────────────────────────────────
CORS_HEADERS = {
    "Content-Type":                     "application/json",
    "Access-Control-Allow-Origin":      "*",
    "Access-Control-Allow-Methods":     "GET,POST,DELETE,OPTIONS",
    "Access-Control-Allow-Headers":     "Content-Type,Authorization",
}
 
def ok(body, status=200):
    return {
        "statusCode": status,
        "headers":    CORS_HEADERS,
        "body":       json.dumps(body, default=str),
    }
 
def err(msg, status=400):
    return ok({"error": msg}, status)
 
 
# ══════════════════════════════════════════════════════════════════════════════
# USERS
# ══════════════════════════════════════════════════════════════════════════════
 
def get_all_users():
    """Scan — returns all users (small table, 10 rows)."""
    resp  = users_table.scan()
    items = resp.get("Items", [])
    while "LastEvaluatedKey" in resp:
        resp   = users_table.scan(ExclusiveStartKey=resp["LastEvaluatedKey"])
        items += resp.get("Items", [])
    return ok({"users": items, "count": len(items)})
 
 
def get_user_by_username(username):
    """GetItem by PK — O(1)."""
    resp = users_table.get_item(Key={"username": username})
    item = resp.get("Item")
    if not item:
        return err(f"User '{username}' not found.", 404)
    return ok(item)
 
 
def get_user_by_email(email):
    """Query GSI EmailIndex — login by email without a Scan."""
    resp  = users_table.query(
        IndexName="EmailIndex",
        KeyConditionExpression=Key("email").eq(email),
    )
    items = resp.get("Items", [])
    if not items:
        return err(f"No user found with email '{email}'.", 404)
    return ok(items[0])
 
 
def create_user(body):
    """PutItem with checks — rejects duplicate usernames and duplicate emails."""
    required = {"username", "email", "password_hash", "full_name"}
    missing  = required - body.keys()
    if missing:
        return err(f"Missing fields: {missing}")

    # check duplicate email first
    existing = users_table.query(
        IndexName="EmailIndex",
        KeyConditionExpression=Key("email").eq(body["email"]),
    ).get("Items", [])

    if existing:
        return err(f"Email '{body['email']}' already exists.", 409)

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
    """DeleteItem — returns 404 when user not found."""
    resp = users_table.delete_item(
        Key={"username": username},
        ReturnValues="ALL_OLD",
    )
    if not resp.get("Attributes"):
        return err(f"User '{username}' not found.", 404)
    return ok({"message": f"User '{username}' deleted."})
 
 
# ══════════════════════════════════════════════════════════════════════════════
# MUSIC
# ══════════════════════════════════════════════════════════════════════════════
 
def get_songs(params):
    """
    Dispatch to the right DynamoDB operation based on query params.
    artist + year  → LSI  ArtistYearIndex
    album          → GSI  AlbumIndex
    year           → GSI  YearIndex
    artist         → Query base table
    (none)         → Scan
    """
    artist = params.get("artist")
    album  = params.get("album")
    year   = params.get("year")
 
    if artist and year:
        resp = music_table.query(
            IndexName="ArtistYearIndex",
            KeyConditionExpression=Key("artist").eq(artist) & Key("year").eq(year),
        )
        return ok({"songs": resp.get("Items", []), "source": "LSI:ArtistYearIndex"})
 
    if artist:
        resp = music_table.query(
            KeyConditionExpression=Key("artist").eq(artist),
        )
        return ok({"songs": resp.get("Items", []), "source": "base_table:artist"})
 
    if album:
        resp = music_table.query(
            IndexName="AlbumIndex",
            KeyConditionExpression=Key("album").eq(album),
        )
        return ok({"songs": resp.get("Items", []), "source": "GSI:AlbumIndex"})
 
    if year:
        resp = music_table.query(
            IndexName="YearIndex",
            KeyConditionExpression=Key("year").eq(year),
        )
        return ok({"songs": resp.get("Items", []), "source": "GSI:YearIndex"})
 
    # full Scan — no filters
    items = []
    resp  = music_table.scan()
    items += resp.get("Items", [])
    while "LastEvaluatedKey" in resp:
        resp   = music_table.scan(ExclusiveStartKey=resp["LastEvaluatedKey"])
        items += resp.get("Items", [])
    return ok({"songs": items, "count": len(items), "source": "scan:all"})
 
 
def get_song(artist, title_album):
    """GetItem by full PK+SK."""
    resp = music_table.get_item(Key={"artist": artist, "title_album": title_album})
    item = resp.get("Item")
    if not item:
        return err(f"Song not found.", 404)
    return ok(item)
 
 
def create_song(body):
    """PutItem — prevents overwrite with condition expression."""
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
    """DeleteItem by PK+SK."""
    resp = music_table.delete_item(
        Key={"artist": artist, "title_album": title_album},
        ReturnValues="ALL_OLD",
    )
    if not resp.get("Attributes"):
        return err("Song not found.", 404)
    return ok({"message": f"Song deleted."})
 
 
# ══════════════════════════════════════════════════════════════════════════════
# SUBSCRIPTIONS  ← NEW
# ══════════════════════════════════════════════════════════════════════════════
#
# Table: UserSubscriptions
#   PK  username    (String)  — which user subscribed
#   SK  title_album (String)  — which song ("title#album")
#
# One user can subscribe to many songs.
# One song can be subscribed by many users.
# Querying by username returns exactly that user's list — no Scan needed.
 
def get_subscriptions(username):
    """
    GET /subscriptions?username=alice
    Query by PK (username) — returns only this user's subscriptions.
    New users return an empty list — never an error.
    """
    if not username:
        return err("Query parameter 'username' is required.")
 
    resp  = sub_table.query(
        KeyConditionExpression=Key("username").eq(username),
    )
    items = resp.get("Items", [])
 
    # paginate if needed (rare but correct)
    while "LastEvaluatedKey" in resp:
        resp   = sub_table.query(
            KeyConditionExpression=Key("username").eq(username),
            ExclusiveStartKey=resp["LastEvaluatedKey"],
        )
        items += resp.get("Items", [])
 
    return ok({"subscriptions": items, "count": len(items)})
 
 
def create_subscription(body):
    """
    POST /subscriptions
    PutItem — saves a song subscription for a user.
    If the user subscribes to the same song twice, it is silently overwritten
    (idempotent — safe to call multiple times).
 
    Required fields: username, title_album
    Optional extras: title, artist, album, year, img_url
    """
    required = {"username", "title_album"}
    missing  = required - body.keys()
    if missing:
        return err(f"Missing fields: {missing}")
 
    sub_table.put_item(Item=body)
    return ok({
        "message": f"Subscribed to '{body.get('title', body['title_album'])}'."
    }, 201)
 
 
def delete_subscription(username, title_album):
    """
    DELETE /subscriptions/{username}/{title_album}
    DeleteItem — removes the subscription for this user+song pair.
    Returns 404 if the subscription didn't exist.
    """
    resp = sub_table.delete_item(
        Key={"username": username, "title_album": title_album},
        ReturnValues="ALL_OLD",
    )
    if not resp.get("Attributes"):
        return err("Subscription not found.", 404)
    return ok({"message": "Subscription removed."})
 
 
# ══════════════════════════════════════════════════════════════════════════════
# LAMBDA ENTRY POINT
# ══════════════════════════════════════════════════════════════════════════════
 
def lambda_handler(event, context):
    method      = event.get("httpMethod", "GET").upper()
    resource    = event.get("resource", "")
    path_params = event.get("pathParameters") or {}
    qs_params   = event.get("queryStringParameters") or {}
    body_raw    = event.get("body") or "{}"
 
    # handle CORS preflight for all routes
    if method == "OPTIONS":
        return ok({})
 
    try:
        body = json.loads(body_raw) if body_raw else {}
    except json.JSONDecodeError:
        return err("Invalid JSON body.", 400)
 
    # ── /users ────────────────────────────────────────────────────────────────
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
 
    # ── /songs ────────────────────────────────────────────────────────────────
    if resource == "/songs":
        if method == "GET":  return get_songs(qs_params)
        if method == "POST": return create_song(body)
 
    if resource == "/songs/{artist}/{title_album}":
        artist      = path_params.get("artist", "")
        title_album = path_params.get("title_album", "")
        if method == "GET":    return get_song(artist, title_album)
        if method == "DELETE": return delete_song(artist, title_album)
 
    # ── /subscriptions ────────────────────────────────────────────────────────
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
