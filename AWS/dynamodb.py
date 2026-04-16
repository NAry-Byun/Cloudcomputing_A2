import boto3, json, os
from botocore.exceptions import ClientError
 
REGION       = os.environ.get("AWS_REGION",        "us-east-1")
ENDPOINT_URL = os.environ.get("DYNAMODB_ENDPOINT", None)
SONGS_FILE   = os.environ.get("SONGS_FILE",        "2026a2_songs.json")
 
_kw = dict(region_name=REGION)
if ENDPOINT_URL:
    _kw["endpoint_url"] = ENDPOINT_URL
 
dynamodb = boto3.resource("dynamodb", **_kw)
client   = boto3.client  ("dynamodb", **_kw)
 
 
# ── helpers ───────────────────────────────────────────────────────────────────
def table_exists(name):
    try:
        client.describe_table(TableName=name)
        return True
    except ClientError as e:
        if e.response["Error"]["Code"] == "ResourceNotFoundException":
            return False
        raise
 
def wait_active(name):
    print(f"  Waiting for '{name}' …", end="", flush=True)
    client.get_waiter("table_exists").wait(TableName=name)
    print(" ACTIVE")
 
 
# ══════════════════════════════════════════════════════════════════════════════
# 1. USERS TABLE
# ══════════════════════════════════════════════════════════════════════════════
#
#  PK  username (S)
#
#  GSI  EmailIndex  PK=email
#       Purpose: login by email without a full Scan
#
USERS_TABLE = "Users"
 
SAMPLE_USERS = [
    {"username":"alice",  "email":"s1234567@student.rmit.edu.au",  "password_hash":"Test123",  "full_name":"Alice Johnson",  "created_at":"2025-01-10","last_login":"2026-04-15","is_active":True},
    {"username":"bob",    "email":"s1234568@student.rmit.edu.au",    "password_hash":"Test123",  "full_name":"Bob Smith",      "created_at":"2025-02-14","last_login":"2026-04-14","is_active":True},
    {"username":"carol",  "email":"s1234569@student.rmit.edu.au",  "password_hash":"Test123",  "full_name":"Carol White",    "created_at":"2025-03-01","last_login":"2026-04-10","is_active":True},
    {"username":"dave",   "email":"s1234560student.rmit.edu.au",   "password_hash":"Test123",  "full_name":"Dave Brown",     "created_at":"2025-03-20","last_login":"2026-03-28","is_active":False},
    {"username":"eve",    "email":"s1234561@student.rmit.edu.au",    "password_hash":"Test123",  "full_name":"Eve Davis",      "created_at":"2025-04-05","last_login":"2026-04-16","is_active":True},
    {"username":"frank",  "email":"s1234562@student.rmit.edu.au",  "password_hash":"Test123",  "full_name":"Frank Miller",   "created_at":"2025-05-12","last_login":"2026-04-12","is_active":True},
    {"username":"grace",  "email":"s1234563@student.rmit.edu.au",  "password_hash":"Test123",  "full_name":"Grace Wilson",   "created_at":"2025-06-18","last_login":"2026-04-01","is_active":True},
    {"username":"henry",  "email":"s1234564@student.rmit.edu.au",  "password_hash":"Test123",  "full_name":"Henry Moore",    "created_at":"2025-07-22","last_login":"2026-03-15","is_active":False},
    {"username":"iris",   "email":"s1234565@student.rmit.edu.au",   "password_hash":"Test123",  "full_name":"Iris Taylor",    "created_at":"2025-08-30","last_login":"2026-04-13","is_active":True},
    {"username":"james",  "email":"s1234566@student.rmit.edu.au",  "password_hash":"Test123",  "full_name":"James Anderson", "created_at":"2025-09-05","last_login":"2026-04-11","is_active":True},
]
 
def create_users_table():
    if table_exists(USERS_TABLE):
        print(f"'{USERS_TABLE}' already exists — skipping.")
        return dynamodb.Table(USERS_TABLE)
    print(f"Creating '{USERS_TABLE}' …")
    dynamodb.create_table(
        TableName=USERS_TABLE,
        KeySchema=[{"AttributeName":"username","KeyType":"HASH"}],
        AttributeDefinitions=[
            {"AttributeName":"username","AttributeType":"S"},
            {"AttributeName":"email",   "AttributeType":"S"},
        ],
        GlobalSecondaryIndexes=[{
            "IndexName": "EmailIndex",
            "KeySchema": [{"AttributeName":"email","KeyType":"HASH"}],
            "Projection": {"ProjectionType":"ALL"},
        }],
        BillingMode="PAY_PER_REQUEST",
    )
    wait_active(USERS_TABLE)
    return dynamodb.Table(USERS_TABLE)
 
def load_users(table):
    print(f"Writing {len(SAMPLE_USERS)} users …")
    with table.batch_writer() as bw:
        for u in SAMPLE_USERS:
            bw.put_item(Item=u)
    print(f"  ✓ {len(SAMPLE_USERS)} users loaded.")
 
 
# ══════════════════════════════════════════════════════════════════════════════
# 2. MUSIC TABLE
# ══════════════════════════════════════════════════════════════════════════════
#
#  KEY DESIGN (from cardinality analysis of 137 songs):
#    title alone          → 130 unique  ✗
#    title + artist       → 133 unique  ✗  (re-releases by same artist)
#    title + artist+album → 137 unique  ✓
#
#  PK  artist      (71 unique values)
#  SK  title_album ("title#album" composite — zero overwrites)
#
#  LSI  ArtistYearIndex  PK=artist  SK=year
#       → "Jimmy Buffett songs from 1974, sorted"
#
#  GSI  AlbumIndex       PK=album   SK=title
#       → "All songs on Fearless"
#
#  GSI  YearIndex        PK=year    SK=artist
#       → "All songs from 2012"
#
MUSIC_TABLE = "Music"
 
def create_music_table():
    if table_exists(MUSIC_TABLE):
        print(f"'{MUSIC_TABLE}' already exists — skipping.")
        return dynamodb.Table(MUSIC_TABLE)
    print(f"Creating '{MUSIC_TABLE}' …")
    dynamodb.create_table(
        TableName=MUSIC_TABLE,
        KeySchema=[
            {"AttributeName":"artist",      "KeyType":"HASH"},
            {"AttributeName":"title_album", "KeyType":"RANGE"},
        ],
        AttributeDefinitions=[
            {"AttributeName":"artist",      "AttributeType":"S"},
            {"AttributeName":"title_album", "AttributeType":"S"},
            {"AttributeName":"album",       "AttributeType":"S"},
            {"AttributeName":"title",       "AttributeType":"S"},
            {"AttributeName":"year",        "AttributeType":"S"},
        ],
        LocalSecondaryIndexes=[{
            "IndexName": "ArtistYearIndex",
            "KeySchema": [
                {"AttributeName":"artist","KeyType":"HASH"},
                {"AttributeName":"year",  "KeyType":"RANGE"},
            ],
            "Projection": {"ProjectionType":"ALL"},
        }],
        GlobalSecondaryIndexes=[
            {
                "IndexName": "AlbumIndex",
                "KeySchema": [
                    {"AttributeName":"album","KeyType":"HASH"},
                    {"AttributeName":"title","KeyType":"RANGE"},
                ],
                "Projection": {"ProjectionType":"ALL"},
            },
            {
                "IndexName": "YearIndex",
                "KeySchema": [
                    {"AttributeName":"year",  "KeyType":"HASH"},
                    {"AttributeName":"artist","KeyType":"RANGE"},
                ],
                "Projection": {"ProjectionType":"ALL"},
            },
        ],
        BillingMode="PAY_PER_REQUEST",
    )
    wait_active(MUSIC_TABLE)
    return dynamodb.Table(MUSIC_TABLE)
 
def load_music(table, path):
    with open(path, encoding="utf-8") as f:
        songs = json.load(f)["songs"]
    print(f"Importing {len(songs)} songs …")
    loaded = 0
    with table.batch_writer() as bw:
        for s in songs:
            bw.put_item(Item={
                "artist":      s["artist"],
                "title_album": f"{s['title']}#{s['album']}",
                "title":       s["title"],
                "album":       s["album"],
                "year":        s.get("year",    ""),
                "img_url":     s.get("img_url", ""),
            })
            loaded += 1
    print(f"  ✓ {loaded} songs loaded.")
 
 
# ══════════════════════════════════════════════════════════════════════════════
# 3. USER SUBSCRIPTIONS TABLE  ← NEW
# ══════════════════════════════════════════════════════════════════════════════
#
#  Stores which songs each user has subscribed to.
#  New users start with zero rows — empty subscription list.
#
#  PK  username    (String) — the logged-in user
#  SK  title_album (String) — the subscribed song key ("title#album")
#
#  Querying by username = O(log n), returns only that user's subscriptions.
#  No GSI needed — access pattern is always "by username".
#
#  Extra attributes stored per item:
#    title, artist, album, year, img_url
#    (denormalised from Music table for fast display without a join)
#
SUB_TABLE = "UserSubscriptions"
 
def create_subscriptions_table():
    if table_exists(SUB_TABLE):
        print(f"'{SUB_TABLE}' already exists — skipping.")
        return dynamodb.Table(SUB_TABLE)
    print(f"Creating '{SUB_TABLE}' …")
    dynamodb.create_table(
        TableName=SUB_TABLE,
        KeySchema=[
            {"AttributeName":"username",    "KeyType":"HASH"},
            {"AttributeName":"title_album", "KeyType":"RANGE"},
        ],
        AttributeDefinitions=[
            {"AttributeName":"username",    "AttributeType":"S"},
            {"AttributeName":"title_album", "AttributeType":"S"},
        ],
        BillingMode="PAY_PER_REQUEST",
    )
    wait_active(SUB_TABLE)
    return dynamodb.Table(SUB_TABLE)
 
 
# ── main ──────────────────────────────────────────────────────────────────────
def main():
    print("=" * 62)
    print("  DynamoDB Setup — Users + Music + UserSubscriptions")
    print("=" * 62)
 
    # Users
    t = create_users_table()
    load_users(t)
    print()
 
    # Music
    m = create_music_table()
    load_music(m, SONGS_FILE)
    print()
 
    # UserSubscriptions (starts empty — users populate it via Subscribe)
    create_subscriptions_table()
    print("  UserSubscriptions table ready (empty — populated by users).")
 
    print("\n" + "=" * 62)
    print("  All tables ready.")
    print("=" * 62)
 
if __name__ == "__main__":
    main()
 