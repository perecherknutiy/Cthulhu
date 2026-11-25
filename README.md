# 🐙 Cthulhu — казино в Telegram Mini App на звёздах

Бэкенд-основа: бот + API мини-приложения + кошелёк в Telegram Stars (XTR) + честные (provably fair) игры + выводы + админка.
Фронт в `webapp/` — минимальный, только чтобы руками прогнать все сценарии; заменяйте на свой.

**Стек:** Python 3.12, FastAPI, aiogram 3.33 (Bot API 10.x), SQLAlchemy 2 (async) + asyncpg, PostgreSQL, Alembic.
Бот и API живут в одном процессе.

---

## Что внутри

| Модуль | Что делает |
|---|---|
| **Авторизация** | Проверка `initData` мини-аппа по HMAC (`app/telegram_auth.py`). Фронт шлёт `Authorization: tma <initData>`. |
| **Кошелёк** | Баланс в целых звёздах, леджер транзакций (`transactions`): любая смена баланса = запись. Блокировка строки юзера (`SELECT … FOR UPDATE`) — параллельные ставки не уводят баланс в минус. |
| **Пополнение** | `createInvoiceLink` в XTR → `WebApp.openInvoice` → `pre_checkout_query` (проверка счёта) → `successful_payment` (идемпотентно по `telegram_payment_charge_id`). Также `/deposit` в боте. |
| **Возвраты** | `/refund <charge_id>` — `refundStarPayment` со списанием с баланса; событие `refunded_payment` от Telegram тоже обрабатывается. |
| **Игры** | Dice, Монетка, Limbo, Plinko (8–16 рядов, 3 уровня риска), Mines (многошаговая). Преимущество казино настраивается (`HOUSE_EDGE`), RTP проверен тестами. |
| **Provably fair** | `HMAC_SHA256(server_seed, "client_seed:nonce:cursor")`, хэш сида заранее, раскрытие при ротации, публичный `/api/fair/verify`. |
| **Вывод** | Заявка → баланс сразу списывается → админ в боте жмёт «Выплатить»/«Отклонить». Способы: `manual` и `gifts` (бот шлёт подарки через `sendGift`). Требование отыгрыша депозита. |
| **Рефералка** | `t.me/<bot>?startapp=ref_<id>` или `/start ref_<id>`, % от пополнений реферала. |
| **Админка в боте** | `/stats`, `/user`, `/give`, `/ban`, `/unban`, `/withdrawals`, `/refund`, `/botbalance`. |
| **Лимиты** | мин/макс ставка, макс. выигрыш за ставку, лимиты депозита/вывода, rate limit ставок. |

```
app/
  main.py               # FastAPI + запуск бота (polling/webhook)
  config.py             # все настройки из .env
  models.py             # таблицы БД
  telegram_auth.py      # проверка initData
  fairness.py           # provably fair RNG
  payouts.py            # способы выплаты (manual / gifts)
  ratelimit.py
  games/                # чистая математика игр, без БД
    base.py  instant.py  mines.py
  services/             # бизнес-логика: wallet, payments, games, withdrawals, seeds, users, stats
  api/                  # HTTP-роуты мини-аппа
  bot/                  # aiogram: handlers/{user,payments,admin}.py, notify.py
migrations/             # Alembic
webapp/                 # минимальный фронт
tests/                  # 100+ тестов на живом PostgreSQL
```

---

## Быстрый старт

### 1. Бот
1. @BotFather → `/newbot` → токен в `BOT_TOKEN`.
2. Платёжного провайдера подключать **не нужно** — звёзды работают без него.
3. Мини-апп: бот сам ставит кнопку меню «🎰 Играть» на `WEBAPP_URL`. Если хотите прямую ссылку `t.me/<bot>/<app>` — `/newapp` в BotFather с тем же URL (тогда реф-ссылки тоже можно делать через неё).

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
(на одинаковых сидах исходы совпадают с бэкендом). Баланс хранится в браузере, «Настройки → Сбросить демо» — 1000 ⭐.

Внутри Telegram (есть `initData`) фронт всегда ходит в настоящий API. Если демо в проде не нужно —
удалите строку `<script src="demo-api.js"></script>` из `webapp/index.html`.

Файлы фронта:
- `index.html` — каркас: хедер, экран, футер; шрифты Golos Text и Yeseva One с Google Fonts.
- `style.css` — две темы (День / Ночь) на палитре `#5dc165` / `#36703f`.
- `app.js` — роутер и все экраны: Играть (карусели новостей, слотов, мини-игр), Чат, Меню (Профиль, Настройки, Помощь), кошелёк, игры.
- `i18n.js` — строки интерфейса RU/EN. `content.js` — соглашение, политика, ответственная игра, FAQ, правила чата, новости.
- `demo-api.js` — демо-бэкенд в браузере.

Юридические тексты в `content.js` — шаблон: перед запуском их должен проверить юрист и вписать юрлицо оператора.

#### Что новый фронт ждёт от бэкенда (пока есть только в демо)
| Метод | Что нужно |
|---|---|
| `GET /api/me` | добавить `public_id` (внутренний ID), `telegram_id`, `nickname`, `photo_url`, `vip {level, key, cashback, wagered, current_min, next_min, next_key}`, `referral {link, invited, earned, percent}` |
| `POST /api/me/nickname` `{nickname}` | выбор ника при первом входе и смена в профиле: 3–20 символов (буквы, цифры, пробел, `_ . -`), уникален без учёта регистра (`nickname_taken`), нельзя похожие на администрацию (`nickname_reserved`: содержит admin/support/moder/official/админ/поддерж/модер/официал или равен cthulhu/ктулху/telegram/system). Пока ник не выбран, `/api/me` отдаёт `nickname: null` — фронт показывает шаг выбора ника |
| `GET /api/chat/messages?after_id&lang` | `{messages:[{id, kind:"user"\|"win", user:{public_id,nickname,vip_level,photo_url}, text, game, amount, created_at}], online, me:{public_id}}` |
| `POST /api/chat/messages` `{text}` | до 300 символов, не чаще раза в 2 с, мут/бан модератором |
| `POST /api/games/slots/play` `{amount, params:{slot}}` | слоты 3×3, 5 линий; алгоритм и таблица выплат — в `demo-api.js` (блок `slots`) |
| `GET /api/config` | добавить `vip_levels` и игру `slots` с `themes`, `weights`, `pays`, `lines` |

### Polling или webhook
- `BOT_MODE=polling` — проще всего, для разработки и одного сервера.
- `BOT_MODE=webhook` + `WEBHOOK_URL=https://domain/tg/webhook` + `WEBHOOK_SECRET` — для продакшна.
- `BOT_MODE=none` — только API (тесты, отдельный воркер).

> Запускайте **один процесс** uvicorn: polling-бот и in-memory rate limiter рассчитаны на один инстанс. Для горизонтального масштабирования: webhook + Redis для лимитера.

---

## Деньги

**Единица — 1 звезда, всё в целых числах.** Выплата = `floor(ставка × множитель)`, поэтому `MIN_BET` не стоит делать меньше ~10: на ставке в 1 ⭐ округление съедает выигрыш.

**Инвариант:** `sum(transactions.amount) == users.balance` для каждого юзера (проверяется в тестах). Меняйте баланс только через `services/wallet.apply()` после `lock_user()`.

Типы транзакций: `deposit`, `bet`, `win`, `withdrawal`, `withdrawal_refund`, `payment_refund`, `referral`, `admin`, `bonus`.

### Вывод — важно знать
В Bot API нет метода «перевести звёзды пользователю». Поэтому:
- **`manual`** (по умолчанию) — админ платит сам любым способом и жмёт «Выплатить» (это просто фиксирует выплату).
- **`gifts`** — бот подбирает набор обычных подарков на сумму ≤ заявки (DP по номиналам из `getAvailableGifts`), проверяет `getMyStarBalance` и шлёт их `sendGift`. Остаток, который нельзя набрать подарками, возвращается на баланс. При обмене подарка на звёзды пользователь получает сумму по курсу Telegram — она может быть меньше цены подарка, пропишите это в условиях.
- Звёзды от продаж становятся доступны боту не мгновенно — держите на балансе бота запас для выплат.
- Свой способ: класс `PayoutMethod` в `app/payouts.py`.

Защита от «пополнил → сразу вывел»: `WITHDRAW_WAGER_RATIO` (по умолчанию нужно проставить сумму депозитов ×1).

---

## Provably fair

1. У каждого игрока активная пара: `server_seed` (секрет) + `client_seed`, `nonce` растёт с каждой ставкой. `sha256(server_seed)` виден заранее (`GET /api/fair`).
2. Случайные числа: `HMAC_SHA256(key=server_seed, msg=f"{client_seed}:{nonce}:{cursor}")`, каждые 4 байта → float в [0,1).
3. `POST /api/fair/rotate` раскрывает старый `server_seed` и выдаёт новую пару. Во время активной игры Mines ротация запрещена (иначе раскрылись бы мины).
4. Любой может пересчитать ставку: `POST /api/fair/verify` (без авторизации) или своим скриптом.

**Не меняйте `app/fairness.py`** после запуска — старые ставки перестанут проверяться (тест `test_rng_known_vector` это ловит).

---

## API

Все `/api/*` кроме `/api/fair/verify` требуют `Authorization: tma <initData>`. Ошибки: `{"error": {"code", "message"}}`.

| Метод | Путь | Описание |
|---|---|---|
| GET | `/api/config` | игры, лимиты, таблицы Plinko, пресеты депозита |
| GET | `/api/me` | профиль, баланс, реф-ссылка, сколько осталось отыграть |
| POST | `/api/wallet/invoice` `{amount}` | ссылка на оплату звёздами → `Telegram.WebApp.openInvoice(link)` |
| GET | `/api/wallet/transactions?limit&before_id` | леджер |
| POST | `/api/wallet/withdraw` `{amount}` | заявка на вывод |
| GET | `/api/wallet/withdrawals` | мои заявки |
| POST | `/api/games/{dice\|coinflip\|limbo\|plinko}/play` `{amount, params}` | мгновенная игра |
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
Покрыто: подпись initData, детерминизм RNG, RTP каждой игры (аналитически и симуляцией), гонка 30 параллельных ставок, двойная доставка `successful_payment`, возвраты, рефералка, все ветки вывода (включая частичный сбой подарков), сквозные сценарии API, хендлеры бота через настоящий `Dispatcher`.

---

## Перед запуском в прод

- [ ] HTTPS, `BOT_MODE=webhook`, длинный `WEBHOOK_SECRET`, `DEBUG=false`
- [ ] Бэкапы PostgreSQL
- [ ] Свой текст `/terms` и `/paysupport` (команда `/paysupport` обязательна для ботов с платежами)
- [ ] Подобрать лимиты (`MAX_BET`, `MAX_PAYOUT`) под свой банкролл
- [ ] Азартные игры регулируются законом в большинстве стран, а условия Telegram для разработчиков ограничивают регулируемые товары и услуги — проверьте юридическую сторону и условия Telegram до запуска
- [ ] Возрастное ограничение и ответственная игра (лимиты, самоисключение — удобно сделать через `is_banned`)

## Идеи для развития
Crash в реальном времени (WebSocket + общий раунд), промокоды и бонусы (`TxKind.bonus` уже есть), ежедневный бонус, лидерборды, мультиязычность, веб-админка поверх `services/stats.py`.
