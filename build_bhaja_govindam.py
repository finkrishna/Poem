#!/usr/bin/env python3
"""Build bhaja-govindam.html (and optional audio) from bhaja-govindam.json.

Does not modify shravan-masi.html, shravan-masi-spoken.html, or index.html.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA_PATH = ROOT / "bhaja-govindam.json"
OUT_HTML = ROOT / "bhaja-govindam.html"
SPOKEN = ROOT / "shravan-masi-spoken.html"


def load_data():
    return json.loads(DATA_PATH.read_text())


def css_from_spoken() -> str:
    html = SPOKEN.read_text()
    m = re.search(r"<style>(.*?)</style>", html, re.S)
    if not m:
        raise SystemExit("could not copy CSS from shravan-masi-spoken.html")
    return m.group(1)


def page_script() -> str:
    return r"""(() => {
  const popup = document.getElementById('meaning-popup');
  const wordAudio = document.getElementById('word-audio');
  const speakBtn = document.getElementById('speak-words');
  let active = null;
  let pinned = false;
  let timer;
  let speakTimer;
  let speakOn = true;
  let lastSpoken = null;

  function stopWord() {
    clearTimeout(speakTimer);
    speakTimer = null;
    lastSpoken = null;
    wordAudio.pause();
    wordAudio.removeAttribute('src');
    try { wordAudio.load(); } catch (e) {}
    if ('speechSynthesis' in window) speechSynthesis.cancel();
  }
  function poemIsPlaying() {
    return currentBtn && !audio.paused;
  }
  function speakFallback(text) {
    if (!('speechSynthesis' in window)) return;
    speechSynthesis.cancel();
    const u = new SpeechSynthesisUtterance(text);
    u.lang = 'hi-IN';
    u.rate = 0.8;
    const voices = speechSynthesis.getVoices();
    const pick = voices.find(v => /^sa(-|$)/i.test(v.lang)) || voices.find(v => /^hi(-|$)/i.test(v.lang));
    if (pick) u.voice = pick;
    speechSynthesis.speak(u);
  }
  function speakNow(word) {
    if (!speakOn || poemIsPlaying()) return;
    const text = word.textContent.trim();
    const src = word.getAttribute('data-speak-src');
    if (lastSpoken === word && wordAudio.getAttribute('src') === src && !wordAudio.paused) return;
    lastSpoken = word;
    if (src) {
      if ('speechSynthesis' in window) speechSynthesis.cancel();
      wordAudio.src = src;
      wordAudio.play().catch(() => speakFallback(text));
    } else {
      speakFallback(text);
    }
  }
  function queueSpeak(word) {
    clearTimeout(speakTimer);
    speakTimer = setTimeout(() => speakNow(word), 220);
  }

  function close() {
    clearTimeout(timer);
    clearTimeout(speakTimer);
    if (active) {
      active.classList.remove('active');
      active.removeAttribute('aria-describedby');
    }
    active = null;
    pinned = false;
    popup.hidden = true;
    stopWord();
  }
  function position() {
    if (!active) return;
    const rect = active.getBoundingClientRect();
    const box = popup.getBoundingClientRect();
    const left = Math.max(12, Math.min(rect.left + rect.width / 2 - box.width / 2, innerWidth - box.width - 12));
    const below = rect.bottom + 8;
    const top = below + box.height <= innerHeight - 12 ? below : Math.max(12, rect.top - box.height - 8);
    popup.style.left = `${left}px`;
    popup.style.top = `${top}px`;
  }
  function show(word, pin = false, immediateSpeak = false) {
    const keepPinned = pin;
    close();
    active = word;
    pinned = keepPinned;
    popup.textContent = word.dataset.meaning;
    popup.hidden = false;
    word.classList.add('active');
    word.setAttribute('aria-describedby', popup.id);
    position();
    if (keepPinned || immediateSpeak) speakNow(word);
    else queueSpeak(word);
  }
  function leave() {
    if (!pinned) timer = setTimeout(close, 180);
  }
  document.querySelectorAll('.poem-word').forEach(word => {
    word.addEventListener('pointerenter', event => {
      if (event.pointerType === 'mouse' && !pinned) show(word);
    });
    word.addEventListener('pointerleave', leave);
    word.addEventListener('focus', () => {
      if (word.matches(':focus-visible')) show(word, false, true);
    });
    word.addEventListener('blur', () => { if (active === word) close(); });
    word.addEventListener('click', () => {
      if (active === word && pinned) close();
      else show(word, true);
    });
  });
  popup.addEventListener('pointerenter', () => clearTimeout(timer));
  popup.addEventListener('pointerleave', leave);
  document.addEventListener('pointerdown', event => {
    if (!event.target.closest('.poem-word, .meaning-popup')) close();
  });
  document.addEventListener('keydown', event => { if (event.key === 'Escape') close(); });
  window.addEventListener('scroll', close, {passive: true});
  window.addEventListener('resize', close);
  document.getElementById('size').onclick = function () {
    close();
    this.setAttribute('aria-pressed', String(document.body.classList.toggle('large')));
  };
  speakBtn.addEventListener('click', () => {
    speakOn = !speakOn;
    speakBtn.setAttribute('aria-pressed', String(speakOn));
    if (!speakOn) stopWord();
  });

  const audio = document.getElementById('poem-audio');
  const buttons = [...document.querySelectorAll('.listen[data-src]')];
  let currentBtn = null;

  function idleLabel(btn) {
    return btn.id === 'play-full' ? 'Play hymn' : 'Play';
  }
  function resetButtons() {
    buttons.forEach(btn => {
      btn.setAttribute('aria-pressed', 'false');
      btn.textContent = idleLabel(btn);
    });
    document.querySelectorAll('.stanza.playing').forEach(s => s.classList.remove('playing'));
  }
  function markPlaying(btn) {
    resetButtons();
    currentBtn = btn;
    btn.setAttribute('aria-pressed', 'true');
    btn.textContent = 'Pause';
    const stanza = btn.closest('.stanza');
    if (stanza) stanza.classList.add('playing');
  }
  buttons.forEach(btn => {
    btn.addEventListener('click', () => {
      stopWord();
      if (currentBtn === btn && !audio.paused) {
        audio.pause();
        btn.setAttribute('aria-pressed', 'false');
        btn.textContent = idleLabel(btn);
        return;
      }
      if (currentBtn === btn && audio.paused && audio.getAttribute('src')) {
        audio.play();
        markPlaying(btn);
        return;
      }
      audio.src = btn.dataset.src;
      audio.play().then(() => markPlaying(btn)).catch(() => {
        btn.textContent = 'Missing audio';
      });
    });
  });
  audio.addEventListener('ended', () => {
    currentBtn = null;
    resetButtons();
    audio.removeAttribute('src');
  });

})();"""


def word_index(data) -> dict[str, str]:
    seen: dict[str, str] = {}
    n = 0
    audio_dir = data["audio_dir"]
    for stanza in data["stanzas"]:
        for line in stanza["sa"]:
            for text, _meaning in line:
                if text not in seen:
                    n += 1
                    seen[text] = f"{audio_dir}/words/w{n:03d}.mp3"
    return seen


def render_word(text: str, meaning: str, src: str) -> str:
    return (
        f'<button type="button" class="poem-word" data-meaning="{escape(meaning, quote=True)}" '
        f'data-speak-src="{escape(src, quote=True)}">{escape(text)}</button>'
    )


def render_line(words, src_map: dict[str, str], end: str) -> str:
    bits = [render_word(t, m, src_map[t]) for t, m in words]
    return '<p class="verse">' + " ".join(bits) + end + "</p>"


def render_stanza(stanza, src_map: dict[str, str], audio_dir: str) -> str:
    n = stanza["n"]
    nn = f"{n:02d}"
    lines = stanza["sa"]
    assert len(lines) == 2
    sa_html = (
        render_line(lines[0], src_map, " ।")
        + render_line(lines[1], src_map, " ॥")
    )
    en_html = "".join(f'<p class="verse">{escape(line)}</p>' for line in stanza["en"])
    note = stanza.get("note")
    details = ""
    if note:
        details = f"<details><summary>Note</summary><p>{escape(note)}</p></details>"
    return f"""<section class="stanza" id="stanza-{n}" style="--rows:3" aria-label="Verse {n}">
<div class="pane original" lang="sa"><span class="mobile-label">Sanskrit</span>
<div class="stanza-head"><a class="number" href="#stanza-{n}" aria-label="Verse {n}">{nn}</a>
<button type="button" class="listen stanza-play" data-src="{audio_dir}/stanza-{nn}.mp3" aria-label="Play verse {n}" aria-pressed="false">Play</button></div>
{sa_html}</div>
<div class="pane rendition"><span class="mobile-label">English</span><span class="number spacer" aria-hidden="true"></span>
{en_html}</div>
{details}</section>"""


def build_html(data) -> str:
    src_map = word_index(data)
    audio_dir = data["audio_dir"]
    stanzas = "\n".join(render_stanza(s, src_map, audio_dir) for s in data["stanzas"])
    n = len(data["stanzas"])
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{escape(data["title_en"])} · Poem Reader</title><style>
{css_from_spoken()}
</style></head><body><header><nav><a class="brand" href="index.html">Poem Reader</a><span class="small"><a href="index.html">All poems</a></span></nav>
<p class="eyebrow">{escape(data["eyebrow"])}</p>
<h1 lang="sa">{escape(data["title_sa"])}</h1>
<h2 class="subtitle">{escape(data["title_en"])}</h2>
<div class="byline">{escape(data["poet"])} &nbsp; <span style="color:var(--muted)">{escape(data["poet_note"])}</span></div>
<p class="intro">{escape(data["intro"])}</p>
<div class="toolbar"><div class="howto"><strong>How to read</strong>
<ol>
<li>Try to read the original Sanskrit first<span class="wide-only"> (left column)</span><span class="narrow-only"> (the first text in each stanza)</span>.</li>
<li><span class="hover-hint">Hover over, or tab to,</span><span class="touch-hint">Tap</span> any word you don’t understand to hear it spoken and see its meaning in English.<span class="touch-hint"> Tap anywhere else to close it.</span></li>
<li>For really difficult lines, read the English version of the whole line <span class="wide-only">in the right column</span><span class="narrow-only">in the English after the stanza</span>.</li>
</ol></div>
<button type="button" id="play-full" class="listen" data-src="{audio_dir}/full.mp3" aria-pressed="false">Play hymn</button>
<button id="size" aria-pressed="false">Larger text</button>
<button type="button" id="speak-words" aria-pressed="true">Speak words</button>
<button onclick="window.print()">Print</button></div></header>
<main>
<div class="columns"><div>Original<small>Sanskrit</small></div><div>English<small>AI generated translation</small></div></div>
{stanzas}
</main>
<footer>
<p>This page is a sibling of the Shravan reader. Existing Marathi pages and audio were not changed.</p>
<p>Sanskrit follows the Vaidika Vignanam Devanagari recension for verses 1–{n}. Word splits follow that text (hyphens become separate words). The English, the word meanings and the notes were written for this site and have not yet been reviewed.</p>
<p>Spoken words use a Hindi TTS voice reading Devanagari — a stand-in for Sanskrit, not a Vedic reciter. The same word can be glossed differently in another line.</p>
<p><a href="https://www.vignanam.org/devanagari/bhaja-govindam-moha-mudagaram.html">Source recension</a> · <a href="shravan-masi-spoken.html">Shravan (spoken)</a> · <a href="index.html">All poems</a></p>
</footer>
<audio id="poem-audio" preload="metadata"></audio>
<audio id="word-audio" preload="none" playsinline></audio>
<div id="meaning-popup" class="meaning-popup" role="tooltip" lang="en" hidden></div>
<script>{page_script()}</script></body></html>
"""


def stanza_speech(stanza) -> str:
    lines = [" ".join(t for t, _ in line) for line in stanza["sa"]]
    return "। ".join(lines) + "॥"


def gtts_save(text: str, dest: Path, lang: str = "hi") -> None:
    from gtts import gTTS

    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(".tmp.mp3")
    for attempt in range(4):
        try:
            gTTS(text=text, lang=lang, slow=False).save(str(tmp))
            tmp.replace(dest)
            return
        except Exception as e:
            print(f"retry {dest.name}: {e}", flush=True)
            time.sleep(1.2 * (attempt + 1))
    raise SystemExit(f"failed to synthesize {dest}")


def generate_audio(data) -> None:
    src_map = word_index(data)
    audio_dir = ROOT / data["audio_dir"]
    words_dir = audio_dir / "words"
    words_dir.mkdir(parents=True, exist_ok=True)

    items = sorted(src_map.items(), key=lambda kv: kv[1])
    print(f"{len(items)} unique words, {len(data['stanzas'])} stanzas", flush=True)
    for text, rel in items:
        dest = ROOT / rel
        if dest.exists() and dest.stat().st_size > 800:
            continue
        print(f"word {dest.name} {text}", flush=True)
        gtts_save(text, dest)
        time.sleep(0.1)

    stanza_files = []
    for stanza in data["stanzas"]:
        nn = f"{stanza['n']:02d}"
        dest = audio_dir / f"stanza-{nn}.mp3"
        stanza_files.append(dest)
        if dest.exists() and dest.stat().st_size > 2000:
            continue
        print(f"stanza {nn}", flush=True)
        gtts_save(stanza_speech(stanza), dest)
        time.sleep(0.15)

    silence = audio_dir / "_silence.mp3"
    if not silence.exists():
        subprocess.run(
            [
                "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
                "-f", "lavfi", "-i", "anullsrc=r=24000:cl=mono",
                "-t", "0.55", "-b:a", "64k", str(silence),
            ],
            check=True,
        )

    full = audio_dir / "full.mp3"
    lst = audio_dir / "_concat.txt"
    lines = []
    for i, path in enumerate(stanza_files):
        lines.append(f"file '{path.name}'")
        if i != len(stanza_files) - 1:
            lines.append(f"file '{silence.name}'")
    lst.write_text("\n".join(lines) + "\n")
    subprocess.run(
        [
            "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
            "-f", "concat", "-safe", "0", "-i", str(lst),
            "-c", "copy", str(full),
        ],
        check=True,
    )
    print(f"full {full.stat().st_size}b", flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--audio", action="store_true", help="also synthesize MP3s")
    args = parser.parse_args()
    data = load_data()
    if len(data["stanzas"]) != 20:
        raise SystemExit(f"expected 20 stanzas, got {len(data['stanzas'])}")
    html = build_html(data)
    OUT_HTML.write_text(html)
    src_map = word_index(data)
    print(f"wrote {OUT_HTML.name} ({len(html)} bytes, {len(src_map)} unique words)")
    if args.audio:
        generate_audio(data)


if __name__ == "__main__":
    main()
