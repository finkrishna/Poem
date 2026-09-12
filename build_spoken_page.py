#!/usr/bin/env python3
"""Build shravan-masi-spoken.html from shravan-masi.html. Does not modify the source page."""
from pathlib import Path
import re

root = Path(__file__).resolve().parent
src = (root / "shravan-masi.html").read_text()
assert "shravan-masi-spoken" not in src

seen = {}
n = 0

def add_speak_src(match):
    global n
    meaning, word = match.group(1), match.group(2)
    if word not in seen:
        n += 1
        seen[word] = f"audio/words/w{n:03d}.mp3"
    return (
        f'<button type="button" class="poem-word" data-meaning="{meaning}" '
        f'data-speak-src="{seen[word]}">{word}</button>'
    )

html = re.sub(
    r'<button type="button" class="poem-word" data-meaning="([^"]*)">([^<]+)</button>',
    add_speak_src,
    src,
)
if n != 125:
    raise SystemExit(f"expected 125 unique words, got {n}")

html = html.replace(
    "<title>The month of Shravan · Poem Reader</title>",
    "<title>The month of Shravan · spoken words</title>",
)
html = html.replace(
    "@media print{.listen,#play-full{display:none!important}",
    "@media print{.listen,#play-full,#speak-words{display:none!important}",
)
html = html.replace(
    '<span class="hover-hint">Hover over, or tab to,</span><span class="touch-hint">Tap</span> any word you don’t understand to see its meaning in English.',
    '<span class="hover-hint">Hover over, or tab to,</span><span class="touch-hint">Tap</span> any word you don’t understand to hear it spoken in Marathi and see its meaning in English.',
)
html = html.replace(
    '<button id="size" aria-pressed="false">Larger text</button>',
    '<button id="size" aria-pressed="false">Larger text</button>'
    '<button type="button" id="speak-words" aria-pressed="true">Speak words</button>',
)
html = html.replace(
    "<p>The Marathi text follows the source image",
    "<p>This copy speaks each Marathi word as you hover or tap it. The original silent-gloss page is unchanged.</p>"
    "<p>The Marathi text follows the source image",
)
html = html.replace(
    '<audio id="poem-audio" preload="metadata"></audio>',
    '<audio id="poem-audio" preload="metadata"></audio>'
    '<audio id="word-audio" preload="none" playsinline></audio>',
)

old_script_start = html.find("<script>(() => {")
old_script_end = html.find("})();\n</script>")
if old_script_end < 0:
    old_script_end = html.find("})();</script>")
    end_token = "})();</script>"
else:
    end_token = "})();\n</script>"
if old_script_start < 0 or old_script_end < 0:
    raise SystemExit("could not find page script")

script = r"""<script>(() => {
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
    u.lang = 'mr-IN';
    u.rate = 0.85;
    const voices = speechSynthesis.getVoices();
    const pick = voices.find(v => /^mr(-|$)/i.test(v.lang)) || voices.find(v => /^hi(-|$)/i.test(v.lang));
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
    return btn.id === 'play-full' ? 'Play poem' : 'Play';
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

})();
</script>"""

html = html[:old_script_start] + script + html[old_script_end + len(end_token):]
(root / "shravan-masi-spoken.html").write_text(html)
print(f"wrote shravan-masi-spoken.html ({len(html)} bytes, {n} word clips)")
