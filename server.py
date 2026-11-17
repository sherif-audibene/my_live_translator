"""Local server: serves index.html and mints ephemeral client secrets so the API key never reaches the browser.

Run: OPENAI_API_KEY=sk-... python3 server.py  ->  http://localhost:8765
"""
import json
import os
import urllib.error
import urllib.request
from http.server import HTTPServer, SimpleHTTPRequestHandler

KEY = os.environ["OPENAI_API_KEY"]
LANGS = {"en", "ar", "de"}


class Handler(SimpleHTTPRequestHandler):
    def do_POST(self):
        path, _, query = self.path.partition("?")
        if path != "/token":
            return self.send_error(404)
        lang = self.rfile.read(int(self.headers.get("Content-Length", 0))).decode()
        if lang not in LANGS:
            return self.send_error(400, "unsupported language")
        audio = {"output": {"language": lang}}
        if query == "src=1":  # also transcribe the original speech
            audio["input"] = {"transcription": {"model": "gpt-realtime-whisper"}}
        req = urllib.request.Request(
            "https://api.openai.com/v1/realtime/translations/client_secrets",
            data=json.dumps({"session": {"model": "gpt-realtime-translate", "audio": audio}}).encode(),
            headers={"Authorization": f"Bearer {KEY}", "Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req) as r:
                status, body = r.status, r.read()
        except urllib.error.HTTPError as e:
            status, body = e.code, e.read()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(body)


if __name__ == "__main__":
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    print("http://localhost:8765")
    # localhost only: anyone who can reach /token can spend the API key
    HTTPServer(("127.0.0.1", 8765), Handler).serve_forever()
