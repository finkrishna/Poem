"""Poem Reader factory for Hugging Face Spaces (Gradio + ZeroGPU hosting)."""
from __future__ import annotations

import json
import os
from pathlib import Path

import gradio as gr
import spaces

from factory_server import approx_truncate, call_llm, fetch_url, hf_token, load_dotenv

ROOT = Path(__file__).resolve().parent
load_dotenv()

TARGETS = [
    ("en", "English"),
    ("hi", "Hindi"),
    ("mr", "Marathi"),
    ("sa", "Sanskrit"),
    ("ta", "Tamil"),
    ("te", "Telugu"),
    ("kn", "Kannada"),
    ("ml", "Malayalam"),
    ("bn", "Bengali"),
    ("gu", "Gujarati"),
    ("pa", "Punjabi"),
    ("ur", "Urdu"),
    ("es", "Spanish"),
    ("fr", "French"),
    ("de", "German"),
    ("it", "Italian"),
    ("pt", "Portuguese"),
    ("ru", "Russian"),
    ("ja", "Japanese"),
    ("ko", "Korean"),
    ("zh", "Chinese"),
    ("ar", "Arabic"),
    ("tr", "Turkish"),
    ("id", "Indonesian"),
    ("vi", "Vietnamese"),
    ("nl", "Dutch"),
    ("fa", "Persian"),
    ("th", "Thai"),
]
CHOICES = [f"{label} · {code}" for code, label in TARGETS]
CSS = (ROOT / "reader.css").read_text(encoding="utf-8")
READER_JS = (ROOT / "reader.js").read_text(encoding="utf-8")
EXAMPLE = (
    "भज गोविन्दं भज गोविन्दं गोविन्दं भज मूढमते ।\n"
    "सम्प्राप्ते सन्निहिते काले नहि नहि रक्षति डुकृङ्करणे ॥"
)


@spaces.GPU(duration=1)
def _zerogpu_slot() -> bool:
    """Required while the Space runs on ZeroGPU hardware. Never called."""
    return True


def make_reader(text: str, url: str, target: str) -> tuple[str, str]:
    """Build a bilingual reader from pasted text or a page URL via Hugging Face Inference."""
    text = (text or "").strip()
    url = (url or "").strip()
    if url and not text:
        text = fetch_url(url)
    text, truncated = approx_truncate(text)
    if not text:
        raise gr.Error("Paste a poem or give a URL.")
    if not hf_token() and not (os.environ.get("XAI_API_KEY") or "").strip():
        raise gr.Error("This Space is missing HF_TOKEN (and has no XAI_API_KEY fallback).")
    label, _, code = (target or "English · en").partition(" · ")
    label, code = (label or "English").strip(), (code or "en").strip()
    poem = call_llm(text, label, code)
    poem["target_lang"] = code
    poem["target_lang_label"] = label
    poem["truncated"] = truncated
    n = len(poem.get("stanzas") or [])
    extra = " (first ~2000 tokens)" if truncated else ""
    status = (
        f"Ready · {n} stanzas{extra}. "
        "Pick a voice on this device, then hover a word to hear it."
    )
    return status, json.dumps(poem, ensure_ascii=False)


with gr.Blocks(
    title="Poem Reader",
    theme=gr.themes.Soft(),
    css=CSS,
    head=f"<script>{READER_JS}</script>",
) as demo:
    gr.Markdown(
        """# Drop a text. Get a reader.
Any language in · any language out.

Translation and word glosses use **Qwen 2.5 72B** on Hugging Face Inference (usually ~15–40 seconds). Speech uses **voices already on your device**. Gloss is unverified."""
    )
    text = gr.Textbox(label="Text", lines=8, placeholder=EXAMPLE)
    url = gr.Textbox(label="Or a URL", placeholder="https://vignanam.org/devanagari/sri-rudram-namakam.html")
    target = gr.Dropdown(choices=CHOICES, value="English · en", label="Translate to")
    go = gr.Button("Make reader", variant="primary")
    status = gr.Markdown()
    poem_json = gr.Textbox(visible=False)
    gr.HTML("<div id='reader-root'></div>")
    go.click(make_reader, inputs=[text, url, target], outputs=[status, poem_json]).then(
        None,
        inputs=[poem_json],
        js=(
            "(raw) => { try { const p = JSON.parse(raw); "
            "const root = document.getElementById('reader-root'); "
            "if (window.PoemReader && root && p && p.stanzas) "
            "PoemReader.mountReader(root, p); } catch (e) {} }"
        ),
    )
    gr.Markdown(
        "Source: [github.com/finkrishna/Poem](https://github.com/finkrishna/Poem). "
        "Library pages (Shravan Masi, Bhaja Govindam) live there too."
    )

if __name__ == "__main__":
    demo.queue()
    demo.launch(
        mcp_server=True,
        theme=gr.themes.Soft(),
        css=CSS,
        head=f"<script>{READER_JS}</script>",
    )
