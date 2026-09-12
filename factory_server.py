#!/usr/bin/env python3
"""Poem Reader factory: static files + /api/fetch + /api/process.

  python3 factory_server.py

Local:  http://127.0.0.1:8765/
Hosted: bind 0.0.0.0 and set PORT (Render / Hugging Face Spaces Docker).
"""
from __future__ import annotations

import json
import os
import re
import sys
import threading
import time
import uuid
import urllib.error
import urllib.request
from collections import defaultdict, deque
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent
HOST = os.environ.get("HOST", "0.0.0.0")
PORT = int(os.environ.get("PORT", "8765"))
MAX_CHARS = 8000  # ~2000 tokens
MAX_FETCH = 1_000_000
MAX_PER_HOUR = int(os.environ.get("MAX_PER_HOUR", "10"))
XAI_URL = "https://api.x.ai/v1/chat/completions"
XAI_MODEL = os.environ.get("XAI_MODEL", "grok-4.5")
HF_URL = "https://router.huggingface.co/v1/chat/completions"
# Novita hosts Qwen 2.5 72B cheaply; :fastest often hits Groq/Together Cloudflare 403s.
HF_MODEL = os.environ.get("HF_MODEL", "Qwen/Qwen2.5-72B-Instruct:novita")
HIDDEN_FILES = {".env", ".git", ".gitignore", ".dockerignore"}
FETCH_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
)


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


_hits = defaultdict(deque)
_hits_lock = threading.Lock()
_jobs = {}
_jobs_lock = threading.Lock()
_job_lock = threading.Lock()


def client_ip(handler: SimpleHTTPRequestHandler) -> str:
    forwarded = handler.headers.get("X-Forwarded-For", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return handler.client_address[0]


def rate_ok(ip: str) -> bool:
    now = time.time()
    with _hits_lock:
        q = _hits[ip]
        while q and q[0] < now - 3600:
            q.popleft()
        if len(q) >= MAX_PER_HOUR:
            return False
        q.append(now)
        return True


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
    raw = re.sub(r"(?is)<!--.*?-->", " ", raw)
    raw = re.sub(r"(?is)<(script|style|nav|noscript).*?>.*?</\1>", " ", raw)
    raw = re.sub(r"(?is)<br\s*/?>", "\n", raw)
    raw = re.sub(r"(?is)</p>", "\n\n", raw)
    raw = re.sub(r"(?is)<[^>]+>", " ", raw)
    raw = re.sub(r"&nbsp;", " ", raw)
    raw = re.sub(r"&amp;", "&", raw)
    raw = re.sub(r"&lt;", "<", raw)
    raw = re.sub(r"&gt;", ">", raw)
    raw = re.sub(r"[ \t]+\n", "\n", raw)
    return re.sub(r"\n{3,}", "\n\n", raw).strip()


def _cut_related(html: str) -> str:
    m = re.search(
        r'(?is)class="[^"]*(relatedCategories|related|aqtree)[^"]*"',
        html,
    )
    return html[: m.start()] if m else html


def _div_after(html: str, attr_re: str) -> str | None:
    m = re.search(rf"(?is)<(?:div|p|h1|h2)[^>]*{attr_re}[^>]*>", html)
    if not m:
        return None
    return _cut_related(html[m.end() :])


def extract_main(html: str) -> str:
    """Prefer the hymn/article body over site chrome (language switchers, related lists)."""
    title = ""
    m = re.search(r'(?is)id="stitle"[^>]*>(.*?)</p>', html)
    if m:
        title = strip_html(m.group(1))
    if not title:
        m = re.search(r'(?is)property="og:title"\s+content="([^"]+)"', html)
        if m:
            title = m.group(1).strip()

    body_html = None
    for attr in (
        r'id=["\']stext["\']',
        r'class=["\'][^"\']*stotramtext',
        r'id=["\']stotramcontent["\']',
        r'id=["\']content["\']',
        r'role=["\']main["\']',
    ):
        chunk = _div_after(html, attr)
        if chunk and len(strip_html(chunk)) > 80:
            body_html = chunk
            break
    if body_html is None:
        m = re.search(r"(?is)<(article|main)[^>]*>", html)
        if m:
            rest = _cut_related(html[m.end() :])
            if len(strip_html(rest)) > 80:
                body_html = rest

    if body_html is None:
        return strip_html(html)
    text = strip_html(body_html)
    if title and title not in text[:240]:
        text = f"{title}\n\n{text}"
    return text


def fetch_url(url: str) -> str:
    if not re.match(r"^https?://", url, re.I):
        raise ValueError("URL must start with http:// or https://")
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": FETCH_UA,
            "Accept": "text/html,application/xhtml+xml,text/plain;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        },
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=25) as resp:
            status = getattr(resp, "status", 200) or 200
            data = resp.read(MAX_FETCH + 1)
            ctype = (resp.headers.get("Content-Type") or "").lower()
            final_url = resp.geturl()
    except urllib.error.HTTPError as e:
        if e.code == 403:
            raise ValueError(
                "That URL returned HTTP 403. Use the full page address "
                "(the URL box can cut off paths like /devanagari/…). "
                f"Tried: {url}"
            ) from e
        if e.code == 404:
            raise ValueError(f"That URL was not found (HTTP 404). Tried: {url}") from e
        raise ValueError(f"Could not fetch URL (HTTP {e.code}). Tried: {url}") from e
    except urllib.error.URLError as e:
        raise ValueError(f"Could not fetch URL: {e.reason}") from e
    if len(data) > MAX_FETCH:
        data = data[:MAX_FETCH]
    head = data[:4000]
    if (
        status in (202, 401, 403)
        or b"awsWafCookie" in head
        or b"captcha" in head.lower()
        or b"Access Denied" in head
    ):
        raise ValueError(
            "That site blocked the fetch (bot challenge or empty response). "
            "Paste the page text instead, or try a different URL."
        )
    if not data.strip():
        raise ValueError(
            f"That URL returned an empty page (HTTP {status}). "
            "Check the address is complete, or paste the text."
        )
    text = data.decode("utf-8", errors="replace")
    if "html" in ctype or "<html" in text[:400].lower():
        text = extract_main(text)
    text = text.strip()
    if len(text) < 40:
        raise ValueError(
            "Could not extract readable text from that URL. "
            f"Fetched {final_url}. Paste the page text instead."
        )
    return text


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


def hf_token() -> str:
    tok = (os.environ.get("HF_TOKEN") or os.environ.get("HUGGING_FACE_HUB_TOKEN") or "").strip()
    if tok:
        return tok
    path = Path.home() / ".cache" / "huggingface" / "token"
    if path.exists():
        return path.read_text().strip()
    return ""


def _chat_completions(url: str, key: str, payload: dict, timeout: int, label: str) -> dict:
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode(),
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="replace")[:400]
        raise RuntimeError(f"{label} {e.code}: {detail}") from e


def call_llm(text: str, target_label: str, target_code: str, api_key: str = "") -> dict:
    messages = [
        {"role": "system", "content": SYSTEM},
        {
            "role": "user",
            "content": f"TARGET language: {target_label} ({target_code})\n\nSOURCE TEXT:\n{text}",
        },
    ]
    errors: list[str] = []
    token = hf_token()
    if token:
        try:
            print(f"llm: Hugging Face {HF_MODEL}", flush=True)
            payload = _chat_completions(
                HF_URL,
                token,
                {
                    "model": HF_MODEL,
                    "temperature": 0.2,
                    "max_tokens": 8192,
                    "messages": messages,
                },
                timeout=90,
                label="HuggingFace",
            )
            content = (payload.get("choices") or [{}])[0].get("message", {}).get("content") or ""
            return extract_json(content)
        except Exception as e:
            errors.append(str(e))
            print(f"hf failed, trying SpaceXAI: {e}", flush=True)

    xai_key = (os.environ.get("XAI_API_KEY") or api_key or "").strip()
    if xai_key:
        body = {
            "model": XAI_MODEL,
            "temperature": 0.2,
            "max_tokens": 8192,
            "search_parameters": {"mode": "off"},
            "messages": messages,
        }
        try:
            print(f"llm: SpaceXAI {XAI_MODEL}", flush=True)
            payload = _chat_completions(XAI_URL, xai_key, body, timeout=180, label="SpaceXAI")
        except RuntimeError as e:
            if "search_parameters" not in str(e).lower():
                errors.append(str(e))
                payload = None
            else:
                body.pop("search_parameters", None)
                payload = _chat_completions(XAI_URL, xai_key, body, timeout=180, label="SpaceXAI")
        if payload is not None:
            content = (payload.get("choices") or [{}])[0].get("message", {}).get("content") or ""
            return extract_json(content)

    raise RuntimeError(
        "No working LLM. Set HF_TOKEN (Hugging Face Inference) or XAI_API_KEY. "
        + (" ".join(errors) if errors else "")
    )


def call_xai(text: str, target_label: str, target_code: str, api_key: str) -> dict:
    return call_llm(text, target_label, target_code, api_key)


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
        path = self.path.split("?", 1)[0]
        name = Path(path).name
        if name in HIDDEN_FILES or path.startswith("/.git"):
            self._json(404, {"error": "not found"})
            return
        if path.startswith("/api/job/"):
            job_id = path.rsplit("/", 1)[-1]
            with _jobs_lock:
                job = _jobs.get(job_id)
            if not job:
                self._json(404, {"error": "Unknown job."})
                return
            out = {"status": job["status"]}
            if job["status"] == "done":
                out["poem"] = job["poem"]
            if job["status"] == "error":
                out["error"] = job.get("error") or "Failed."
            self._json(200, out)
            return
        if path == "/api/health":
            has_hf = bool(hf_token())
            has_xai = bool(os.environ.get("XAI_API_KEY"))
            self._json(
                200,
                {
                    "ok": True,
                    "has_key": has_hf or has_xai,
                    "provider": "huggingface" if has_hf else "spacexai",
                    "model": HF_MODEL if has_hf else XAI_MODEL,
                    "max_per_hour": MAX_PER_HOUR,
                },
            )
            return
        if path in ("/", "/index.html"):
            self.path = "/index.html"
        super().do_GET()

    def _read_json_body(self) -> dict:
        length = int(self.headers.get("Content-Length") or 0)
        if length > 2_000_000:
            raise ValueError("Request too large.")
        try:
            return json.loads(self.rfile.read(length) or b"{}")
        except json.JSONDecodeError as e:
            raise ValueError("Invalid JSON.") from e

    def do_POST(self) -> None:
        path = self.path.split("?", 1)[0]
        if path not in ("/api/process", "/api/fetch"):
            self._json(404, {"error": "not found"})
            return
        ip = client_ip(self)
        if path == "/api/process" and not rate_ok(ip):
            self._json(
                429,
                {
                    "error": f"This host allows {MAX_PER_HOUR} readers per hour per visitor. Try later."
                },
            )
            return
        try:
            body = self._read_json_body()
        except ValueError as e:
            code = 413 if "large" in str(e).lower() else 400
            self._json(code, {"error": str(e)})
            return
        try:
            if path == "/api/fetch":
                url = (body.get("url") or "").strip()
                if not url:
                    raise ValueError("Give a URL.")
                text = fetch_url(url)
                text, truncated = approx_truncate(text)
                if not text:
                    raise ValueError("Could not extract readable text from that URL. Paste the page text instead.")
                print(f"fetch: {len(text)} chars from {url}", flush=True)
                self._json(200, {"text": text, "truncated": truncated})
                return

            text = (body.get("text") or "").strip()
            url = (body.get("url") or "").strip()
            if url and not text:
                text = fetch_url(url)
            elif not text and not url:
                raise ValueError("Paste text, drop a file, or give a URL.")
            text, truncated = approx_truncate(text)
            if not text:
                raise ValueError(
                    "Nothing to read from that source. If you used a URL, paste the page text instead."
                )
            api_key = (os.environ.get("XAI_API_KEY") or body.get("api_key") or "").strip()
            if not hf_token() and not api_key:
                raise ValueError("Missing HF_TOKEN or XAI_API_KEY.")
            target_code = body.get("target_lang") or "en"
            target_label = body.get("target_lang_label") or "English"
            if not _job_lock.acquire(blocking=False):
                self._json(429, {"error": "Factory is already building a reader. Try again in a minute."})
                return
            job_id = uuid.uuid4().hex[:12]
            with _jobs_lock:
                _jobs[job_id] = {"status": "working", "t0": time.time()}

            def run() -> None:
                try:
                    print(f"process: {len(text)} chars", flush=True)
                    poem = call_llm(text, target_label, target_code, api_key)
                    poem["target_lang"] = target_code
                    poem["target_lang_label"] = target_label
                    poem["truncated"] = truncated
                    print(f"ready: {len(poem.get('stanzas') or [])} stanzas", flush=True)
                    with _jobs_lock:
                        _jobs[job_id] = {"status": "done", "poem": poem}
                except Exception as exc:
                    with _jobs_lock:
                        _jobs[job_id] = {"status": "error", "error": str(exc)}
                finally:
                    _job_lock.release()

            threading.Thread(target=run, daemon=True).start()
            self._json(202, {"job_id": job_id, "status": "working"})
        except Exception as e:
            self._json(400, {"error": str(e)})


def main() -> None:
    load_dotenv()
    os.chdir(ROOT)
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"Poem factory http://{HOST}:{PORT}/", flush=True)
    if not os.environ.get("XAI_API_KEY"):
        print("No XAI_API_KEY in env — paste a SpaceXAI key in the page.", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nbye", flush=True)


if __name__ == "__main__":
    main()
