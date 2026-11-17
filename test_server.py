"""Run: python3 test_server.py"""
import base64
import json
import os
import threading
import urllib.error
import urllib.request
from http.server import HTTPServer

import server

server.PUBLIC_HOST = server.PASSWORD = None  # start in local mode whatever the environment says
server.open_db(":memory:")
httpd = HTTPServer(("127.0.0.1", 0), server.Handler)
threading.Thread(target=httpd.serve_forever, daemon=True).start()
BASE = f"http://127.0.0.1:{httpd.server_port}"


def call(method, path, body=None, headers=None):
    req = urllib.request.Request(BASE + path, method=method, headers=headers or {},
                                 data=json.dumps(body).encode() if body is not None else None)
    try:
        with urllib.request.urlopen(req) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


def j(result):
    return result[0], json.loads(result[1])


assert call("GET", "/")[0] == 200
assert call("GET", "/.key")[0] == 404, "must not serve files other than the page"
assert call("GET", "/calls.db")[0] == 404
assert call("GET", "/calls", headers={"Host": "evil.example"})[0] == 403
assert call("POST", "/calls", {"lang": "en"}, {"Origin": "https://evil.example"})[0] == 403
assert call("POST", "/token", {"lang": "es"})[0] == 400
os.environ.pop("SONIOX_API_KEY", None)
assert call("POST", "/token", {"lang": "en", "engine": "soniox"})[0] == 400, "Soniox needs its own key"
assert call("POST", "/calls", {"lang": "xx"})[0] == 400

status, created = j(call("POST", "/calls", {"lang": "de"}))
assert status == 201
cid = created["id"]
assert call("PUT", f"/calls/{cid}", {"original": "مرحبا", "translation": "Hallo Welt"})[0] == 200
assert call("PUT", f"/calls/{cid}", {"translation": 5})[0] == 400
assert call("PUT", f"/calls/{cid}", {"marks": ["x"]})[0] == 400
assert j(call("GET", f"/calls/{cid}"))[1]["marks"] == []
assert call("PUT", f"/calls/{cid}", {"original": "مرحبا", "translation": "Hallo Welt", "marks": [[3, 5]]})[0] == 200
assert j(call("GET", f"/calls/{cid}"))[1]["marks"] == [[3, 5]]
assert call("PUT", f"/calls/{cid}", {"title": 5})[0] == 400
assert call("PUT", f"/calls/{cid}", {"title": " Zahnarzt "})[0] == 200
renamed = j(call("GET", f"/calls/{cid}"))[1]
assert (renamed["title"], renamed["translation"]) == ("Zahnarzt", "Hallo Welt"), "renaming keeps the transcript"
assert [c["title"] for c in j(call("GET", "/calls?q=Zahn"))[1]] == ["Zahnarzt"], "search covers the name"
assert call("PUT", "/calls/999", {"translation": "x"})[0] == 404

status, saved = j(call("GET", f"/calls/{cid}"))
assert (saved["original"], saved["translation"], saved["lang"]) == ("مرحبا", "Hallo Welt", "de")
assert [c["id"] for c in j(call("GET", "/calls"))[1]] == [cid]
assert [c["id"] for c in j(call("GET", "/calls?q=Welt"))[1]] == [cid]
assert j(call("GET", "/calls?q=%D9%85%D8%B1%D8%AD"))[1], "search covers the original text"
assert j(call("GET", "/calls?q=nothing"))[1] == []

assert call("DELETE", f"/calls/{cid}")[0] == 200
assert call("GET", f"/calls/{cid}")[0] == 404

# Server mode: public hostname allowed, password required on everything.
server.PUBLIC_HOST, server.PASSWORD = "translator.example.com", "s3cret"
basic = lambda pw: {"Authorization": "Basic " + base64.b64encode(f"me:{pw}".encode()).decode()}
assert call("GET", "/")[0] == 401
assert call("GET", "/calls", headers=basic("wrong"))[0] == 401
assert call("GET", "/calls", headers={"Authorization": "Basic !!!"})[0] == 401
assert call("GET", "/calls", headers=basic("s3cret"))[0] == 200
assert call("GET", "/calls", headers={**basic("s3cret"), "Host": "translator.example.com",
                                      "Origin": "https://translator.example.com"})[0] == 200
assert call("GET", "/calls", headers={**basic("s3cret"), "Host": "evil.example"})[0] == 403
print("ok")
