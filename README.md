# Live Translator

Live subtitles for a phone call (or anything the Mac's microphone hears), translated in real time with OpenAI's `gpt-realtime-translate` over WebRTC.

- Target languages: English, Arabic, German (source language is auto-detected)
- Optional side-by-side original transcript
- Optional translated voice playback (use headphones)
- Every call is saved automatically to a local SQLite file (`calls.db`) and can be searched, reread and deleted from the sidebar
- Adjustable transcript font and size

## Run

Needs Python 3 and an OpenAI API key. No dependencies.

```bash
OPENAI_API_KEY=sk-... python3 server.py
```

Open http://localhost:8765 in Chrome, click **Start call** and allow the microphone.

Run the checks with `python3 test_server.py`.

The local server only exists to mint short-lived session tokens, so the API key never reaches the browser. It listens on localhost only. Do not expose it to a network: anyone who can reach it can spend your key.

## Capturing a call that runs on the Mac

Install [BlackHole](https://github.com/ExistentialAudio/BlackHole) and select it as the system input device, so the call audio is captured directly instead of through the microphone.

## Deploying to a server

The `Jenkinsfile` tests the app, copies it to `/opt/live-translator` on the Jenkins box and restarts it on `127.0.0.1:6303`. Saved calls (`calls.db`) are kept across deployments.

One-time setup:

1. In Jenkins, add two **Secret text** credentials: `live-translator-openai-key` (the OpenAI API key) and `live-translator-password` (the password for opening the page).
2. Point an HTTPS hostname at `http://localhost:6303`, for example with a Cloudflare Tunnel ingress. The microphone only works over HTTPS.
3. Set `PUBLIC_HOST` in the `Jenkinsfile` to that hostname.

The page then asks for the password (any username). The app refuses to start with `PUBLIC_HOST` set and no `APP_PASSWORD`. It is not restarted after a reboot: run the Jenkins job again.
