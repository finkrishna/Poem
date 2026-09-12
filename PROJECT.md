# श्रावण मासी · Poem Reader + Marathi read-aloud

Project brief for Grok CLI. Source conversation: 11 Sep 2026. Use this file as the starting context if the work splits into several directions.

## Goal

Keep the **exact look, feel, and layout** of Balakavi’s poem page, and add audio so a visitor can:

1. Play the **full poem** from a top toolbar button.
2. Play **one couplet at a time** from a small button beside each stanza number (`01`–`10`).
3. Hear a **slow, professional Marathi** recitation (not a generic English TTS read).

Original page (do not treat as writable from this sandbox):

- https://poemreader.smritiweb.com/shravan-masi.html
- Title on page: **श्रावण मासी** / *The month of Shravan*
- Poet: बालकवी · Balakavi Tryambak Bapuji Thombre (1890–1918)
- Form: Marathi, 10 couplets, bilingual columns, per-word English glosses, optional notes

This sandbox **cannot edit the live smritiweb site**. Deliverables here are a faithful local replica plus audio files and integration notes for whoever hosts the site.

## What exists now

| Path | What it is |
|---|---|
| `artifacts/shravan-masi.html` | Local replica of the original page + Play poem + per-stanza Play |
| `artifacts/audio/full.mp3` | Full recitation, ~93.5 s, 128 kbps mono, 24 kHz |
| `artifacts/audio/stanza-01.mp3` … `stanza-10.mp3` | One clip per couplet, ~8.7–10.3 s each |
| `artifacts/audio/raw/` | Unslowed TTS takes (source before `atempo=0.82`) |
| `artifacts/shravan-masi-recitation.mp3` | Same file as `audio/full.mp3` (earlier name) |
| `artifacts/shravan-masi-naksh.mp3` | Full poem before time-stretch (~76.7 s) |
| `artifacts/shravan-masi-reader.html` | First prototype (not layout-faithful). Prefer `shravan-masi.html` |
| `artifacts/shravan-masi-playable.zip` | Packaged page + `audio/full.mp3` + ten stanza mp3s |

Working copy to open locally: keep `shravan-masi.html` and the `audio/` folder as siblings. Buttons resolve `audio/full.mp3` and `audio/stanza-0N.mp3` as relative URLs.

## Poem text used for TTS

Matches the live page’s Marathi (including that page’s spelling and spacing). Title + poet spoken only on the full-poem track.

```
श्रावण मासी हर्ष मानसी हिरवळ दाटे चोहिकडे;
क्षणात येते सरसर शिरवे क्षणात फिरुनी ऊन पडे.

वरती बघता इंद्रधनुचा गोफ दुहेरी विणलासे,
मंगल तोरण काय बांधले नभोमंडपी कुणी भासे!

झालासा सूर्यास्त वाटतो सांज अहाहा! तो उघडे,
तरु शिखरांवर, उंच घरांवर पिवळे पिवळे ऊन पडे.

उठती वरती जलदांवरती अनंत संध्या राग पहा;
पूर्ण नभांवर होय रेखिले सुंदरतेचे रूप महा.

बलाकमाला उडता भासे कल्प सुमांची माळचि ते,
उतरुनि येती अवनीवरती ग्रहगोलचि कि एकमते.

फडफड करुनी भिजले अपुले पंख पाखरे सावरती;
सुंदर हरिणी हिरव्या कुरणी निजबाळांसह बागडती.

खिल्लारे ही चरती रानी गोपहि गाणी गात फिरे
मंजुळ पावा गाय तयाचा श्रावण महिमा एकसुरे

सुवर्णचंपक फुलला, विपिनी रम्य केवडा दरवळला,
पारिजात ही बघता भामा, रोष मनीचा मावळला!

सुंदर परडि घेउनि हाती पुरोपकंठी शुद्धमती
सुंदर बाला या फुलमाला, रम्य फुले पत्री खुडती

देव दर्शना निघती ललना, हर्ष माइना हृदयात,
वदनी त्यांच्या वाचुनि घ्यावे श्रावण महिन्याचे गीत.
```

English column on the replica is the site’s existing AI translation, unchanged.

## Design decisions already made

- **Layout fidelity first.** CSS, structure, sticky column headers, word-gloss popups, Larger text, Print, notes `<details>`, and footer copy were taken from the live HTML. Only play controls and a light “now playing” tint were added.
- **Buttons match the site chrome.** Same border, radius, hover wash as “Larger text” / “Print”. Playing state fills `#263d34`.
- **Placement.** Full control sits in the existing toolbar. Stanza control sits in a `.stanza-head` flex row next to the couplet number, not in the English column.
- **Voice.** xAI Voice connector, voice id `naksh` (male, multilingual), `language: mr`. Then `ffmpeg atempo=0.82` so the read is slower than the raw TTS.
- **One `<audio>` element.** Clicking another button replaces `src`. Same button toggles pause/resume. On `ended`, labels reset.
- **No autoplay.** Click is the user gesture.
- **Print.** Play buttons hidden.

## How playback works (replica)

```
#play-full          data-src="audio/full.mp3"
.stanza-play        data-src="audio/stanza-01.mp3" … stanza-10.mp3
#poem-audio         single hidden <audio>
```

Labels: idle `Play poem` / `Play` → `Pause` while playing. Missing file → button text `Missing audio`.

Original interactions still work: hover/tap a Marathi word for the English gloss; Larger text toggles `body.large`; Print uses the existing print CSS.

## How to ship this on poemreader.smritiweb.com

The live host must do this. Sandbox cannot.

1. Upload `audio/full.mp3` and `audio/stanza-01.mp3`…`10.mp3` so they are public next to the poem HTML (or under `/audio/`).
2. Paste the extra CSS already in `shravan-masi.html` (`.listen`, `.stanza-head`, `.stanza.playing`, print hide).
3. Add the toolbar button before “Larger text”.
4. Wrap each `.number` link in `.stanza-head` and add the matching stanza button.
5. Add `<audio id="poem-audio" preload="metadata"></audio>` and the play/pause script from the replica (keep the existing gloss + larger-text IIFE).
6. Smoke-test desktop and phone: full play, one stanza, switch stanza mid-play, pause, print.

If the MP3 path is wrong, the button will show “Missing audio”.

## Constraints / known limits

- Live site is third-party from this session’s point of view.
- `naksh` is multilingual, not a dedicated All-India Radio Marathi voice. Pronunciation of a few sandhi forms and names (भामा, केवडा, परडि) should be checked by a Marathi ear.
- Full-poem track and stanza tracks were generated separately, so join points / energy will not match a single continuous take split by timestamps.
- Time-stretch (`atempo=0.82`) slightly colours the voice. Going much slower will sound drunk.
- First prototype `shravan-masi-reader.html` is a different visual design; do not mix it with the faithful replica unless a direction explicitly wants a new skin.

## Suggested directions (pick any)

Treat each as its own workstream. Do not assume all of them.

### A. Ship to the live Poem Reader
Patch the real `shravan-masi.html` on smritiweb (user pastes source, or they apply the zip). Add the same control pattern to other poems in that library.

### B. Better Marathi voice
Re-record with a different Voice id (`liora`, `aurora`, …), a human reader, or a Marathi-specific TTS. Keep the same filenames so the HTML does not change. Compare couplet 1 and 8 first (names + compact metre).

### C. One take, many cues
Generate **one** full poem with `with_timestamps: true`, then derive stanza start/end instead of ten separate files. Enables karaoke / current-line highlight.

### D. Follow-the-line UI
While audio plays, underline or tint the active Marathi verse (and optionally scroll it into view). Needs timestamps (direction C) or manual cue JSON.

### E. Whole Poem Reader kit
Reusable snippet: `data-audio-full` + `data-audio-stanza` conventions, shared CSS/JS, so every poem page gets the same buttons.

### F. Offline / share pack
PWA or a single self-contained HTML with audio inlined (heavy) or a small zip for classrooms. Marathi-first “How to read” copy.

### G. Recitation film / short
User also produces 10–20 s video and cultural work. Possible spin: one couplet, monsoon stills, piano under the same `naksh` (or a human) read. Separate from the reader page.

### H. Text-critical pass
Wikisource and other printings differ slightly (`श्रावणमासी` vs `श्रावण मासी`, `चोहीकडे` vs `चोहिकडे`, etc.). Page currently follows **smritiweb’s source image**. A direction could annotate variants without changing the spoken text until the site owner agrees.

## Voice / ffmpeg recipe (repeatable)

```text
Voice tool: voice_generate_speech
  voice: naksh
  language: mr
  dest_path: audio/raw/stanza-NN.mp3   (or full raw)

ffmpeg -i raw.mp3 -filter:a "atempo=0.82" -b:a 128k out.mp3
```

Full poem raw ≈ 76.7 s → stretched ≈ 93.5 s.  
Each couplet raw ≈ 7–8.5 s → stretched ≈ 9 s.

## Check before changing files

- Does the two-column desktop layout still match a screenshot of the live page?
- Do word glosses still open/close?
- Does only one clip play at a time?
- Are relative audio paths valid from wherever the HTML will be served?
- Print stylesheet: no play buttons, no grey playing tint.

## Out of scope unless asked

Rewriting the English translation, redesigning Poem Reader, adding background music on the reader page, or claiming the live URL was updated.
