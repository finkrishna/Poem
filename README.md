---
title: Poem Reader
emoji: 📜
colorFrom: green
colorTo: yellow
sdk: gradio
sdk_version: 6.27.0
app_file: app.py
python_version: "3.12"
startup_duration_timeout: 30m
short_description: Drop a poem, get a bilingual spoken reader
pinned: false
---

# Poem Reader

A bilingual poem / shloka reader. Paste text or a URL, get a two-column page: original on the left (hover a word to hear it and see a gloss), translation on the right.

Hobby project. Translations are model-generated and **not** scholar-reviewed.

## What you are looking at

| Piece | What it does |
|---|---|
| **Factory** (`index.html`) | Drop text, a file, or a URL. Grok detects the language, glosses words, writes a translation. |
| **Library** | Finished pages: [श्रावण मासी](shravan-masi-spoken.html) (Marathi) and [भज गोविन्दम्](bhaja-govindam.html) (Sanskrit, first 20 verses). |
| **Speech** | Factory readers use **voices already on your device** (browser Web Speech). Pick one in the Voice menu. Library poems also have recorded mp3s. |
| **Translation** | Hugging Face Inference **Kimi K2** (`moonshotai/Kimi-K2-Instruct:novita`), then DeepSeek V3.2, then SpaceXAI Grok. First ~2,000 tokens. Usually 10–20 seconds. |

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

1. **Hugging Face Spaces** — Gradio. Inference is **Kimi K2** via Hugging Face Inference Providers (Novita), chosen for gloss quality not price. Set Space secret `HF_TOKEN`. Optional fallback: `XAI_API_KEY`.
2. **[Render](https://render.com)** — Docker web service for the original HTML factory (`Dockerfile` + `render.yaml`).

Both: set a **spend cap** (you mentioned $5) at [console.x.ai](https://console.x.ai). The factory also caps **10 readers per visitor per hour** (`MAX_PER_HOUR`) and only builds **one reader at a time**.

The key stays on the server. Friends should not need to paste a key. `.env` is gitignored and is not served over HTTP.

```bash
docker build -t poem-reader .
docker run --rm -p 7860:7860 -e XAI_API_KEY=xai-... poem-reader
```

### Hugging Face Spaces, step by step

Do this **after** a spend cap is set at [console.x.ai](https://console.x.ai).

1. Make an account at [huggingface.co](https://huggingface.co/join) if you do not have one.
2. Open **[New Space](https://huggingface.co/new-space)**.
3. Fill in:
   - **Space name:** `poem-reader` (or anything)
   - **License:** MIT is fine
   - **SDK:** **Docker** (not Gradio, not Streamlit, not Static)
   - **Hardware:** CPU basic (free)
   - **Visibility:** Public (friends need no Hugging Face login). Private Spaces usually need a paid plan.
4. Click **Create Space**. You get an empty Space repo. Leave the tab open.
5. Add the API key: Space page → **Settings** → **Variables and secrets** → **New secret**
   - Name: `XAI_API_KEY` (exact spelling)
   - Value: your `xai-…` key  
   Runtime secrets become environment variables. The factory reads that name. Do **not** put the key in a public Variable, only in a Secret.
6. Push this GitHub repo into the Space (from your laptop, in the Poem folder):

```bash
# one-time: Hugging Face write token from https://huggingface.co/settings/tokens
git remote add spaces https://huggingface.co/spaces/YOUR_HF_USERNAME/poem-reader
git push spaces main
```

Use the Space name you actually created. The first push takes a few minutes while Docker builds.

7. Space page → **App** (or **Logs** if it is still building). When it is up, the URL is:

`https://huggingface.co/spaces/YOUR_HF_USERNAME/poem-reader`

Friends can use the factory there. They should **not** see a key box if the secret loaded (`/api/health` will show `"has_key": true`).

**If the App is blank or “port not ready”:** Logs should show `Poem factory http://0.0.0.0:7860/`. Hardware must be Docker + port 7860 (already set in this README’s header and in the Dockerfile).

**Sleep:** free CPU Spaces nap after idle time. The first visit after a nap is slow; that is normal.

**Later updates:** `git push origin main` (GitHub) and `git push spaces main` (Hugging Face), unless you later hook the two together.

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
