from flask import Flask, request, Response
from lamda_handler import lambda_handler

app = Flask(__name__)

def forward_to_lambda(resource, path_params=None):
    raw_body = request.get_data(as_text=True)
    event = {
        "httpMethod": request.method,
        "resource": resource,
        "pathParameters": path_params or {},
        "queryStringParameters": request.args.to_dict(flat=True) or {},
        "body": raw_body if raw_body else None,
    }
    result = lambda_handler(event, None)
    return Response(
        response=result.get("body", ""),
        status=result.get("statusCode", 200),
        headers=result.get("headers", {}),
        mimetype="application/json",
    )

@app.route("/health", methods=["GET"])
def health():
    return Response('{"status":"ok"}', status=200, mimetype="application/json")

@app.route("/users", methods=["GET", "POST", "OPTIONS"])
def users():
    return forward_to_lambda("/users")

@app.route("/users/by-email", methods=["GET", "OPTIONS"])
def users_by_email():
    return forward_to_lambda("/users/by-email")

@app.route("/users/<username>", methods=["GET", "DELETE", "OPTIONS"])
def user_by_username(username):
    return forward_to_lambda("/users/{username}", {"username": username})

@app.route("/songs", methods=["GET", "POST", "OPTIONS"])
def songs():
    return forward_to_lambda("/songs")

@app.route("/songs/<artist>/<title_album>", methods=["GET", "DELETE", "OPTIONS"])
def song_by_key(artist, title_album):
    return forward_to_lambda(
        "/songs/{artist}/{title_album}",
        {"artist": artist, "title_album": title_album},
    )

@app.route("/subscriptions", methods=["GET", "POST", "OPTIONS"])
def subscriptions():
    return forward_to_lambda("/subscriptions")

@app.route("/subscriptions/<username>/<title_album>", methods=["DELETE", "OPTIONS"])
def subscription_by_key(username, title_album):
    return forward_to_lambda(
        "/subscriptions/{username}/{title_album}",
        {"username": username, "title_album": title_album},
    )

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=False)
