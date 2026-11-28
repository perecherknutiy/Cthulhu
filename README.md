# 💎 ARA Casino — казино в Telegram Mini App на USDT

Бот + API мини-приложения + кошелёк в USDT (пополнение и вывод в сети TON через ваш собственный кошелёк) + 8 честных (provably fair) игр + админка + фронт.
Рулетка, Crash, рейтинг, ежедневный бонус и иллюстрации перенесены из прототипа на Node + SQLite на этот бэкенд и фронт.

**Стек:** Python 3.12, FastAPI, aiogram 3.33 (Bot API 10.x), SQLAlchemy 2 (async) + asyncpg, PostgreSQL, Alembic.
Бот и API живут в одном процессе.

---

## Что внутри

| Модуль | Что делает |
|---|---|
| **Авторизация** | Проверка `initData` мини-аппа по HMAC (`app/telegram_auth.py`). Фронт шлёт `Authorization: tma <initData>`. |
| **Кошелёк** | Баланс в USDT: внутри целые микро-USDT (1 USDT = 1 000 000, как у самого токена), леджер транзакций (`transactions`): любая смена баланса = запись. Блокировка строки юзера (`SELECT … FOR UPDATE`) — параллельные ставки не уводят баланс в минус. |
| **Пополнение** | Игрок переводит USDT в сети TON на ваш кошелёк, в комментарии — свой ID из профиля. Сторож (`app/ton/watcher.py`) раз в 10 с читает транзакции кошелька в toncenter.com и зачисляет перевод. Каждый перевод учитывается один раз (по хэшу). Переводы без ID попадают в `/deposits`, админ зачисляет их `/credit`. |
| **Игры** | Crash, Рулетка (европейская), Слоты 3×3 (3 темы, 5 линий), Mines, Dice, Монетка, Limbo, Plinko (8–16 рядов, 3 уровня риска). Преимущество казино настраивается (`HOUSE_EDGE`; в рулетке его задают правила — 1/37), RTP проверен тестами. |
| **Профиль** | Внутренний ID игрока (`public_id`, с 100001) — его видно в профиле, рейтинге и реф-ссылке вместо Telegram ID. Ник 3–20 символов, уникален без учёта регистра. Уровни: Бронза → Серебро → Золото → Сапфир → Бриллиант по сумме ставок. |
| **Рейтинг** | `GET /api/leaderboard?period=week\|all` — топ-20 по сумме ставок и место игрока. |
| **Ежедневный бонус** | `DAILY_BONUS` USDT раз в сутки по UTC (по умолчанию выключен — это настоящие деньги). Бонус входит в отыгрыш перед выводом. |
| **Provably fair** | `HMAC_SHA256(server_seed, "client_seed:nonce:cursor")`, хэш сида заранее, раскрытие при ротации, публичный `/api/fair/verify`. |
| **Вывод** | Игрок указывает сумму и адрес TON → баланс сразу списывается → админу приходит заявка с кнопкой «Открыть перевод в Tonkeeper» (адрес, сумма и комментарий уже подставлены). Отправили — «✅ Отправил», иначе «❌ Отклонить» (деньги вернутся). Требование отыгрыша депозита. |
| **Рефералка** | `t.me/<bot>?startapp=ref_<ID игрока>` или `/start ref_<ID>`, % от пополнений реферала. Старые ссылки с Telegram ID тоже работают. |
| **Админка в боте** | `/stats`, `/user`, `/give #ID 2.5`, `/ban`, `/unban`, `/withdrawals`, `/paid`, `/deposits`, `/credit`. Игрока можно указать Telegram ID или `#ID` из профиля. |
| **Лимиты** | мин/макс ставка, макс. выигрыш за ставку, лимиты депозита/вывода, rate limit ставок. |

```
app/
  main.py               # FastAPI + запуск бота (polling/webhook)
  config.py             # все настройки из .env
  models.py             # таблицы БД
  telegram_auth.py      # проверка initData
  fairness.py           # provably fair RNG
  money.py              # USDT: целые микро-единицы, перевод из «0.1» и обратно
  ton/                  # сеть TON: адреса, разбор переводов USDT, клиент toncenter, сторож пополнений
  ratelimit.py
  games/                # чистая математика игр, без БД
    base.py  instant.py  mines.py  extra.py (рулетка, слоты)  crash.py
  vip.py                # уровни привилегий
  services/             # бизнес-логика: wallet, deposits, games, withdrawals, seeds, users, stats, leaderboard, bonus
  api/                  # HTTP-роуты мини-аппа
  bot/                  # aiogram: handlers/{user,admin}.py, notify.py
migrations/             # Alembic
webapp/                 # фронт мини-аппа (чистый JS) + assets/ с иллюстрациями; адрес API — в webapp/config.js
.github/workflows/      # публикация webapp/ на GitHub Pages
tests/                  # 130+ тестов на живом PostgreSQL
```

---

## Быстрый старт

### 1. Бот
1. @BotFather → `/newbot` → токен в `BOT_TOKEN`.
2. Кошелёк казино: создайте отдельный кошелёк TON (Tonkeeper) только для казино и впишите его адрес в `TON_WALLET_ADDRESS`. На нём должно быть немного TON (≈1–2) — на газ при выводах. Сид-фразу кошелька **никуда не вписывайте** — серверу она не нужна: он только читает входящие переводы.
   Сделайте тестовый перевод 1 USDT с комментарием-ID и убедитесь, что он зачислился, прежде чем звать игроков.
3. Мини-апп: бот сам ставит кнопку меню «💎 ARA Casino» на `WEBAPP_URL`. Если хотите прямую ссылку `t.me/<bot>/<app>` — `/newapp` в BotFather с тем же URL (тогда реф-ссылки тоже можно делать через неё).

### 2. Docker
```bash
cp .env.example .env      # заполнить BOT_TOKEN, WEBAPP_URL, ADMIN_IDS
docker compose up -d --build
```
Миграции применяются при старте. Приложение слушает `:8000`; поставьте перед ним HTTPS (Caddy/nginx) — Telegram открывает мини-аппы только по HTTPS.

### 3. Локальная разработка
```bash
python -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env      # DATABASE_URL на свой Postgres
alembic upgrade head
uvicorn app.main:create_app --factory --reload --port 8000
```
HTTPS для теста: `cloudflared tunnel --url http://localhost:8000` → полученный `https://…trycloudflare.com` в `WEBAPP_URL`, перезапустить.

Дёрнуть API без Telegram:
```bash
curl -H "Authorization: tma $(python scripts/make_initdata.py 123456789)" localhost:8000/api/me
```
С `DEBUG=true` доступен Swagger на `/docs`.

### Фронтенд без бэкенда (демо-режим)
Откройте `webapp/index.html` в браузере через любой локальный сервер (`python -m http.server` в папке `webapp`,
затем `http://localhost:8000`). Без Telegram фронт включает демо-режим: `webapp/demo-api.js` отвечает
вместо сервера в том же формате, что и настоящий API, и считает игры по тому же provably-fair алгоритму
(на одинаковых сидах исходы совпадают с бэкендом — сверено на 400 ставках рулетки, слотов и Crash). Баланс хранится в браузере,
«Настройки → Сбросить демо» — 100 USDT. Пополнение в демо — кнопкой «Демо: сымитировать перевод». В демо включён ежедневный бонус 0.50 USDT, соперники в рейтинге и чате — боты.

Внутри Telegram (есть `initData`) фронт ходит в настоящий API — кроме случая `demo: true` в `webapp/config.js`
(удобно посмотреть приложение в Telegram, пока сервера нет). Если демо в проде не нужно —
удалите строку `<script src="demo-api.js"></script>` из `webapp/index.html`.

### Фронт на GitHub Pages
GitHub Pages отдаёт только статические файлы: игры с настоящими деньгами требуют работающий сервер (бот + API + PostgreSQL)
на VPS или в облаке. Pages подходит, чтобы раздавать `webapp/`, а сервер держать отдельно.
1. Репозиторий **публичный** (на бесплатном плане Pages для приватных не работает) — иначе шаг `configure-pages`
   падает с «Get Pages site failed … Not Found».
2. Settings → Pages → Build and deployment → Source: **GitHub Actions**.
3. Workflow `.github/workflows/pages.yml` уже в проекте: публикует папку `webapp/` при пуше в `main`.
4. В `webapp/config.js` впишите `apiBase` — адрес сервера; на сервере — `CORS_ORIGINS=https://ИМЯ.github.io`
   и `WEBAPP_URL=https://ИМЯ.github.io/РЕПОЗИТОРИЙ/`. Пока сервера нет — поставьте `demo: true`.

Файлы фронта:
- `index.html` — каркас: хедер, экран, футер; шрифты Golos Text и Prata с Google Fonts.
- `style.css` — две темы (День / Ночь): сапфировая основа (`#3a74ff`, глубокий `#1c3b8f`, фон `#0a1226`), золото `#e8c879` — только для денег (значок USDT), выигрышей и наград.
- `app.js` — роутер и все экраны: Играть (карусели новостей, слотов, мини-игр), Чат, Меню (Профиль, Настройки, Помощь), кошелёк, игры, рейтинг.
- `assets/` — иллюстрации (WebP, ужаты до нужного размера, ~0,8 МБ): обложки игр, символы слотов, колесо рулетки, ракета, медали уровней.
- `i18n.js` — строки интерфейса RU/EN. `content.js` — соглашение, политика, ответственная игра, FAQ, правила чата, новости.
- `demo-api.js` — демо-бэкенд в браузере.

Юридические тексты в `content.js` — шаблон: перед запуском их должен проверить юрист и вписать юрлицо оператора.

#### Что фронт ждёт от бэкенда, но пока есть только в демо
| Метод | Что нужно |
|---|---|
| `GET /api/chat/messages?after_id&lang` | `{messages:[{id, kind:"user"\|"win", user:{public_id,nickname,vip_level,photo_url}, text, game, amount, created_at}], online, me:{public_id}}` |
| `POST /api/chat/messages` `{text}` | до 300 символов, не чаще раза в 2 с, мут/бан модератором |

Всё остальное (ник, внутренний ID, уровни, слоты, рулетка, Crash, рейтинг, бонус) уже есть в API.

### Polling или webhook
- `BOT_MODE=polling` — проще всего, для разработки и одного сервера.
- `BOT_MODE=webhook` + `WEBHOOK_URL=https://domain/tg/webhook` + `WEBHOOK_SECRET` — для продакшна.
- `BOT_MODE=none` — только API (тесты, отдельный воркер).

> Запускайте **один процесс** uvicorn: polling-бот и in-memory rate limiter рассчитаны на один инстанс. Для горизонтального масштабирования: webhook + Redis для лимитера.

---

## Деньги

**Валюта — USDT, внутри всё в целых микро-USDT** (1 USDT = 1 000 000 — ровно как у токена USDT в сети TON, так что сумма перевода зачисляется без пересчёта). В `.env` суммы пишутся обычно: `MIN_BET=0.1`. Выплата = `floor(ставка × множитель)` в микро-единицах — округление не больше 0.000001 USDT. API отдаёт суммы тоже в микро-USDT, фронт делит на 1 000 000.

**Инвариант:** `sum(transactions.amount) == users.balance` для каждого юзера (проверяется в тестах). Меняйте баланс только через `services/wallet.apply()` после `lock_user()`.

Типы транзакций: `deposit`, `bet`, `win`, `withdrawal`, `withdrawal_refund`, `referral`, `admin`, `bonus`.

### Пополнение — как устроена защита
- Зачисляются только уведомления `transfer_notification`, пришедшие на кошелёк казино **от его настоящего USDT-кошелька**.
  Адрес этого jetton-кошелька сервер спрашивает у самого контракта USDT (`get_wallet_address`), поэтому подделка
  «USDT» с другим контрактом не пройдёт. Можно задать его и вручную: `TON_USDT_JETTON_WALLET` (виден в tonviewer).
- Перевод учитывается один раз: уникальный хэш транзакции в `ton_deposits`. Позиция чтения хранится в `kv`.
- При первом запуске старая история кошелька не зачисляется — только новые переводы.
- Сторож запускайте в одном процессе (`DEPOSIT_WATCHER=true` только у одного экземпляра).
- Перевод без ID / с несуществующим ID: статус `unmatched`, админу приходит уведомление, `/credit <номер> #ID` зачисляет.

### Вывод — важно знать
Автоматических выплат нет намеренно: для них серверу нужна сид-фраза горячего кошелька, а это главный риск кражи.
Админ отправляет USDT из Tonkeeper по кнопке в заявке (адрес, сумма и комментарий `ARA Casino #N` подставлены)
и жмёт «✅ Отправил» — или `/paid N <хэш>`, чтобы сохранить хэш перевода. Газ сети TON (~0.05 TON за перевод)
платит кошелёк казино; `WITHDRAW_FEE` позволяет удерживать комиссию с игрока.

Защита от «пополнил → сразу вывел»: `WITHDRAW_WAGER_RATIO` (по умолчанию нужно проставить сумму депозитов ×1).

---

## Provably fair

1. У каждого игрока активная пара: `server_seed` (секрет) + `client_seed`, `nonce` растёт с каждой ставкой. `sha256(server_seed)` виден заранее (`GET /api/fair`).
2. Случайные числа: `HMAC_SHA256(key=server_seed, msg=f"{client_seed}:{nonce}:{cursor}")`, каждые 4 байта → float в [0,1).
3. `POST /api/fair/rotate` раскрывает старый `server_seed` и выдаёт новую пару. Во время активной игры Mines или полёта в Crash ротация запрещена (иначе раскрылись бы мины или точка краха).
4. Любой может пересчитать ставку: `POST /api/fair/verify` (без авторизации) или своим скриптом.

**Не меняйте `app/fairness.py`** после запуска — старые ставки перестанут проверяться (тест `test_rng_known_vector` это ловит).

---

## API

Все `/api/*` кроме `/api/fair/verify` требуют `Authorization: tma <initData>`. Ошибки: `{"error": {"code", "message"}}`.

| Метод | Путь | Описание |
|---|---|---|
| GET | `/api/config` | игры, лимиты, таблицы Plinko, `currency: {code: "USDT", decimals: 6, network: "TON"}`, пресеты депозита |
| GET | `/api/config` → `vip_levels`, `daily_bonus` | уровни привилегий и размер бонуса |
| GET | `/api/me` | профиль: `public_id`, `telegram_id`, `nickname` (null — фронт попросит выбрать), `vip`, `referral {link, invited, earned, percent}`, `bonus`, сколько осталось отыграть |
| POST | `/api/me/nickname` `{nickname}` | выбрать/сменить ник: 3–20 символов (буквы, цифры, пробел, `_ . -`), ошибки `nickname_taken`, `nickname_reserved` (похож на администрацию или на название казино) |
| POST | `/api/bonus/claim` | ежедневный бонус (`bonus_disabled`, `bonus_claimed`) |
| GET | `/api/leaderboard?period=week\|all` | `{top:[{rank, public_id, nickname, photo_url, vip_level, wagered, best_win}], me:{rank, wagered}\|null}` |
| GET | `/api/wallet/deposit` | `{enabled, address, memo, jetton_master, min, presets, links: {ton, tonkeeper}}` — куда и с каким комментарием переводить |
| GET | `/api/wallet/transactions?limit&before_id` | леджер |
| POST | `/api/wallet/withdraw` `{amount, address}` | заявка на вывод на адрес TON (`bad_address` — опечатка, тестовая сеть или адрес казино) |
| GET | `/api/wallet/withdrawals` | мои заявки |
| POST | `/api/games/{dice\|coinflip\|limbo\|plinko\|roulette\|slots}/play` `{amount, params}` | мгновенная игра |
| GET | `/api/games/crash/active` | текущий полёт (без точки краха) + `server_now` для синхронизации часов |
| POST | `/api/games/crash/start` `{amount, params:{auto_cashout?}}` | взлёт |
| POST | `/api/games/crash/cashout` | забрать на текущем множителе (время — серверное) |
| GET | `/api/games/mines/active` | текущая игра Mines |
| POST | `/api/games/mines/start` `{amount, params:{mines}}` | начать |
| POST | `/api/games/mines/reveal` `{tile}` | открыть клетку 0–24 |
| POST | `/api/games/mines/cashout` | забрать |
| GET | `/api/bets?limit&before_id&game`, `/api/bets/{id}` | история ставок (с server_seed после ротации) |
| GET | `/api/fair` | хэш сида, client seed, nonce |
| POST | `/api/fair/rotate` `{client_seed?}` | раскрыть и сменить пару |
| POST | `/api/fair/verify` `{game, server_seed, client_seed, nonce, params}` | пересчитать исход |

Параметры игр:
- dice: `{target: 1.00–99.00, direction: "under"|"over"}` — under: `roll < target`, over: `roll >= target`, шанс 1–98%
- coinflip: `{side: "heads"|"tails"}`
- limbo: `{target: 1.01–1000000}`
- plinko: `{rows: 8–16, risk: "low"|"medium"|"high"}`
- mines: `{mines: 1–24}`
- roulette: `{bet: "red"|"black"|"even"|"odd"|"zero"|0–36}` — цвет и чётность ×2, число и зеро ×36
- slots: `{slot: "classic"|"treasury"|"royal"}` — 3×3, 5 линий; темы отличаются только картинками
- crash: `{auto_cashout: 1.01–1000}` (необязательно). Множитель `e^(0.18·t)`; точка краха `floor(RTP/(1−r)·100)/100`, от 1.00 до 1000. Потолок — `MAX_PAYOUT / ставка`: на нём срабатывает автовывод. Расчёт ленивый: закрыл приложение — полёт досчитается при следующем запросе (автовывод сработает, без него ставка сгорит).

---

## Как добавить игру

```python
# app/games/instant.py
class WheelParams(BaseModel):
    segments: Literal[10, 20]

class Wheel(InstantGame):
    name, title, Params = "wheel", "Колесо", WheelParams

    def max_multiplier(self, p): return floor_dec(self.rtp * p.segments)

    def play(self, rng, p):
        hit = rng.int_below(p.segments) == 0
        return Outcome(self.max_multiplier(p) if hit else Decimal(0), {"hit": hit})
```
и добавить `Wheel` в `INSTANT_GAMES` в `app/games/__init__.py`. Баланс, сиды, лимиты, история и `/verify` подхватятся сами. Добавьте тест на RTP в `tests/test_games_math.py`.

Многошаговые игры (как Mines) — по образцу `GameService.mines_*`: ставка списывается на старте, состояние в `bets.state`, частичный уникальный индекс не даёт открыть две активные игры.

---

## Тесты

```bash
createdb casino_test
TEST_DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/casino_test pytest -q
```
Покрыто: подпись initData, детерминизм RNG, RTP каждой игры (аналитически и симуляцией), гонка 30 параллельных ставок, повторная доставка одного перевода, поддельный «USDT», разбор комментариев (в т.ч. длинных и в ссылке), пагинация сторожа, клиент toncenter на локальном сервере, адреса TON (контрольная сумма, тестовая сеть), рефералка, вывод с комиссией, сквозные сценарии API, хендлеры бота через настоящий `Dispatcher`.

---

## Перед запуском в прод

- [ ] HTTPS, `BOT_MODE=webhook`, длинный `WEBHOOK_SECRET`, `DEBUG=false`
- [ ] Бэкапы PostgreSQL
- [ ] Свой текст `/terms` и `/support`
- [ ] Отдельный кошелёк TON для казино, тестовый перевод 1 USDT с комментарием-ID зачислился
- [ ] Ключ toncenter (`TONCENTER_API_KEY`, у @tonapibot) — без него 1 запрос в секунду
- [ ] Подобрать лимиты (`MAX_BET`, `MAX_PAYOUT`) под свой банкролл
- [ ] Азартные игры регулируются законом в большинстве стран, а условия Telegram для разработчиков ограничивают регулируемые товары и услуги — проверьте юридическую сторону и условия Telegram до запуска
- [ ] Возрастное ограничение и ответственная игра (лимиты, самоисключение — удобно сделать через `is_banned`)

## Идеи для развития
Бэкенд чата, общий раунд Crash для всех игроков (WebSocket), промокоды (`TxKind.bonus` уже есть), еженедельный кешбэк по уровням (проценты уже в `app/vip.py`), веб-админка поверх `services/stats.py`.
