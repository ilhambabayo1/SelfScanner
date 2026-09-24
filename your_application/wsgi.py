import asyncio
from app.main import app

_REASONS = {
    200: "OK", 201: "Created", 204: "No Content", 400: "Bad Request",
    404: "Not Found", 405: "Method Not Allowed", 413: "Payload Too Large",
    422: "Unprocessable Entity", 429: "Too Many Requests",
    500: "Internal Server Error", 503: "Service Unavailable",
}


def application(environ, start_response):
    loop = asyncio.new_event_loop()
    try:
        status, headers, body = loop.run_until_complete(_invoke(environ))
    finally:
        loop.close()
    start_response("%d %s" % (status, _REASONS.get(status, "")),
                   [(k, str(v)) for k, v in headers])
    return [body]


async def _invoke(environ):
    body_data = b""
    length = int(environ.get("CONTENT_LENGTH") or 0)
    if length:
        body_data = environ["wsgi.input"].read(length)
    headers = [(k.lower().encode(), str(v).encode())
               for k, v in environ.items() if k.startswith("HTTP_")]
    if environ.get("CONTENT_TYPE"):
        headers.append((b"content-type", environ["CONTENT_TYPE"].encode()))
    if length:
        headers.append((b"content-length", str(length).encode()))
    path = environ.get("PATH_INFO", "/")
    scope = {
        "type": "http",
        "asgi": {"version": "3.0", "spec_version": "2.3"},
        "http_version": environ.get("SERVER_PROTOCOL", "HTTP/1.1").split("/")[-1],
        "method": environ["REQUEST_METHOD"],
        "scheme": environ.get("wsgi.url_scheme", "https"),
        "path": path,
        "raw_path": path.encode(),
        "query_string": (environ.get("QUERY_STRING") or "").encode(),
        "root_path": environ.get("SCRIPT_NAME", ""),
        "server": (environ.get("SERVER_NAME"), int(environ.get("SERVER_PORT") or 80)),
        "client": (environ.get("REMOTE_ADDR") or "", int(environ.get("REMOTE_PORT") or 0)),
        "headers": headers,
    }
    result = {}
    consumed = []

    async def receive():
        if not consumed:
            consumed.append(True)
            return {"type": "http.request", "body": body_data, "more_body": False}
        return {"type": "http.disconnect"}

    async def send(message):
        if message["type"] == "http.response.start":
            result["status"] = message["status"]
            result["headers"] = [(k.decode(), v.decode())
                                 for k, v in message.get("headers", [])]
        elif message["type"] == "http.response.body":
            result.setdefault("chunks", []).append(message.get("body", b""))

    await app(scope, receive, send)
    return result.get("status", 500), result.get("headers", []), b"".join(result.get("chunks", []))

