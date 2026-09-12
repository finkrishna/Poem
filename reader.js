/* Shared poem-reader: gloss popups + Web Speech (hover word, stanza, full). */
(function (global) {
  const VOICE_STORE = "poem.voiceURI";

  function allVoices() {
    if (!global.speechSynthesis) return [];
    return speechSynthesis.getVoices() || [];
  }

  function pickVoice(lang) {
    const voices = allVoices();
    if (!voices.length) return null;
    const saved = localStorage.getItem(VOICE_STORE);
    if (saved) {
      const chosen = voices.find((v) => v.voiceURI === saved);
      if (chosen) return chosen;
    }
    const prefix = (lang || "en").split("-")[0].toLowerCase();
    const fallbacks = { sa: ["hi", "en"], mr: ["hi", "en"], bn: ["hi", "en"], ta: ["en"], te: ["en"] };
    const order = [prefix].concat(fallbacks[prefix] || ["en"]);
    for (const p of order) {
      const hit = voices.find((v) => (v.lang || "").toLowerCase().startsWith(p));
      if (hit) return hit;
    }
    return voices[0] || null;
  }

  function fillVoiceSelect(select) {
    if (!select) return;
    const voices = allVoices();
    const saved = localStorage.getItem(VOICE_STORE) || "";
    const keep = select.value;
    select.innerHTML = "";
    const auto = document.createElement("option");
    auto.value = "";
    auto.textContent = "Auto (match poem language)";
    select.appendChild(auto);
    const groups = new Map();
    voices.forEach((v) => {
      const key = v.lang || "other";
      if (!groups.has(key)) groups.set(key, []);
      groups.get(key).push(v);
    });
    [...groups.keys()].sort().forEach((lang) => {
      const og = document.createElement("optgroup");
      og.label = lang;
      groups.get(lang).forEach((v) => {
        const o = document.createElement("option");
        o.value = v.voiceURI;
        o.textContent = v.name;
        og.appendChild(o);
      });
      select.appendChild(og);
    });
    const want = saved || keep;
    if (want && [...select.options].some((o) => o.value === want)) select.value = want;
    else select.value = "";
  }

  function wireVoiceSelect(select) {
    if (!select || select.dataset.wired) return;
    select.dataset.wired = "1";
    fillVoiceSelect(select);
    select.addEventListener("change", () => {
      if (select.value) localStorage.setItem(VOICE_STORE, select.value);
      else localStorage.removeItem(VOICE_STORE);
      document.querySelectorAll("select.voice-select").forEach((el) => {
        if (el !== select) fillVoiceSelect(el);
      });
    });
    if (typeof speechSynthesis !== "undefined" && speechSynthesis.addEventListener) {
      speechSynthesis.addEventListener("voiceschanged", () => {
        document.querySelectorAll("select.voice-select").forEach(fillVoiceSelect);
      });
    }
  }

  function speakText(text, lang, rate) {
    if (!global.speechSynthesis || !text) return;
    speechSynthesis.cancel();
    const u = new SpeechSynthesisUtterance(text);
    u.lang = lang || "en-US";
    u.rate = rate || 0.85;
    const v = pickVoice(u.lang);
    if (v) {
      u.voice = v;
      u.lang = v.lang || u.lang;
    }
    speechSynthesis.speak(u);
  }

  function stanzaOriginalText(stanza) {
    return (stanza.original || [])
      .map((line) => line.map((w) => w.t).join(" "))
      .join("। ");
  }

  function el(tag, attrs, children) {
    const node = document.createElement(tag);
    if (attrs) {
      Object.entries(attrs).forEach(([k, v]) => {
        if (v == null || v === false) return;
        if (k === "class") node.className = v;
        else if (k === "text") node.textContent = v;
        else if (k.startsWith("on") && typeof v === "function") node.addEventListener(k.slice(2), v);
        else node.setAttribute(k, v === true ? "" : String(v));
      });
    }
    (children || []).forEach((c) => {
      if (c == null) return;
      node.appendChild(typeof c === "string" ? document.createTextNode(c) : c);
    });
    return node;
  }

  function bindGloss(root, speechLang, getPlaying) {
    const popup = root.querySelector("#meaning-popup");
    const speakBtn = root.querySelector("#speak-words");
    let active = null;
    let pinned = false;
    let timer;
    let speakTimer;
    let speakOn = true;

    function stopWord() {
      clearTimeout(speakTimer);
      if (global.speechSynthesis) speechSynthesis.cancel();
    }
    function close() {
      clearTimeout(timer);
      clearTimeout(speakTimer);
      if (active) {
        active.classList.remove("active");
        active.removeAttribute("aria-describedby");
      }
      active = null;
      pinned = false;
      popup.hidden = true;
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
    function speakNow(word) {
      if (!speakOn || getPlaying()) return;
      speakText(word.textContent.trim(), speechLang, 0.8);
    }
    function show(word, pin, immediate) {
      close();
      active = word;
      pinned = pin;
      popup.textContent = word.dataset.meaning || "";
      popup.hidden = false;
      word.classList.add("active");
      word.setAttribute("aria-describedby", popup.id);
      position();
      if (pin || immediate) speakNow(word);
      else speakTimer = setTimeout(() => speakNow(word), 220);
    }

    root.querySelectorAll(".poem-word").forEach((word) => {
      word.addEventListener("pointerenter", (event) => {
        if (event.pointerType === "mouse" && !pinned) show(word, false, false);
      });
      word.addEventListener("pointerleave", () => {
        if (!pinned) timer = setTimeout(close, 180);
      });
      word.addEventListener("focus", () => {
        if (word.matches(":focus-visible")) show(word, false, true);
      });
      word.addEventListener("blur", () => {
        if (active === word) close();
      });
      word.addEventListener("click", () => {
        if (active === word && pinned) close();
        else show(word, true, true);
      });
    });
    popup.addEventListener("pointerenter", () => clearTimeout(timer));
    popup.addEventListener("pointerleave", () => {
      if (!pinned) timer = setTimeout(close, 180);
    });
    const ac = mountReader._ac;
    document.addEventListener("pointerdown", (event) => {
      if (!event.target.closest(".poem-word, .meaning-popup")) close();
    }, { signal: ac.signal });
    document.addEventListener("keydown", (event) => {
      if (event.key === "Escape") close();
    }, { signal: ac.signal });
    window.addEventListener("scroll", close, { passive: true, signal: ac.signal });
    window.addEventListener("resize", close, { signal: ac.signal });
    const size = root.querySelector("#size");
    if (size) {
      size.onclick = function () {
        close();
        this.setAttribute("aria-pressed", String(document.body.classList.toggle("large")));
      };
    }
    if (speakBtn) {
      speakBtn.addEventListener("click", () => {
        speakOn = !speakOn;
        speakBtn.setAttribute("aria-pressed", String(speakOn));
        if (!speakOn) stopWord();
      });
    }
    return { close, stopWord };
  }

  function mountReader(target, data) {
    if (mountReader._ac) mountReader._ac.abort();
    mountReader._ac = new AbortController();
    const speechLang = data.speech_lang || "en-US";
    const stanzas = data.stanzas || [];
    let currentBtn = null;
    const playing = { on: false };

    const toolbar = el("div", { class: "toolbar" }, [
      el("div", { class: "howto" }, [
        el("strong", { text: "How to read" }),
        el("ol", null, [
          el("li", null, [
            "Try to read the original first",
            el("span", { class: "wide-only", text: " (left column)" }),
            el("span", { class: "narrow-only", text: " (the first text in each stanza)" }),
            ".",
          ]),
          el("li", null, [
            el("span", { class: "hover-hint", text: "Hover over, or tab to," }),
            el("span", { class: "touch-hint", text: "Tap" }),
            " any word you don’t understand to hear it spoken and see its meaning.",
            el("span", { class: "touch-hint", text: " Tap anywhere else to close it." }),
          ]),
          el("li", null, [
            "For really difficult lines, read the translation ",
            el("span", { class: "wide-only", text: "in the right column" }),
            el("span", { class: "narrow-only", text: "after the stanza" }),
            ".",
          ]),
        ]),
      ]),
      el("button", { type: "button", id: "play-full", class: "listen", "aria-pressed": "false", text: "Play poem" }),
      el("label", { class: "voice-field", for: "reader-voice" }, [
        el("span", { text: "Voice" }),
        el("select", { id: "reader-voice", class: "voice-select", title: "Voices installed on this device" }),
      ]),
      el("button", { id: "size", "aria-pressed": "false", text: "Larger text" }),
      el("button", { type: "button", id: "speak-words", "aria-pressed": "true", text: "Speak words" }),
      el("button", { type: "button", text: "Print", onclick: () => window.print() }),
    ]);

    const sections = stanzas.map((stanza) => {
      const n = stanza.n;
      const nn = String(n).padStart(2, "0");
      const originalLines = (stanza.original || []).map((line, i, arr) => {
        const words = line.map((w) =>
          el("button", {
            type: "button",
            class: "poem-word",
            "data-meaning": w.m || "",
            text: w.t,
          })
        );
        const punct = i === arr.length - 1 ? " ॥" : " ।";
        const kids = [];
        words.forEach((w, idx) => {
          if (idx) kids.push(" ");
          kids.push(w);
        });
        kids.push(punct);
        return el("p", { class: "verse" }, kids);
      });
      const rendition = (stanza.rendition || []).map((line) => el("p", { class: "verse", text: line }));
      const note = stanza.note
        ? el("details", null, [el("summary", { text: "Note" }), el("p", { text: stanza.note })])
        : null;
      const play = el("button", {
        type: "button",
        class: "listen stanza-play",
        "aria-label": `Play stanza ${n}`,
        "aria-pressed": "false",
        "data-stanza": String(n - 1),
        text: "Play",
      });
      return el("section", { class: "stanza", id: `stanza-${n}`, style: "--rows:3", "aria-label": `Stanza ${n}` }, [
        el("div", { class: "pane original", lang: data.source_lang || "" }, [
          el("span", { class: "mobile-label", text: data.source_lang_label || "Original" }),
          el("div", { class: "stanza-head" }, [
            el("a", { class: "number", href: `#stanza-${n}`, "aria-label": `Stanza ${n}`, text: nn }),
            play,
          ]),
          ...originalLines,
        ]),
        el("div", { class: "pane rendition" }, [
          el("span", { class: "mobile-label", text: data.target_lang_label || "English" }),
          el("span", { class: "number spacer", "aria-hidden": "true" }),
          ...rendition,
        ]),
        note,
      ]);
    });

    const root = el("article", { class: "made-reader" }, [
      el("header", null, [
        el("p", { class: "eyebrow", text: `${data.source_lang_label || "Original"} · ${stanzas.length} stanza${stanzas.length === 1 ? "" : "s"}` }),
        el("h1", { lang: data.source_lang || "", text: data.title_original || "Untitled" }),
        el("h2", { class: "subtitle", text: data.title_translated || "" }),
        el("div", { class: "byline", text: data.poet || "" }),
        el("p", { class: "intro", text: data.intro || "" }),
        toolbar,
      ]),
      el("main", null, [
        el("div", { class: "columns" }, [
          el("div", null, [data.source_lang_label || "Original", el("small", { text: "original language" })]),
          el("div", null, [data.target_lang_label || "English", el("small", { text: "translation" })]),
        ]),
        ...sections,
      ]),
      el("footer", null, [
        el("p", {
          text: "Word meanings and the translation were generated for this reading and have not been reviewed. Hover or tap a word to hear the original and see the gloss.",
        }),
      ]),
      el("div", { id: "meaning-popup", class: "meaning-popup", role: "tooltip", lang: data.target_lang || "en", hidden: true }),
    ]);

    target.innerHTML = "";
    target.appendChild(root);

    function idleLabel(btn) {
      return btn.id === "play-full" ? "Play poem" : "Play";
    }
    function resetButtons() {
      root.querySelectorAll(".listen").forEach((btn) => {
        btn.setAttribute("aria-pressed", "false");
        btn.textContent = idleLabel(btn);
      });
      root.querySelectorAll(".stanza.playing").forEach((s) => s.classList.remove("playing"));
      currentBtn = null;
      playing.on = false;
    }
    function markPlaying(btn) {
      resetButtons();
      currentBtn = btn;
      playing.on = true;
      btn.setAttribute("aria-pressed", "true");
      btn.textContent = "Pause";
      const stanza = btn.closest(".stanza");
      if (stanza) stanza.classList.add("playing");
    }
    function toggleSpeak(btn, text) {
      if (currentBtn === btn && playing.on && speechSynthesis.speaking) {
        speechSynthesis.cancel();
        resetButtons();
        return;
      }
      markPlaying(btn);
      const u = new SpeechSynthesisUtterance(text);
      u.lang = speechLang;
      u.rate = 0.88;
      const v = pickVoice(speechLang);
      if (v) {
        u.voice = v;
        u.lang = v.lang || u.lang;
      }
      u.onend = () => {
        if (currentBtn === btn) resetButtons();
      };
      u.onerror = () => {
        if (currentBtn === btn) resetButtons();
      };
      speechSynthesis.cancel();
      speechSynthesis.speak(u);
    }

    bindGloss(root, speechLang, () => playing.on);
    wireVoiceSelect(root.querySelector("#reader-voice"));
    root.querySelector("#play-full").addEventListener("click", () => {
      const text = stanzas.map(stanzaOriginalText).join(". ");
      toggleSpeak(root.querySelector("#play-full"), text);
    });
    root.querySelectorAll(".stanza-play").forEach((btn) => {
      btn.addEventListener("click", () => {
        const stanza = stanzas[Number(btn.dataset.stanza)];
        toggleSpeak(btn, stanzaOriginalText(stanza));
      });
    });
    root.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  global.PoemReader = { mountReader, speakText, fillVoiceSelect, wireVoiceSelect };
})(window);
