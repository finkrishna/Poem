const TARGETS = [
  ["en", "English"],
  ["hi", "Hindi"],
  ["mr", "Marathi"],
  ["sa", "Sanskrit"],
  ["ta", "Tamil"],
  ["te", "Telugu"],
  ["kn", "Kannada"],
  ["ml", "Malayalam"],
  ["bn", "Bengali"],
  ["gu", "Gujarati"],
  ["pa", "Punjabi"],
  ["ur", "Urdu"],
  ["es", "Spanish"],
  ["fr", "French"],
  ["de", "German"],
  ["it", "Italian"],
  ["pt", "Portuguese"],
  ["ru", "Russian"],
  ["ja", "Japanese"],
  ["ko", "Korean"],
  ["zh", "Chinese"],
  ["ar", "Arabic"],
  ["tr", "Turkish"],
  ["id", "Indonesian"],
  ["vi", "Vietnamese"],
  ["nl", "Dutch"],
  ["fa", "Persian"],
  ["th", "Thai"],
];

const MAX_CHARS = 8000; // ~2000 tokens

const $ = (id) => document.getElementById(id);

function truncate(text) {
  const t = (text || "").replace(/\u0000/g, " ").trim();
  if (t.length <= MAX_CHARS) return { text: t, truncated: false };
  const cut = t.slice(0, MAX_CHARS);
  const sp = cut.lastIndexOf(" ");
  return { text: (sp > 2000 ? cut.slice(0, sp) : cut).trim(), truncated: true };
}

function setStatus(msg, isError) {
  const el = $("status");
  el.textContent = msg || "";
  el.classList.toggle("error", Boolean(isError));
}

function fillLangs() {
  const sel = $("target-lang");
  TARGETS.forEach(([code, label]) => {
    const o = document.createElement("option");
    o.value = code;
    o.textContent = label;
    if (code === "en") o.selected = true;
    sel.appendChild(o);
  });
}

function currentTarget() {
  const sel = $("target-lang");
  const opt = sel.selectedOptions[0];
  return { code: sel.value, label: opt ? opt.textContent : "English" };
}

function readFileAsText(file) {
  return new Promise((resolve, reject) => {
    const lower = file.name.toLowerCase();
    if (/\.(pdf|png|jpe?g|gif|webp|mp3|zip)$/.test(lower)) {
      reject(new Error("Please drop a text file (.txt, .md, .html) or paste the text."));
      return;
    }
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result || ""));
    reader.onerror = () => reject(new Error("Could not read that file."));
    reader.readAsText(file);
  });
}

async function health() {
  try {
    const r = await fetch("/api/health", { cache: "no-store" });
    if (!r.ok) return { ok: false };
    return await r.json();
  } catch {
    return { ok: false };
  }
}

async function processOnServer(payload) {
  const r = await fetch("/api/process", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const data = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(data.error || `Server error ${r.status}`);
  return data;
}

function systemPrompt() {
  return `You are a poem/shloka reader factory. Turn source text into a bilingual reader.
Rules:
- Detect the source language. Do not invent verses or words that are not in the input.
- Keep original spelling. Split into stanzas the way the source is lined (blank lines, verse numbers, or couplets).
- Each original line is an array of words {t, m}. t is the source word; m is a short gloss in the TARGET language, as used in that line.
- rendition: fluent TARGET-language lines, one per original line (or two lines per couplet if that reads better), not a word salad.
- If the source is prose, one paragraph = one stanza; split into short lines.
- speech_lang must be a BCP-47 tag the browser can speak for the SOURCE (sa → hi-IN, mr → mr-IN, hi → hi-IN, en → en-US, zh → zh-CN, etc.).
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
}`;
}

async function processInBrowser(text, target, apiKey) {
  const r = await fetch("https://api.x.ai/v1/chat/completions", {
    method: "POST",
    headers: {
      Authorization: `Bearer ${apiKey}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      model: "grok-4.5",
      temperature: 0.2,
      messages: [
        { role: "system", content: systemPrompt() },
        {
          role: "user",
          content: `TARGET language: ${target.label} (${target.code})\n\nSOURCE TEXT:\n${text}`,
        },
      ],
    }),
  });
  if (!r.ok) {
    const err = await r.text();
    throw new Error(`SpaceXAI ${r.status}: ${err.slice(0, 240)}`);
  }
  const data = await r.json();
  const content = data.choices?.[0]?.message?.content || "";
  const start = content.indexOf("{");
  const end = content.lastIndexOf("}");
  if (start < 0 || end < 0) throw new Error("Model did not return JSON.");
  const poem = JSON.parse(content.slice(start, end + 1));
  poem.target_lang = target.code;
  poem.target_lang_label = target.label;
  return poem;
}

function normalizePoem(poem, target) {
  const stanzas = (poem.stanzas || []).map((s, i) => {
    let original = s.original;
    if (!original && s.sa) {
      original = s.sa.map((line) =>
        line.map((pair) => (Array.isArray(pair) ? { t: pair[0], m: pair[1] } : pair))
      );
    }
    return {
      n: s.n || i + 1,
      original: original || [],
      rendition: s.rendition || s.en || [],
      note: s.note || null,
    };
  });
  return {
    source_lang: poem.source_lang || poem.lang || "",
    source_lang_label: poem.source_lang_label || poem.lang_label || "Original",
    speech_lang: poem.speech_lang || "en-US",
    title_original: poem.title_original || poem.title_sa || "Untitled",
    title_translated: poem.title_translated || poem.title_en || "",
    poet: poem.poet || "",
    intro: poem.intro || "",
    stanzas,
    target_lang: poem.target_lang || target.code,
    target_lang_label: poem.target_lang_label || target.label,
  };
}

async function makeReader() {
  const target = currentTarget();
  const url = $("source-url").value.trim();
  let raw = $("source-text").value;
  setStatus("Working…");
  $("go").disabled = true;
  try {
    if (!raw.trim() && !url) throw new Error("Paste text, drop a file, or give a URL.");
    const info = await health();
    const apiKey = $("api-key").value.trim() || sessionStorage.getItem("poem.xaiKey") || "";
    if (apiKey) sessionStorage.setItem("poem.xaiKey", apiKey);

    let poem;
    if (info.ok) {
      poem = await processOnServer({
        text: raw,
        url: url || undefined,
        target_lang: target.code,
        target_lang_label: target.label,
        api_key: apiKey || undefined,
      });
    } else {
      if (url && !raw.trim()) {
        throw new Error("URL fetch needs the local factory server (python3 factory_server.py). Or paste the text.");
      }
      const clipped = truncate(raw);
      if (!clipped.text) throw new Error("Nothing to read.");
      if (!apiKey) {
        throw new Error("No factory server and no SpaceXAI key. Run python3 factory_server.py (with XAI_API_KEY) or paste a key below.");
      }
      if (clipped.truncated) setStatus("Using the first ~2000 tokens…");
      poem = await processInBrowser(clipped.text, target, apiKey);
    }

    poem = normalizePoem(poem, target);
    $("detected").hidden = false;
    $("detected").textContent = `Detected: ${poem.source_lang_label || poem.source_lang || "unknown"} → ${poem.target_lang_label}`;
    PoemReader.mountReader($("reader-root"), poem);
    const extra = poem.truncated ? " (first ~2000 tokens)" : "";
    setStatus(`Ready · ${poem.stanzas?.length || 0} stanzas${extra}`);
  } catch (err) {
    setStatus(err.message || String(err), true);
  } finally {
    $("go").disabled = false;
  }
}

function wireDrop() {
  const drop = $("drop");
  const prevent = (e) => {
    e.preventDefault();
    e.stopPropagation();
  };
  ["dragenter", "dragover"].forEach((ev) =>
    drop.addEventListener(ev, (e) => {
      prevent(e);
      drop.classList.add("drag");
    })
  );
  ["dragleave", "drop"].forEach((ev) =>
    drop.addEventListener(ev, (e) => {
      prevent(e);
      if (ev === "dragleave") drop.classList.remove("drag");
    })
  );
  drop.addEventListener("drop", async (e) => {
    drop.classList.remove("drag");
    const file = e.dataTransfer.files && e.dataTransfer.files[0];
    if (!file) return;
    try {
      $("source-text").value = await readFileAsText(file);
      setStatus(`Loaded ${file.name}`);
    } catch (err) {
      setStatus(err.message, true);
    }
  });
  $("file-input").addEventListener("change", async (e) => {
    const file = e.target.files && e.target.files[0];
    if (!file) return;
    try {
      $("source-text").value = await readFileAsText(file);
      setStatus(`Loaded ${file.name}`);
    } catch (err) {
      setStatus(err.message, true);
    }
  });
}

async function boot() {
  fillLangs();
  wireDrop();
  $("go").addEventListener("click", makeReader);
  const saved = sessionStorage.getItem("poem.xaiKey");
  if (saved) $("api-key").value = saved;
  const info = await health();
  if (info.ok) {
    $("key-wrap").hidden = Boolean(info.has_key);
    setStatus(info.has_key ? "Factory server is up." : "Factory server is up. Paste a SpaceXAI key to run.");
  } else {
    $("key-wrap").hidden = false;
    setStatus("Static page: paste a SpaceXAI key to run in the browser, or start python3 factory_server.py for URL fetch.");
  }
  if (speechSynthesis.getVoices) speechSynthesis.getVoices();
  if (new URLSearchParams(location.search).get("demo") === "1") {
    const raw = await fetch("bhaja-govindam.json").then((r) => r.json());
    raw.speech_lang = "hi-IN";
    const poem = normalizePoem(raw, { code: "en", label: "English" });
    $("detected").hidden = false;
    $("detected").textContent = `Detected: ${poem.source_lang_label} → English (demo)`;
    PoemReader.mountReader($("reader-root"), poem);
    setStatus("Demo reader from the Bhaja Govindam library file.");
  }
}

document.addEventListener("DOMContentLoaded", boot);
