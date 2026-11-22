// Минимальный фронт мини-приложения: только чтобы проверить весь бэкенд руками.
// Замените на свой React/Vue/что угодно — API описан в README.
const tg = window.Telegram?.WebApp;
tg?.ready();
tg?.expand();

const $ = (id) => document.getElementById(id);
const state = { config: null, me: null, game: "dice" };

// ---------------------------------------------------------------- API
async function api(path, body) {
  const res = await fetch(path, {
    method: body === undefined ? "GET" : "POST",
    headers: { "Content-Type": "application/json", Authorization: "tma " + (tg?.initData || "") },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data?.error?.message || `HTTP ${res.status}`);
  return data;
}

function toast(text) {
  const t = $("toast");
  t.textContent = text;
  t.style.display = "block";
  clearTimeout(toast._t);
  toast._t = setTimeout(() => (t.style.display = "none"), 2500);
}

async function guard(fn) {
  try { return await fn(); } catch (e) { toast("⚠️ " + e.message); tg?.HapticFeedback?.notificationOccurred("error"); }
}

function setBalance(b) { $("balance").textContent = b; if (state.me) state.me.balance = b; }

function showResult(bet) {
  const win = bet.payout > 0;
  $("result").className = "result " + (win ? "win" : "lose");
  $("result").textContent = win ? `+${bet.payout} ⭐ (x${bet.multiplier})` : `−${bet.amount} ⭐`;
  tg?.HapticFeedback?.notificationOccurred(win ? "success" : "warning");
}

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
}

// ---------------------------------------------------------------- instant games
const params = {
  dice: () => ({ target: +$("dice-target").value, direction: $("dice-dir").value }),
  coinflip: () => ({ side: $("coin-side").value }),
  limbo: () => ({ target: +$("limbo-target").value }),
  plinko: () => ({ rows: +$("plinko-rows").value, risk: $("plinko-risk").value }),
};

const describe = {
  dice: (r) => `Выпало ${r.roll.toFixed(2)}`,
  coinflip: (r) => (r.side === "heads" ? "Орёл" : "Решка"),
  limbo: (r) => `Выпало x${r.point}`,
  plinko: (r) => `Лунка ${r.bucket}: x${r.multiplier}`,
};

document.querySelectorAll("[data-play]").forEach((btn) =>
  btn.addEventListener("click", () => guard(async () => {
    const g = btn.dataset.play;
    btn.disabled = true;
    try {
      const res = await api(`/api/games/${g}/play`, { amount: +$("bet").value, params: params[g]() });
      setBalance(res.balance);
      showResult(res.bet);
      $("result").textContent = describe[g](res.result) + " · " + $("result").textContent;
    } finally { btn.disabled = false; }
  }))
);

function renderPlinkoTable() {
  const t = state.config?.games.find((g) => g.name === "plinko")?.tables;
  const row = t?.[$("plinko-risk").value]?.[$("plinko-rows").value];
  $("plinko-table").textContent = row ? row.map((x) => "x" + x).join("  ") : "";
}
$("plinko-rows").addEventListener("input", renderPlinkoTable);
$("plinko-risk").addEventListener("change", renderPlinkoTable);

// ---------------------------------------------------------------- mines
function renderMines(game) {
  const grid = $("mines-grid");
  grid.innerHTML = "";
  const revealed = new Set(game?.revealed || []);
  const mines = new Set(game?.mines || []);
  for (let i = 0; i < 25; i++) {
    const b = document.createElement("button");
    if (revealed.has(i)) { b.textContent = "💎"; b.className = "safe"; }
    else if (mines.has(i)) { b.textContent = "💣"; b.className = "mine"; }
    b.disabled = !game || game.status !== "active" || revealed.has(i);
    b.onclick = () => guard(async () => {
      const res = await api("/api/games/mines/reveal", { tile: i });
      setBalance(res.balance);
      renderMines(res.result);
      if (res.result.status !== "active") showResult(res.bet);
      else $("result").textContent = `x${res.result.multiplier} → следующая x${res.result.next_multiplier}`;
    });
    grid.appendChild(b);
  }
  $("mines-cashout").disabled = !game || game.status !== "active" || !(game.revealed || []).length;
  $("mines-start").disabled = game?.status === "active";
}

async function loadMines() {
  await guard(async () => renderMines((await api("/api/games/mines/active")).game));
}

$("mines-start").onclick = () => guard(async () => {
  const res = await api("/api/games/mines/start", { amount: +$("bet").value, params: { mines: +$("mines-count").value } });
  setBalance(res.balance);
  $("result").textContent = "";
  renderMines(res.result);
});

$("mines-cashout").onclick = () => guard(async () => {
  const res = await api("/api/games/mines/cashout", {});
  setBalance(res.balance);
  renderMines(res.result);
  showResult(res.bet);
});

// ---------------------------------------------------------------- wallet
async function loadWallet() {
  await guard(async () => {
    const me = (state.me = await api("/api/me"));
    setBalance(me.balance);
    $("ref-link").value = me.referral_link;
    $("ref-info").textContent = `Приглашено: ${me.referrals}` +
      (state.config.referral_deposit_percent ? ` · вы получаете ${state.config.referral_deposit_percent}% от их пополнений` : "");
    const w = state.config.withdraw;
    $("wager-info").textContent = `От ${w.min} до ${w.max} ⭐.` + (me.wager_left ? ` Осталось отыграть: ${me.wager_left} ⭐` : "");
    const txs = await api("/api/wallet/transactions");
    $("tx-list").innerHTML = txs.map((t) =>
      `<li><span>${t.kind} <span class="muted small">${new Date(t.created_at).toLocaleString()}</span></span>` +
      `<b class="${t.amount > 0 ? "win" : "lose"}">${t.amount > 0 ? "+" : ""}${t.amount}</b></li>`).join("");
  });
}

function renderDepositPresets() {
  $("deposit-presets").innerHTML = "";
  for (const amount of state.config.deposit.presets) {
    const b = document.createElement("button");
    b.textContent = `${amount} ⭐`;
    b.onclick = () => guard(async () => {
      const { invoice_link } = await api("/api/wallet/invoice", { amount });
      if (!tg?.openInvoice) return window.open(invoice_link);
      tg.openInvoice(invoice_link, (status) => {
        if (status === "paid") { toast("Оплачено! Зачисляем…"); setTimeout(refreshMe, 1500); }
        else if (status === "failed") toast("Оплата не прошла");
      });
    });
    $("deposit-presets").appendChild(b);
  }
}

$("withdraw-btn").onclick = () => guard(async () => {
  const w = await api("/api/wallet/withdraw", { amount: +$("withdraw-amount").value });
  toast(`Заявка #${w.id} создана`);
  loadWallet();
});

$("ref-copy").onclick = () => { navigator.clipboard?.writeText($("ref-link").value); toast("Скопировано"); };

// ---------------------------------------------------------------- history & fairness
async function loadHistory() {
  await guard(async () => {
    const bets = await api("/api/bets");
    $("bet-list").innerHTML = bets.map((b) =>
      `<li><span>#${b.id} ${b.game} <span class="muted small">nonce ${b.nonce}</span></span>` +
      `<b class="${b.payout > 0 ? "win" : "lose"}">${b.payout > 0 ? "+" + b.payout : "−" + b.amount}</b></li>`).join("");
  });
}

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
    `client seed: ${r.previous_client_seed}, ставок: ${r.previous_nonce}`;
  loadFair();
});

async function refreshMe() {
  await guard(async () => { state.me = await api("/api/me"); setBalance(state.me.balance); });
}

// ---------------------------------------------------------------- init
(async function init() {
  if (!tg?.initData) {
    $("result").textContent = "Откройте приложение из Telegram";
    return;
  }
  await guard(async () => {
    state.config = await api("/api/config");
    $("bet").min = state.config.min_bet;
    $("bet").max = state.config.max_bet;
    $("bet").value = state.config.min_bet;
    $("game-list").innerHTML = "";
    for (const g of state.config.games) {
      const b = document.createElement("button");
      b.textContent = g.title;
      b.dataset.g = g.name;
      b.onclick = () => selectGame(g.name);
      $("game-list").appendChild(b);
    }
    renderDepositPresets();
    await refreshMe();
    selectGame("dice");
  });
})();
