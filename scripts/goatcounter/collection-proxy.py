#!/usr/bin/python3
"""Expose only GoatCounter's query-string count API, without request logs."""
from http.client import HTTPConnection
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import re
from urllib.parse import parse_qs, urlencode, urlsplit

LABEL = re.compile(r"[a-z0-9-]{1,40}\Z")
GIF = bytes.fromhex("47494638396101000100800100000000ffffff21f904010a0001002c00000000010001000002024c01003b")


class Counter(BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass

    def reply(self, status, body=b""):
        self.send_response(status)
        self.send_header("Content-Type", "image/gif" if status == 200 else "text/plain")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Cross-Origin-Resource-Policy", "cross-origin")
        self.end_headers()
        self.wfile.write(body)

    def count(self):
        target = urlsplit(self.path)
        if target.path != "/count":
            self.reply(404)
            return
        if self.headers.get("DNT") == "1" or self.headers.get("Sec-GPC") == "1":
            self.reply(200, GIF)
            return
        if len(self.path) > 8192:
            self.reply(414)
            return
        values = parse_qs(target.query, max_num_fields=16)
        path = values.get("p", [""])[0]
        event = values.get("e", [""])[0] == "true"
        path = path.split("?", 1)[0].split("#", 1)[0]
        if event:
            if not LABEL.fullmatch(path):
                self.reply(400)
                return
        elif not path.startswith("/") or path.startswith("//"):
            self.reply(400)
            return
        if path == "/poster-review" or path.startswith("/poster-review/"):
            self.reply(404)
            return
        query = {"p": path}
        if event:
            query["e"] = "true"
        else:
            labels = parse_qs(values.get("q", [""])[0])
            label = labels.get("ref", [])
            if len(labels) == 1 and len(label) == 1 and LABEL.fullmatch(label[0]):
                query["q"] = "ref=" + label[0]
            ref = urlsplit(values.get("r", [""])[0])
            if ref.scheme in ("http", "https") and ref.hostname:
                query["r"] = ref.scheme + "://" + ref.hostname
        upstream = HTTPConnection("127.0.0.1", 8081, timeout=5)
        try:
            # Forward UA only for GoatCounter's bot detection. Never forward IP,
            # cookies, language, Referer, arbitrary headers or the request body.
            upstream.request(self.command, "/count?" + urlencode(query), headers={
                "Host": "stats.localhost:8081",
                "User-Agent": self.headers.get("User-Agent", ""),
            })
            response = upstream.getresponse()
            self.reply(response.status, response.read(1024))
        finally:
            upstream.close()

    def handle_count(self):
        try:
            self.count()
        except (ValueError, OSError):
            self.reply(400)
        except Exception:
            self.reply(502)

    do_GET = do_POST = handle_count

    def denied(self):
        self.reply(404)

    do_HEAD = do_OPTIONS = do_PUT = do_PATCH = do_DELETE = do_TRACE = do_CONNECT = denied


if __name__ == "__main__":
    ThreadingHTTPServer(("127.0.0.1", 8444), Counter).serve_forever()
