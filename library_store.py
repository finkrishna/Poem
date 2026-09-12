"""Persist factory-made readers locally and, when possible, on a Hub dataset."""
from __future__ import annotations

import hashlib
import json
import os
import re
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
LIB_DIR = ROOT / "library"
MANIFEST = LIB_DIR / "index.json"
MAX_ITEMS = 120
ID_RE = re.compile(r"^[\w.\-\u0900-\u097F]{1,80}$")
_lock = threading.Lock()


def library_repo() -> str:
    return os.environ.get("LIBRARY_REPO", "finkrishna/poem-library")


def _token() -> str:
    return (
        os.environ.get("HF_TOKEN")
        or os.environ.get("HUGGING_FACE_HUB_TOKEN")
        or ""
    ).strip() or (
        (Path.home() / ".cache" / "huggingface" / "token").read_text().strip()
        if (Path.home() / ".cache" / "huggingface" / "token").exists()
        else ""
    )


def source_hash(text: str, target_code: str) -> str:
    blob = f"{(target_code or 'en').strip()}\n{(text or '').strip()}".encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


def _slug(title: str, digest: str) -> str:
    raw = re.sub(r"\s+", "-", (title or "poem").strip())[:48]
    raw = re.sub(r"[^\w\u0900-\u097F\-]+", "", raw) or "poem"
    return f"{raw}-{digest[:8]}"


def _read_manifest() -> list:
    if not MANIFEST.exists():
        return []
    try:
        data = json.loads(MANIFEST.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except Exception:
        return []


def _write_manifest(items: list) -> None:
    LIB_DIR.mkdir(parents=True, exist_ok=True)
    MANIFEST.write_text(json.dumps(items, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def list_items() -> list:
    with _lock:
        return _read_manifest()


def find_by_hash(digest: str) -> dict | None:
    for it in list_items():
        if it.get("source_hash") == digest:
            return it
    return None


def load_poem(item_id: str) -> dict | None:
    if not ID_RE.match(item_id or ""):
        return None
    path = LIB_DIR / f"{item_id}.json"
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else None
    except Exception:
        return None


def save_poem(poem: dict, text: str, target_code: str) -> dict:
    digest = source_hash(text, target_code)
    existing = find_by_hash(digest)
    if existing:
        full = load_poem(existing["id"])
        if full:
            return existing
    title = (poem.get("title_original") or poem.get("title_translated") or "poem").strip()
    item_id = _slug(title, digest)
    if not ID_RE.match(item_id):
        item_id = f"poem-{digest[:8]}"
    record = {
        "id": item_id,
        "source_hash": digest,
        "created": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "title_original": poem.get("title_original") or title,
        "title_translated": poem.get("title_translated") or "",
        "source_lang_label": poem.get("source_lang_label") or "",
        "target_lang_label": poem.get("target_lang_label") or "",
        "source_lang": poem.get("source_lang") or "",
        "target_lang": poem.get("target_lang") or target_code,
        "poet": poem.get("poet") or "",
    }
    payload = dict(poem)
    payload["id"] = item_id
    payload["source_hash"] = digest
    payload["created"] = record["created"]
    LIB_DIR.mkdir(parents=True, exist_ok=True)
    with _lock:
        (LIB_DIR / f"{item_id}.json").write_text(
            json.dumps(payload, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        items = [it for it in _read_manifest() if it.get("id") != item_id and it.get("source_hash") != digest]
        items.insert(0, record)
        _write_manifest(items[:MAX_ITEMS])
    _push_hub(item_id)
    return record


def pull_hub() -> None:
    tok = _token()
    if not tok:
        return
    try:
        from huggingface_hub import snapshot_download
    except ImportError:
        return
    try:
        snapshot_download(
            repo_id=library_repo(),
            repo_type="dataset",
            local_dir=str(LIB_DIR),
            token=tok,
        )
        print(f"library: pulled {library_repo()}", flush=True)
    except Exception as e:
        print(f"library pull skipped: {e}", flush=True)


def _push_hub(item_id: str) -> None:
    tok = _token()
    if not tok:
        return
    try:
        from huggingface_hub import HfApi
    except ImportError:
        return
    api = HfApi(token=tok)
    repo = library_repo()
    try:
        api.create_repo(repo_id=repo, repo_type="dataset", exist_ok=True, private=False)
        poem_path = LIB_DIR / f"{item_id}.json"
        if poem_path.exists():
            api.upload_file(
                path_or_fileobj=str(poem_path),
                path_in_repo=f"{item_id}.json",
                repo_id=repo,
                repo_type="dataset",
                commit_message=f"Add reader {item_id}",
            )
        if MANIFEST.exists():
            api.upload_file(
                path_or_fileobj=str(MANIFEST),
                path_in_repo="index.json",
                repo_id=repo,
                repo_type="dataset",
                commit_message=f"Update library index {time.strftime('%Y-%m-%d')}",
            )
        print(f"library: pushed {item_id} to {repo}", flush=True)
    except Exception as e:
        print(f"library push skipped: {e}", flush=True)
