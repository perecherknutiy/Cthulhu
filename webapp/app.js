// Минимальный фронт мини-приложения. Замените на свой React/Vue/что угодно — API описан в README.
// Внутри Telegram ходит в настоящий API. Открыт в обычном браузере (нет initData) и подключён
// demo-api.js — работает в демо-режиме: всё считается в браузере.
const tg = window.Telegram?.WebApp;
tg?.ready();
tg?.expand();

const DEMO = !tg?.initData && !!window.DemoApi;
const $ = (id) => document.getElementById(id);
const state = { config: null, me: null, game: "dice" };

const GAME_TITLES = { dice: "Dice", coinflip: "Монетка", limbo: "Limbo", plinko: "Plinko", mines: "Mines" };
const TX_TITLES = {
  deposit: "Пополнение", bet: "Ставка", win: "Выигрыш", withdrawal: "Вывод", withdrawal_refund: "Возврат вывода",
  payment_refund: "Возврат платежа", referral: "Реферальный бонус", admin: "Корректировка", bonus: "Бонус",
};
const WD_STATUS = { pending: "⏳ ждёт", processing: "⏳ выплачивается", completed: "✅ выплачено",
                    rejected: "❌ отклонено", failed: "⚠️ ошибка" };

// ---------------------------------------------------------------- API
async function api(path, body) {
  if (DEMO) return window.DemoApi.request(path, body);
  const res = await fetch(path, {
    method: body === undefined ? "GET" : "POST",
    headers: { "Content-Type": "application/json", Authorization: "tma " + (tg?.initData || "") },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data?.error?.message || `HTTP ${res.status}`);
  return data;
}

// ---------------------------------------------------------------- ui helpers
function toast(text) {
  const t = $("toast");
  t.textContent = text;
  t.style.display = "block";
  clearTimeout(toast._t);
  toast._t = setTimeout(() => (t.style.display = "none"), 2500);
}

async function guard(fn) {
  try { return await fn(); } catch (e) {
    toast("⚠️ " + e.message);
    tg?.HapticFeedback?.notificationOccurred("error");
  }
}

const esc = (s) => String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
const fmtTime = (iso) => new Date(iso).toLocaleString("ru-RU", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" });

function setBalance(b) { $("balance").textContent = b; if (state.me) state.me.balance = b; }

function modal(html, actions) {
  $("modal-body").innerHTML = html;
  const box = $("modal-actions");
  box.innerHTML = "";
  for (const [label, fn, primary] of actions) {
    const b = document.createElement("button");
    b.textContent = label;
    if (primary) b.className = "primary";
    b.onclick = async () => { closeModal(); await fn?.(); };
    box.appendChild(b);
  }
  $("modal").hidden = false;
}
function closeModal() { $("modal").hidden = true; }
$("modal").addEventListener("click", (e) => { if (e.target.id === "modal") closeModal(); });

function showResult(bet, detail) {
  const win = bet.payout > 0;
  $("result").className = "result " + (win ? "win" : "lose");
  $("result").innerHTML = (win ? `+${bet.payout} ⭐ <small>(x${bet.multiplier})</small>` : `−${bet.amount} ⭐`) +
    (detail ? `<span class="sub">${esc(detail)}</span>` : "");
  tg?.HapticFeedback?.notificationOccurred(win ? "success" : "warning");
}

const edge = () => state.config?.house_edge ?? 0.03;
const floor4 = (x) => Math.floor(x * 10000 + 1e-9) / 10000;

// ---------------------------------------------------------------- tabs
document.querySelectorAll("#tabs button").forEach((b) =>
  b.addEventListener("click", () => {
    document.querySelectorAll("#tabs button").forEach((x) => x.classList.toggle("active", x === b));
    document.querySelectorAll(".tab").forEach((t) => t.classList.toggle("active", t.id === "tab-" + b.dataset.tab));
    ({ wallet: loadWallet, history: loadHistory, fair: loadFair })[b.dataset.tab]?.();
  })
);

function selectGame(name) {
  state.game = name;
  document.querySelectorAll("#game-list button").forEach((b) => b.classList.toggle("active", b.dataset.g === name));
  document.querySelectorAll(".game").forEach((g) => g.classList.toggle("active", g.dataset.game === name));
  $("result").textContent = "";
  if (name === "mines") loadMines();
  if (name === "plinko") renderPlinkoTable();
  updateHints();
}

// ---------------------------------------------------------------- bet amount
document.querySelectorAll("[data-bet]").forEach((b) => b.addEventListener("click", () => {
  const c = state.config;
  const cur = +$("bet").value || c.min_bet;
  const v = { min: c.min_bet, max: Math.min(c.max_bet, state.me?.balance ?? c.max_bet),
              half: Math.floor(cur / 2), double: cur * 2 }[b.dataset.bet];
  $("bet").value = Math.max(c.min_bet, Math.min(c.max_bet, v));
  updateHints();
}));

// ---------------------------------------------------------------- hints (шанс и множитель до ставки)
function updateHints() {
  const bet = +$("bet").value || 0;
  const rtp = 1 - edge();
  const t = +$("dice-target").value;
  const chance = $("dice-dir").value === "under" ? t / 100 : (100 - t) / 100;
  const dm = floor4(rtp / chance);
  $("dice-hint").textContent = chance > 0 && chance < 1
    ? `Шанс ${(chance * 100).toFixed(2)}% · множитель x${dm} · выигрыш ${Math.floor(bet * dm)} ⭐`
    : "Число от 1 до 99";
  $("coin-hint").textContent = `Шанс 50% · множитель x${floor4(rtp * 2)} · выигрыш ${Math.floor(bet * floor4(rtp * 2))} ⭐`;
  const lt = +$("limbo-target").value;
  $("limbo-hint").textContent = lt >= 1.01
    ? `Шанс ${((rtp / lt) * 100).toFixed(2)}% · выигрыш ${Math.floor(bet * lt)} ⭐`
    : "Множитель от 1.01";
}
["bet", "dice-target", "limbo-target"].forEach((id) => $(id).addEventListener("input", updateHints));
$("dice-dir").addEventListener("change", updateHints);

// ---------------------------------------------------------------- instant games
const params = {
  dice: () => ({ target: +$("dice-target").value, direction: $("dice-dir").value }),
  coinflip: () => ({ side: $("coin-side").value }),
  limbo: () => ({ target: +$("limbo-target").value }),
  plinko: () => ({ rows: +$("plinko-rows").value, risk: $("plinko-risk").value }),
};

const describe = {
  dice: (r) => `Выпало ${r.roll.toFixed(2)} (нужно ${r.direction === "under" ? "<" : "≥"} ${r.target})`,
  coinflip: (r) => `Выпал${r.side === "heads" ? " орёл" : "а решка"}`,
  limbo: (r) => `Выпало x${r.point} (нужно ≥ x${r.target})`,
  plinko: (r) => `Шар упал в лунку x${r.multiplier}`,
};

document.querySelectorAll("[data-play]").forEach((btn) =>
  btn.addEventListener("click", () => guard(async () => {
    const g = btn.dataset.play;
    btn.disabled = true;
    try {
      const res = await api(`/api/games/${g}/play`, { amount: +$("bet").value, params: params[g]() });
      setBalance(res.balance);
      showResult(res.bet, describe[g](res.result));
      if (g === "plinko") renderPlinkoTable(res.result.bucket);
    } finally { btn.disabled = false; }
  }))
);

function renderPlinkoTable(hit) {
  const t = state.config?.games.find((g) => g.name === "plinko")?.tables;
  const row = t?.[$("plinko-risk").value]?.[$("plinko-rows").value] || [];
  $("plinko-table").innerHTML = row.map((x, i) =>
    `<span class="${i === hit ? "hit" : x >= 2 ? "hot" : ""}">${x}</span>`).join("");
}
$("plinko-rows").addEventListener("input", () => renderPlinkoTable());
$("plinko-risk").addEventListener("change", () => renderPlinkoTable());

// ---------------------------------------------------------------- mines
function renderMines(game) {
  const grid = $("mines-grid");
  grid.innerHTML = "";
  const revealed = new Set(game?.revealed || []);
  const mines = new Set(game?.mines || []);
  const lastPick = game?.picked?.[game.picked.length - 1];
  const active = game?.status === "active";
  for (let i = 0; i < 25; i++) {
    const b = document.createElement("button");
    if (revealed.has(i)) { b.textContent = "💎"; b.className = "safe"; }
    else if (mines.has(i)) { b.textContent = "💣"; b.className = i === lastPick ? "boom" : "mine"; }
    b.disabled = !active || revealed.has(i);
    b.onclick = () => guard(async () => {
      const res = await api("/api/games/mines/reveal", { tile: i });
      setBalance(res.balance);
      renderMines(res.result);
      if (res.result.status !== "active") showResult(res.bet, res.result.status === "lost" ? "Мина!" : "Все клетки открыты");
      else {
        $("result").className = "result";
        $("result").innerHTML = `x${res.result.multiplier} = ${Math.floor(res.bet.amount * res.result.multiplier)} ⭐` +
          `<span class="sub">следующая клетка: x${res.result.next_multiplier}</span>`;
      }
    });
    grid.appendChild(b);
  }
  $("mines-cashout").disabled = !active || !(game.revealed || []).length;
  $("mines-cashout").textContent = active && game.revealed.length
    ? `Забрать ${Math.floor(game.amount * game.multiplier)} ⭐` : "Забрать";
  $("mines-start").disabled = active;
  $("mines-count").disabled = active;
}

async function loadMines() {
  await guard(async () => renderMines((await api("/api/games/mines/active")).game));
}

$("mines-start").onclick = () => guard(async () => {
  const res = await api("/api/games/mines/start", { amount: +$("bet").value, params: { mines: +$("mines-count").value } });
  setBalance(res.balance);
  $("result").className = "result";
  $("result").textContent = "Открывайте клетки";
  renderMines(res.result);
});

$("mines-cashout").onclick = () => guard(async () => {
  const res = await api("/api/games/mines/cashout", {});
  setBalance(res.balance);
  renderMines(res.result);
  showResult(res.bet, "Забрали выигрыш");
});

// ---------------------------------------------------------------- wallet
async function loadWallet() {
  await guard(async () => {
    const me = (state.me = await api("/api/me"));
    setBalance(me.balance);
    $("ref-link").value = me.referral_link;
    const pct = state.config.referral_deposit_percent;
    $("ref-info").textContent = `Приглашено: ${me.referrals}` + (pct ? ` · вы получаете ${pct}% от их пополнений` : "");
    const w = state.config.withdraw;
    $("wager-info").textContent = `От ${w.min} до ${w.max} ⭐.` +
      (me.wager_left ? ` Перед выводом нужно сделать ставок ещё на ${me.wager_left} ⭐.` : "") +
      (DEMO ? " В демо заявка «одобряется» через 5 секунд." : "");

    const wds = await api("/api/wallet/withdrawals");
    $("wd-list").innerHTML = wds.map((x) =>
      `<li><span>Заявка #${x.id} · ${x.amount} ⭐ <span class="muted small">${fmtTime(x.created_at)}</span></span>` +
      `<span>${WD_STATUS[x.status] || x.status}</span></li>`).join("");

    const txs = await api("/api/wallet/transactions");
    $("tx-list").innerHTML = txs.length ? txs.map((t) =>
      `<li><span>${TX_TITLES[t.kind] || t.kind} <span class="muted small">${fmtTime(t.created_at)}</span></span>` +
      `<b class="${t.amount > 0 ? "win" : "lose"}">${t.amount > 0 ? "+" : ""}${t.amount}</b></li>`).join("")
      : `<li class="empty">Пока пусто</li>`;
  });
}

function renderDepositPresets() {
  $("deposit-presets").innerHTML = "";
  for (const amount of state.config.deposit.presets) {
    const b = document.createElement("button");
    b.textContent = `${amount} ⭐`;
    b.onclick = () => guard(async () => {
      const { invoice_id, invoice_link } = await api("/api/wallet/invoice", { amount });
      if (DEMO) return demoInvoice(invoice_id, amount);
      if (!tg?.openInvoice) return toast("Оплата работает только внутри Telegram");
      tg.openInvoice(invoice_link, (status) => {
        if (status === "paid") { toast("Оплачено! Зачисляем…"); setTimeout(refreshAll, 1500); }
        else if (status === "failed") toast("Оплата не прошла");
      });
    });
    $("deposit-presets").appendChild(b);
  }
}

// в Telegram здесь открывается нативное окно оплаты звёздами; в демо — его имитация
function demoInvoice(invoiceId, amount) {
  modal(`<div class="hint">Пополнение баланса (имитация окна оплаты Telegram)</div><div class="big">${amount} ⭐</div>`, [
    ["Отмена", () => toast("Оплата отменена")],
    [`Оплатить ${amount} ⭐`, () => guard(async () => {
      await api("/demo/pay", { invoice_id: invoiceId });
      toast(`Зачислено ${amount} ⭐`);
      await refreshAll();
    }), true],
  ]);
}

$("withdraw-btn").onclick = () => guard(async () => {
  const w = await api("/api/wallet/withdraw", { amount: +$("withdraw-amount").value });
  toast(`Заявка #${w.id} создана`);
  $("withdraw-amount").value = "";
  await loadWallet();
  if (DEMO) setTimeout(() => $("tab-wallet").classList.contains("active") && loadWallet(), 5500);
});

$("ref-copy").onclick = async () => {
  try { await navigator.clipboard.writeText($("ref-link").value); toast("Скопировано"); }
  catch { $("ref-link").select(); toast("Выделено — скопируйте вручную"); }
};

// ---------------------------------------------------------------- history
async function loadHistory() {
  await guard(async () => {
    const bets = await api("/api/bets");
    state.bets = Object.fromEntries(bets.map((b) => [b.id, b]));
    $("bet-list").innerHTML = bets.length ? bets.map((b) =>
      `<li data-bet-id="${b.id}"><span>#${b.id} ${GAME_TITLES[b.game] || b.game} · ${b.amount} ⭐ ` +
      `<span class="muted small">${fmtTime(b.created_at)}</span></span>` +
      `<b class="${b.payout > 0 ? "win" : "lose"}">${b.payout > 0 ? "+" + b.payout : "−" + b.amount}</b></li>`).join("")
      : `<li class="empty">Ставок ещё нет</li>`;
  });
}

$("bet-list").addEventListener("click", (e) => {
  const li = e.target.closest("[data-bet-id]");
  if (li) showBet(state.bets[li.dataset.betId]);
});

function showBet(b) {
  const info = `<h3>Ставка #${b.id} · ${GAME_TITLES[b.game] || b.game}</h3>
    <div class="kv"><b>Ставка / выплата</b><code>${b.amount} ⭐ → ${b.payout} ⭐ (x${b.multiplier})</code></div>
    <div class="kv"><b>Параметры</b><code>${esc(JSON.stringify(b.params))}</code></div>
    <div class="kv"><b>Исход</b><code>${esc(JSON.stringify(b.result))}</code></div>
    <div class="kv"><b>Server seed hash</b><code>${b.server_seed_hash}</code></div>
    <div class="kv"><b>Server seed</b><code>${b.server_seed || "ещё не раскрыт — смените пару во вкладке «Честность»"}</code></div>
    <div class="kv"><b>Client seed / nonce</b><code>${esc(b.client_seed)} / ${b.nonce}</code></div>`;
  const actions = [["Закрыть"]];
  if (b.server_seed) actions.push(["Проверить честность", () => verifyBet(b), true]);
  modal(info, actions);
}

async function verifyBet(b) {
  await guard(async () => {
    const v = await api("/api/fair/verify", { game: b.game, server_seed: b.server_seed, client_seed: b.client_seed,
                                               nonce: b.nonce, params: b.params });
    const hashOk = v.server_seed_hash === b.server_seed_hash;
    const outcomeOk = b.game === "mines"
      ? JSON.stringify(v.mines) === JSON.stringify(b.result?.mines)
      : Math.abs(v.multiplier - b.multiplier) < 1e-9;
    modal(`<h3>Проверка ставки #${b.id}</h3>
      <p class="${hashOk ? "ok" : "bad"}">${hashOk ? "✓" : "✗"} sha256(server seed) совпадает с хэшем, показанным до ставки</p>
      <p class="${outcomeOk ? "ok" : "bad"}">${outcomeOk ? "✓" : "✗"} Пересчитанный исход совпадает с результатом ставки</p>
      <pre>${esc(JSON.stringify(v, null, 2))}</pre>`, [["Готово", null, true]]);
  });
}

// ---------------------------------------------------------------- fairness
async function loadFair() {
  await guard(async () => {
    const s = await api("/api/fair");
    $("fair-hash").textContent = s.server_seed_hash;
    $("fair-client").textContent = s.client_seed;
    $("fair-nonce").textContent = s.nonce;
  });
}

$("fair-rotate").onclick = () => guard(async () => {
  const client_seed = $("fair-new-client").value.trim() || null;
  const r = await api("/api/fair/rotate", { client_seed });
  $("fair-revealed").textContent =
    `Раскрыт server seed:\n${r.previous_server_seed}\nhash: ${r.previous_server_seed_hash}\n` +
    `client seed: ${r.previous_client_seed}, ставок: ${r.previous_nonce}\n\nТеперь ставки с этой пары можно проверить в «Истории».`;
  $("fair-new-client").value = "";
  await loadFair();
});

// ---------------------------------------------------------------- init
async function refreshAll() {
  await guard(async () => { state.me = await api("/api/me"); setBalance(state.me.balance); });
  if ($("tab-wallet").classList.contains("active")) await loadWallet();
}

$("demo-reset").onclick = () => guard(async () => {
  await api("/demo/reset", {});
  await refreshAll();
  if (state.game === "mines") loadMines();
  $("result").textContent = "";
  toast("Демо сброшено: снова 1000 ⭐");
});

(async function init() {
  if (!tg?.initData && !DEMO) {
    $("result").textContent = "Откройте приложение из Telegram";
    return;
  }
  $("demo-banner").hidden = !DEMO;
  await guard(async () => {
    state.config = await api("/api/config");
    $("bet").min = state.config.min_bet;
    $("bet").max = state.config.max_bet;
    $("bet").value = state.config.min_bet * 5;
    $("game-list").innerHTML = "";
    for (const g of state.config.games) {
      const b = document.createElement("button");
      b.textContent = g.title;
      b.dataset.g = g.name;
      b.onclick = () => selectGame(g.name);
      $("game-list").appendChild(b);
    }
    renderDepositPresets();
    await refreshAll();
    selectGame("dice");
  });
})();
