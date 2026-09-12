#!/usr/bin/env python3
"""Local factory API + static file server for the Poem Reader.

  XAI_API_KEY=... python3 factory_server.py

Then open http://127.0.0.1:8765/
"""
from __future__ import annotations

import json
import os
import re
import sys
import urllib.error
import urllib.request
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PORT = int(os.environ.get("PORT", "8765"))
MAX_CHARS = 8000  # ~2000 tokens
MAX_FETCH = 1_000_000
XAI_URL = "https://api.x.ai/v1/chat/completions"
XAI_MODEL = os.environ.get("XAI_MODEL", "grok-4.5")


def load_dotenv() -> None:
    path = ROOT / ".env"
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, val = line.split("=", 1)
        os.environ.setdefault(key.strip(), val.strip().strip('"').strip("'"))


def approx_truncate(text: str) -> tuple[str, bool]:
    text = text.replace("\u0000", " ").strip()
    if len(text) <= MAX_CHARS:
        return text, False
    cut = text[:MAX_CHARS]
    sp = max(cut.rfind(" "), cut.rfind("\n"))
    if sp > 2000:
        cut = cut[:sp]
    return cut.strip(), True


def strip_html(raw: str) -> str:
    raw = re.sub(r"(?is)<(script|style).*?>.*?</\1>", " ", raw)
    raw = re.sub(r"(?is)<br\s*/?>", "\n", raw)
    raw = re.sub(r"(?is)</p>", "\n\n", raw)
    raw = re.sub(r"(?is)<[^>]+>", " ", raw)
    raw = re.sub(r"&nbsp;", " ", raw)
    raw = re.sub(r"&amp;", "&", raw)
    raw = re.sub(r"&lt;", "<", raw)
    raw = re.sub(r"&gt;", ">", raw)
    raw = re.sub(r"[ \t]+\n", "\n", raw)
    return re.sub(r"\n{3,}", "\n\n", raw).strip()


def fetch_url(url: str) -> str:
    if not re.match(r"^https?://", url, re.I):
        raise ValueError("URL must start with http:// or https://")
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "PoemReaderFactory/1.0"},
        method="GET",
    )
    with urllib.request.urlopen(req, timeout=25) as resp:
        data = resp.read(MAX_FETCH + 1)
        ctype = resp.headers.get("Content-Type", "")
    if len(data) > MAX_FETCH:
        data = data[:MAX_FETCH]
    text = data.decode("utf-8", errors="replace")
    if "html" in ctype.lower() or "<html" in text[:400].lower():
        return strip_html(text)
    return text.strip()


SYSTEM = """You are a poem/shloka reader factory. Turn source text into a bilingual reader.
Rules:
- Detect the source language. Do not invent verses or words that are not in the input.
- Keep original spelling. Split into stanzas the way the source is lined (blank lines, verse numbers, or couplets).
- Each original line is an array of words {t, m}. t is the source word; m is a short gloss in the TARGET language, as used in that line.
- rendition: fluent TARGET-language lines, one per original line (or two lines per couplet if that reads better).
- If the source is prose, one paragraph = one stanza; split into short lines.
- speech_lang must be a BCP-47 tag the browser can speak for the SOURCE (sa → hi-IN, mr → mr-IN, hi → hi-IN, en → en-US, zh → zh-CN).
- Cap at 40 stanzas. Skip front matter.
Return JSON only with this shape:
{
  "source_lang": "sa",
  "source_lang_label": "Sanskrit",
  "speech_lang": "hi-IN",
  "title_original": "...",
  "title_translated": "...",
  "poet": "",
  "intro": "one or two sentences",
  "stanzas": [
    {"n": 1, "original": [[{"t":"word","m":"gloss"}]], "rendition": ["..."], "note": null}
  ]
}"""


def extract_json(content: str) -> dict:
    content = content.strip()
    content = re.sub(r"^```(?:json)?\s*", "", content)
    content = re.sub(r"\s*```$", "", content)
    start, end = content.find("{"), content.rfind("}")
    if start < 0 or end < start:
        raise ValueError("Model did not return JSON.")
    return json.loads(content[start : end + 1])


def call_xai(text: str, target_label: str, target_code: str, api_key: str) -> dict:
    body = json.dumps(
        {
            "model": XAI_MODEL,
            "temperature": 0.2,
            "messages": [
                {"role": "system", "content": SYSTEM},
                {
                    "role": "user",
                    "content": f"TARGET language: {target_label} ({target_code})\n\nSOURCE TEXT:\n{text}",
                },
            ],
        }
    ).encode()
    req = urllib.request.Request(
        XAI_URL,
        data=body,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            payload = json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="replace")[:400]
        raise RuntimeError(f"SpaceXAI {e.code}: {detail}") from e
    content = payload["choices"][0]["message"]["content"]
    return extract_json(content)


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def log_message(self, fmt: str, *args) -> None:
        sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))

    def _json(self, code: int, obj: dict) -> None:
        raw = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self) -> None:
        if self.path.split("?", 1)[0] == "/api/health":
            key = os.environ.get("XAI_API_KEY", "")
            self._json(200, {"ok": True, "has_key": bool(key), "provider": "spacexai", "model": XAI_MODEL})
            return
        if self.path in ("/", "/index.html"):
            self.path = "/index.html"
        super().do_GET()

    def do_POST(self) -> None:
        if self.path.split("?", 1)[0] != "/api/process":
            self._json(404, {"error": "not found"})
            return
        length = int(self.headers.get("Content-Length") or 0)
        if length > 2_000_000:
            self._json(413, {"error": "Request too large."})
            return
        try:
            body = json.loads(self.rfile.read(length) or b"{}")
        except json.JSONDecodeError:
            self._json(400, {"error": "Invalid JSON."})
            return
        try:
            text = (body.get("text") or "").strip()
            url = (body.get("url") or "").strip()
            if url and not text:
                text = fetch_url(url)
            text, truncated = approx_truncate(text)
            if not text:
                raise ValueError("Paste text, drop a file, or give a URL.")
            api_key = (body.get("api_key") or os.environ.get("XAI_API_KEY") or "").strip()
            if not api_key:
                raise ValueError("Missing XAI_API_KEY. Set it in the environment or paste a SpaceXAI key in the page.")
            target_code = body.get("target_lang") or "en"
            target_label = body.get("target_lang_label") or "English"
            poem = call_xai(text, target_label, target_code, api_key)
            poem["target_lang"] = target_code
            poem["target_lang_label"] = target_label
            poem["truncated"] = truncated
            self._json(200, poem)
        except Exception as e:
            self._json(400, {"error": str(e)})


def main() -> None:
    load_dotenv()
    os.chdir(ROOT)
    server = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    print(f"Poem factory http://127.0.0.1:{PORT}/", flush=True)
    if not os.environ.get("XAI_API_KEY"):
        print("No XAI_API_KEY in env — paste a SpaceXAI key in the page.", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nbye", flush=True)


if __name__ == "__main__":
    main()
