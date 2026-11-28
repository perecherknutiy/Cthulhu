// ARA Casino — мини-приложение казино на USDT. Чистый JS без сборки.
// Внутри Telegram ходит в настоящий API, вне Telegram (если подключён demo-api.js) — в демо-режиме.
// Адрес API и принудительное демо — в config.js.
(function () {
  "use strict";

  const tg = window.Telegram?.WebApp;
  tg?.ready();
  tg?.expand();
  tg?.disableVerticalSwipes?.(); // своя прокрутка: случайный свайп вниз не сворачивает приложение
  const CFG = window.ARA_CONFIG || {};
  const DEMO = !!window.DemoApi && (CFG.demo === true || !tg?.initData);
  const API_BASE = String(CFG.apiBase || "").replace(/\/+$/, "");
  const VERSION = "0.5.0";

  // ================================================================ helpers
  const $ = (sel, root = document) => root.querySelector(sel);
  const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];
  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
  const clamp = (v, a, b) => Math.min(b, Math.max(a, v));
  const locale = () => (S.lang === "ru" ? "ru-RU" : "en-US");
  const fmt = (n) => Number(n || 0).toLocaleString(locale());
  // Деньги — USDT. API отдаёт целые микро-USDT (1 USDT = 1 000 000); показываем 2–4 знака, лишнее отбрасываем.
  const U = 1e6;
  const usd = (u) => {
    const n = Math.round(Number(u || 0));
    const v = Math.floor(Math.abs(n) / 100) / 1e4;
    return (n < 0 ? "−" : "") + v.toLocaleString(locale(), { minimumFractionDigits: 2, maximumFractionDigits: 4 });
  };
  // ввод «12,5» / «12.50» → микро-USDT (точность 0.0001)
  const toUnits = (x) => Math.round(parseFloat(String(x).replace(",", ".").replace(/\s/g, "")) * 1e4) * 100 || 0;
  const fmtX = (m) => Number(m).toLocaleString(locale(), { minimumFractionDigits: 2, maximumFractionDigits: 2 }) + "×";
  const fmtTime = (iso) => new Date(iso).toLocaleTimeString(locale(), { hour: "2-digit", minute: "2-digit" });
  const fmtDate = (iso) => new Date(iso).toLocaleString(locale(), { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" });

  // ---------------------------------------------------------------- icons (24×24, stroke)
  const P = {
    menu: '<path d="M4 7h16M4 12h16M4 17h16"/>',
    chat: '<path d="M21 11.5a8.4 8.4 0 0 1-12.2 7.5L3 20.5l1.6-5A8.4 8.4 0 1 1 21 11.5z"/>',
    play: '<rect x="2.5" y="6.5" width="19" height="11" rx="5.5"/><path d="M7 12h4M9 10v4M15.5 11h.01M18 13h.01"/>',
    plus: '<path d="M12 5v14M5 12h14"/>',
    user: '<circle cx="12" cy="8" r="4"/><path d="M4 21a8 8 0 0 1 16 0"/>',
    gear: '<circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.5-1.1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z"/>',
    help: '<circle cx="12" cy="12" r="10"/><path d="M9.1 9a3 3 0 0 1 5.8 1c0 2-3 3-3 3M12 17h.01"/>',
    back: '<path d="m15 18-6-6 6-6"/>',
    chev: '<path d="m9 18 6-6-6-6"/>',
    x: '<path d="M18 6 6 18M6 6l12 12"/>',
    send: '<path d="M22 2 11 13M22 2l-7 20-4-9-9-4z"/>',
    copy: '<rect x="9" y="9" width="12" height="12" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/>',
    share: '<circle cx="18" cy="5" r="3"/><circle cx="6" cy="12" r="3"/><circle cx="18" cy="19" r="3"/><path d="m8.6 13.5 6.8 4M15.4 6.5l-6.8 4"/>',
    pen: '<path d="M17 3a2.8 2.8 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5z"/>',
    crown: '<path d="M3 18h18M4 8l4.5 4L12 5l3.5 7L20 8l-1.5 10h-13z"/>',
    gift: '<rect x="3" y="8" width="18" height="4" rx="1"/><path d="M12 8v13M19 12v7a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2v-7M7.5 8a2.5 2.5 0 0 1 0-5C11 3 12 8 12 8s1-5 4.5-5a2.5 2.5 0 0 1 0 5"/>',
    shield: '<path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/><path d="m9 12 2 2 4-4"/>',
    clock: '<circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/>',
    list: '<path d="M8 6h13M8 12h13M8 18h13M3 6h.01M3 12h.01M3 18h.01"/>',
    wallet: '<path d="M20 7H5a2 2 0 0 1 0-4h13v4"/><path d="M3 5v14a2 2 0 0 0 2 2h15V7"/><path d="M16 14h.01"/>',
    up: '<path d="M7 17 17 7M8 7h9v9"/>',
    info: '<circle cx="12" cy="12" r="10"/><path d="M12 16v-4M12 8h.01"/>',
    doc: '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><path d="M14 2v6h6M8 13h8M8 17h5"/>',
    check: '<path d="M20 6 9 17l-5-5"/>',
    lock: '<rect x="4" y="11" width="16" height="10" rx="2"/><path d="M8 11V7a4 4 0 0 1 8 0v4"/>',
    grid: '<rect x="3" y="3" width="7.5" height="7.5" rx="2"/><rect x="13.5" y="3" width="7.5" height="7.5" rx="2"/><rect x="3" y="13.5" width="7.5" height="7.5" rx="2"/><rect x="13.5" y="13.5" width="7.5" height="7.5" rx="2"/>',
    trophy: '<path d="M8 21h8M12 17v4M7 4h10v5a5 5 0 0 1-10 0z"/><path d="M17 5h3v2a3 3 0 0 1-3 3M7 5H4v2a3 3 0 0 0 3 3"/>',
    pin: '<path d="M20 10c0 6-8 12-8 12s-8-6-8-12a8 8 0 0 1 16 0z"/><circle cx="12" cy="10" r="3"/>',
    support: '<path d="M3 18v-6a9 9 0 0 1 18 0v6"/><path d="M21 19a2 2 0 0 1-2 2h-1v-6h3zM3 19a2 2 0 0 0 2 2h1v-6H3z"/>',
  };
  const ic = (name, cls = "i") => `<svg class="${cls}" viewBox="0 0 24 24" aria-hidden="true">${P[name]}</svg>`;
  // значок USDT: ₮ в круге
  const CUR = '<svg class="cur" viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="11"/><path class="cur-t" d="M6.6 6.4h10.8V9h-4.1v1.9c2.5.2 4.4.8 4.4 1.6s-1.9 1.4-4.4 1.6v4.6h-2.6v-4.6c-2.5-.2-4.4-.8-4.4-1.6s1.9-1.4 4.4-1.6V9H6.6zm4.1 5.2c-1.6.1-2.6.4-2.6.6s1.2.6 3.9.6 3.9-.3 3.9-.6-1-.5-2.6-.6v1h-2.6z"/></svg>';
  const LOGO = `<svg viewBox="0 0 64 64" aria-hidden="true"><defs>
    <linearGradient id="au-bg" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#3a74ff"/><stop offset="1" stop-color="#0c1b4d"/></linearGradient>
    <linearGradient id="au-gd" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#f7e5ad"/><stop offset="1" stop-color="#c8963a"/></linearGradient></defs>
    <rect width="64" height="64" rx="16" fill="url(#au-bg)"/><rect x="1.5" y="1.5" width="61" height="61" rx="14.5" fill="none" stroke="url(#au-gd)" stroke-opacity=".6"/>
    <path d="M16 46 29 14h6l14 32h-8l-3-8H26l-3 8Zm12-14h8l-4-12Z" fill="url(#au-gd)"/><path d="m32 49 4 4-4 4-4-4Z" fill="url(#au-gd)"/></svg>`;

  // ---------------------------------------------------------------- иллюстрации (webapp/assets)
  const A = (p) => `assets/${p}.webp`;
  const img = (p, cls = "", alt = "") => `<img src="${A(p)}"${cls ? ` class="${cls}"` : ""} alt="${esc(alt)}" draggable="false" decoding="async">`;
  const COVER = { dice: "covers/dice", coinflip: "covers/coinflip", plinko: "covers/plinko", mines: "covers/mines", roulette: "covers/roulette", crash: "covers/crash" };
  const cover = (g) => (g === "limbo" ? `${img("effects/gold-starburst")}<span class="limbo-x">2,00×</span>` : img(COVER[g]));
  const NEWS_IMG = { rocket: "future/rocket", "chip-stack": "roulette/chip-stack", trophy: "shared/trophy", seven: "slots/seven", "gift-sapphire": "shared/gift-sapphire" };
  // символы слотов: от самого частого (0) к самому редкому (5) — порядок как в таблице выплат
  const SLOT_SYMBOLS = {
    classic: ["slots/cherries", "slots/lemon", "slots/bell", "slots/star", "slots/diamond-blue", "slots/seven"],
    treasury: ["shared/daily-token", "shared/key", "shared/mystery-token", "shared/gift-sapphire", "shared/chest-open", "mines/gem-emerald"],
    royal: ["shared/heart", "shared/shield", "shared/medal-silver", "shared/medal-gold", "shared/trophy", "shared/crown-diamond"],
  };
  const VIP_IMG = ["shared/medal-bronze", "shared/medal-silver", "shared/medal-gold", "slots/diamond-blue", "shared/crown-diamond"];
  const preload = (paths) => paths.forEach((p) => { const i = new Image(); i.src = A(p); });

  // ================================================================ settings
  const SETTINGS_KEY = "ara-settings-v2"; // v2 — суммы в USDT (микро-единицы)
  const userLang = (tg?.initDataUnsafe?.user?.language_code || navigator.language || "ru").toLowerCase();
  const DEFAULTS = {
    lang: userLang.startsWith("ru") || userLang.startsWith("uk") || userLang.startsWith("be") || userLang.startsWith("kk") ? "ru" : "en",
    theme: "auto", sound: true, haptics: true, motion: true, hideBalance: false,
    confirmAbove: 0, depositLimit: 0, pauseUntil: 0, ageOk: false, bet: 1_000_000, crashAuto: 0,
  };
  let S = { ...DEFAULTS };
  try { Object.assign(S, JSON.parse(localStorage.getItem(SETTINGS_KEY) || "{}")); } catch { /* приватный режим */ }

  function saveSettings() {
    const json = JSON.stringify(S);
    try { localStorage.setItem(SETTINGS_KEY, json); } catch { /* нет localStorage */ }
    try { tg?.CloudStorage?.setItem(SETTINGS_KEY, json); } catch { /* старый клиент */ }
  }
  function loadCloudSettings() {
    return new Promise((resolve) => {
      if (!tg?.CloudStorage?.getItem) return resolve();
      try {
        tg.CloudStorage.getItem(SETTINGS_KEY, (err, val) => {
          if (!err && val) { try { Object.assign(S, JSON.parse(val)); } catch { /* битые данные */ } }
          resolve();
        });
      } catch { resolve(); }
      setTimeout(resolve, 800);
    });
  }

  // ================================================================ i18n
  const missing = (window.__missingI18n = window.__missingI18n || new Set());
  function t(key, vars) {
    let s = window.I18N?.[S.lang]?.[key] ?? window.I18N?.ru?.[key];
    if (s == null) { missing.add(key); return key; }
    if (vars) s = s.replace(/\{(\w+)\}/g, (_, k) => (vars[k] ?? ""));
    return s;
  }
  const hasKey = (key) => window.I18N?.[S.lang]?.[key] != null;
  const C = () => window.CONTENT?.[S.lang] || window.CONTENT?.ru;

  // ================================================================ theme
  function isDark() {
    if (S.theme === "dark") return true;
    if (S.theme === "light") return false;
    if (tg?.colorScheme) return tg.colorScheme === "dark";
    return window.matchMedia?.("(prefers-color-scheme: dark)").matches ?? true;
  }
  function applyTheme() {
    const dark = isDark();
    document.documentElement.dataset.theme = dark ? "dark" : "light";
    document.documentElement.classList.toggle("reduce-motion", !S.motion);
    document.documentElement.lang = S.lang;
    const bg = dark ? "#0c1812" : "#edf4ee";
    try { tg?.setHeaderColor?.(bg); tg?.setBackgroundColor?.(bg); tg?.setBottomBarColor?.(bg); } catch { /* старый клиент */ }
  }
  tg?.onEvent?.("themeChanged", applyTheme);

  // ================================================================ sound & haptics
  let audio = null;
  function tone(freq, dur = 0.08, type = "sine", gain = 0.06, delay = 0) {
    if (!S.sound) return;
    try {
      audio = audio || new (window.AudioContext || window.webkitAudioContext)();
      const o = audio.createOscillator(), g = audio.createGain();
      const t0 = audio.currentTime + delay;
      o.type = type; o.frequency.value = freq;
      g.gain.setValueAtTime(gain, t0);
      g.gain.exponentialRampToValueAtTime(0.0001, t0 + dur);
      o.connect(g).connect(audio.destination);
      o.start(t0); o.stop(t0 + dur + 0.02);
    } catch { /* без звука */ }
  }
  const fx = {
    tap() { if (S.haptics) tg?.HapticFeedback?.impactOccurred("light"); tone(520, 0.04, "triangle", 0.03); },
    win() { if (S.haptics) tg?.HapticFeedback?.notificationOccurred("success"); [523, 659, 784].forEach((f, i) => tone(f, 0.14, "triangle", 0.06, i * 0.08)); },
    lose() { if (S.haptics) tg?.HapticFeedback?.notificationOccurred("warning"); tone(196, 0.18, "sine", 0.05); },
    error() { if (S.haptics) tg?.HapticFeedback?.notificationOccurred("error"); },
    tick() { tone(880, 0.02, "square", 0.015); },
  };

  // ================================================================ API
  class ApiErr extends Error { constructor(code, message) { super(message); this.code = code; } }
  async function api(path, body) {
    if (DEMO) return window.DemoApi.request(path, body);
    const res = await fetch(API_BASE + path, {
      method: body === undefined ? "GET" : "POST",
      headers: { "Content-Type": "application/json", Authorization: "tma " + (tg?.initData || "") },
      body: body === undefined ? undefined : JSON.stringify(body),
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new ApiErr(data?.error?.code || "http_" + res.status, data?.error?.message || `HTTP ${res.status}`);
    return data;
  }
  function errText(e) {
    const c = state.config || {};
    const vars = { min_bet: usd(c.min_bet), max_bet: usd(c.max_bet), max_payout: usd(c.max_payout), dep_min: usd(c.deposit?.min),
                   wd_min: usd(c.withdraw?.min), wd_max: usd(c.withdraw?.max), left: usd(state.me?.wager_left) };
    if (e?.code && hasKey("err." + e.code)) return t("err." + e.code, vars);
    return e?.message || t("err.generic");
  }
  async function guard(fn) {
    try { return await fn(); } catch (e) { toast(errText(e)); fx.error(); return undefined; }
  }

  // ================================================================ toast & sheets
  let toastTimer;
  function toast(text) {
    const el = $("#toast");
    el.textContent = text;
    el.classList.add("show");
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => el.classList.remove("show"), 2600);
  }

  function openSheet(html, { onClose, cls = "" } = {}) {
    closeSheet({ instant: true });
    const bg = document.createElement("div");
    bg.className = "sheet-bg";
    bg.innerHTML = `<div class="sheet ${cls}" role="dialog" aria-modal="true"><div class="grip"></div>${html}</div>`;
    bg.addEventListener("click", (e) => { if (e.target === bg) closeSheet(); });
    bg._onClose = onClose;
    document.body.appendChild(bg);
    return bg.firstElementChild;
  }
  function closeSheet({ instant = false } = {}) {
    const bg = $(".sheet-bg:not(.closing)");
    if (!bg) return;
    bg._onClose?.();
    if (instant || !S.motion) return bg.remove();
    bg.classList.add("closing"); // шторка уезжает вниз, фон гаснет
    setTimeout(() => bg.remove(), 200);
  }
  function confirmSheet(title, text, okLabel, danger = false) {
    return new Promise((resolve) => {
      const sh = openSheet(`<h2>${esc(title)}</h2><p class="muted">${esc(text)}</p>
        <div class="actions"><button class="btn ghost" data-a="no">${t("common.cancel")}</button>
        <button class="btn ${danger ? "danger" : "primary"}" data-a="yes">${esc(okLabel)}</button></div>`, { onClose: () => resolve(false) });
      sh.querySelector('[data-a="no"]').onclick = () => closeSheet();
      sh.querySelector('[data-a="yes"]').onclick = () => { $(".sheet-bg")._onClose = null; closeSheet(); resolve(true); };
    });
  }

  async function copy(text) {
    try { await navigator.clipboard.writeText(text); toast(t("common.copied")); }
    catch { toast(t("common.copy_failed")); }
  }

  // ================================================================ state & router
  const state = { config: null, me: null, route: "play", stack: [], cleanup: [], bets: {} };
  // рейтинг открывается и с «Играть» (новости), и из профиля — подсвечиваем вкладку, откуда пришли
  const ROOT_OF = (r) => (r === "chat" ? "chat" : /^(play|game|slot|wallet)/.test(r) ? "play"
    : r === "leaders" && state.stack[0] && ROOT_OF(state.stack[0]) === "play" ? "play" : "menu");

  // ---------------------------------------------------------------- переходы
  // forward — вглубь (новый экран приезжает справа), back — назад (слева),
  // tab-right / tab-left — между вкладками футера, fade — смена темы/языка.
  const TAB_INDEX = { menu: 0, chat: 1, play: 2 }; // порядок вкладок слева направо
  const memo = {}; // прокрутка экранов: route -> { top, car: [scrollLeft каруселей] }
  const reducedMotion = () => !S.motion || window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;

  // Старый экран превращается в неактивную «тень» поверх и уезжает, новый экран сразу живой:
  // нажатие во время анимации не теряется, и всё работает в любом WebView Telegram.
  function transition(update, dir = "fade") {
    if (reducedMotion() || dir === "none") return update();
    const view = $("#view");
    $$(".view.ghost").forEach((g) => g.remove());
    const ghost = view.cloneNode(true);
    ghost.removeAttribute("id");
    ghost.querySelectorAll("[id]").forEach((el) => el.removeAttribute("id"));
    ghost.setAttribute("aria-hidden", "true");
    ghost.inert = true;
    ghost.classList.add("ghost");
    document.body.appendChild(ghost);
    ghost.scrollTop = view.scrollTop;
    const oldCar = $$(".carousel", view), newCar = $$(".carousel", ghost);
    newCar.forEach((c, i) => { c.scrollLeft = oldCar[i]?.scrollLeft || 0; });
    const oldCv = $$("canvas", view), newCv = $$("canvas", ghost);
    newCv.forEach((c, i) => { try { c.getContext("2d").drawImage(oldCv[i], 0, 0); } catch { /* пустой холст */ } });

    update();

    const out = { forward: "out-left", "tab-right": "out-left", back: "out-right", "tab-left": "out-right" }[dir] || "out-fade";
    const inn = { forward: "in-right", "tab-right": "in-right", back: "in-left", "tab-left": "in-left" }[dir] || "in-fade";
    ghost.classList.add(out);
    const scr = $("#screen");
    scr.classList.remove("in-right", "in-left", "in-fade");
    void scr.offsetWidth;
    scr.classList.add(inn);
    const done = () => ghost.remove();
    ghost.addEventListener("animationend", done, { once: true });
    setTimeout(done, 450);
  }

  function remember() {
    const v = $("#view");
    memo[state.route] = { top: v.scrollTop, car: $$(".carousel", v).map((c) => c.scrollLeft) };
  }
  function tabDir(from, to) {
    const a = TAB_INDEX[ROOT_OF(from)], b = TAB_INDEX[ROOT_OF(to)];
    return b > a ? "tab-right" : b < a ? "tab-left" : "back";
  }

  function go(route) {
    if (state.route === route) return;
    remember();
    state.stack.push(state.route);
    state.route = route;
    render("forward");
  }
  function goRoot(route) {
    if (state.route === route && !state.stack.length) return;
    remember();
    const dir = tabDir(state.route, route);
    state.stack = [];
    state.route = route;
    render(dir, { restore: true });
  }
  function back() {
    state.route = state.stack.pop() || "play";
    render("back", { restore: true });
  }
  tg?.BackButton?.onClick?.(back);

  function render(dir = "none", opts = {}) { transition(() => draw(opts), dir); }

  function draw({ restore = false } = {}) {
    state.cleanup.splice(0).forEach((fn) => { try { fn(); } catch { /* ignore */ } });
    closeSheet({ instant: true });
    const r = state.route;
    const view = $("#view");
    const screen = $("#screen");
    const [name, arg] = r.split("/");
    const screens = { play: renderPlay, chat: renderChat, profile: renderProfile, settings: renderSettings, help: renderHelp,
                      about: renderAbout, doc: renderDoc, wallet: renderWallet, history: renderHistory, txs: renderTxs,
                      fair: renderFair, game: renderGame, slot: renderSlot, leaders: renderLeaders };
    screen.innerHTML = "";
    view.dataset.screen = name;
    (screens[name] || renderPlay)(screen, arg);
    updateTabbar();
    if (state.stack.length && !["play", "chat"].includes(r)) tg?.BackButton?.show?.(); else tg?.BackButton?.hide?.();
    const m = restore && memo[r];
    view.scrollTop = m ? m.top : 0;
    if (m) $$(".carousel", view).forEach((c, i) => { c.scrollLeft = m.car[i] || 0; });
  }

  // ================================================================ shell: header & tabbar
  function renderHeader() {
    $("#topbar").innerHTML = `<div class="topbar-in">
      <button class="brand" id="brand" aria-label="ARA Casino">${LOGO}<span class="brand-name">ARA Casino</span></button>
      <div class="wallet-pill"><span class="bal num" id="hdr-bal">${CUR}<span>—</span></span>
        <button class="plus-btn" id="hdr-plus" aria-label="${esc(t("header.topup"))}">${ic("plus")}</button></div></div>`;
    $("#brand").onclick = () => goRoot("play");
    $("#hdr-plus").onclick = () => { fx.tap(); go("wallet"); };
    setBalance(state.me?.balance);
  }
  function setBalance(b) {
    if (state.me && b != null) state.me.balance = b;
    const el = $("#hdr-bal span");
    if (el) el.textContent = b == null ? "—" : S.hideBalance ? "•••" : usd(b);
  }
  function renderTabbar() {
    // справа налево: Играть, Чат, Меню
    $("#tabbar").innerHTML = `<div class="tabbar-in"><span class="tab-ind" aria-hidden="true"></span>
      ${[["menu", "menu"], ["chat", "chat"], ["play", "play"]].map(([k, i]) => `<button class="tab-btn" id="tab-${k}">${ic(i)}<span>${t("tab." + k)}</span></button>`).join("")}</div>`;
    updateTabbar();
    $("#tab-menu").onclick = () => { fx.tap(); openMenu(); };
    $("#tab-chat").onclick = () => { fx.tap(); goRoot("chat"); };
    $("#tab-play").onclick = () => { fx.tap(); goRoot("play"); };
  }
  function updateTabbar() {
    if (!$("#tab-play")) return renderTabbar();
    const root = ROOT_OF(state.route);
    ["menu", "chat", "play"].forEach((k) => $("#tab-" + k).classList.toggle("on", root === k));
    $(".tab-ind").style.transform = `translateX(${TAB_INDEX[root] * 100}%)`;
  }
  function openMenu() {
    const items = [["profile", "user"], ["settings", "gear"], ["help", "help"]];
    const sh = openSheet(items.map(([r, i]) =>
      `<button class="menu-item" data-r="${r}"><span class="ic">${ic(i)}</span><span class="grow">${t("menu." + r)}</span>${ic("chev", "i chev")}</button>`).join(""));
    $$("[data-r]", sh).forEach((b) => (b.onclick = () => {
      const to = b.dataset.r;
      remember();
      const dir = ROOT_OF(state.route) === "menu" ? (state.route === to ? "none" : "fade") : tabDir(state.route, to);
      state.stack = []; state.route = to;
      render(dir, { restore: true });
    }));
  }

  function pageHead(title, { backBtn = true, extra = "" } = {}) {
    return `<div class="page-head">${backBtn && state.stack.length ? `<button class="icon-btn" data-back aria-label="${t("common.back")}">${ic("back")}</button>` : ""}
      <h1>${esc(title)}</h1>${extra}</div>`;
  }
  function bindBack(root) { $$("[data-back]", root).forEach((b) => (b.onclick = back)); }
  function disclaimer() { return `<div class="disclaimer"><span class="age-badge">18+</span><span>${esc(C().disclaimer)}</span></div>`; }

  // ================================================================ PLAY
  const MINI = ["crash", "roulette", "mines", "dice", "coinflip", "limbo", "plinko"];
  const SLOTS = ["classic", "treasury", "royal"];

  // стрелки ‹ › для карусели: прокрутка на одну карточку, неактивны у краёв
  const arrows = (target) => `<span class="arrows" data-for="${target}">
      <button class="arrow" data-dir="-1" aria-label="${esc(t("common.prev"))}" aria-controls="${target}">${ic("back")}</button>
      <button class="arrow" data-dir="1" aria-label="${esc(t("common.next"))}" aria-controls="${target}">${ic("chev")}</button></span>`;
  function bindCarousel(track, onUser) {
    const box = $(`.arrows[data-for="${track.id}"]`);
    const [prev, next] = box ? $$(".arrow", box) : [];
    const step = () => (track.firstElementChild?.offsetWidth || 160) + 10;
    const sync = () => {
      if (!prev) return;
      const max = track.scrollWidth - track.clientWidth - 2;
      prev.disabled = track.scrollLeft <= 2;
      next.disabled = track.scrollLeft >= max;
    };
    const move = (dir) => {
      fx.tap(); onUser?.();
      track.scrollBy({ left: dir * step(), behavior: S.motion ? "smooth" : "auto" });
    };
    if (prev) { prev.onclick = () => move(-1); next.onclick = () => move(1); }
    track.tabIndex = 0;
    track.addEventListener("keydown", (e) => {
      if (e.key === "ArrowLeft" || e.key === "ArrowRight") { e.preventDefault(); move(e.key === "ArrowLeft" ? -1 : 1); }
    });
    track.addEventListener("scroll", sync, { passive: true });
    requestAnimationFrame(sync);
  }
  // меню игр: все слоты и мини-игры одной сеткой
  function gamesMenu() {
    const tile = (route, thumb, name, tag) => `<button class="gm-tile" data-go-game="${route}"><span class="gm-thumb">${thumb}</span>
        <span class="gm-name">${name}</span><span class="gm-tag">${tag}</span></button>`;
    const sh = openSheet(`<h2>${t("play.menu")}</h2>
      <div class="gm-group">${t("play.slots")}</div>
      <div class="gm-grid">${SLOTS.map((id) => tile("slot/" + id, `<span class="gm-slot">${img(SLOT_SYMBOLS[id][5])}</span>`, t("slot." + id), t("slot." + id + ".tag"))).join("")}</div>
      <div class="gm-group">${t("play.mini")}</div>
      <div class="gm-grid">${MINI.map((g) => tile("game/" + g, cover(g), t("game." + g), t("game." + g + ".tag"))).join("")}</div>`, { cls: "gm-sheet" });
    $$("[data-go-game]", sh).forEach((b) => (b.onclick = () => { fx.tap(); closeSheet(); go(b.dataset.goGame); }));
  }

  function renderPlay(view) {
    const news = C().news;
    view.innerHTML = `
      ${DEMO ? `<div class="demo-note"><span>${t("demo.note")}</span></div>` : ""}
      <button class="games-menu-btn" id="games-menu">${ic("grid")}<span class="grow">${t("play.menu")}</span>
        <span class="count num">${SLOTS.length + MINI.length}</span>${ic("chev")}</button>
      <section class="rail"><div class="carousel" id="news" aria-label="${esc(t("play.news"))}">${news.map((n) => `
        <article class="news-card" style="background-image:url(${A("backgrounds/" + n.bg)})">${n.img ? img(NEWS_IMG[n.img], "art") : ""}
          <div><h3>${esc(n.title)}</h3><p>${esc(n.text)}</p></div>
          <button class="btn gold" data-route="${n.route}">${esc(n.cta)}</button></article>`).join("")}</div>
        <div class="news-nav">${arrows("news").replace('class="arrows"', 'class="arrows split"')}
          <div class="dots" id="news-dots">${news.map((_, i) => `<i class="${i ? "" : "on"}"></i>`).join("")}</div></div></section>

      <section class="rail" id="rail-slots"><div class="rail-head"><h2>${t("play.slots")}</h2><span class="hint">${t("play.slots_hint")}</span>${arrows("slots-track")}</div>
        <div class="carousel" id="slots-track" aria-label="${esc(t("play.slots"))}">${SLOTS.map((id) => {
          const sym = SLOT_SYMBOLS[id];
          return `<button class="game-card slot-card" data-slot="${id}"><div class="thumb"><div class="slot-thumb">
            ${[5, 4, 3].map((k) => `<span>${img(sym[k])}</span>`).join("")}</div></div>
            <div class="meta"><span class="name">${t("slot." + id)}</span><span class="tag">${t("slot." + id + ".tag")}</span>
            <span class="btn primary">${t("common.play")}</span></div></button>`;
        }).join("")}</div></section>

      <section class="rail"><div class="rail-head"><h2>${t("play.mini")}</h2><span class="hint">${t("play.rtp", { rtp: rtpText() })}</span>${arrows("mini-track")}</div>
        <div class="carousel" id="mini-track" aria-label="${esc(t("play.mini"))}">${MINI.map((g) => `
          <button class="game-card" data-game="${g}"><div class="thumb">${cover(g)}</div>
            <div class="meta"><span class="name">${t("game." + g)}</span><span class="tag">${t("game." + g + ".tag")}</span>
            <span class="btn primary">${t("common.play")}</span></div></button>`).join("")}</div></section>
      ${disclaimer()}`;

    $("#games-menu").onclick = () => { fx.tap(); gamesMenu(); };
    $$("[data-route]", view).forEach((b) => (b.onclick = () => {
      fx.tap();
      const r = b.dataset.route;
      if (r === "slots") $("#rail-slots").scrollIntoView({ behavior: S.motion ? "smooth" : "auto", block: "start" });
      else go(r);
    }));
    $$("[data-slot]", view).forEach((b) => (b.onclick = () => { fx.tap(); go("slot/" + b.dataset.slot); }));
    $$("[data-game]", view).forEach((b) => (b.onclick = () => { fx.tap(); go("game/" + b.dataset.game); }));

    // точки, стрелки и автопрокрутка новостей (останавливается, как только игрок листает сам)
    const track = $("#news");
    const dots = $$("#news-dots i");
    let idx = 0, paused = false;
    const onScroll = () => {
      const w = track.firstElementChild.offsetWidth + 10;
      idx = Math.round(track.scrollLeft / w);
      dots.forEach((d, i) => d.classList.toggle("on", i === idx));
    };
    track.addEventListener("scroll", onScroll, { passive: true });
    track.addEventListener("pointerdown", () => (paused = true));
    bindCarousel(track, () => (paused = true));
    bindCarousel($("#slots-track"));
    bindCarousel($("#mini-track"));
    const timer = setInterval(() => {
      if (paused || !S.motion || document.hidden) return;
      const w = track.firstElementChild.offsetWidth + 10;
      track.scrollTo({ left: ((idx + 1) % news.length) * w, behavior: "smooth" });
    }, 6000);
    state.cleanup.push(() => clearInterval(timer));
  }
  const rtpText = () => Math.round((1 - (state.config?.house_edge ?? 0.03)) * 100) + "%";
  const slotCfg = () => state.config?.games.find((g) => g.name === "slots");

  // ================================================================ BET BOX (общий)
  function betBox(actionLabel, { id = "bet" } = {}) {
    const c = state.config;
    return `<div class="betbox"><div class="label"><span>${t("bet.amount")}</span><span>${t("bet.limits", { min: usd(c.min_bet), max: usd(c.max_bet) })}</span></div>
      <div class="bet-row"><button class="step-btn" data-step="-1" aria-label="−">−</button>
        <label class="field">${CUR}<input id="${id}" class="num" type="text" inputmode="decimal" autocomplete="off" value="${S.bet / U}" aria-label="${esc(t("bet.amount"))}"><span class="suffix">USDT</span></label>
        <button class="step-btn" data-step="1" aria-label="+">+</button></div>
      <div class="chips"><button data-q="min">${t("bet.min")}</button><button data-q="half">½</button><button data-q="double">×2</button><button data-q="max">${t("bet.max")}</button></div></div>
      <div class="action-dock"><button class="btn primary xl block" data-action>${esc(actionLabel)}</button></div>`;
  }
  function bindBetBox(root, onChange) {
    const c = state.config;
    const input = $("#bet", root);
    // ставка хранится в микро-USDT, в поле — обычные доллары с центами
    const read = () => toUnits(input.value);
    const setV = (v) => {
      const u = clamp(Math.round((v || c.min_bet) / 10000) * 10000, c.min_bet, c.max_bet); // шаг 0.01
      input.value = String(u / U);
      S.bet = u; saveSettings(); onChange?.();
    };
    input.addEventListener("change", () => setV(read()));
    input.addEventListener("input", () => { S.bet = read(); onChange?.(); });
    $$("[data-step]", root).forEach((b) => (b.onclick = () => {
      fx.tap();
      const cur = read() || c.min_bet;
      const step = cur >= 100 * U ? 10 * U : cur >= 10 * U ? U : cur >= U ? 0.1 * U : 0.01 * U;
      setV(cur + step * +b.dataset.step);
    }));
    $$("[data-q]", root).forEach((b) => (b.onclick = () => {
      fx.tap();
      const cur = read() || c.min_bet;
      const bal = state.me?.balance ?? c.max_bet;
      setV({ min: c.min_bet, max: Math.min(c.max_bet, Math.max(c.min_bet, Math.floor(bal / 10000) * 10000)), half: cur / 2, double: cur * 2 }[b.dataset.q]);
    }));
    return () => clamp(read(), 0, 1e15);
  }
  async function preBet(amount) {
    if (S.pauseUntil > Date.now()) { toast(t("rg.paused_until", { date: fmtDate(new Date(S.pauseUntil).toISOString()) })); fx.error(); return false; }
    if (S.confirmAbove && amount >= S.confirmAbove) {
      return confirmSheet(t("bet.confirm_title"), t("bet.confirm_text", { amount: usd(amount) }), t("bet.confirm_ok"));
    }
    return true;
  }
  function showOutcome(el, bet, detail) {
    const win = bet.payout > 0;
    el.className = "result-line " + (win ? "win-c" : "lose-c");
    el.innerHTML = (win ? `+${usd(bet.payout)} USDT <span class="muted small">${fmtX(bet.multiplier)}</span>` : `−${usd(bet.amount)} USDT`) +
      (detail ? ` <span class="muted small">· ${esc(detail)}</span>` : "");
    el.classList.remove("pop"); void el.offsetWidth; el.classList.add("pop");
    win ? fx.win() : fx.lose();
  }
  function gameInfo(name) {
    openSheet(`<h2>${t("game." + name)}</h2><p>${esc(t("game." + name + ".rules"))}</p>
      <p class="muted small">${t("game.rtp_note", { rtp: rtpText() })}</p>
      <div class="actions"><button class="btn ghost" data-fair>${t("profile.fair")}</button><button class="btn primary" data-close>${t("common.ok")}</button></div>`);
    $("[data-close]").onclick = closeSheet;
    $("[data-fair]").onclick = () => { closeSheet(); go("doc/fair"); };
  }

  // ================================================================ GAMES
  function renderGame(view, name) {
    if (!MINI.includes(name)) return renderPlay(view);
    view.innerHTML = pageHead(t("game." + name), { extra: `<button class="icon-btn" data-info aria-label="${t("common.rules")}">${ic("info")}</button>` }) +
      `<div id="game-root"></div>`;
    bindBack(view);
    $("[data-info]", view).onclick = () => gameInfo(name);
    ({ dice: gameDice, coinflip: gameCoin, limbo: gameLimbo, plinko: gamePlinko, mines: gameMines, roulette: gameRoulette, crash: gameCrash })[name]($("#game-root", view));
  }

  async function playInstant(game, params, getAmount, btn) {
    const amount = getAmount();
    if (!(await preBet(amount))) return null;
    btn.disabled = true;
    try {
      const res = await guard(() => api(`/api/games/${game}/play`, { amount, params }));
      if (res) state.me && (state.me.total_wagered += amount);
      return res;
    } finally { btn.disabled = false; }
  }

  // ---------------- Dice
  function gameDice(root) {
    let target = 50, dir = "under";
    root.innerHTML = `<div class="stage">
        <div class="stage-big num" id="d-roll">50.00</div><div class="stage-sub" id="d-sub">${t("dice.hint")}</div>
        <div class="dice-wrap"><div class="dice-marker num" id="d-marker" style="left:50%">50.00</div>
          <div class="dice-track"><div class="zone" id="d-zone"></div></div>
          <input type="range" id="d-target" min="2" max="98" step="1" value="50" aria-label="${t("dice.target")}"></div>
        <div class="dice-scale"><span>0</span><span>25</span><span>50</span><span>75</span><span>100</span></div>
        <div class="seg" style="margin-top:12px"><button data-dir="under" class="on">${t("dice.under")}</button><button data-dir="over">${t("dice.over")}</button></div>
        <div class="stats"><div class="stat"><div class="k">${t("game.chance")}</div><div class="v num" id="d-chance"></div></div>
          <div class="stat"><div class="k">${t("game.multiplier")}</div><div class="v num" id="d-mult"></div></div>
          <div class="stat"><div class="k">${t("game.payout")}</div><div class="v num" id="d-pay"></div></div></div>
        <div class="result-line" id="d-res"></div></div>${betBox(t("dice.roll"))}`;
    const rtp = 1 - state.config.house_edge;
    const upd = () => {
      const chance = dir === "under" ? target / 100 : (100 - target) / 100;
      const mult = Math.floor((rtp / chance) * 10000 + 1e-9) / 10000;
      $("#d-chance").textContent = (chance * 100).toFixed(0) + "%";
      $("#d-mult").textContent = fmtX(mult);
      $("#d-pay").innerHTML = `${CUR}${usd(Math.floor(S.bet * mult))}`;
      const z = $("#d-zone");
      z.style.left = dir === "under" ? "0" : target + "%";
      z.style.width = (dir === "under" ? target : 100 - target) + "%";
      $("#d-sub").textContent = dir === "under" ? t("dice.win_under", { n: target }) : t("dice.win_over", { n: target });
    };
    $("#d-target").oninput = (e) => { target = +e.target.value; upd(); };
    $$("[data-dir]", root).forEach((b) => (b.onclick = () => {
      fx.tap(); dir = b.dataset.dir;
      $$("[data-dir]", root).forEach((x) => x.classList.toggle("on", x === b)); upd();
    }));
    const getAmount = bindBetBox(root, upd);
    upd();
    const btn = $("[data-action]", root);
    btn.onclick = async () => {
      const res = await playInstant("dice", { target, direction: dir }, getAmount, btn);
      if (!res) return;
      const roll = res.result.roll;
      const el = $("#d-roll");
      if (S.motion) for (let i = 0; i < 8; i++) { el.textContent = (Math.random() * 100).toFixed(2); fx.tick(); await sleep(35); }
      el.textContent = roll.toFixed(2);
      const m = $("#d-marker"); m.style.left = roll + "%"; m.textContent = roll.toFixed(2);
      el.className = "stage-big num " + (res.bet.payout > 0 ? "win-c" : "lose-c");
      setBalance(res.balance);
      showOutcome($("#d-res"), res.bet);
    };
  }

  // ---------------- Coinflip
  function gameCoin(root) {
    let side = "heads", rot = 0;
    root.innerHTML = `<div class="stage"><div class="coin-wrap"><div class="coin" id="coin" role="img" aria-label="${esc(t("coin.heads"))} / ${esc(t("coin.tails"))}">
        <div class="face front"></div><div class="face back"></div></div></div>
        <div class="seg"><button data-side="heads" class="on">${img("coinflip/coin-heads")}${t("coin.heads")}</button><button data-side="tails">${img("coinflip/coin-tails")}${t("coin.tails")}</button></div>
        <div class="stats"><div class="stat"><div class="k">${t("game.chance")}</div><div class="v num">50%</div></div>
          <div class="stat"><div class="k">${t("game.multiplier")}</div><div class="v num" id="c-mult"></div></div>
          <div class="stat"><div class="k">${t("game.payout")}</div><div class="v num" id="c-pay"></div></div></div>
        <div class="result-line" id="c-res"></div></div>${betBox(t("coin.flip"))}`;
    const mult = Math.floor((1 - state.config.house_edge) * 2 * 10000 + 1e-9) / 10000;
    const upd = () => { $("#c-mult").textContent = fmtX(mult); $("#c-pay").innerHTML = `${CUR}${usd(Math.floor(S.bet * mult))}`; };
    $$("[data-side]", root).forEach((b) => (b.onclick = () => {
      fx.tap(); side = b.dataset.side;
      $$("[data-side]", root).forEach((x) => x.classList.toggle("on", x === b));
    }));
    const getAmount = bindBetBox(root, upd);
    upd();
    const btn = $("[data-action]", root);
    btn.onclick = async () => {
      const res = await playInstant("coinflip", { side }, getAmount, btn);
      if (!res) return;
      const land = res.result.side === "heads" ? 0 : 180;
      rot = rot - (rot % 360) + 1800 + land;
      $("#coin").style.transform = `rotateY(${rot}deg)`;
      if (S.motion) await sleep(1100);
      setBalance(res.balance);
      showOutcome($("#c-res"), res.bet, res.result.side === "heads" ? t("coin.heads") : t("coin.tails"));
    };
  }

  // ---------------- Limbo
  function gameLimbo(root) {
    let target = 2;
    root.innerHTML = `<div class="stage"><div class="limbo-num num" id="l-num">1.00×</div><div class="stage-sub">${t("limbo.hint")}</div>
        <div class="ctrl" style="margin-top:14px"><div class="ctrl-label"><span>${t("limbo.target")}</span></div>
          <label class="field"><input id="l-target" class="num" type="number" step="0.01" min="1.01" value="2.00"><span class="suffix">×</span></label>
          <div class="chips"><button data-t="1.5">1.5×</button><button data-t="2" class="on">2×</button><button data-t="5">5×</button><button data-t="10">10×</button></div></div>
        <div class="stats"><div class="stat"><div class="k">${t("game.chance")}</div><div class="v num" id="l-chance"></div></div>
          <div class="stat"><div class="k">${t("game.multiplier")}</div><div class="v num" id="l-mult"></div></div>
          <div class="stat"><div class="k">${t("game.payout")}</div><div class="v num" id="l-pay"></div></div></div>
        <div class="result-line" id="l-res"></div></div>${betBox(t("common.play"))}`;
    const rtp = 1 - state.config.house_edge;
    const upd = () => {
      $("#l-chance").textContent = target >= 1.01 ? ((rtp / target) * 100).toFixed(2) + "%" : "—";
      $("#l-mult").textContent = fmtX(target);
      $("#l-pay").innerHTML = `${CUR}${usd(Math.floor(S.bet * target))}`;
      $$("[data-t]", root).forEach((b) => b.classList.toggle("on", +b.dataset.t === target));
    };
    $("#l-target").oninput = (e) => { target = Math.floor(+e.target.value * 100) / 100 || 0; upd(); };
    $$("[data-t]", root).forEach((b) => (b.onclick = () => { fx.tap(); target = +b.dataset.t; $("#l-target").value = target.toFixed(2); upd(); }));
    const getAmount = bindBetBox(root, upd);
    upd();
    const btn = $("[data-action]", root);
    btn.onclick = async () => {
      const res = await playInstant("limbo", { target }, getAmount, btn);
      if (!res) return;
      const el = $("#l-num"); const end = res.result.point;
      el.className = "limbo-num num";
      if (S.motion) {
        const t0 = performance.now(), dur = 650;
        await new Promise((done) => {
          const step = (now) => {
            const k = Math.min(1, (now - t0) / dur), e = 1 - (1 - k) ** 3;
            el.textContent = fmtX(1 + (Math.min(end, 1000) - 1) * e);
            k < 1 ? requestAnimationFrame(step) : done();
          };
          requestAnimationFrame(step);
        });
      }
      el.textContent = fmtX(end);
      el.classList.add(res.bet.payout > 0 ? "win-c" : "lose-c");
      setBalance(res.balance);
      showOutcome($("#l-res"), res.bet);
    };
  }

  // ---------------- Plinko
  function gamePlinko(root) {
    let rows = 12, risk = "medium", busy = false;
    root.innerHTML = `<div class="stage"><canvas class="plinko-canvas" id="p-canvas"></canvas><div class="buckets" id="p-buckets"></div>
        <div class="result-line" id="p-res"></div>
        <div class="ctrl"><div class="ctrl-label"><span>${t("plinko.risk")}</span></div>
          <div class="seg"><button data-risk="low">${t("plinko.low")}</button><button data-risk="medium" class="on">${t("plinko.medium")}</button><button data-risk="high">${t("plinko.high")}</button></div></div>
        <div class="ctrl"><div class="ctrl-label"><span>${t("plinko.rows")}</span><b class="num" id="p-rows-v">12</b></div>
          <input type="range" id="p-rows" min="8" max="16" step="1" value="12" aria-label="${t("plinko.rows")}"></div></div>${betBox(t("plinko.drop"))}`;
    const canvas = $("#p-canvas");
    const ctx = canvas.getContext("2d");
    const table = () => state.config.games.find((g) => g.name === "plinko").tables[risk][rows] || [];
    let geo = null;
    function layout() {
      const W = canvas.clientWidth || 320, dpr = window.devicePixelRatio || 1;
      const sp = W / (rows + 2), rowH = Math.min(sp * 0.92, 26), H = rowH * (rows + 0.6) + 10;
      canvas.width = W * dpr; canvas.height = H * dpr; canvas.style.height = H + "px";
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      geo = { W, H, sp, rowH, top: 10 };
      const b = $("#p-buckets");
      b.style.padding = `0 ${(sp / 2).toFixed(1)}px`;
      const short = (m) => (m >= 10 ? String(Math.round(m)) : m.toFixed(1)); // точный множитель — в строке результата
      b.innerHTML = table().map((m) => `<span class="${m >= 2 ? "hot" : ""}" title="${fmtX(m)}">${short(m)}</span>`).join("");
      draw(null);
    }
    const css = (v) => getComputedStyle(document.documentElement).getPropertyValue(v).trim();
    function draw(ball) {
      const { W, H, sp, rowH, top } = geo;
      ctx.clearRect(0, 0, W, H);
      ctx.fillStyle = css("--faint");
      for (let r = 0; r < rows; r++) for (let i = 0; i < r + 3; i++) {
        ctx.beginPath(); ctx.arc(W / 2 + (i - (r + 2) / 2) * sp, top + r * rowH, 2.6, 0, Math.PI * 2); ctx.fill();
      }
      if (ball) { ctx.fillStyle = css("--accent"); ctx.beginPath(); ctx.arc(ball.x, ball.y, Math.max(5, sp * 0.22), 0, Math.PI * 2); ctx.fill(); }
    }
    async function animate(path) {
      const { W, sp, rowH, top } = geo;
      const pts = [{ x: W / 2, y: top - rowH * 0.6 }];
      let off = 0;
      path.forEach((dirR, r) => { off += dirR ? 0.5 : -0.5; pts.push({ x: W / 2 + off * sp, y: top + r * rowH + rowH * 0.5 }); });
      if (!S.motion) return draw(pts[pts.length - 1]);
      for (let k = 1; k < pts.length; k++) {
        const a = pts[k - 1], b = pts[k], t0 = performance.now(), dur = 70;
        await new Promise((done) => {
          const step = (now) => {
            const q = Math.min(1, (now - t0) / dur);
            draw({ x: a.x + (b.x - a.x) * q, y: a.y + (b.y - a.y) * q - Math.sin(q * Math.PI) * rowH * 0.35 });
            q < 1 ? requestAnimationFrame(step) : done();
          };
          requestAnimationFrame(step);
        });
        if (k % 2) fx.tick();
      }
    }
    $$("[data-risk]", root).forEach((b) => (b.onclick = () => {
      if (busy) return; fx.tap(); risk = b.dataset.risk;
      $$("[data-risk]", root).forEach((x) => x.classList.toggle("on", x === b)); layout();
    }));
    $("#p-rows").oninput = (e) => { if (busy) return; rows = +e.target.value; $("#p-rows-v").textContent = rows; layout(); };
    const getAmount = bindBetBox(root);
    layout();
    const onResize = () => layout();
    window.addEventListener("resize", onResize);
    state.cleanup.push(() => window.removeEventListener("resize", onResize));
    const btn = $("[data-action]", root);
    btn.onclick = async () => {
      busy = true;
      try {
        const res = await playInstant("plinko", { rows, risk }, getAmount, btn);
        if (!res) return;
        $$("#p-buckets span").forEach((s) => s.classList.remove("hit"));
        await animate(res.result.path);
        $$("#p-buckets span")[res.result.bucket]?.classList.add("hit");
        setBalance(res.balance);
        showOutcome($("#p-res"), res.bet);
      } finally { busy = false; }
    };
  }

  // ---------------- Mines
  function gameMines(root) {
    let mines = 3, game = null;
    root.innerHTML = `<div class="stage"><div class="mines-grid" id="m-grid"></div>
        <div class="result-line" id="m-res"></div>
        <div class="ctrl"><div class="ctrl-label"><span>${t("mines.count")}</span><b class="num" id="m-count-v">3</b></div>
          <input type="range" id="m-count" min="1" max="24" step="1" value="3" aria-label="${t("mines.count")}"></div>
        <div class="stats"><div class="stat"><div class="k">${t("mines.now")}</div><div class="v num" id="m-now">—</div></div>
          <div class="stat"><div class="k">${t("mines.next")}</div><div class="v num" id="m-next">—</div></div>
          <div class="stat"><div class="k">${t("mines.safe_left")}</div><div class="v num" id="m-left">—</div></div></div></div>
      ${betBox(t("mines.start"))}`;
    const btn = $("[data-action]", root);
    const getAmount = bindBetBox(root);
    function paint() {
      const grid = $("#m-grid");
      const active = game?.status === "active";
      const revealed = new Set(game?.revealed || []);
      const ms = new Set(game?.mines || []);
      const last = game?.picked?.[game.picked.length - 1];
      grid.innerHTML = Array.from({ length: 25 }, (_, i) => {
        let cls = "tile", txt = "";
        if (revealed.has(i)) { cls += " safe"; txt = img("mines/gem-emerald"); }
        else if (ms.has(i)) { cls += i === last && game.status === "lost" ? " boom" : " mine"; txt = img("mines/mine"); }
        else if (game && !active) cls += " dim";
        return `<button class="${cls}" data-tile="${i}" ${active && !revealed.has(i) ? "" : "disabled"} aria-label="${i + 1}">${txt}</button>`;
      }).join("");
      $$("[data-tile]", grid).forEach((b) => (b.onclick = () => reveal(+b.dataset.tile)));
      const n = (game?.revealed || []).length;
      $("#m-now").textContent = game && n ? fmtX(game.multiplier) : "—";
      $("#m-next").textContent = active && game.next_multiplier ? fmtX(game.next_multiplier) : "—";
      $("#m-left").textContent = game ? 25 - game.mines_count - n : "—";
      $("#m-count").disabled = active;
      btn.textContent = active ? (n ? t("mines.cashout", { amount: usd(Math.floor(game.amount * game.multiplier)) }) : t("mines.pick")) : t("mines.start");
      btn.disabled = active && !n;
      btn.className = "btn xl block " + (active ? "gold" : "primary");
    }
    async function reveal(tile) {
      fx.tap();
      const res = await guard(() => api("/api/games/mines/reveal", { tile }));
      if (!res) return;
      game = res.result;
      setBalance(res.balance);
      paint();
      if (game.status === "lost") showOutcome($("#m-res"), res.bet, t("mines.boom"));
      else if (game.status === "won") showOutcome($("#m-res"), res.bet, t("mines.all_clear"));
      else fx.tick();
    }
    $("#m-count").oninput = (e) => { mines = +e.target.value; $("#m-count-v").textContent = mines; };
    btn.onclick = async () => {
      if (game?.status === "active") {
        const res = await guard(() => api("/api/games/mines/cashout", {}));
        if (!res) return;
        game = res.result; setBalance(res.balance); paint();
        showOutcome($("#m-res"), res.bet, t("mines.cashed"));
        return;
      }
      const amount = getAmount();
      if (!(await preBet(amount))) return;
      const res = await guard(() => api("/api/games/mines/start", { amount, params: { mines } }));
      if (!res) return;
      game = res.result; setBalance(res.balance);
      $("#m-res").className = "result-line"; $("#m-res").textContent = t("mines.pick");
      paint();
    };
    guard(async () => { game = (await api("/api/games/mines/active")).game; if (game) { mines = game.mines_count; $("#m-count").value = mines; $("#m-count-v").textContent = mines; } paint(); });
    paint();
  }

  // ---------------- Slots
  function renderSlot(view, id) {
    if (!SLOTS.includes(id)) return renderPlay(view);
    const sym = SLOT_SYMBOLS[id];
    const cfg = slotCfg();
    preload(sym);
    view.innerHTML = pageHead(t("slot." + id), { extra: `<button class="icon-btn" data-pay aria-label="${t("slot.paytable")}">${ic("info")}</button>` }) +
      `<div class="stage"><div class="reels-frame"><div class="reels" id="reels">${Array.from({ length: 9 }, (_, i) => `<div class="cell" data-c="${i}">${img(sym[[5, 4, 3, 2, 5, 1, 0, 3, 4][i]])}</div>`).join("")}</div></div>
        <div class="stage-sub" style="margin-top:10px">${t("slot.lines_hint")}</div><div class="result-line" id="s-res"></div></div>${betBox(t("slot.spin"))}`;
    bindBack(view);
    $("[data-pay]", view).onclick = () => {
      openSheet(`<h2>${t("slot.paytable")}</h2><p class="muted small">${t("slot.paytable_note")}</p><div class="paytable">
        ${sym.map((g, i) => `<div><span class="g">${img(g)}${img(g)}${img(g)}</span><b class="num">${fmtX(cfg.pays[i])}</b></div>`).reverse().join("")}</div>
        <p class="muted small" style="margin-top:12px">${t("game.rtp_note", { rtp: rtpText() })}</p>
        <div class="actions"><button class="btn primary" data-close>${t("common.ok")}</button></div>`);
      $("[data-close]").onclick = closeSheet;
    };
    const getAmount = bindBetBox(view);
    const btn = $("[data-action]", view);
    const cells = $$(".cell", view);
    const setCell = (c, k) => { c.firstElementChild.src = A(sym[k]); };
    btn.onclick = async () => {
      const res = await playInstant("slots", { slot: id }, getAmount, btn);
      if (!res) return;
      btn.disabled = true;
      cells.forEach((c) => c.classList.remove("win"));
      const grid = res.result.grid;
      if (S.motion) {
        cells.forEach((c) => c.classList.add("spin"));
        const stopAt = [520, 760, 1000];
        const t0 = performance.now();
        await new Promise((done) => {
          const iv = setInterval(() => {
            const el = performance.now() - t0;
            cells.forEach((c, i) => {
              const col = i % 3;
              if (el < stopAt[col]) setCell(c, Math.floor(Math.random() * 6));
              else if (c.classList.contains("spin")) { c.classList.remove("spin"); setCell(c, grid[i]); if (i >= 6) fx.tick(); }
            });
            if (el >= stopAt[2]) { clearInterval(iv); done(); }
          }, 70);
          state.cleanup.push(() => { clearInterval(iv); done(); });
        });
      }
      cells.forEach((c, i) => { c.classList.remove("spin"); setCell(c, grid[i]); });
      res.result.wins.forEach((w) => cfg.lines[w.line].forEach((k) => cells[k].classList.add("win")));
      btn.disabled = false;
      setBalance(res.balance);
      showOutcome($("#s-res"), res.bet, res.result.wins.length ? t("slot.lines_won", { n: res.result.wins.length }) : "");
    };
  }

  // ---------------- Roulette (европейская)
  const RED = new Set([1, 3, 5, 7, 9, 12, 14, 16, 18, 19, 21, 23, 25, 27, 30, 32, 34, 36]);
  const rColor = (n) => (n === 0 ? "green" : RED.has(n) ? "red" : "black");
  function gameRoulette(root) {
    let bet = "red", rot = 0, spinning = false;
    const last = state.rouletteLast || (state.rouletteLast = []);
    const multOf = (b) => (typeof b === "number" || b === "zero" ? 36 : 2);
    const chanceOf = (b) => (typeof b === "number" || b === "zero" ? 1 : 18) / 37;
    root.innerHTML = `<div class="stage roulette-stage">
        <div class="wheel-wrap"><img class="wheel" id="r-wheel" src="${A("roulette/wheel-top")}" alt="" draggable="false"><div class="r-ball num" id="r-ball" aria-live="polite">?</div></div>
        <div class="r-last" id="r-last" aria-label="${esc(t("roulette.last"))}"></div>
        <div class="result-line" id="r-res"></div></div>
      <div class="r-bets" role="group" aria-label="${esc(t("roulette.your_bet"))}">
        ${["red", "black", "zero", "even", "odd"].map((k) => `<button class="r-opt ${k}" data-bet="${k}"><span>${t("roulette." + k)}</span><b class="num">×${multOf(k)}</b></button>`).join("")}
        <button class="r-opt pick" data-bet="num"><span id="r-num-label">${t("roulette.numbers")}</span><b class="num">×36</b></button></div>
      <div class="stats" style="margin:0 0 12px"><div class="stat"><div class="k">${t("game.chance")}</div><div class="v num" id="r-ch"></div></div>
        <div class="stat"><div class="k">${t("game.multiplier")}</div><div class="v num" id="r-mult"></div></div>
        <div class="stat"><div class="k">${t("game.payout")}</div><div class="v num" id="r-pay"></div></div></div>
      ${betBox(t("roulette.spin"))}`;
    const paintLast = () => { $("#r-last").innerHTML = last.map((n) => `<span class="r-chip ${rColor(n)} num">${n}</span>`).join(""); };
    const upd = () => {
      $$("[data-bet]", root).forEach((b) => b.classList.toggle("on", b.dataset.bet === (typeof bet === "number" ? "num" : bet)));
      $("#r-num-label").textContent = typeof bet === "number" ? t("roulette.number", { n: bet }) : t("roulette.numbers");
      $("#r-ch").textContent = (chanceOf(bet) * 100).toLocaleString(locale(), { maximumFractionDigits: 1 }) + "%";
      $("#r-mult").textContent = fmtX(multOf(bet));
      $("#r-pay").innerHTML = `${CUR}${usd(S.bet * multOf(bet))}`;
    };
    const pickNumber = () => {
      const sh = openSheet(`<h2>${t("roulette.numbers")}</h2><p class="muted small">${t("roulette.pick")}</p>
        <div class="r-grid"><button class="r-n green zero ${bet === 0 ? "on" : ""}" data-n="0">0</button>${Array.from({ length: 36 }, (_, i) => i + 1)
          .map((n) => `<button class="r-n ${rColor(n)} ${bet === n ? "on" : ""}" data-n="${n}">${n}</button>`).join("")}</div>`);
      $$("[data-n]", sh).forEach((b) => (b.onclick = () => { fx.tap(); bet = +b.dataset.n; upd(); closeSheet(); }));
    };
    $$("[data-bet]", root).forEach((b) => (b.onclick = () => {
      fx.tap();
      if (b.dataset.bet === "num") return pickNumber();
      bet = b.dataset.bet; upd();
    }));
    const getAmount = bindBetBox(root, upd);
    paintLast(); upd();
    const btn = $("[data-action]", root);
    btn.onclick = async () => {
      if (spinning) return;
      const res = await playInstant("roulette", { bet }, getAmount, btn);
      if (!res) return;
      const n = res.result.number;
      spinning = true; btn.disabled = true;
      const ball = $("#r-ball");
      ball.className = "r-ball num spin"; ball.textContent = "";
      rot += 1440 + Math.floor(Math.random() * 360);
      $("#r-wheel").style.transform = `rotate(${rot}deg)`;
      if (S.motion) await sleep(2300);
      if (!root.isConnected) return;
      ball.className = "r-ball num pop " + rColor(n); ball.textContent = n;
      last.unshift(n); last.splice(12); paintLast();
      setBalance(res.balance);
      showOutcome($("#r-res"), res.bet, t("roulette.landed", { n }));
      spinning = false; btn.disabled = false;
    };
  }

  // ---------------- Crash: время ведёт сервер, точку краха он не раскрывает до конца полёта
  function gameCrash(root) {
    const G = 0.18;
    let round = null, offset = 0, raf = 0, poll = 0, finishing = false;
    const hist = state.crashLast || (state.crashLast = []);
    const auto = () => (S.crashAuto ? S.crashAuto : 0);
    root.innerHTML = `<div class="stage crash-stage" id="cr-stage" style="background-image:url(${A("backgrounds/space-nebula")})">
        <svg class="cr-graph" viewBox="0 0 320 200" preserveAspectRatio="none" aria-hidden="true"><path id="cr-area" class="area"/><path id="cr-line" class="line"/></svg>
        <img class="cr-rocket" id="cr-rocket" src="${A("future/rocket")}" alt="" draggable="false">
        <div class="cr-hud"><div class="cr-mult num" id="cr-mult" aria-live="off">1,00×</div><div class="cr-status" id="cr-status">${t("crash.ready")}</div></div></div>
      <div class="cr-last" id="cr-last" aria-label="${esc(t("crash.last"))}"></div>
      <div class="result-line" id="cr-res" style="margin:0 0 8px"></div>
      <div class="panel cr-auto"><div class="cr-auto-row"><div class="grow"><div>${t("crash.auto")}</div><div class="sub">${t("crash.auto_sub")}</div></div>
          <label class="field cr-auto-field ${auto() ? "" : "off"}"><input id="cr-auto" class="num" type="number" inputmode="decimal" step="0.1" min="1.01" max="1000" value="${(auto() || 2).toFixed(2)}" aria-label="${esc(t("crash.auto"))}"><span class="suffix">×</span></label>
          <button class="switch ${auto() ? "on" : ""}" id="cr-auto-sw" role="switch" aria-checked="${!!auto()}" aria-label="${esc(t("crash.auto"))}"></button></div></div>
      ${betBox(t("crash.launch"))}`;
    const btn = $("[data-action]", root);
    const getAmount = bindBetBox(root);
    const now = () => Date.now() / 1000 + offset;
    const sync = (serverNow) => { if (serverNow) offset = serverNow - Date.now() / 1000; };
    const multAt = (el) => Math.max(1, Math.floor(Math.exp(Math.max(0, el) * G) * 100 + 1e-9) / 100);
    const paintHist = () => { $("#cr-last").innerHTML = hist.map((x) => `<span class="cr-chip num ${x >= 2 ? "hi" : ""}">${fmtX(x)}</span>`).join(""); };

    // ---- автовывод
    const sw = $("#cr-auto-sw"), autoIn = $("#cr-auto"), autoField = $(".cr-auto-field", root);
    const readAuto = () => { const v = clamp(Math.floor((+autoIn.value || 2) * 100) / 100, 1.01, 1000); autoIn.value = v.toFixed(2); return v; };
    sw.onclick = () => {
      fx.tap();
      const on = !sw.classList.contains("on");
      sw.classList.toggle("on", on); sw.setAttribute("aria-checked", on);
      autoField.classList.toggle("off", !on);
      S.crashAuto = on ? readAuto() : 0; saveSettings();
    };
    autoIn.addEventListener("change", () => { const v = readAuto(); if (sw.classList.contains("on")) { S.crashAuto = v; saveSettings(); } });

    // ---- рисование
    function paint(el, m, mode) {
      const T = Math.max(6, el * 1.15), Y = Math.max(1.8, m * 1.12);
      const pt = (tt) => [(tt / T) * 320, 196 - ((multAt(tt) - 1) / (Y - 1)) * 170];
      const N = 36, pts = [];
      for (let i = 0; i <= N; i++) pts.push(pt((el * i) / N));
      const d = "M" + pts.map(([x, y]) => `${x.toFixed(1)} ${y.toFixed(1)}`).join(" L");
      $("#cr-line").setAttribute("d", d);
      $("#cr-area").setAttribute("d", `${d} L${pts[N][0].toFixed(1)} 200 L0 200 Z`);
      const [x, y] = pts[N], [px, py] = pts[Math.max(0, N - 3)];
      const ang = el > 0.05 ? (Math.atan2(y - py, x - px) * 180) / Math.PI + 45 : -45 + 0;
      const r = $("#cr-rocket");
      r.style.left = (x / 320) * 100 + "%"; r.style.top = (y / 200) * 100 + "%";
      r.style.transform = `translate(-50%, -50%) rotate(${ang}deg)`;
      $("#cr-mult").textContent = fmtX(m);
      $("#cr-stage").dataset.mode = mode;
    }
    function idle() {
      paint(0, 1, "idle");
      $("#cr-status").textContent = t("crash.ready");
      btn.textContent = t("crash.launch"); btn.className = "btn primary xl block"; btn.disabled = false;
    }
    function frame() {
      if (!round) return;
      const el = now() - round.started_at;
      let m = multAt(el);
      if (round.auto_target && m >= round.auto_target) m = round.auto_target; // дальше скажет сервер
      paint(el, m, "fly");
      btn.textContent = t("crash.cashout", { amount: usd(Math.floor(round.amount * m)) });
      raf = requestAnimationFrame(frame);
    }
    function stop() { cancelAnimationFrame(raf); clearInterval(poll); raf = 0; poll = 0; }
    state.cleanup.push(stop);

    function fly(r) {
      round = r;
      $("#cr-status").textContent = t("crash.flying");
      $("#cr-res").className = "result-line"; $("#cr-res").textContent = round.max_multiplier < 1000 ? t("crash.cap", { x: fmtX(round.max_multiplier) }) : "";
      btn.className = "btn gold xl block"; btn.disabled = false;
      stop();
      raf = requestAnimationFrame(frame);
      poll = setInterval(check, 450);
    }
    async function check() {
      if (!round || finishing) return;
      try {
        const a = await api("/api/games/crash/active");
        sync(a.server_now);
        if (a.game && a.game.status === "active") return;
        const bet = await api(`/api/bets/${round.bet_id}`);
        finish({ status: bet.status, amount: bet.amount, payout: bet.payout, multiplier: bet.multiplier,
                 crash_point: bet.result.crash_point, cashout: bet.result.cashout }, bet);
        loadMe().catch(() => {});
      } catch { /* сеть моргнула — спросим ещё раз */ }
    }
    function finish(v, bet, balance) {
      stop();
      const started = round?.started_at;
      round = null; finishing = false;
      const won = v.status === "won";
      const endM = won ? v.multiplier : v.crash_point;
      paint(started ? Math.log(Math.max(1, endM)) / G : 0, endM, won ? "won" : "lost");
      $("#cr-mult").textContent = fmtX(endM);
      $("#cr-status").textContent = won ? t(v.cashout === "auto" ? "crash.auto_cashed" : "crash.cashed", { x: fmtX(v.multiplier) }) + " · " + t("crash.ended", { x: fmtX(v.crash_point) })
                                        : t("crash.ended", { x: fmtX(v.crash_point) });
      hist.unshift(v.crash_point); hist.splice(10); paintHist();
      if (balance != null) setBalance(balance);
      showOutcome($("#cr-res"), { payout: v.payout, amount: v.amount, multiplier: v.multiplier }, "");
      btn.textContent = t("crash.launch"); btn.className = "btn primary xl block"; btn.disabled = false;
    }

    btn.onclick = async () => {
      if (round) {
        finishing = true; btn.disabled = true;
        let res;
        try { res = await api("/api/games/crash/cashout", {}); } catch (e) {
          finishing = false; btn.disabled = false;
          if (e.code === "no_active_game") return check(); // раунд уже досчитан сервером
          toast(errText(e)); fx.error(); return;
        }
        finishing = false;
        const r = res.result;
        return finish({ status: r.status, amount: r.amount, payout: r.payout, multiplier: r.multiplier, crash_point: r.crash_point, cashout: r.cashout }, res.bet, res.balance);
      }
      const amount = getAmount();
      if (!(await preBet(amount))) return;
      const params = sw.classList.contains("on") ? { auto_cashout: readAuto() } : {};
      btn.disabled = true;
      const res = await guard(() => api("/api/games/crash/start", { amount, params }));
      btn.disabled = false;
      if (!res) return;
      setBalance(res.balance);
      state.me && (state.me.total_wagered += amount);
      sync(res.result.server_now);
      fx.tap();
      if (res.result.status !== "active") {
        const r = res.result;
        return finish({ status: r.status, amount: r.amount, payout: r.payout, multiplier: r.multiplier, crash_point: r.crash_point, cashout: r.cashout }, res.bet);
      }
      fly(res.result);
    };

    paintHist(); idle();
    guard(async () => {
      const a = await api("/api/games/crash/active");
      sync(a.server_now);
      if (a.game && root.isConnected) { toast(t("crash.resumed")); fly(a.game); }
    });
  }

  // ================================================================ CHAT
  function renderChat(view) {
    view.innerHTML = `<div class="chat"><div class="chat-head"><div class="title"><b>${t("chat.title")}</b><span class="online" id="online">—</span></div>
        <button class="rules-btn" id="chat-rules" aria-label="${t("chat.rules")}">!</button></div>
      <div class="msgs" id="msgs" aria-live="polite"></div>
      <form class="composer" id="composer"><label class="field"><input id="msg-in" maxlength="300" autocomplete="off" placeholder="${esc(t("chat.placeholder"))}"></label>
        <button class="send-btn" aria-label="${t("chat.send")}">${ic("send")}</button></form></div>`;
    const box = $("#msgs");
    let lastId = 0, myId = state.me?.public_id;
    const near = () => box.scrollHeight - box.scrollTop - box.clientHeight < 80;
    function msgHtml(m) {
      if (m.kind === "win") return `<div class="sysmsg">${CUR}${esc(t("chat.win", { name: m.user.nickname, amount: usd(m.amount), game: m.game }))}</div>`;
      const mine = m.user.public_id === myId;
      return `<div class="msg ${mine ? "me" : ""}">${avatar(m.user)}<div class="bubble">
        <div class="who">${esc(m.user.nickname)}${m.user.vip_level ? vipBadge(m.user.vip_level) : ""}</div>
        <div class="txt">${esc(m.text)}</div><div class="time">${fmtTime(m.created_at)}</div></div></div>`;
    }
    async function poll() {
      const data = await api(`/api/chat/messages?after_id=${lastId}&lang=${S.lang}`).catch(() => null);
      if (!data || state.route !== "chat") return;
      myId = data.me?.public_id ?? myId;
      $("#online").textContent = t("chat.online", { n: data.online });
      if (data.messages.length) {
        const stick = near() || !lastId;
        box.insertAdjacentHTML("beforeend", data.messages.map(msgHtml).join(""));
        lastId = data.messages[data.messages.length - 1].id;
        if (stick) box.scrollTop = box.scrollHeight;
      } else if (!lastId) box.innerHTML = `<div class="empty">${t("chat.empty")}</div>`;
    }
    poll();
    const iv = setInterval(poll, 2500);
    state.cleanup.push(() => clearInterval(iv));
    $("#chat-rules").onclick = showChatRules;
    $("#composer").onsubmit = async (e) => {
      e.preventDefault();
      const input = $("#msg-in");
      const text = input.value.trim();
      if (!text) return;
      if (S.pauseUntil > Date.now()) { toast(t("rg.paused_short")); return; }
      const ok = await guard(() => api("/api/chat/messages", { text }));
      if (ok) { input.value = ""; fx.tap(); await poll(); box.scrollTop = box.scrollHeight; }
    };
  }
  function showChatRules() {
    openSheet(`<h2>${t("chat.rules")}</h2><ol class="rules">${C().chatRules.map((r) => `<li>${esc(r)}</li>`).join("")}</ol>
      <div class="actions"><button class="btn primary" data-close>${t("chat.rules_ok")}</button></div>`);
    $("[data-close]").onclick = closeSheet;
  }
  function avatar(u, cls = "") {
    const photo = u.photo_url;
    const letter = esc((u.nickname || "?").trim().charAt(0).toUpperCase());
    const hues = ["#1c3b8f", "#2a4fb3", "#1f3f78", "#3359c4", "#274a9e"];
    const bg = hues[(u.public_id || 0) % hues.length];
    return `<span class="avatar ${cls}" style="background:${bg}">${photo ? `<img src="${esc(photo)}" alt="">` : letter}</span>`;
  }
  const vipKey = (lvl) => state.config?.vip_levels?.[lvl]?.key || "bronze";
  const vipBadge = (lvl, big = false) => `<span class="vip-badge l${lvl}${big ? " big" : ""}">${img(VIP_IMG[lvl] || VIP_IMG[0])}${esc(t("vip." + vipKey(lvl)))}</span>`;
  const vipMedal = (lvl) => img(VIP_IMG[lvl] || VIP_IMG[0], "vip-medal", t("vip." + vipKey(lvl)));

  // ================================================================ PROFILE
  async function loadMe() { state.me = await api("/api/me"); setBalance(state.me.balance); return state.me; }

  function renderProfile(view) {
    view.innerHTML = pageHead(t("menu.profile"), { backBtn: false }) + `<div id="prof"><div class="empty">${t("common.loading")}</div></div>`;
    // рисуем сразу из последних данных, чтобы переход был без «Загружаем…», и обновляем в фоне
    let shown = "";
    const paint = (me) => {
      const key = JSON.stringify(me);
      if (key === shown || !$("#prof", view)) return;
      shown = key;
      drawProfile(view, me);
    };
    if (state.me?.vip) paint(state.me);
    guard(async () => paint(await loadMe()));
  }
  function drawProfile(view, me) {
    {
      const tgPhoto = tg?.initDataUnsafe?.user?.photo_url;
      const u = { ...me, photo_url: me.photo_url || tgPhoto };
      const vip = me.vip;
      const levels = state.config.vip_levels;
      const next = vip.next_min;
      const pct = next ? Math.min(100, ((vip.wagered - vip.current_min) / (next - vip.current_min)) * 100) : 100;
      const perks = (lvl) => [
        { on: true, text: t("vip.perk.badge") },
        { on: levels[lvl].cashback > 0, text: levels[lvl].cashback ? t("vip.perk.cashback", { n: levels[lvl].cashback }) : t("vip.perk.cashback_from") },
        { on: lvl >= 3, text: t("vip.perk.priority") },
        { on: lvl >= 4, text: t("vip.perk.manager") },
      ];
      $("#prof").innerHTML = `
        <div class="profile-top">${avatar(u, "xl")}
          <div class="nick"><span id="nick">${esc(me.nickname)}</span><button id="nick-edit" aria-label="${t("profile.edit_nick")}">${ic("pen")}</button></div>
          ${vipBadge(vip.level, true)}</div>
        <div id="bonus-slot"></div>

        <div class="group"><ul class="list">
          <li class="row"><div class="grow"><div class="sub">${t("profile.id")}</div><div class="num">${me.public_id}</div></div>
            <button class="copy-btn" data-copy="${me.public_id}" aria-label="${t("common.copy")}">${ic("copy")}</button></li>
          <li class="row"><div class="grow"><div class="sub">${t("profile.tg_id")}</div><div class="num">${me.telegram_id}</div></div>
            <button class="copy-btn" data-copy="${me.telegram_id}" aria-label="${t("common.copy")}">${ic("copy")}</button></li>
        </ul></div>

        <div class="panel"><div class="sub muted small">${t("profile.balance")}</div>
          <div class="balance-big num">${CUR}${S.hideBalance ? "•••" : usd(me.balance)}</div>
          <div class="actions" style="display:flex;gap:8px;margin-top:12px"><button class="btn primary" style="flex:1" data-go="wallet">${ic("plus")}${t("wallet.deposit")}</button>
            <button class="btn ghost" style="flex:1" data-go="wallet/withdraw">${ic("up")}${t("wallet.withdraw")}</button></div></div>

        <div class="panel"><h3 style="display:flex;justify-content:space-between;align-items:center">${t("profile.privileges")}${vipBadge(vip.level)}</h3>
          <div class="progress"><i style="width:${pct.toFixed(1)}%"></i></div>
          <div class="levels"><span>${esc(t("vip." + vip.key))}</span><span>${next ? t("vip.to_next", { amount: usd(next - vip.wagered), name: t("vip." + vip.next_key) }) : t("vip.max")}</span></div>
          <ul class="perks">${perks(vip.level).map((p) => `<li class="${p.on ? "" : "locked"}">${ic(p.on ? "check" : "lock")}${esc(p.text)}</li>`).join("")}</ul>
          <button class="btn ghost sm" style="margin-top:12px" id="vip-all">${t("vip.all_levels")}</button></div>

        <div class="panel"><h3>${t("profile.referral")}</h3>
          <p class="muted small" style="margin:0 0 10px">${t("ref.text", { pct: me.referral.percent })}</p>
          <label class="field"><input value="${esc(me.referral.link)}" readonly style="font-weight:500;font-size:14px"></label>
          <div style="display:flex;gap:8px;margin-top:8px"><button class="btn ghost" style="flex:1" data-copy="${esc(me.referral.link)}">${ic("copy")}${t("common.copy")}</button>
            <button class="btn deep" style="flex:1" id="ref-share">${ic("share")}${t("ref.share")}</button></div>
          <div class="stats" style="grid-template-columns:repeat(2,1fr)"><div class="stat"><div class="k">${t("ref.invited")}</div><div class="v num">${fmt(me.referral.invited)}</div></div>
            <div class="stat"><div class="k">${t("ref.earned")}</div><div class="v num">${CUR}${usd(me.referral.earned)}</div></div></div></div>

        <div class="group" style="margin-top:12px"><ul class="list">
          ${[["leaders", "trophy"], ["history", "clock"], ["txs", "list"], ["fair", "shield"]].map(([r, i]) =>
            `<li><button class="row" data-go="${r}">${ic(i)}<span class="grow">${t("profile." + r)}</span>${ic("chev", "i chev")}</button></li>`).join("")}
        </ul></div>`;
      $$("[data-copy]", view).forEach((b) => (b.onclick = () => copy(b.dataset.copy)));
      $$("[data-go]", view).forEach((b) => (b.onclick = () => { fx.tap(); go(b.dataset.go); }));
      $("#nick-edit").onclick = editNick;
      paintBonus($("#bonus-slot", view), me);
      $("#ref-share").onclick = () => {
        const url = `https://t.me/share/url?url=${encodeURIComponent(me.referral.link)}&text=${encodeURIComponent(t("ref.share_text"))}`;
        if (tg?.openTelegramLink && tg.initData) tg.openTelegramLink(url); else copy(me.referral.link);
      };
      $("#vip-all").onclick = () => {
        const sh = openSheet(`<h2>${t("profile.privileges")}</h2><ul class="list">${levels.map((l) => `
          <li class="row">${vipBadge(l.level)}<span class="grow small muted">${t("vip.from", { amount: usd(l.min) })}</span>
          <span class="small">${l.cashback ? t("vip.perk.cashback", { n: l.cashback }) : "—"}</span></li>`).join("")}</ul>
          <div class="actions"><button class="btn primary" data-close>${t("common.ok")}</button></div>`);
        $("[data-close]", sh).onclick = closeSheet;
      };
    }
  }
  // ---------------- ежедневный бонус (если включён на сервере)
  function paintBonus(el, me) {
    const b = me.bonus;
    if (!el || !b?.enabled) { if (el) el.innerHTML = ""; return; }
    const left = b.next_at ? Math.max(0, new Date(b.next_at) - Date.now()) : 0;
    const hhmm = `${Math.floor(left / 3600e3)}:${String(Math.floor((left % 3600e3) / 60e3)).padStart(2, "0")}`;
    el.innerHTML = `<div class="bonus-card">${img("shared/gift-sapphire")}<div class="grow"><b>${t("bonus.title")}</b>
      <div class="small muted">${t("bonus.text", { amount: usd(b.amount) })}</div>
      ${b.available ? `<button class="btn gold sm" id="bonus-claim">${t("bonus.claim", { amount: usd(b.amount) })}</button>`
        : `<div class="small bonus-next">${t("bonus.next", { time: hhmm })}</div>`}</div></div>`;
    const btn = $("#bonus-claim", el);
    if (btn) btn.onclick = async () => {
      btn.disabled = true;
      const r = await guard(() => api("/api/bonus/claim", {}));
      if (!r) { btn.disabled = false; return; }
      fx.win(); toast(t("bonus.done", { amount: usd(r.amount) }));
      setBalance(r.balance);
      state.me = { ...state.me, balance: r.balance, bonus: r.bonus };
      paintBonus(el, state.me);
    };
  }

  // ================================================================ LEADERBOARD
  function renderLeaders(view) {
    let period = "week";
    view.innerHTML = pageHead(t("leaders.title")) + `<div class="lb-hero">${img("shared/trophy")}<div><div class="muted small">${t("leaders.hint")}</div>
        <div class="seg" id="lb-seg"><button data-p="week" class="on">${t("leaders.week")}</button><button data-p="all">${t("leaders.all")}</button></div></div></div>
      <div class="lb-me" id="lb-me"></div>
      <div class="group"><ul class="list" id="lb-list"><li class="empty">${t("common.loading")}</li></ul></div>`;
    bindBack(view);
    const MEDAL = ["shared/medal-gold", "shared/medal-silver", "shared/medal-bronze"];
    const load = () => guard(async () => {
      const lb = await api("/api/leaderboard?period=" + period);
      if (!$("#lb-list", view)) return;
      const mine = state.me?.public_id;
      $("#lb-list", view).innerHTML = lb.top.length ? lb.top.map((e) => `<li class="row lb-row${e.public_id === mine ? " me" : ""}">
          <span class="lb-rank num">${e.rank <= 3 ? img(MEDAL[e.rank - 1], "", "#" + e.rank) : e.rank}</span>${avatar(e)}
          <div class="grow"><div class="lb-name"><span>${esc(e.nickname)}</span>${vipMedal(e.vip_level)}</div>
            <div class="sub">${e.best_win ? t("leaders.best", { amount: usd(e.best_win) }) : "&nbsp;"}</div></div>
          <b class="num lb-sum">${CUR}${usd(e.wagered)}</b></li>`).join("")
        : `<li class="empty">${t("leaders.empty")}</li>`;
      $("#lb-me", view).innerHTML = lb.me ? `<b>${t("leaders.you", { rank: lb.me.rank })}</b><span class="num">${CUR}${usd(lb.me.wagered)}</span>`
        : `<span class="muted">${t("leaders.you_none")}</span>`;
    });
    $$("#lb-seg button", view).forEach((b) => (b.onclick = () => {
      fx.tap(); period = b.dataset.p;
      $$("#lb-seg button", view).forEach((x) => x.classList.toggle("on", x === b));
      load();
    }));
    load();
  }

  function editNick() {
    const sh = openSheet(`<h2>${t("profile.edit_nick")}</h2><form id="nick-form"><label class="field"><input id="nick-in" maxlength="20" value="${esc(state.me.nickname)}"></label>
      <p class="muted small">${t("profile.nick_rules")}</p><div class="actions"><button type="button" class="btn ghost" data-close>${t("common.cancel")}</button>
      <button class="btn primary">${t("common.save")}</button></div></form>`);
    $("[data-close]", sh).onclick = closeSheet;
    $("#nick-form").onsubmit = async (e) => {
      e.preventDefault();
      const me = await guard(() => api("/api/me/nickname", { nickname: $("#nick-in").value }));
      if (me) { state.me = me; closeSheet(); toast(t("profile.nick_saved")); $("#nick").textContent = me.nickname; }
    };
    setTimeout(() => $("#nick-in")?.focus(), 50);
  }

  // ================================================================ WALLET
  function renderWallet(view, tab = "deposit") {
    view.innerHTML = pageHead(t("wallet.title")) + `<div class="seg" style="margin-bottom:14px">
      <button data-tab="deposit" class="${tab === "deposit" ? "on" : ""}">${t("wallet.deposit")}</button>
      <button data-tab="withdraw" class="${tab === "withdraw" ? "on" : ""}">${t("wallet.withdraw")}</button></div><div id="w-body"></div>`;
    bindBack(view);
    $$("[data-tab]", view).forEach((b) => (b.onclick = () => {
      if (b.classList.contains("on")) return;
      const to = b.dataset.tab;
      state.route = to === "deposit" ? "wallet" : "wallet/withdraw";
      transition(() => { state.cleanup.splice(0).forEach((fn) => fn()); renderWallet(view, to); }, to === "withdraw" ? "forward" : "back");
    }));
    tab === "deposit" ? walletDeposit($("#w-body")) : walletWithdraw($("#w-body"));
  }
  // ---------------- пополнение: USDT в сети TON на адрес казино, ID игрока — в комментарии
  function walletDeposit(root) {
    root.innerHTML = `<div class="empty">${t("common.loading")}</div>`;
    guard(async () => {
      const [d, txs] = await Promise.all([api("/api/wallet/deposit"), S.depositLimit ? api("/api/wallet/transactions?limit=100") : []]);
      if (!d.enabled) { root.innerHTML = `<div class="panel"><p style="margin:0">${t("dep.disabled")}</p></div>`; return; }
      const day = Date.now() - 864e5;
      const today = txs.filter((x) => x.kind === "deposit" && Date.parse(x.created_at) > day).reduce((a, x) => a + x.amount, 0);
      const overLimit = S.depositLimit && today >= S.depositLimit;
      const paused = S.pauseUntil > Date.now();
      const copyRow = (label, value, id) => `<div class="dep-row"><div class="grow"><div class="dep-k">${label}</div>
          <div class="dep-v num" id="${id}">${esc(value)}</div></div>
          <button class="btn ghost sm" data-copy="${id}">${ic("copy")}${t("common.copy")}</button></div>`;
      root.innerHTML = `<div class="panel dep">
          <div class="dep-head">${CUR}<div><b>${t("dep.title")}</b><div class="muted small">${t("dep.sub")}</div></div></div>
          <ol class="dep-steps">
            <li>${copyRow(t("dep.address"), d.address, "dep-addr")}</li>
            <li>${copyRow(t("dep.memo"), d.memo, "dep-memo")}<p class="dep-warn">${t("dep.memo_warn")}</p></li>
            <li><div class="dep-k">${t("dep.send")}</div>
              <div class="dep-btns"><button class="btn primary" id="dep-tk">${t("dep.open_tonkeeper")}</button>
                <button class="btn ghost" id="dep-ton">${t("dep.open_wallet")}</button></div></li>
          </ol>
          <p class="muted small" style="margin:12px 0 0">${t("dep.note", { min: usd(d.min) })}</p>
          ${S.depositLimit ? `<p class="muted small" style="margin:6px 0 0">${t("rg.limit_note", { amount: usd(S.depositLimit) })}</p>` : ""}
          <button class="btn deep block" style="margin-top:14px" id="dep-sent">${t("dep.sent")}</button>
          ${DEMO ? `<button class="btn ghost block" style="margin-top:8px" id="dep-demo">${t("dep.demo")}</button>` : ""}</div>
        <div class="dep-wait" id="dep-wait" hidden><span class="spinner"></span><span>${t("dep.waiting")}</span></div>`;
      if (paused || overLimit) {
        const body = $(".dep", root);
        body.classList.add("blocked");
        body.insertAdjacentHTML("afterbegin", `<div class="dep-block">${paused ? t("rg.paused_short")
          : t("rg.limit_reached", { amount: usd(S.depositLimit) })}</div>`);
      }
      $$("[data-copy]", root).forEach((b) => (b.onclick = () => { fx.tap(); copy($("#" + b.dataset.copy).textContent); }));
      const open = (url) => { fx.tap(); if (tg?.openLink && url.startsWith("https://")) tg.openLink(url); else location.href = url; };
      $("#dep-tk").onclick = () => open(d.links.tonkeeper);
      $("#dep-ton").onclick = () => open(d.links.ton);
      // «Я отправил» — ждём зачисления: баланс обновится сам, как только перевод появится в сети
      $("#dep-sent").onclick = () => {
        fx.tap();
        const start = state.me?.balance ?? 0;
        $("#dep-wait").hidden = false;
        $("#dep-sent").disabled = true;
        let n = 0;
        const iv = setInterval(() => guard(async () => {
          const me = await loadMe();
          if (me.balance > start) { clearInterval(iv); fx.win(); toast(t("dep.credited", { amount: usd(me.balance - start) })); walletDeposit(root); }
          else if (++n > 60) { clearInterval(iv); $("#dep-wait").innerHTML = `<span>${t("dep.slow")}</span>`; $("#dep-sent").disabled = false; }
        }), 5000);
        state.cleanup.push(() => clearInterval(iv));
      };
      const demoBtn = $("#dep-demo");
      if (demoBtn) demoBtn.onclick = () => demoDeposit(root, d);
    });
  }
  // в демо перевода в сети нет — имитируем его
  function demoDeposit(root, d) {
    let amount = d.presets[1] || 10 * U;
    const sh = openSheet(`<h2>${t("dep.demo_title")}</h2><p class="muted small">${t("dep.demo_text", { memo: d.memo })}</p>
      <div class="chips" style="grid-template-columns:repeat(3,1fr)">${d.presets.map((p) =>
        `<button data-p="${p}" class="${p === amount ? "on" : ""}" style="height:44px;font-size:15px">${usd(p)}</button>`).join("")}</div>
      <div class="actions"><button class="btn ghost" data-a="no">${t("common.cancel")}</button><button class="btn primary" data-a="yes">${t("dep.demo_send")}</button></div>`);
    $$("[data-p]", sh).forEach((b) => (b.onclick = () => { fx.tap(); amount = +b.dataset.p; $$("[data-p]", sh).forEach((x) => x.classList.toggle("on", x === b)); }));
    $('[data-a="no"]', sh).onclick = closeSheet;
    $('[data-a="yes"]', sh).onclick = () => guard(async () => {
      await api("/demo/deposit", { amount, comment: d.memo });
      closeSheet(); fx.win(); toast(t("dep.credited", { amount: usd(amount) }));
      await loadMe(); walletDeposit(root);
    });
  }
  // ---------------- вывод: USDT на свой кошелёк TON, отправляет администратор
  function walletWithdraw(root) {
    root.innerHTML = `<div class="empty">${t("common.loading")}</div>`;
    guard(async () => {
      const me = await loadMe();
      const w = state.config.withdraw;
      const wds = await api("/api/wallet/withdrawals");
      const need = Math.floor((me.total_deposited + (me.total_bonus || 0)) * w.wager_ratio);
      const pct = need ? Math.min(100, (me.total_wagered / need) * 100) : 100;
      const savedAddr = (() => { try { return localStorage.getItem("ara-wd-address") || ""; } catch { return ""; } })();
      root.innerHTML = `<div class="panel"><div class="muted small">${t("wallet.available")}</div>
          <div class="balance-big num">${CUR}${usd(me.balance)}</div>
          ${me.wager_left ? `<div style="margin-top:12px"><div class="ctrl-label"><span>${t("wallet.wager")}</span><span class="num">${usd(me.total_wagered)} / ${usd(need)}</span></div>
            <div class="progress"><i style="width:${pct.toFixed(1)}%"></i></div><p class="muted small" style="margin:6px 0 0">${t("wallet.wager_left", { amount: usd(me.wager_left) })}</p></div>` : ""}
          <div class="ctrl-label" style="margin-top:14px"><span>${t("wallet.amount")}</span><span>${t("wallet.range", { min: usd(w.min), max: usd(w.max) })}</span></div>
          <div class="wd-amount"><label class="field">${CUR}<input id="wd-in" class="num" type="text" inputmode="decimal" autocomplete="off" placeholder="${usd(w.min)}" aria-label="${esc(t("wallet.amount"))}"><span class="suffix">USDT</span></label>
            <button class="btn ghost" id="wd-max">${t("bet.max")}</button></div>
          <div class="ctrl-label" style="margin-top:14px"><span>${t("wd.address")}</span><span>${t("wd.network")}</span></div>
          <label class="field addr"><input id="wd-addr" type="text" autocomplete="off" autocapitalize="off" spellcheck="false" placeholder="UQ…" value="${esc(savedAddr)}" aria-label="${esc(t("wd.address"))}"></label>
          <p class="muted small" style="margin:6px 0 0">${t("wd.address_hint")}${w.fee ? " " + t("wd.fee", { fee: usd(w.fee) }) : ""}</p>
          <button class="btn primary xl block" style="margin-top:12px" id="wd-btn">${t("wallet.withdraw_btn")}</button>
          <p class="muted small" style="margin:10px 0 0">${t(DEMO ? "wallet.demo_withdraw" : "wallet.withdraw_note")}</p></div>
        <h3 style="margin:18px 0 8px">${t("wallet.requests")}</h3>
        <div class="group"><ul class="list">${wds.length ? wds.map((x) => `<li class="row"><div class="grow"><div>${t("wallet.request_n", { id: x.id })} · <span class="num">${usd(x.amount)}</span> USDT</div>
          <div class="sub num">${fmtDate(x.created_at)}${x.address ? " · " + esc(x.address.slice(0, 6) + "…" + x.address.slice(-4)) : ""}</div></div><span class="small">${t("wd." + x.status)}</span></li>`).join("") : `<li class="empty">${t("wallet.no_requests")}</li>`}</ul></div>`;
      $("#wd-max").onclick = () => { fx.tap(); $("#wd-in").value = String(Math.min(me.balance, w.max) / U); };
      $("#wd-btn").onclick = () => guard(async () => {
        const amount = toUnits($("#wd-in").value);
        const address = $("#wd-addr").value.trim();
        if (!address) { toast(t("wd.need_address")); fx.error(); return; }
        const ok = await confirmSheet(t("wd.confirm_title"), t("wd.confirm_text", { amount: usd(amount - (w.fee || 0)), address: address.slice(0, 8) + "…" + address.slice(-6) }), t("wd.confirm_ok"));
        if (!ok) return;
        const res = await api("/api/wallet/withdraw", { amount, address });
        try { localStorage.setItem("ara-wd-address", address); } catch { /* приватный режим */ }
        toast(t("wallet.request_created", { id: res.id }));
        walletWithdraw(root);
        if (DEMO) { const tm = setTimeout(() => state.route === "wallet/withdraw" && walletWithdraw(root), 5600); state.cleanup.push(() => clearTimeout(tm)); }
      });
    });
  }

  // ================================================================ HISTORY / TXS / FAIR
  function renderHistory(view) {
    view.innerHTML = pageHead(t("profile.history")) + `<p class="muted small">${t("history.hint")}</p><div class="group"><ul class="list" id="h-list"><li class="empty">${t("common.loading")}</li></ul></div>`;
    bindBack(view);
    guard(async () => {
      const bets = await api("/api/bets?limit=50");
      state.bets = Object.fromEntries(bets.map((b) => [b.id, b]));
      $("#h-list").innerHTML = bets.length ? bets.map((b) => `<li><button class="row" data-bet="${b.id}"><div class="grow">
        <div>${esc(gameTitle(b))} <span class="muted small">#${b.id}</span></div><div class="sub">${fmtDate(b.created_at)} · ${fmt(b.amount)} ⭐</div></div>
        <b class="num ${b.payout > 0 ? "win-c" : "lose-c"}">${b.payout > 0 ? "+" + usd(b.payout) : "−" + usd(b.amount)}</b></button></li>`).join("")
        : `<li class="empty">${t("history.empty")}</li>`;
      $$("[data-bet]", view).forEach((b) => (b.onclick = () => showBet(state.bets[b.dataset.bet])));
    });
  }
  const gameTitle = (b) => (b.game === "slots" ? t("slot." + b.params.slot) : t("game." + b.game));
  function showBet(b) {
    const sh = openSheet(`<h2>${esc(gameTitle(b))} #${b.id}</h2>
      <div class="kv"><b>${t("bet.stake_payout")}</b><code>${fmt(b.amount)} → ${fmt(b.payout)} (${fmtX(b.multiplier)})</code></div>
      <div class="kv"><b>${t("bet.params")}</b><code>${esc(JSON.stringify(b.params))}</code></div>
      <div class="kv"><b>${t("bet.outcome")}</b><code>${esc(JSON.stringify(b.result))}</code></div>
      <div class="kv"><b>Server seed hash</b><code>${b.server_seed_hash}</code></div>
      <div class="kv"><b>Server seed</b><code>${b.server_seed || esc(t("bet.seed_hidden"))}</code></div>
      <div class="kv"><b>Client seed / nonce</b><code>${esc(b.client_seed)} / ${b.nonce}</code></div>
      <div class="actions"><button class="btn ghost" data-close>${t("common.close")}</button>${b.server_seed ? `<button class="btn primary" data-verify>${t("bet.verify")}</button>` : ""}</div>`);
    $("[data-close]", sh).onclick = closeSheet;
    const v = $("[data-verify]", sh);
    if (v) v.onclick = () => verifyBet(b);
  }
  async function verifyBet(b) {
    await guard(async () => {
      const v = await api("/api/fair/verify", { game: b.game, server_seed: b.server_seed, client_seed: b.client_seed, nonce: b.nonce, params: b.params });
      const hashOk = v.server_seed_hash === b.server_seed_hash;
      const outOk = b.game === "mines" ? JSON.stringify(v.mines) === JSON.stringify(b.result?.mines)
        : b.game === "crash" ? v.crash_point === b.result?.crash_point
        : Math.abs(v.multiplier - b.multiplier) < 1e-9;
      const sh = openSheet(`<h2>${t("bet.verify_title", { id: b.id })}</h2>
        <p class="${hashOk ? "win-c" : "lose-c"}">${hashOk ? "✓" : "✗"} ${t("bet.verify_hash")}</p>
        <p class="${outOk ? "win-c" : "lose-c"}">${outOk ? "✓" : "✗"} ${t("bet.verify_outcome")}</p>
        <pre class="code">${esc(JSON.stringify(v, null, 2))}</pre><div class="actions"><button class="btn primary" data-close>${t("common.ok")}</button></div>`);
      $("[data-close]", sh).onclick = closeSheet;
    });
  }
  function renderTxs(view) {
    view.innerHTML = pageHead(t("profile.txs")) + `<div class="group"><ul class="list" id="t-list"><li class="empty">${t("common.loading")}</li></ul></div>`;
    bindBack(view);
    guard(async () => {
      const txs = await api("/api/wallet/transactions?limit=100");
      $("#t-list").innerHTML = txs.length ? txs.map((x) => `<li class="row"><div class="grow"><div>${t("tx." + x.kind)}</div><div class="sub">${fmtDate(x.created_at)}</div></div>
        <b class="num ${x.amount > 0 ? "win-c" : ""}">${x.amount > 0 ? "+" : "−"}${usd(Math.abs(x.amount))}</b></li>`).join("") : `<li class="empty">${t("history.empty")}</li>`;
    });
  }
  function renderFair(view) {
    view.innerHTML = pageHead(t("profile.fair")) + `<p class="muted small">${t("fair.intro")}</p><div class="panel" id="f-box"><div class="empty">${t("common.loading")}</div></div>
      <div class="panel"><div class="ctrl-label"><span>${t("fair.new_client")}</span></div><label class="field"><input id="f-client" placeholder="${esc(t("fair.optional"))}" style="font-weight:500"></label>
      <button class="btn primary block" style="margin-top:10px" id="f-rotate">${t("fair.rotate")}</button><pre class="code" id="f-out" hidden></pre></div>
      <button class="btn ghost block" style="margin-top:12px" data-doc>${t("fair.how")}</button>`;
    bindBack(view);
    const load = () => guard(async () => {
      const s = await api("/api/fair");
      $("#f-box").innerHTML = `<div class="kv"><b>Server seed hash</b><code>${s.server_seed_hash}</code></div>
        <div class="kv"><b>Client seed</b><code>${esc(s.client_seed)}</code></div><div class="kv" style="margin:0"><b>Nonce</b><code>${s.nonce}</code></div>`;
    });
    load();
    $("[data-doc]", view).onclick = () => go("doc/fair");
    $("#f-rotate").onclick = () => guard(async () => {
      const r = await api("/api/fair/rotate", { client_seed: $("#f-client").value.trim() || null });
      const out = $("#f-out"); out.hidden = false;
      out.textContent = `${t("fair.revealed")}\n${r.previous_server_seed}\n\nhash: ${r.previous_server_seed_hash}\nclient seed: ${r.previous_client_seed}\n${t("fair.bets_count", { n: r.previous_nonce })}`;
      $("#f-client").value = ""; toast(t("fair.rotated")); load();
    });
  }

  // ================================================================ SETTINGS
  function renderSettings(view) {
    const seg = (key, opts) => `<div class="seg" data-set="${key}">${opts.map(([v, l]) => `<button data-v="${v}" class="${S[key] === v ? "on" : ""}">${esc(l)}</button>`).join("")}</div>`;
    const sw = (key) => `<button class="switch ${S[key] ? "on" : ""}" data-sw="${key}" role="switch" aria-checked="${!!S[key]}" aria-label="${esc(t("settings." + key))}"></button>`;
    const sel = (key, opts) => `<select class="select" data-sel="${key}">${opts.map(([v, l]) => `<option value="${v}" ${S[key] === v ? "selected" : ""}>${esc(l)}</option>`).join("")}</select>`;
    const paused = S.pauseUntil > Date.now();
    view.innerHTML = pageHead(t("menu.settings"), { backBtn: false }) + `
      <div class="group-title">${t("settings.lang")}</div><div style="margin-bottom:18px">${seg("lang", [["ru", "Русский"], ["en", "English"]])}</div>
      <div class="group-title">${t("settings.theme")}</div><div style="margin-bottom:18px">${seg("theme", [["auto", t("settings.theme_auto")], ["light", t("settings.theme_light")], ["dark", t("settings.theme_dark")]])}</div>

      <div class="group-title">${t("settings.app")}</div><div class="group"><ul class="list">
        ${["sound", "haptics", "motion", "hideBalance"].map((k) => `<li class="row"><div class="grow"><div>${t("settings." + k)}</div><div class="sub">${t("settings." + k + ".sub")}</div></div>${sw(k)}</li>`).join("")}
        <li class="row"><div class="grow"><div>${t("settings.confirmAbove")}</div><div class="sub">${t("settings.confirmAbove.sub")}</div></div>
          ${sel("confirmAbove", [[0, t("settings.off")], [10 * U, "10 USDT"], [50 * U, "50 USDT"], [100 * U, "100 USDT"]])}</li></ul></div>

      <div class="group-title">${t("settings.rg")}</div><div class="group"><ul class="list">
        <li class="row"><div class="grow"><div>${t("settings.depositLimit")}</div><div class="sub">${t("settings.depositLimit.sub")}</div></div>
          ${sel("depositLimit", [[0, t("settings.no_limit")], [50 * U, "50 USDT"], [100 * U, "100 USDT"], [500 * U, "500 USDT"], [1000 * U, "1 000 USDT"]])}</li>
        <li><button class="row" id="pause">${ic("clock")}<div class="grow"><div>${t("settings.pause")}</div><div class="sub">${paused ? t("rg.paused_until", { date: fmtDate(new Date(S.pauseUntil).toISOString()) }) : t("settings.pause.sub")}</div></div>${ic("chev", "i chev")}</button></li>
        <li><button class="row" data-doc="responsible">${ic("help")}<span class="grow">${t("settings.rg_doc")}</span>${ic("chev", "i chev")}</button></li></ul></div>

      <div class="group-title">${t("settings.about_group")}</div><div class="group"><ul class="list">
        <li><button class="row" id="about">${ic("info")}<span class="grow">${t("about.title")}</span>${ic("chev", "i chev")}</button></li></ul></div>
      ${DEMO ? `<button class="btn danger block" id="demo-reset" style="margin-bottom:12px">${t("demo.reset")}</button>` : ""}
      <p class="muted small center">ARA Casino v${VERSION}${DEMO ? " · demo" : ""}</p>`;

    $$("[data-set]", view).forEach((g) => $$("button", g).forEach((b) => (b.onclick = () => {
      const key = g.dataset.set;
      if (S[key] === b.dataset.v) return;
      fx.tap();
      if (key === "theme") { // цвета перетекают за 0,35 с, экран не перерисовываем
        S.theme = b.dataset.v; saveSettings();
        const root = document.documentElement;
        if (!reducedMotion()) { root.classList.add("theme-anim"); setTimeout(() => root.classList.remove("theme-anim"), 420); }
        applyTheme();
        $$("button", g).forEach((x) => x.classList.toggle("on", x === b));
        return;
      }
      const top = $("#view").scrollTop;
      transition(() => {
        S[key] = b.dataset.v; saveSettings(); applyTheme(); renderHeader(); renderTabbar(); draw();
        $("#view").scrollTop = top;
      }, "fade");
    })));
    $$("[data-sw]", view).forEach((b) => (b.onclick = () => {
      const k = b.dataset.sw; S[k] = !S[k]; saveSettings(); fx.tap();
      b.classList.toggle("on", S[k]); b.setAttribute("aria-checked", S[k]);
      applyTheme(); setBalance(state.me?.balance);
    }));
    $$("[data-sel]", view).forEach((s) => (s.onchange = () => { S[s.dataset.sel] = +s.value; saveSettings(); }));
    $("#pause").onclick = () => paused ? toast(t("rg.paused_until", { date: fmtDate(new Date(S.pauseUntil).toISOString()) })) : pauseSheet();
    $("#about").onclick = () => go("about");
    $$("[data-doc]", view).forEach((b) => (b.onclick = () => go("doc/" + b.dataset.doc)));
    const dr = $("#demo-reset");
    if (dr) dr.onclick = async () => {
      if (!(await confirmSheet(t("demo.reset"), t("demo.reset_text"), t("demo.reset"), true))) return;
      await guard(() => api("/demo/reset", {}));
      S.pauseUntil = 0; saveSettings(); await guard(loadMe); render();
      if (!state.me.nickname) { leaveGate(await nickGate(null)); draw(); }
      toast(t("demo.reset_done"));
    };
  }
  function pauseSheet() {
    const opts = [[1, t("rg.p24h")], [7, t("rg.p7d")], [30, t("rg.p30d")]];
    const sh = openSheet(`<h2>${t("settings.pause")}</h2><p class="muted">${t("rg.pause_text")}</p>
      <div style="display:grid;gap:8px">${opts.map(([d, l]) => `<button class="btn ghost block" data-d="${d}">${esc(l)}</button>`).join("")}</div>
      <div class="actions"><button class="btn primary" data-close>${t("common.cancel")}</button></div>`);
    $("[data-close]", sh).onclick = closeSheet;
    $$("[data-d]", sh).forEach((b) => (b.onclick = async () => {
      const days = +b.dataset.d;
      closeSheet();
      if (!(await confirmSheet(t("settings.pause"), t("rg.pause_confirm", { period: b.textContent }), t("rg.pause_ok"), true))) return;
      S.pauseUntil = Date.now() + days * 864e5; saveSettings(); toast(t("rg.pause_set")); render();
    }));
  }

  // ================================================================ ABOUT, DOCS, HELP
  function renderAbout(view) {
    const a = C().about;
    view.innerHTML = pageHead(a.title) + `<div class="doc">${a.text.map((p) => `<p>${esc(p)}</p>`).join("")}</div>
      <div class="group"><ul class="list">
        <li class="row">${ic("pin")}<div class="grow"><div class="sub">${t("about.address")}</div><div>${esc(C().address)}</div></div></li>
        <li class="row">${ic("support")}<div class="grow"><div class="sub">${t("about.support")}</div><div>${esc(a.contacts)}</div></div></li></ul></div>
      <div class="group-title">${t("about.docs")}</div><div class="group"><ul class="list">
        ${["terms", "privacy", "responsible", "fair", "chat-rules"].map((d) => `<li><button class="row" data-doc="${d}">${ic("doc")}<span class="grow">${esc(docTitle(d))}</span>${ic("chev", "i chev")}</button></li>`).join("")}</ul></div>
      ${disclaimer()}`;
    bindBack(view);
    $$("[data-doc]", view).forEach((b) => (b.onclick = () => go("doc/" + b.dataset.doc)));
  }
  const docTitle = (id) => (id === "chat-rules" ? t("chat.rules") : C().docs[id]?.title || id);
  function renderDoc(view, id) {
    if (id === "chat-rules") {
      view.innerHTML = pageHead(t("chat.rules")) + `<ol class="rules">${C().chatRules.map((r) => `<li>${esc(r)}</li>`).join("")}</ol>`;
      return bindBack(view);
    }
    const d = C().docs[id];
    if (!d) return renderAbout(view);
    view.innerHTML = pageHead(d.title) + `<article class="doc"><p class="meta">${t("doc.updated", { date: new Date(window.CONTENT.UPDATED).toLocaleDateString(locale()) })}</p>
      ${d.sections.map((s) => `<h2>${esc(s.h)}</h2>${s.p.map((p) => `<p>${esc(p)}</p>`).join("")}`).join("")}</article>${disclaimer()}`;
    bindBack(view);
  }
  function renderHelp(view) {
    view.innerHTML = pageHead(t("menu.help"), { backBtn: false }) + `<div>${C().faq.map((f) => `<details class="faq"><summary>${esc(f.q)}</summary><p>${esc(f.a)}</p></details>`).join("")}</div>
      <div class="panel" style="margin-top:18px"><h3>${t("help.still")}</h3><p class="muted small" style="margin:0 0 12px">${t("help.still_text")}</p>
        <button class="btn primary block" id="support">${ic("support")}${t("help.contact")}</button></div>
      <button class="btn ghost block" style="margin-top:12px" id="to-about">${t("about.title")}</button>`;
    $("#support").onclick = () => {
      const bot = state.config.bot_username;
      if (tg?.openTelegramLink && tg.initData) { tg.openTelegramLink(`https://t.me/${bot}?start=support`); tg.close?.(); }
      else toast(t("help.demo_support", { bot }));
    };
    $("#to-about").onclick = () => go("about");
  }

  // ================================================================ AGE GATE & INIT
  // Экраны первого входа: 1) возраст 18+, 2) ник. Переход между ними — сдвигом, выход в приложение — растворением.
  function leaveGate(g, how = "fade") {
    if (!g) return;
    if (reducedMotion()) return g.remove();
    g.classList.add(how === "left" ? "out-left" : "out-fade");
    g.style.pointerEvents = "none";
    setTimeout(() => g.remove(), 320);
  }
  const steps = (n) => `<div class="steps" aria-label="${esc(t("gate.step", { n }))}"><i class="${n === 1 ? "on" : ""}"></i><i class="${n === 2 ? "on" : ""}"></i></div>`;

  function ageGate() {
    return new Promise((resolve) => {
      if (S.ageOk) return resolve(null);
      const g = document.createElement("div");
      g.className = "gate";
      g.innerHTML = `${steps(1)}${LOGO.replace("<svg", '<svg class="logo"')}<h1>ARA Casino</h1><p>${esc(t("gate.text"))}</p>
        <p class="small">${esc(C().disclaimer)}</p><div class="btns"><button class="btn primary xl" id="g-yes">${t("gate.yes")}</button>
        <button class="btn ghost" id="g-no">${t("gate.no")}</button></div>
        <div class="seg" style="width:200px"><button data-l="ru" class="${S.lang === "ru" ? "on" : ""}">RU</button><button data-l="en" class="${S.lang === "en" ? "on" : ""}">EN</button></div>`;
      document.body.appendChild(g);
      $$("[data-l]", g).forEach((b) => (b.onclick = () => { S.lang = b.dataset.l; saveSettings(); g.remove(); ageGate().then(resolve); }));
      $("#g-yes", g).onclick = () => { S.ageOk = true; saveSettings(); fx.tap(); resolve(g); }; // экран убирает следующий шаг
      $("#g-no", g).onclick = () => { if (tg?.close && tg.initData) tg.close(); else $("p", g).textContent = t("gate.bye"); };
    });
  }

  // ---------------------------------------------------------------- ник
  const NICK_RE = /^[A-Za-zА-Яа-яЁё0-9_ .-]+$/;
  function nickProblem(raw) {
    const v = raw.trim();
    if (v.length < 3) return t("nick.too_short");
    if (v.length > 20) return t("nick.too_long");
    if (!NICK_RE.test(v)) return t("nick.bad_chars");
    return null;
  }
  const NICK_WORDS = ["Sapphire", "Aurelius", "Comet", "Orbit", "Royal", "Lucky", "Nova", "Ace", "Jackpot", "Crown", "Emerald", "Meteor"];
  const randomNick = () => NICK_WORDS[Math.floor(Math.random() * NICK_WORDS.length)] + "_" + (10 + Math.floor(Math.random() * 990));
  function suggestNick() {
    const u = tg?.initDataUnsafe?.user;
    for (const cand of [u?.username, [u?.first_name, u?.last_name].filter(Boolean).join(" ")]) {
      const v = (cand || "").replace(/[^A-Za-zА-Яа-яЁё0-9_ .-]/g, "").replace(/\s+/g, " ").trim().slice(0, 20);
      if (!nickProblem(v)) return v;
    }
    return randomNick();
  }

  function nickGate(prev) {
    return new Promise((resolve) => {
      const g = document.createElement("div");
      g.className = "gate gate-nick" + (prev ? " in-right" : "");
      const id = state.me?.public_id || 0;
      g.innerHTML = `${steps(2)}<span id="ng-ava"></span><h1>${t("nick.title")}</h1><p>${esc(t("nick.text"))}</p>
        <form class="nick-form" id="ng-form" novalidate>
          <label class="field"><input id="ng-in" maxlength="20" autocomplete="off" autocapitalize="off" spellcheck="false"
            enterkeyhint="done" aria-describedby="ng-hint" placeholder="${esc(t("nick.placeholder"))}"></label>
          <div class="nick-hint" id="ng-hint" aria-live="polite"></div>
          <div class="btns"><button class="btn primary xl" id="ng-go">${t("nick.continue")}</button>
            <button type="button" class="btn ghost" id="ng-rand">${t("nick.random")}</button></div>
        </form>`;
      document.body.appendChild(g);
      leaveGate(prev, "left");
      const input = $("#ng-in", g), hint = $("#ng-hint", g), go = $("#ng-go", g);
      const update = (serverError) => {
        const v = input.value;
        $("#ng-ava", g).innerHTML = avatar({ nickname: v.trim() || "?", public_id: id }, "xl");
        const problem = serverError || (v.trim() ? nickProblem(v) : null);
        hint.textContent = problem || t("profile.nick_rules");
        hint.classList.toggle("bad", !!problem);
        go.disabled = !!nickProblem(v);
      };
      input.value = suggestNick();
      input.addEventListener("input", () => update());
      $("#ng-rand", g).onclick = () => { fx.tap(); input.value = randomNick(); update(); input.focus(); };
      $("#ng-form", g).onsubmit = async (e) => {
        e.preventDefault();
        if (nickProblem(input.value)) return update();
        go.disabled = true;
        go.textContent = t("common.loading");
        try {
          state.me = await api("/api/me/nickname", { nickname: input.value.trim() });
          fx.win();
          resolve(g);
        } catch (err) {
          fx.error();
          go.textContent = t("nick.continue");
          update(errText(err));
        }
      };
      update();
    });
  }

  async function init() {
    await loadCloudSettings();
    applyTheme();
    if (!tg?.initData && !DEMO) {
      document.body.innerHTML = `<div class="gate">${LOGO.replace("<svg", '<svg class="logo"')}<h1>ARA Casino</h1><p>${t("gate.open_tg")}</p></div>`;
      return;
    }
    let gate = await ageGate(); // экран возраста остаётся на месте, пока грузятся данные
    renderHeader();
    renderTabbar();
    try {
      state.config = await api("/api/config");
      await loadMe();
    } catch (e) {
      leaveGate(gate);
      $("#screen").innerHTML = `<div class="empty">${esc(errText(e))}</div>`;
      return;
    }
    if (!S.bet || S.bet < state.config.min_bet || S.bet > state.config.max_bet) S.bet = clamp(U, state.config.min_bet, state.config.max_bet);
    // ссылка #slot-classic, #game-crash и т.п. открывает экран сразу
    const h = location.hash.slice(1);
    const deep = h.match(/^(game|slot|doc)-(.+)$/);
    if (deep) { state.stack = ["play"]; state.route = `${deep[1]}/${deep[2]}`; }
    else if (["chat", "profile", "settings", "help", "about", "wallet", "leaders"].includes(h)) { state.stack = h === "chat" ? [] : ["play"]; state.route = h; }
    render();
    if (!state.me.nickname) gate = await nickGate(gate);
    if (gate) { setBalance(state.me.balance); leaveGate(gate); if (ROOT_OF(state.route) === "menu") draw(); }
  }

  window.__app = { go, goRoot, back, state, settings: () => S, t };
  init();
})();
