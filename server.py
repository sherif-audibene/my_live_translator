"""Local server for the live translator.

Serves the page, mints short-lived OpenAI session tokens (so the API key never
reaches the browser) and stores call transcripts in a local SQLite file.

Run: OPENAI_API_KEY=sk-... python3 server.py  ->  http://localhost:8765
"""
import json
import os
import re
import sqlite3
import urllib.error
import urllib.request
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs

ROOT = os.path.dirname(os.path.abspath(__file__))
PORT = 8765
LANGS = {"en", "ar", "de"}
db = None


def open_db(path):
    global db
    db = sqlite3.connect(path, check_same_thread=False)  # one request at a time; the test serves from a thread
    db.row_factory = sqlite3.Row
    db.execute(
        """CREATE TABLE IF NOT EXISTS calls (
            id INTEGER PRIMARY KEY,
            started_at TEXT NOT NULL,
            ended_at TEXT NOT NULL,
            lang TEXT NOT NULL,
            original TEXT NOT NULL DEFAULT '',
            translation TEXT NOT NULL DEFAULT '')"""
    )
    db.commit()


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def mint_token(lang, with_original):
    audio = {"output": {"language": lang}}
    if with_original:  # also transcribe the original speech
        audio["input"] = {"transcription": {"model": "gpt-realtime-whisper"}}
    req = urllib.request.Request(
        "https://api.openai.com/v1/realtime/translations/client_secrets",
        data=json.dumps({"session": {"model": "gpt-realtime-translate", "audio": audio}}).encode(),
        headers={"Authorization": f"Bearer {os.environ['OPENAI_API_KEY']}",
                 "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


class Handler(BaseHTTPRequestHandler):
    def reply(self, status, body):
        if not isinstance(body, bytes):
            body = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def json_body(self):
        data = json.loads(self.rfile.read(int(self.headers.get("Content-Length") or 0)) or b"{}")
        if not isinstance(data, dict):
            raise ValueError("expected a JSON object")
        return data

    def allowed(self):
        # Host check stops DNS rebinding; Origin check stops other websites from
        # calling this server (and spending the API key) through the browser.
        port = self.server.server_port
        hosts = {f"localhost:{port}", f"127.0.0.1:{port}"}
        origin = self.headers.get("Origin")
        return self.headers.get("Host") in hosts and (origin is None or origin.split("//")[-1] in hosts)

    def route(self):
        if not self.allowed():
            return self.reply(403, {"error": "forbidden"})
        path, _, query = self.path.partition("?")
        method = self.command
        call = re.fullmatch(r"/calls/(\d+)", path)
        try:
            if method == "GET" and path == "/":
                with open(os.path.join(ROOT, "index.html"), "rb") as f:
                    page = f.read()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(page)))
                self.end_headers()
                return self.wfile.write(page)

            if method == "POST" and path == "/token":
                data = self.json_body()
                if data.get("lang") not in LANGS:
                    return self.reply(400, {"error": "unsupported language"})
                return self.reply(*mint_token(data["lang"], bool(data.get("original"))))

            if method == "GET" and path == "/calls":
                q = f"%{parse_qs(query).get('q', [''])[0]}%"
                rows = db.execute(
                    """SELECT id, started_at, ended_at, lang, substr(translation, 1, 140) AS preview
                       FROM calls WHERE translation LIKE ? OR original LIKE ? ORDER BY id DESC""",
                    (q, q),
                ).fetchall()
                return self.reply(200, [dict(r) for r in rows])

            if method == "POST" and path == "/calls":
                lang = self.json_body().get("lang")
                if lang not in LANGS:
                    return self.reply(400, {"error": "unsupported language"})
                t = now()
                cur = db.execute("INSERT INTO calls (started_at, ended_at, lang) VALUES (?, ?, ?)", (t, t, lang))
                db.commit()
                return self.reply(201, {"id": cur.lastrowid})

            if call:
                call_id = int(call.group(1))
                if method == "GET":
                    row = db.execute("SELECT * FROM calls WHERE id = ?", (call_id,)).fetchone()
                    return self.reply(200, dict(row)) if row else self.reply(404, {"error": "call not found"})
                if method == "PUT":
                    data = self.json_body()
                    original, translation = data.get("original", ""), data.get("translation", "")
                    if not isinstance(original, str) or not isinstance(translation, str):
                        return self.reply(400, {"error": "original and translation must be text"})
                    cur = db.execute(
                        "UPDATE calls SET original = ?, translation = ?, ended_at = ? WHERE id = ?",
                        (original, translation, now(), call_id),
                    )
                    db.commit()
                    return self.reply(200, {"ok": True}) if cur.rowcount else self.reply(404, {"error": "call not found"})
                if method == "DELETE":
                    db.execute("DELETE FROM calls WHERE id = ?", (call_id,))
                    db.commit()
                    return self.reply(200, {"ok": True})

            self.reply(404, {"error": "not found"})
        except ValueError as e:  # includes malformed JSON
            self.reply(400, {"error": str(e)})

    do_GET = do_POST = do_PUT = do_DELETE = route


if __name__ == "__main__":
    os.environ["OPENAI_API_KEY"]  # fail now rather than on the first call
    open_db(os.path.join(ROOT, "calls.db"))
    print(f"http://localhost:{PORT}")
    # localhost only: anyone who can reach this server can spend the API key and read the calls
    HTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
