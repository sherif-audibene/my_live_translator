# Live Translator

Live subtitles for a phone call (or anything the Mac's microphone hears), translated in real time with OpenAI's `gpt-realtime-translate` over WebRTC.

- Target languages: English, Arabic, German (source language is auto-detected)
- Optional side-by-side original transcript
- Optional translated voice playback (use headphones)

## Run

Needs Python 3 and an OpenAI API key. No dependencies.

```bash
OPENAI_API_KEY=sk-... python3 server.py
```

Open http://localhost:8765 in Chrome, click **Start** and allow the microphone.

The local server only exists to mint short-lived session tokens, so the API key never reaches the browser. It listens on localhost only. Do not expose it to a network: anyone who can reach it can spend your key.

## Capturing a call that runs on the Mac

Install [BlackHole](https://github.com/ExistentialAudio/BlackHole) and select it as the system input device, so the call audio is captured directly instead of through the microphone.
