// Демо-бэкенд в браузере: те же ответы, что у настоящего API, но всё считается локально.
// Подключается только для теста интерфейса без сервера и Telegram. В проде этот файл не нужен —
// удалите <script src="demo-api.js"> из index.html.
// Provably fair тот же: HMAC_SHA256(server_seed, "client_seed:nonce:cursor") → floats.
(function () {
  "use strict";
  const PLINKO = {"low":{"8":[4.98,2.68,1.43,0.77,0.41,0.77,1.43,2.68,4.98],"9":[5.58,3.12,1.75,0.98,0.55,0.55,0.98,1.75,3.12,5.58],"10":[6.38,3.71,2.15,1.25,0.73,0.42,0.73,1.25,2.15,3.71,6.38],"11":[7.03,4.22,2.53,1.52,0.91,0.54,0.54,0.91,1.52,2.53,4.22,7.03],"12":[7.84,4.84,2.99,1.84,1.14,0.7,0.43,0.7,1.14,1.84,2.99,4.84,7.84],"13":[8.52,5.39,3.41,2.16,1.36,0.86,0.54,0.54,0.86,1.36,2.16,3.41,5.39,8.52],"14":[9.37,6.07,3.93,2.54,1.64,1.06,0.68,0.44,0.68,1.06,1.64,2.54,3.93,6.07,9.37],"15":[10.05,6.63,4.38,2.89,1.9,1.26,0.83,0.54,0.54,0.83,1.26,1.9,2.89,4.38,6.63,10.05],"16":[10.95,7.36,4.94,3.32,2.23,1.5,1.0,0.67,0.45,0.67,1.0,1.5,2.23,3.32,4.94,7.36,10.95]},"medium":{"8":[12.07,4.05,1.43,0.55,0.25,0.55,1.43,4.05,12.07],"9":[14.33,5.26,2.01,0.82,0.36,0.36,0.82,2.01,5.26,14.33],"10":[17.01,6.73,2.75,1.18,0.53,0.28,0.53,1.18,2.75,6.73,17.01],"11":[19.5,8.22,3.56,1.6,0.75,0.38,0.38,0.75,1.6,3.56,8.22,19.5],"12":[22.35,9.95,4.54,2.13,1.03,0.53,0.31,0.53,1.03,2.13,4.54,9.95,22.35],"13":[25.06,11.7,5.57,2.72,1.37,0.71,0.4,0.4,0.71,1.37,2.72,5.57,11.7,25.06],"14":[28.24,13.75,6.81,3.44,1.79,0.95,0.53,0.33,0.53,0.95,1.79,3.44,6.81,13.75,28.24],"15":[30.97,15.64,8.03,4.19,2.23,1.22,0.69,0.42,0.42,0.69,1.22,2.23,4.19,8.03,15.64,30.97],"16":[34.19,17.85,9.45,5.08,2.78,1.56,0.89,0.54,0.35,0.54,0.89,1.56,2.78,5.08,9.45,17.85,34.19]},"high":{"8":[32.89,5.43,1.06,0.26,0.1,0.26,1.06,5.43,32.89],"9":[43.63,8.45,1.87,0.49,0.16,0.16,0.49,1.87,8.45,43.63],"10":[55.84,12.35,3.04,0.86,0.29,0.13,0.29,0.86,3.04,12.35,55.84],"11":[69.36,17.14,4.64,1.39,0.48,0.2,0.2,0.48,1.39,4.64,17.14,69.36],"12":[84.2,22.88,6.71,2.15,0.77,0.31,0.17,0.31,0.77,2.15,6.71,22.88,84.2],"13":[99.98,29.49,9.28,3.15,1.16,0.48,0.24,0.24,0.48,1.16,3.15,9.28,29.49,99.98],"14":[117.7,37.3,12.5,4.46,1.72,0.72,0.34,0.21,0.34,0.72,1.72,4.46,12.5,37.3,117.7],"15":[135.21,45.65,16.18,6.06,2.42,1.04,0.49,0.27,0.27,0.49,1.04,2.42,6.06,16.18,45.65,135.21],"16":[154.32,55.11,20.55,8.04,3.32,1.46,0.69,0.37,0.24,0.37,0.69,1.46,3.32,8.04,20.55,55.11,154.32]}};

  const EDGE = 0.03;
  const RTP = 1 - EDGE;
  const LIMITS = { min_bet: 10, max_bet: 10000, max_payout: 500000 };
  const STORE_KEY = "cthulhu-demo-v1";
  const START_BALANCE = 1000;

  const CONFIG = {
    house_edge: EDGE, ...LIMITS,
    games: [
      { name: "dice", title: "Dice" },
      { name: "coinflip", title: "Монетка" },
      { name: "limbo", title: "Limbo" },
      { name: "plinko", title: "Plinko", tables: PLINKO },
      { name: "mines", title: "Mines", tiles: 25 },
    ],
    bot_username: "cthulhu_demo_bot",
    deposit: { min: 50, max: 10000, presets: [50, 100, 250, 500, 1000, 2500] },
    withdraw: { min: 100, max: 100000, method: "manual", wager_ratio: 1 },
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
      user: { id: 777000, username: "demo", first_name: "Демо", balance: 0, total_deposited: 0, total_withdrawn: 0,
              total_wagered: 0, total_won: 0 },
      seed: await newSeed(), revealed: {}, txs: [], bets: [], withdrawals: [], invoices: {},
      seq: { tx: 0, bet: 0, wd: 0 },
    };
    apply("bonus", START_BALANCE, "demo", 0);
    if (persist) save();
  }

  const now = () => new Date().toISOString();

  function apply(kind, amount, ref_type, ref_id) {
    const u = S.user;
    if (u.balance + amount < 0) fail("insufficient_funds", "Недостаточно звёзд на балансе");
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
      fail("bad_amount", `Ставка должна быть от ${LIMITS.min_bet} до ${LIMITS.max_bet} ⭐`);
  }

  async function takeBet(amount) {
    if (S.user.balance < amount) fail("insufficient_funds", "Недостаточно звёзд на балансе");
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
    return Math.max(0, Math.floor(S.user.total_deposited * CONFIG.withdraw.wager_ratio) - S.user.total_wagered);
  }

  function me() {
    return { ...S.user, wager_left: wagerLeft(), referrals: 0,
             referral_link: `https://t.me/${CONFIG.bot_username}?startapp=ref_${S.user.id}` };
  }

  // имитация админа: заявка «одобряется» через 5 секунд
  function tickWithdrawals() {
    for (const w of S.withdrawals) {
      if (w.status === "pending" && Date.now() - Date.parse(w.created_at) > 5000) {
        Object.assign(w, { status: "completed", paid_amount: w.amount, processed_at: now() });
        S.user.total_withdrawn += w.amount;
      }
    }
  }

  // ------------------------------------------------------------ routes
  async function route(method, path, body) {
    const [p, qs] = path.split("?");
    const q = Object.fromEntries(new URLSearchParams(qs || ""));
    const limit = Math.min(+q.limit || 30, 100);

    if (method === "GET" && p === "/api/config") return CONFIG;
    if (method === "GET" && p === "/api/me") { tickWithdrawals(); return me(); }

    if (method === "POST" && p === "/api/wallet/invoice") {
      const amount = body.amount;
      if (!Number.isInteger(amount) || amount < CONFIG.deposit.min || amount > CONFIG.deposit.max)
        fail("bad_amount", `Сумма пополнения: от ${CONFIG.deposit.min} до ${CONFIG.deposit.max} ⭐`);
      const id = randHex(16);
      S.invoices[id] = { amount, status: "pending" };
      return { invoice_id: id, invoice_link: `demo-invoice:${id}` };
    }
    // только демо: имитация успешной оплаты (в реальности это successful_payment в боте)
    if (method === "POST" && p === "/demo/pay") {
      const inv = S.invoices[body.invoice_id] || fail("not_found", "Счёт не найден");
      if (inv.status !== "pending") fail("bad_status", "Этот счёт уже оплачен");
      inv.status = "paid";
      apply("deposit", inv.amount, "payment", body.invoice_id.slice(0, 8));
      S.user.total_deposited += inv.amount;
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
        fail("bad_amount", `Сумма вывода: от ${w.min} до ${w.max} ⭐`);
      const left = wagerLeft();
      if (left > 0) fail("wager_required", `Для вывода нужно сделать ставок ещё на ${left} ⭐`);
      if (S.withdrawals.some((x) => x.status === "pending" || x.status === "processing"))
        fail("withdrawal_pending", "У вас уже есть заявка на вывод в обработке");
      const wd = { id: ++S.seq.wd, amount, paid_amount: 0, status: "pending", method: w.method, created_at: now(),
                   processed_at: null };
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

    // instant
    const play = p.match(/^\/api\/games\/([a-z]+)\/play$/);
    if (method === "POST" && play) {
      const game = GAMES[play[1]] || fail("not_found", "Игра не найдена");
      checkAmount(body.amount);
      const params = game.parse(body.params || {});
      if (payoutFor(body.amount, game.maxMult(params)) > LIMITS.max_payout)
        fail("max_payout", `Возможный выигрыш превышает лимит ${LIMITS.max_payout} ⭐`);
      const { seed, nonce, rng } = await takeBet(body.amount);
      const outcome = game.play(rng, params);
      const { chance, ...publicParams } = params;
      const bet = newBet(play[1], body.amount, publicParams, seed, nonce, { result: outcome.result });
      settle(bet, outcome.mult);
      return playOut(bet, outcome.result);
    }

    // history
    if (method === "GET" && p === "/api/bets") {
      return S.bets.filter((b) => b.status !== "active" && (!q.game || b.game === q.game))
        .slice().reverse().slice(0, limit).map(betOut);
    }

    // fairness
    if (method === "GET" && p === "/api/fair") {
      const { server_seed_hash, client_seed, nonce } = S.seed;
      return { server_seed_hash, client_seed, nonce };
    }
    if (method === "POST" && p === "/api/fair/rotate") {
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
