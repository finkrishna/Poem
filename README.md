# Poem Reader

A bilingual poem / shloka reader. Paste text or a URL, get a two-column page: original on the left (hover a word to hear it and see a gloss), translation on the right.

Hobby project. Translations are model-generated and **not** scholar-reviewed.

## What you are looking at

| Piece | What it does |
|---|---|
| **Factory** (`index.html`) | Drop text, a file, or a URL. Grok detects the language, glosses words, writes a translation. |
| **Library** | Finished pages: [श्रावण मासी](shravan-masi-spoken.html) (Marathi) and [भज गोविन्दम्](bhaja-govindam.html) (Sanskrit, first 20 verses). |
| **Speech** | Factory readers use **voices already on your device** (browser Web Speech). Pick one in the Voice menu. Library poems also have recorded mp3s. |
| **Translation** | [SpaceXAI](https://console.x.ai) **Grok** (`grok-4.5` by default). First ~2,000 tokens of the source. Often 1–2 minutes. |

There is no Sanskrit vidwan or ghanapāṭha engine here. A Hindi or Indian-English system voice is usually the closest the browser has.

## Run on your laptop

Python 3.9+ (stdlib only). No pip packages.

```bash
cp .env.example .env
# put XAI_API_KEY=xai-... in .env  (from https://console.x.ai)
python3 factory_server.py
```

Open http://127.0.0.1:8765/

GitHub Pages can serve the **library HTML** statically. It cannot run the factory (that needs the Python process and the key).

## Put the factory on the internet (for friends)

**Do not use Streamlit.** This app is already HTML/JS plus a tiny Python API. Streamlit would throw the reader away.

Use a **Docker** host that keeps a process running and lets requests take a couple of minutes (Grok is slow on a long shloka):

1. **[Hugging Face Spaces](https://huggingface.co/new-space)** — Docker SDK, port **7860**. Good for sharing an AI hobby app. Add a Space secret `XAI_API_KEY`.
2. **[Render](https://render.com)** — New Web Service from this repo, Docker runtime. This repo includes `render.yaml`. Set `XAI_API_KEY` in the dashboard.

Both: set a **spend cap** (you mentioned $5) at [console.x.ai](https://console.x.ai). The factory also caps **10 readers per visitor per hour** (`MAX_PER_HOUR`) and only builds **one reader at a time**.

The key stays on the server. Friends should not need to paste a key. `.env` is gitignored and is not served over HTTP.

```bash
docker build -t poem-reader .
docker run --rm -p 7860:7860 -e XAI_API_KEY=xai-... poem-reader
```

## Voice menu

- **Auto** — pick a system voice that matches the poem language (Sanskrit → Hindi if present).
- **Named voices** — whatever your OS/browser installed. macOS usually has more than a phone.
- Choice is saved in `localStorage` on that browser, not on the server.

Recorded recitation (xAI Voice `naksh` on the Shravan / Bhaja pages) is separate from this picker.

## API (factory server)

| Path | Point |
|---|---|
| `GET /api/health` | `{ ok, has_key, model }` |
| `POST /api/fetch` | `{ url }` → `{ text, truncated }` |
| `POST /api/process` | `{ text, target_lang, target_lang_label }` → `{ job_id }` then poll |
| `GET /api/job/<id>` | `{ status: working \| done \| error, poem? }` |

## Repo map

- `factory_server.py` — static files + fetch + Grok job
- `factory.js` / `index.html` — drop zone
- `reader.js` / `reader.css` — two-column reader + voice menu
- `audio/` — mp3s for the library pages
- `PROJECT.md` — original Shravan Masi brief

## Safety

- Do not commit `.env`.
- Cap spend on the xAI console before you send the link.
- Gloss and translation can be wrong; treat them as a reading aid.
