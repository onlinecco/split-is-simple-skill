#!/usr/bin/env python3
"""Anonymous Split Is Simple API client; Python 3 standard library only."""
import argparse
import json
import re
import sys
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlparse, quote
from urllib.request import Request, build_opener, HTTPRedirectHandler

PRODUCTION = "https://splitissimple.com"
SECRET = re.compile(r"[A-Za-z0-9_-]{21}[AQgw]\Z")

class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None

def base_url(value):
    url = urlparse(value)
    if url.username or url.password or url.query or url.fragment or url.path not in ("", "/"):
        raise ValueError("Use the service origin only.")
    if value.rstrip("/") == PRODUCTION:
        return PRODUCTION
    if url.scheme == "http" and url.hostname in ("localhost", "127.0.0.1", "::1"):
        return value.rstrip("/")
    raise ValueError("Only splitissimple.com or an explicitly chosen localhost HTTP test server is allowed.")

def event_id(value, origin):
    if SECRET.fullmatch(value):
        return value
    url = urlparse(value)
    if f"{url.scheme}://{url.netloc}" != origin or url.username or url.password:
        raise ValueError("The event link must use the selected service origin.")
    values = parse_qs(url.query).get("event", [])
    if len(values) != 1 or not SECRET.fullmatch(values[0]):
        raise ValueError("Provide one complete, case-sensitive event link or 22-character secret.")
    return values[0]

def request(method, url, headers, body=None):
    data = None if body is None else json.dumps(body, ensure_ascii=False, allow_nan=False).encode("utf-8")
    if data is not None and len(data) > 250000:
        raise ValueError("Event JSON exceeds 250,000 bytes.")
    req = Request(url, data=data, headers=headers, method=method)
    try:
        with build_opener(NoRedirect).open(req, timeout=30) as response:
            return response.status, json.loads(response.read(1000000)), response.headers
    except HTTPError as error:
        try:
            payload = json.loads(error.read(1000000))
        except (ValueError, UnicodeError):
            payload = {"error": "Service returned an unexpected HTTP response."}
        return error.code, payload, error.headers

def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["create", "get", "update"])
    parser.add_argument("--base-url", default=PRODUCTION, help="Production by default; localhost only for authorized testing")
    parser.add_argument("--file", type=Path)
    parser.add_argument("--event")
    parser.add_argument("--request-key", help="Fresh random UUID for create; reuse on identical retries")
    parser.add_argument("--revision", type=int)
    args = parser.parse_args(argv)
    try:
        origin = base_url(args.base_url)
        headers = {"Accept": "application/json"}
        payload = None
        if args.action != "get":
            if not args.file:
                raise ValueError("--file is required for create/update.")
            if args.file.stat().st_size > 250000:
                raise ValueError("Event JSON exceeds 250,000 bytes.")
            payload = json.loads(args.file.read_text(encoding="utf-8"))
            headers["Content-Type"] = "application/json"
        if args.action == "create":
            if not args.request_key or not re.fullmatch(r"[A-Za-z0-9_-]{16,128}", args.request_key):
                raise ValueError("Provide --request-key with a fresh UUID; keep it unchanged for retries.")
            headers["Idempotency-Key"] = args.request_key
            method, endpoint = "POST", "/api/v1/events"
        else:
            if not args.event:
                raise ValueError("--event is required.")
            endpoint = "/api/v1/events/" + quote(event_id(args.event, origin), safe="")
            method = "GET" if args.action == "get" else "PATCH"
            if method == "PATCH":
                if args.revision is None or not 1 <= args.revision <= 2147483647:
                    raise ValueError("Provide --revision from the latest event read.")
                headers["X-Event-Revision"] = str(args.revision)
        status, result, response_headers = request(method, origin + endpoint, headers, payload)
        if status >= 400:
            print(json.dumps({"status": status, "error": result.get("error", "Request failed"),
                              "retryAfter": response_headers.get("Retry-After")}, ensure_ascii=False), file=sys.stderr)
            return 1
        if not isinstance(result, dict) or not isinstance(result.get("url"), str) or not SECRET.fullmatch(result.get("id", "")):
            raise ValueError("Service response did not confirm an event link.")
        expected = f"{PRODUCTION}/?event={result['id']}"
        if result["url"] != expected:
            raise ValueError("Service returned an unexpected event URL.")
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (ValueError, OSError, URLError) as error:
        # Transport errors may contain secret URLs; report a generic message instead.
        message = "Could not reach the service. A creation retry must keep the same key and body; read before retrying an update." if isinstance(error, URLError) else str(error)
        print(json.dumps({"error": message}, ensure_ascii=False), file=sys.stderr)
        return 1

if __name__ == "__main__":
    sys.exit(main())
