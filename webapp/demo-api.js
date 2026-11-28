// Демо-бэкенд в браузере: те же ответы, что у настоящего API, но всё считается локально.
// Подключается только для теста интерфейса без сервера и Telegram. В проде этот файл не нужен —
// удалите <script src="demo-api.js"> из index.html.
// Provably fair тот же: HMAC_SHA256(server_seed, "client_seed:nonce:cursor") → floats.
(function () {
  "use strict";
  const PLINKO = {"low":{"8":[4.98,2.68,1.43,0.77,0.41,0.77,1.43,2.68,4.98],"9":[5.58,3.12,1.75,0.98,0.55,0.55,0.98,1.75,3.12,5.58],"10":[6.38,3.71,2.15,1.25,0.73,0.42,0.73,1.25,2.15,3.71,6.38],"11":[7.03,4.22,2.53,1.52,0.91,0.54,0.54,0.91,1.52,2.53,4.22,7.03],"12":[7.84,4.84,2.99,1.84,1.14,0.7,0.43,0.7,1.14,1.84,2.99,4.84,7.84],"13":[8.52,5.39,3.41,2.16,1.36,0.86,0.54,0.54,0.86,1.36,2.16,3.41,5.39,8.52],"14":[9.37,6.07,3.93,2.54,1.64,1.06,0.68,0.44,0.68,1.06,1.64,2.54,3.93,6.07,9.37],"15":[10.05,6.63,4.38,2.89,1.9,1.26,0.83,0.54,0.54,0.83,1.26,1.9,2.89,4.38,6.63,10.05],"16":[10.95,7.36,4.94,3.32,2.23,1.5,1.0,0.67,0.45,0.67,1.0,1.5,2.23,3.32,4.94,7.36,10.95]},"medium":{"8":[12.07,4.05,1.43,0.55,0.25,0.55,1.43,4.05,12.07],"9":[14.33,5.26,2.01,0.82,0.36,0.36,0.82,2.01,5.26,14.33],"10":[17.01,6.73,2.75,1.18,0.53,0.28,0.53,1.18,2.75,6.73,17.01],"11":[19.5,8.22,3.56,1.6,0.75,0.38,0.38,0.75,1.6,3.56,8.22,19.5],"12":[22.35,9.95,4.54,2.13,1.03,0.53,0.31,0.53,1.03,2.13,4.54,9.95,22.35],"13":[25.06,11.7,5.57,2.72,1.37,0.71,0.4,0.4,0.71,1.37,2.72,5.57,11.7,25.06],"14":[28.24,13.75,6.81,3.44,1.79,0.95,0.53,0.33,0.53,0.95,1.79,3.44,6.81,13.75,28.24],"15":[30.97,15.64,8.03,4.19,2.23,1.22,0.69,0.42,0.42,0.69,1.22,2.23,4.19,8.03,15.64,30.97],"16":[34.19,17.85,9.45,5.08,2.78,1.56,0.89,0.54,0.35,0.54,0.89,1.56,2.78,5.08,9.45,17.85,34.19]},"high":{"8":[32.89,5.43,1.06,0.26,0.1,0.26,1.06,5.43,32.89],"9":[43.63,8.45,1.87,0.49,0.16,0.16,0.49,1.87,8.45,43.63],"10":[55.84,12.35,3.04,0.86,0.29,0.13,0.29,0.86,3.04,12.35,55.84],"11":[69.36,17.14,4.64,1.39,0.48,0.2,0.2,0.48,1.39,4.64,17.14,69.36],"12":[84.2,22.88,6.71,2.15,0.77,0.31,0.17,0.31,0.77,2.15,6.71,22.88,84.2],"13":[99.98,29.49,9.28,3.15,1.16,0.48,0.24,0.24,0.48,1.16,3.15,9.28,29.49,99.98],"14":[117.7,37.3,12.5,4.46,1.72,0.72,0.34,0.21,0.34,0.72,1.72,4.46,12.5,37.3,117.7],"15":[135.21,45.65,16.18,6.06,2.42,1.04,0.49,0.27,0.27,0.49,1.04,2.42,6.06,16.18,45.65,135.21],"16":[154.32,55.11,20.55,8.04,3.32,1.46,0.69,0.37,0.24,0.37,0.69,1.46,3.32,8.04,20.55,55.11,154.32]}};

  const EDGE = 0.03;
  const RTP = 1 - EDGE;
  // валюта — USDT; все суммы, как и на сервере, целые микро-USDT (1 USDT = 1 000 000)
  const U = 1_000_000;
  const LIMITS = { min_bet: 0.1 * U, max_bet: 1000 * U, max_payout: 10_000 * U };
  const usdt = (u) => (u / U).toFixed(2) + " USDT";
  const STORE_KEY = "ara-demo-v2"; // v2 — USDT
  const DAILY_BONUS = 0.5 * U; // в демо бонус включён; на сервере — DAILY_BONUS (по умолчанию 0)
  const START_BALANCE = 100 * U;
  const DEMO_WALLET = "UQ-DEMO-ADDRESS-NOT-REAL-DO-NOT-SEND"; // в демо адреса нет: отправить на него ничего нельзя
  const USDT_MASTER = "EQCxE6mUtQJKFnGfaROTKOt1lZbDiiX1kCixRv7Nw2Id_sDs";

  // ------------------------------------------------------------ slots
  // 3×3, 5 линий. Каждая клетка независимо выбирает символ по весам (из одного числа RNG).
  // Выплата линии (3 одинаковых) — в ставках на линию; ставка на линию = ставка / 5.
  // RTP = Σ p_i³ · pay_i — считается точно, таблица подгоняется под 1 − house_edge.
  const SLOT_WEIGHTS = [32, 26, 20, 12, 7, 3];
  const SLOT_BASE = [2, 4, 8, 30, 120, 600];
  const SLOT_LINES = [[0, 1, 2], [3, 4, 5], [6, 7, 8], [0, 4, 8], [6, 4, 2]];
  const SLOT_PAYS = (() => {
    const ev = SLOT_WEIGHTS.reduce((a, w, i) => a + (w / 100) ** 3 * SLOT_BASE[i], 0);
    return SLOT_BASE.map((b) => Math.floor(b * (RTP / ev) * 100 + 1e-9) / 100);
  })();
  const SLOT_THEMES = { classic: {}, treasury: {}, royal: {} }; // картинки символов — во фронте (app.js, SLOT_SYMBOLS)

  // ------------------------------------------------------------ roulette (европейская) и crash
  const RED = new Set([1, 3, 5, 7, 9, 12, 14, 16, 18, 19, 21, 23, 25, 27, 30, 32, 34, 36]);
  const rColor = (n) => (n === 0 ? "green" : RED.has(n) ? "red" : "black");
  const CRASH_G = 0.18; // множитель e^(0.18·t)
  const CRASH_MAX = 1000;

  // привилегии по сумме ставок
  const VIP_LEVELS = [
    { level: 0, key: "bronze", min: 0, cashback: 0 },
    { level: 1, key: "silver", min: 100 * U, cashback: 1 },
    { level: 2, key: "gold", min: 1_000 * U, cashback: 2 },
    { level: 3, key: "sapphire", min: 5_000 * U, cashback: 3 },
    { level: 4, key: "diamond", min: 25_000 * U, cashback: 5 },
  ];

  const CONFIG = {
    house_edge: EDGE, ...LIMITS,
    games: [
      { name: "dice", title: "Dice" },
      { name: "coinflip", title: "Coinflip" },
      { name: "limbo", title: "Limbo" },
      { name: "plinko", title: "Plinko", tables: PLINKO },
      { name: "roulette", title: "Roulette" },
      { name: "slots", title: "Slots", themes: Object.keys(SLOT_THEMES).map((id) => ({ id })),
        weights: SLOT_WEIGHTS, pays: SLOT_PAYS, lines: SLOT_LINES },
      { name: "mines", title: "Mines", tiles: 25 },
      { name: "crash", title: "Crash", growth: CRASH_G, max: CRASH_MAX },
    ],
    vip_levels: VIP_LEVELS,
    daily_bonus: DAILY_BONUS,
    bot_username: "ara_casino_demo_bot",
    currency: { code: "USDT", decimals: 6, network: "TON" },
    deposit: { enabled: true, min: 1 * U, presets: [5, 10, 25, 50, 100, 250].map((x) => x * U) },
    withdraw: { min: 5 * U, max: 5000 * U, fee: 0, method: "ton", wager_ratio: 1 },
    referral_deposit_percent: 5,
  };

  class ApiError extends Error {
    constructor(code, message) { super(message); this.code = code; }
  }
  const fail = (code, msg) => { throw new ApiError(code, msg); };

  // ------------------------------------------------------------ crypto / provably fair
  const enc = new TextEncoder();
  const hex = (buf) => [...new Uint8Array(buf)].map((b) => b.toString(16).padStart(2, "0")).join("");
  const randHex = (n) => hex(crypto.getRandomValues(new Uint8Array(n)));
  const sha256 = async (s) => hex(await crypto.subtle.digest("SHA-256", enc.encode(s)));

  async function fairRng(serverSeed, clientSeed, nonce) {
    const key = await crypto.subtle.importKey("raw", enc.encode(serverSeed), { name: "HMAC", hash: "SHA-256" },
      false, ["sign"]);
    const bytes = [];
    for (let cursor = 0; cursor < 4; cursor++) { // 128 байт = 32 числа, хватает любой игре
      const sig = await crypto.subtle.sign("HMAC", key, enc.encode(`${clientSeed}:${nonce}:${cursor}`));
      bytes.push(...new Uint8Array(sig));
    }
    let i = 0;
    const float = () => {
      const b = bytes.slice(i, i + 4);
      i += 4;
      return b[0] / 256 + b[1] / 256 ** 2 + b[2] / 256 ** 3 + b[3] / 256 ** 4;
    };
    const intBelow = (n) => Math.floor(float() * n);
    return {
      float,
      floats: (n) => Array.from({ length: n }, float),
      shuffle(items) {
        const pool = [...items], out = [];
        while (pool.length) out.push(pool.splice(intBelow(pool.length), 1)[0]);
        return out;
      },
    };
  }

  // ------------------------------------------------------------ math helpers
  const floorTo = (x, d) => Math.floor(x * 10 ** d + 1e-9) / 10 ** d;
  const payoutFor = (amount, mult) => Math.floor(amount * mult + 1e-9);
  const num = (v, name) => {
    const n = Number(v);
    if (v === "" || v === null || v === undefined || !Number.isFinite(n)) fail("bad_params", `Неверный параметр ${name}`);
    return n;
  };

  // ------------------------------------------------------------ games (порт app/games/*)
  const GAMES = {
    dice: {
      parse(p) {
        const target = floorTo(num(p.target, "target"), 2);
        const direction = p.direction === "over" ? "over" : "under";
        if (target < 1 || target > 99) fail("bad_params", "Неверный параметр target: от 1.00 до 99.00");
        const chance = direction === "under" ? target / 100 : (100 - target) / 100;
        if (chance < 0.01 - 1e-9 || chance > 0.98 + 1e-9) fail("bad_params", "Шанс выигрыша должен быть от 1% до 98%");
        return { target, direction, chance };
      },
      maxMult: (p) => floorTo(RTP / p.chance, 4),
      play(rng, p) {
        const mult = floorTo(RTP / p.chance, 4);
        const roll = Math.floor(rng.float() * 10000) / 100;
        const win = p.direction === "under" ? roll < p.target : roll >= p.target;
        return { mult: win ? mult : 0, result: { roll, target: p.target, direction: p.direction, payout_multiplier: mult } };
      },
    },
    coinflip: {
      parse(p) {
        if (p.side !== "heads" && p.side !== "tails") fail("bad_params", "Неверный параметр side");
        return { side: p.side };
      },
      maxMult: () => floorTo(RTP * 2, 4),
      play(rng, p) {
        const side = rng.float() < 0.5 ? "heads" : "tails";
        return { mult: side === p.side ? floorTo(RTP * 2, 4) : 0, result: { side, chosen: p.side } };
      },
    },
    limbo: {
      parse(p) {
        const target = floorTo(num(p.target, "target"), 2);
        if (target < 1.01 || target > 1e6) fail("bad_params", "Неверный параметр target: от 1.01 до 1000000");
        return { target };
      },
      maxMult: (p) => p.target,
      play(rng, p) {
        const raw = RTP / (1 - rng.float());
        const point = Math.min(Math.max(1, floorTo(raw, 2)), 1e6);
        return { mult: point >= p.target ? p.target : 0, result: { point, target: p.target } };
      },
    },
    plinko: {
      parse(p) {
        const rows = num(p.rows, "rows");
        if (!Number.isInteger(rows) || rows < 8 || rows > 16) fail("bad_params", "Неверный параметр rows: от 8 до 16");
        const risk = ["low", "medium", "high"].includes(p.risk) ? p.risk : fail("bad_params", "Неверный параметр risk");
        return { rows, risk };
      },
      maxMult: (p) => Math.max(...PLINKO[p.risk][p.rows]),
      play(rng, p) {
        const path = rng.floats(p.rows).map((f) => (f >= 0.5 ? 1 : 0));
        const bucket = path.reduce((a, b) => a + b, 0);
        const mult = PLINKO[p.risk][p.rows][bucket];
        return { mult, result: { path, bucket, multiplier: mult } };
      },
    },
    roulette: {
      parse(p) {
        const b = p.bet;
        if (["red", "black", "even", "odd", "zero"].includes(b)) return { bet: b };
        if (Number.isInteger(b) && b >= 0 && b <= 36) return { bet: b };
        fail("bad_params", "Ставка: red, black, even, odd, zero или число 0–36");
      },
      maxMult: (p) => (typeof p.bet === "number" || p.bet === "zero" ? 36 : 2),
      play(rng, p) {
        const n = Math.floor(rng.float() * 37), b = p.bet;
        const win = (typeof b === "number" && b === n) || (b === "zero" && n === 0) || ((b === "red" || b === "black") && rColor(n) === b)
          || (b === "even" && n !== 0 && n % 2 === 0) || (b === "odd" && n % 2 === 1);
        return { mult: win ? GAMES.roulette.maxMult(p) : 0, result: { number: n, color: rColor(n), bet: b } };
      },
    },
    slots: {
      parse(p) {
        if (!SLOT_THEMES[p.slot]) fail("bad_params", "Неверный параметр slot");
        return { slot: p.slot };
      },
      maxMult: () => null, // выигрыш режется лимитом max_payout при расчёте, ставку не отклоняем
      capPayout: true,
      play(rng, p) {
        const cum = SLOT_WEIGHTS.map((_, i) => SLOT_WEIGHTS.slice(0, i + 1).reduce((a, b) => a + b, 0));
        const grid = rng.floats(9).map((f) => cum.findIndex((c) => Math.floor(f * 100) < c));
        const wins = [];
        SLOT_LINES.forEach((line, i) => {
          const [a, b, c] = line.map((k) => grid[k]);
          if (a === b && b === c) wins.push({ line: i, symbol: a, pay: SLOT_PAYS[a] });
        });
        const mult = floorTo(wins.reduce((s, w) => s + w.pay, 0) / SLOT_LINES.length, 4);
        return { mult, result: { slot: p.slot, grid, wins, multiplier: mult } };
      },
    },
  };

  const minesMultiplier = (mines, revealed) => {
    if (revealed === 0) return 0;
    let prob = 1;
    for (let i = 0; i < revealed; i++) prob *= (25 - mines - i) / (25 - i);
    return floorTo(RTP / prob, 4);
  };

  // ------------------------------------------------------------ state
  let S = null;

  async function newSeed(clientSeed) {
    const server_seed = randHex(32);
    return { server_seed, server_seed_hash: await sha256(server_seed), client_seed: clientSeed || randHex(8), nonce: 0 };
  }

  async function load() {
    if (S) return S;
    try { S = JSON.parse(localStorage.getItem(STORE_KEY) || "null"); } catch { S = null; }
    if (!S) await reset(false);
    return S;
  }

  function save() {
    try { localStorage.setItem(STORE_KEY, JSON.stringify(S)); } catch { /* без localStorage живём в памяти */ }
  }

  async function reset(persist = true) {
    S = {
      user: { id: 777000, public_id: 104233, username: "demo", first_name: "Демо", nickname: null, // ник выбирается при первом входе
              photo_url: null, balance: 0, total_deposited: 0, total_withdrawn: 0, total_wagered: 0, total_won: 0,
              total_bonus: 0, bonus_claimed_on: null, referral_invited: 3, referral_earned: 0 },
      seed: await newSeed(), revealed: {}, txs: [], bets: [], withdrawals: [],
      chat: { messages: [], lastBotAt: 0, lastUserAt: 0 },
      seq: { tx: 0, bet: 0, wd: 0, msg: 0 },
    };
    apply("bonus", START_BALANCE, "demo", 0);
    if (persist) save();
  }

  const now = () => new Date().toISOString();

  function apply(kind, amount, ref_type, ref_id) {
    const u = S.user;
    if (u.balance + amount < 0) fail("insufficient_funds", "Недостаточно средств на балансе");
    u.balance += amount;
    S.txs.push({ id: ++S.seq.tx, kind, amount, balance_after: u.balance, ref_type, ref_id: String(ref_id),
                 created_at: now() });
  }

  function betOut(b) {
    const server_seed = S.revealed[b.server_seed_hash] || null;
    return { ...b, state: undefined, result: b.status === "active" ? null : b.result, server_seed };
  }

  function checkAmount(amount) {
    if (!Number.isInteger(amount) || amount < LIMITS.min_bet || amount > LIMITS.max_bet)
      fail("bad_amount", `Ставка должна быть от ${usdt(LIMITS.min_bet)} до ${usdt(LIMITS.max_bet)}`);
  }

  async function takeBet(amount) {
    if (S.user.balance < amount) fail("insufficient_funds", "Недостаточно средств на балансе");
    const nonce = S.seed.nonce++;
    return { seed: S.seed, nonce, rng: await fairRng(S.seed.server_seed, S.seed.client_seed, nonce) };
  }

  function newBet(game, amount, params, seed, nonce, extra) {
    const bet = { id: ++S.seq.bet, game, amount, payout: 0, multiplier: 0, status: "lost", params,
                  client_seed: seed.client_seed, nonce, server_seed_hash: seed.server_seed_hash,
                  created_at: now(), ...extra };
    S.bets.push(bet);
    apply("bet", -amount, "bet", bet.id);
    S.user.total_wagered += amount;
    return bet;
  }

  function settle(bet, mult, cap = false) {
    let payout = payoutFor(bet.amount, mult);
    if (cap) payout = Math.min(payout, LIMITS.max_payout);
    Object.assign(bet, { multiplier: mult, payout, status: payout > 0 ? "won" : "lost" });
    if (payout > 0) { apply("win", payout, "bet", bet.id); S.user.total_won += payout; }
  }

  const activeMines = () => S.bets.find((b) => b.game === "mines" && b.status === "active");

  function minesView(bet) {
    const st = bet.state;
    const mines = bet.params.mines;
    const safe = st.revealed.filter((t) => !st.mines.includes(t));
    const view = {
      mines_count: mines, revealed: safe, multiplier: minesMultiplier(mines, safe.length),
      next_multiplier: safe.length < 25 - mines ? minesMultiplier(mines, safe.length + 1) : null,
      bet_id: bet.id, amount: bet.amount, status: bet.status, payout: bet.payout,
    };
    if (bet.status !== "active") Object.assign(view, { mines: st.mines, picked: st.revealed });
    return view;
  }

  const playOut = (bet, result) => ({ bet: betOut(bet), balance: S.user.balance, result });

  function wagerLeft() {
    const u = S.user;
    return Math.max(0, Math.floor((u.total_deposited + (u.total_bonus || 0)) * CONFIG.withdraw.wager_ratio) - u.total_wagered);
  }

  function vipFor(wagered) {
    let cur = VIP_LEVELS[0];
    for (const l of VIP_LEVELS) if (wagered >= l.min) cur = l;
    const next = VIP_LEVELS[cur.level + 1] || null;
    return { level: cur.level, key: cur.key, cashback: cur.cashback, wagered, current_min: cur.min,
             next_min: next ? next.min : null, next_key: next ? next.key : null };
  }

  const today = () => new Date().toISOString().slice(0, 10); // сутки по UTC, как на сервере
  function bonusInfo() {
    const available = S.user.bonus_claimed_on !== today();
    const next = new Date(); next.setUTCHours(24, 0, 0, 0);
    return { enabled: DAILY_BONUS > 0, amount: DAILY_BONUS, available, next_at: available ? null : next.toISOString() };
  }

  function me() {
    const u = S.user;
    return {
      ...u, telegram_id: u.id, wager_left: wagerLeft(), vip: vipFor(u.total_wagered), bonus: bonusInfo(),
      referral: { link: `https://t.me/${CONFIG.bot_username}?startapp=ref_${u.public_id}`,
                  invited: u.referral_invited, earned: u.referral_earned, percent: CONFIG.referral_deposit_percent },
    };
  }

  // ------------------------------------------------------------ chat (в демо остальные игроки — боты)
  const BOT_NAMES = ["Sapphire_Fox", "Comet77", "Lady Luck", "Orbit_9", "GoldenAce", "nova.mia", "RoyalFlush",
                     "Meteor", "Emerald_K", "Jackpot_Joe"];
  const pick = (arr) => arr[Math.floor(Math.random() * arr.length)];
  const GAME_NAMES = ["Crash", "Roulette", "Dice", "Limbo", "Plinko", "Mines", "Slots"];

  function botUser(name) {
    const h = [...name].reduce((a, c) => (a * 31 + c.charCodeAt(0)) >>> 0, 7);
    return { public_id: 100000 + (h % 90000), nickname: name, vip_level: h % 5, photo_url: null };
  }

  function pushMsg(m) {
    S.chat.messages.push({ id: ++S.seq.msg, created_at: now(), ...m });
    if (S.chat.messages.length > 100) S.chat.messages.splice(0, S.chat.messages.length - 100);
  }

  function tickChat(lang) {
    const lines = (window.CONTENT?.[lang] || window.CONTENT?.ru)?.chatBots || ["hi"];
    const c = S.chat;
    if (!c.messages.length) { // стартовая история
      for (let i = 0; i < 6; i++) pushMsg({ kind: "user", user: botUser(pick(BOT_NAMES)), text: pick(lines) });
      c.lastBotAt = Date.now();
    }
    if (Date.now() - c.lastBotAt > 4000 + Math.random() * 6000) {
      if (Math.random() < 0.25) {
        pushMsg({ kind: "win", user: botUser(pick(BOT_NAMES)), game: pick(GAME_NAMES),
                  amount: [12.4, 34, 56.5, 120, 250][Math.floor(Math.random() * 5)] * U });
      } else {
        pushMsg({ kind: "user", user: botUser(pick(BOT_NAMES)), text: pick(lines) });
      }
      c.lastBotAt = Date.now();
    }
  }

  const myChatUser = () => ({ public_id: S.user.public_id, nickname: S.user.nickname,
                              vip_level: vipFor(S.user.total_wagered).level, photo_url: S.user.photo_url });

  // имитация админа: заявка «одобряется» через 5 секунд
  function tickWithdrawals() {
    for (const w of S.withdrawals) {
      if (w.status === "pending" && Date.now() - Date.parse(w.created_at) > 5000) {
        Object.assign(w, { status: "completed", paid_amount: w.amount - w.fee, processed_at: now() });
        S.user.total_withdrawn += w.amount;
      }
    }
  }

  // ------------------------------------------------------------ адрес TON (порт app/ton/address.py: формат и контрольная сумма)
  function crc16(bytes) {
    let crc = 0;
    for (const b of bytes) {
      crc ^= b << 8;
      for (let i = 0; i < 8; i++) crc = crc & 0x8000 ? ((crc << 1) ^ 0x1021) & 0xffff : (crc << 1) & 0xffff;
    }
    return crc;
  }
  function tonAddress(raw) {
    const s = String(raw || "").trim();
    const bad = () => fail("bad_address", "Неверный адрес TON — скопируйте его из кошелька целиком");
    if (/^0:[0-9a-fA-F]{64}$/.test(s)) return s.toLowerCase();
    if (!/^[A-Za-z0-9_\-+/]{48}$/.test(s)) bad();
    const bin = atob(s.replace(/-/g, "+").replace(/_/g, "/"));
    const bytes = Array.from(bin, (c) => c.charCodeAt(0));
    if (bytes.length !== 36) bad();
    if (crc16(bytes.slice(0, 34)) !== ((bytes[34] << 8) | bytes[35])) bad();
    if (bytes[0] & 0x80) fail("bad_address", "Это адрес тестовой сети — нужен адрес основной сети TON");
    if (bytes[1] !== 0) fail("bad_address", "Нужен адрес в основной сети (workchain 0)");
    if (s === DEMO_WALLET) fail("bad_address", "Это адрес казино — укажите свой кошелёк");
    return s;
  }

  // ------------------------------------------------------------ crash (порт app/games/crash.py)
  const clock = () => Date.now() / 1000;
  const crashMultAt = (el) => Math.min(CRASH_MAX, Math.max(1, Math.floor(Math.exp(Math.max(0, el) * CRASH_G) * 100 + 1e-9) / 100));
  const elapsedFor = (m) => Math.log(m) / CRASH_G;
  const activeCrash = () => S.bets.find((b) => b.game === "crash" && b.status === "active");
  function crashResolve(st, t) {
    const el = t - st.started_at;
    if (st.auto <= st.point && el >= elapsedFor(st.auto)) return ["won", st.auto];
    if (el >= elapsedFor(st.point)) return ["lost", 0];
    return null;
  }
  function crashFinish(bet, status, mult, kind) {
    settle(bet, status === "won" ? mult : 0, true);
    bet.result = { crash_point: bet.state.point, cashout: kind, multiplier: status === "won" ? mult : 0 };
    bigWin(bet);
  }
  function settleCrash() { // ленивый расчёт: раунд, который закончился сам
    const b = activeCrash();
    const r = b && crashResolve(b.state, clock());
    if (r) crashFinish(b, r[0], r[1], r[0] === "won" ? "auto" : null);
  }
  function crashView(bet, t = clock()) {
    const st = bet.state;
    const v = { bet_id: bet.id, amount: bet.amount, status: bet.status, payout: bet.payout, started_at: st.started_at, server_now: t,
                auto_cashout: st.auto_user, auto_target: st.auto, max_multiplier: st.cap };
    if (bet.status === "active") v.multiplier = crashMultAt(t - st.started_at);
    else Object.assign(v, { crash_point: st.point, multiplier: bet.multiplier, cashout: bet.result?.cashout ?? null });
    return v;
  }
  function bigWin(bet) { // крупный выигрыш — в ленту чата
    if (bet.payout >= 10 * bet.amount && bet.payout >= 5 * U)
      pushMsg({ kind: "win", user: myChatUser(), game: CONFIG.games.find((g) => g.name === bet.game).title, amount: bet.payout });
  }

  // ------------------------------------------------------------ рейтинг (в демо соперники — боты чата)
  function leaderboard(period) {
    const since = period === "all" ? 0 : Date.now() - 7 * 864e5;
    const mineBets = S.bets.filter((b) => b.status !== "active" && Date.parse(b.created_at) >= since);
    const mine = mineBets.reduce((a, b) => a + b.amount, 0);
    const BASE = [4820, 3175, 2240, 1580, 990, 730, 465, 290, 180, 95].map((x) => x * U);
    const rows = BOT_NAMES.map((n, i) => {
      const u = botUser(n), all = BASE[i] * 6 + (u.public_id % 997) * U;
      const w = period === "all" ? all : BASE[i];
      return { ...u, vip_level: vipFor(all).level, wagered: w, best_win: Math.round(w * (0.06 + (u.public_id % 7) / 60) / 10000) * 10000 };
    });
    if (mine > 0) rows.push({ ...myChatUser(), wagered: mine, best_win: mineBets.reduce((a, b) => Math.max(a, b.payout), 0) });
    rows.sort((a, b) => b.wagered - a.wagered || a.public_id - b.public_id);
    const top = rows.slice(0, 20).map((e, i) => ({ rank: i + 1, public_id: e.public_id, nickname: e.nickname || `Player ${e.public_id}`,
      photo_url: e.photo_url, vip_level: e.vip_level, wagered: e.wagered, best_win: e.best_win }));
    const idx = rows.findIndex((e) => e.public_id === S.user.public_id);
    return { period_days: period === "all" ? null : 7, top, me: idx >= 0 ? { rank: idx + 1, wagered: mine } : null };
  }

  // ------------------------------------------------------------ routes
  async function route(method, path, body) {
    const [p, qs] = path.split("?");
    const q = Object.fromEntries(new URLSearchParams(qs || ""));
    const limit = Math.min(+q.limit || 30, 100);

    if (method === "GET" && p === "/api/config") return CONFIG;
    if (method === "GET" && p === "/api/me") { tickWithdrawals(); return me(); }
    if (method === "POST" && p === "/api/bonus/claim") {
      if (DAILY_BONUS <= 0) fail("bonus_disabled", "Ежедневный бонус выключен");
      if (S.user.bonus_claimed_on === today()) fail("bonus_claimed", "Бонус уже получен сегодня");
      apply("bonus", DAILY_BONUS, "daily", today());
      S.user.total_bonus = (S.user.total_bonus || 0) + DAILY_BONUS;
      S.user.bonus_claimed_on = today();
      return { balance: S.user.balance, amount: DAILY_BONUS, bonus: bonusInfo() };
    }
    if (method === "GET" && p === "/api/leaderboard") {
      if (!["week", "all", undefined].includes(q.period)) fail("bad_params", "period: week или all");
      return leaderboard(q.period || "week");
    }
    if (method === "POST" && p === "/api/me/nickname") {
      const nick = String(body.nickname || "").trim().replace(/\s+/g, " ");
      if (!/^[A-Za-zА-Яа-яЁё0-9_ .-]{3,20}$/.test(nick))
        fail("bad_nickname", "Ник: 3–20 символов — буквы, цифры, пробел, _ . -");
      const low = nick.toLowerCase().replace(/[\s_.-]/g, "");
      // нельзя выдавать себя за администрацию (на бэкенде — тот же список)
      const RESERVED_PARTS = ["admin", "support", "moder", "official", "админ", "поддерж", "модер", "официал"];
      const RESERVED_EXACT = ["ara", "ара", "aracasino", "араказино", "telegram", "телеграм", "system", "система"];
      if (RESERVED_PARTS.some((w) => low.includes(w)) || RESERVED_EXACT.includes(low))
        fail("nickname_reserved", "Такой ник выбрать нельзя");
      // занятые ники (в демо — ники ботов чата), сравнение без учёта регистра
      if (BOT_NAMES.some((b) => b.toLowerCase() === nick.toLowerCase()) && nick !== S.user.nickname)
        fail("nickname_taken", "Этот ник уже занят");
      S.user.nickname = nick;
      return me();
    }
    if (method === "GET" && p === "/api/chat/messages") {
      tickChat(q.lang || "ru");
      const after = +q.after_id || 0;
      return { messages: S.chat.messages.filter((m) => m.id > after), online: 90 + (Math.floor(Date.now() / 60000) % 60),
               me: { public_id: S.user.public_id } };
    }
    if (method === "POST" && p === "/api/chat/messages") {
      const text = String(body.text || "").trim();
      if (!text) fail("empty_message", "Пустое сообщение");
      if (text.length > 300) fail("message_too_long", "Сообщение длиннее 300 символов");
      if (Date.now() - S.chat.lastUserAt < 2000) fail("rate_limited", "Слишком часто, подождите секунду");
      S.chat.lastUserAt = Date.now();
      pushMsg({ kind: "user", user: myChatUser(), text });
      return S.chat.messages[S.chat.messages.length - 1];
    }

    // пополнение: на сервере — перевод USDT в сети TON с ID игрока в комментарии
    if (method === "GET" && p === "/api/wallet/deposit") {
      const memo = String(S.user.public_id);
      return { enabled: true, network: "TON", token: "USDT", decimals: 6, address: DEMO_WALLET, memo, jetton_master: USDT_MASTER,
               min: CONFIG.deposit.min, presets: CONFIG.deposit.presets,
               links: { ton: `ton://transfer/${DEMO_WALLET}?jetton=${USDT_MASTER}&text=${memo}`,
                        tonkeeper: `https://app.tonkeeper.com/transfer/${DEMO_WALLET}?jetton=${USDT_MASTER}&text=${memo}` } };
    }
    // только демо: имитация входящего перевода (на сервере его находит сторож в сети TON)
    if (method === "POST" && p === "/demo/deposit") {
      const amount = body.amount;
      if (!Number.isInteger(amount) || amount <= 0) fail("bad_amount", "Неверная сумма");
      if (String(body.comment) !== String(S.user.public_id)) fail("bad_params", "Комментарий не совпадает с ID");
      apply("deposit", amount, "ton", randHex(8));
      S.user.total_deposited += amount;
      return { ok: true, balance: S.user.balance };
    }
    if (method === "POST" && p === "/demo/reset") { await reset(); return { ok: true }; }

    if (method === "GET" && p === "/api/wallet/transactions") return S.txs.slice().reverse().slice(0, limit);
    if (method === "GET" && p === "/api/wallet/withdrawals") {
      tickWithdrawals();
      return S.withdrawals.slice().reverse().slice(0, limit);
    }
    if (method === "POST" && p === "/api/wallet/withdraw") {
      const amount = body.amount;
      const w = CONFIG.withdraw;
      if (!Number.isInteger(amount) || amount < w.min || amount > w.max)
        fail("bad_amount", `Сумма вывода: от ${usdt(w.min)} до ${usdt(w.max)}`);
      const address = tonAddress(body.address);
      const left = wagerLeft();
      if (left > 0) fail("wager_required", `Для вывода нужно сделать ставок ещё на ${usdt(left)}`);
      if (S.withdrawals.some((x) => x.status === "pending" || x.status === "processing"))
        fail("withdrawal_pending", "У вас уже есть заявка на вывод в обработке");
      const wd = { id: ++S.seq.wd, amount, fee: w.fee, paid_amount: 0, status: "pending", method: "ton", address,
                   tx_hash: null, created_at: now(), processed_at: null };
      apply("withdrawal", -amount, "withdrawal", wd.id);
      S.withdrawals.push(wd);
      return wd;
    }

    // mines
    if (method === "GET" && p === "/api/games/mines/active") {
      const b = activeMines();
      return { game: b ? minesView(b) : null };
    }
    if (method === "POST" && p === "/api/games/mines/start") {
      checkAmount(body.amount);
      const mines = num(body.params?.mines, "mines");
      if (!Number.isInteger(mines) || mines < 1 || mines > 24) fail("bad_params", "Неверный параметр mines: от 1 до 24");
      if (activeMines()) fail("active_game", "У вас уже есть активная игра Mines");
      const { seed, nonce, rng } = await takeBet(body.amount);
      const state = { mines: rng.shuffle([...Array(25).keys()]).slice(0, mines).sort((a, b) => a - b), revealed: [] };
      const bet = newBet("mines", body.amount, { mines }, seed, nonce, { status: "active", state });
      return playOut(bet, minesView(bet));
    }
    if (method === "POST" && p === "/api/games/mines/reveal") {
      const bet = activeMines() || fail("no_active_game", "Нет активной игры");
      const tile = num(body.tile, "tile");
      if (!Number.isInteger(tile) || tile < 0 || tile > 24) fail("bad_params", "Неверный параметр tile");
      const st = bet.state;
      if (st.revealed.includes(tile)) fail("already_revealed", "Клетка уже открыта");
      st.revealed.push(tile);
      const m = bet.params.mines;
      if (st.mines.includes(tile)) settle(bet, 0);
      else {
        const mult = minesMultiplier(m, st.revealed.length);
        if (st.revealed.length >= 25 - m || payoutFor(bet.amount, mult) >= LIMITS.max_payout) settle(bet, mult, true);
      }
      if (bet.status !== "active") bet.result = minesView(bet);
      return playOut(bet, minesView(bet));
    }
    if (method === "POST" && p === "/api/games/mines/cashout") {
      const bet = activeMines() || fail("no_active_game", "Нет активной игры");
      if (!bet.state.revealed.length) fail("nothing_revealed", "Откройте хотя бы одну клетку");
      settle(bet, minesMultiplier(bet.params.mines, bet.state.revealed.length), true);
      bet.result = minesView(bet);
      return playOut(bet, minesView(bet));
    }

    // crash
    if (method === "GET" && p === "/api/games/crash/active") {
      settleCrash();
      const b = activeCrash();
      return { game: b ? crashView(b) : null, server_now: clock() };
    }
    if (method === "POST" && p === "/api/games/crash/start") {
      checkAmount(body.amount);
      let auto = body.params?.auto_cashout ?? null;
      if (auto !== null) {
        auto = num(auto, "auto_cashout");
        if (auto < 1.01 || auto > CRASH_MAX) fail("bad_params", "Автовывод: от 1.01 до 1000");
        auto = floorTo(auto, 2);
      }
      settleCrash();
      if (activeCrash()) fail("active_game", "У вас уже идёт раунд Crash");
      const { seed, nonce, rng } = await takeBet(body.amount);
      const point = Math.min(Math.max(1, floorTo(RTP / (1 - rng.float()), 2)), CRASH_MAX);
      const cap = Math.max(1.01, Math.min(CRASH_MAX, floorTo(LIMITS.max_payout / body.amount, 2)));
      const st = { point, started_at: clock(), cap, auto: auto === null || auto > cap ? cap : auto, auto_user: auto };
      const bet = newBet("crash", body.amount, { auto_cashout: auto }, seed, nonce, { status: "active", state: st });
      const r = crashResolve(st, clock()); // точка 1.00× — конец сразу
      if (r) crashFinish(bet, r[0], r[1], null);
      return playOut(bet, crashView(bet));
    }
    if (method === "POST" && p === "/api/games/crash/cashout") {
      const t = clock();
      const bet = activeCrash() || fail("no_active_game", "Нет активного раунда");
      const r = crashResolve(bet.state, t);
      if (r) crashFinish(bet, r[0], r[1], r[0] === "won" ? "auto" : null);
      else crashFinish(bet, "won", crashMultAt(t - bet.state.started_at), "manual");
      return playOut(bet, crashView(bet, t));
    }

    // instant
    const play = p.match(/^\/api\/games\/([a-z]+)\/play$/);
    if (method === "POST" && play) {
      const game = GAMES[play[1]] || fail("not_found", "Игра не найдена");
      checkAmount(body.amount);
      const params = game.parse(body.params || {});
      const maxMult = game.maxMult(params);
      if (maxMult !== null && payoutFor(body.amount, maxMult) > LIMITS.max_payout)
        fail("max_payout", `Возможный выигрыш превышает лимит ${usdt(LIMITS.max_payout)}`);
      const { seed, nonce, rng } = await takeBet(body.amount);
      const outcome = game.play(rng, params);
      const { chance, ...publicParams } = params;
      const bet = newBet(play[1], body.amount, publicParams, seed, nonce, { result: outcome.result });
      settle(bet, outcome.mult, !!game.capPayout);
      bigWin(bet);
      return playOut(bet, outcome.result);
    }

    // history
    const one = p.match(/^\/api\/bets\/(\d+)$/);
    if (method === "GET" && one) {
      settleCrash();
      const b = S.bets.find((x) => x.id === +one[1] && x.status !== "active") || fail("not_found", "Ставка не найдена");
      return betOut(b);
    }
    if (method === "GET" && p === "/api/bets") {
      settleCrash();
      return S.bets.filter((b) => b.status !== "active" && (!q.game || b.game === q.game))
        .slice().reverse().slice(0, limit).map(betOut);
    }

    // fairness
    if (method === "GET" && p === "/api/fair") {
      const { server_seed_hash, client_seed, nonce } = S.seed;
      return { server_seed_hash, client_seed, nonce };
    }
    if (method === "POST" && p === "/api/fair/rotate") {
      settleCrash();
      if (S.bets.some((b) => b.status === "active")) fail("active_game", "Сначала завершите текущую игру");
      const cs = body.client_seed;
      if (cs != null && !/^[A-Za-z0-9_-]{1,64}$/.test(cs))
        fail("bad_client_seed", "Client seed: 1–64 символа, латиница, цифры, _ и -");
      const old = S.seed;
      S.revealed[old.server_seed_hash] = old.server_seed;
      S.seed = await newSeed(cs || old.client_seed);
      return {
        previous_server_seed: old.server_seed, previous_server_seed_hash: old.server_seed_hash,
        previous_client_seed: old.client_seed, previous_nonce: old.nonce,
        current: { server_seed_hash: S.seed.server_seed_hash, client_seed: S.seed.client_seed, nonce: 0 },
      };
    }
    if (method === "POST" && p === "/api/fair/verify") {
      const rng = await fairRng(body.server_seed, body.client_seed, body.nonce);
      const server_seed_hash = await sha256(body.server_seed);
      if (body.game === "crash") return { server_seed_hash, crash_point: Math.min(Math.max(1, floorTo(RTP / (1 - rng.float()), 2)), CRASH_MAX) };
      if (body.game === "mines") {
        const mines = rng.shuffle([...Array(25).keys()]).slice(0, body.params.mines).sort((a, b) => a - b);
        return { server_seed_hash, mines };
      }
      const game = GAMES[body.game] || fail("not_found", "Игра не найдена");
      const o = game.play(rng, game.parse(body.params || {}));
      return { server_seed_hash, multiplier: o.mult, ...o.result };
    }
    fail("not_found", `Нет такого метода: ${method} ${p}`);
  }

  window.DemoApi = {
    async request(path, body) {
      await load();
      const method = body === undefined ? "GET" : "POST";
      const snapshot = JSON.stringify(S); // как транзакция в БД: при ошибке откатываем всё
      try {
        const res = await route(method, path, body === undefined ? undefined : JSON.parse(JSON.stringify(body)));
        save();
        return JSON.parse(JSON.stringify(res));
      } catch (e) {
        S = JSON.parse(snapshot);
        throw e;
      }
    },
  };
})();
