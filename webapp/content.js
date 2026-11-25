// Тексты: документы, FAQ, правила чата, новости. Два языка: ru, en.
// Юридические тексты — шаблон. Перед запуском их должен проверить юрист
// и вписать юридическое лицо оператора.
window.CONTENT = (function () {
  const ADDRESS = "1553 W Grand River Ave, East Lansing, Michigan, USA";
  const UPDATED = "2026-11-25";

  const ru = {
    address: "1553 W Grand River Ave, Ист-Лансинг, Мичиган, США",
    disclaimer: "18+. Азартные игры созданы для развлечения. Помните: делая ставку, вы рискуете деньгами. Не тратьте больше, чем можете позволить себе проиграть.",
    about: {
      title: "О нас",
      text: [
        "Cthulhu — казино в мини-приложении Telegram. Пополнение — звёздами Telegram, все игры используют проверяемо честный алгоритм: исход любой ставки можно пересчитать самостоятельно.",
        "Мы делаем игру прозрачной: преимущество казино указано в каждой игре, история ставок и операций всегда под рукой, а лимиты и перерывы в игре можно включить в настройках.",
      ],
      contacts: "Поддержка: команда /paysupport в боте. Отвечаем в течение 24 часов.",
    },
    docs: {
      terms: {
        title: "Пользовательское соглашение",
        sections: [
          { h: "1. Общие положения", p: [
            "Настоящее соглашение регулирует использование мини-приложения Cthulhu (далее — «Сервис») в Telegram. Оператор Сервиса: Cthulhu, адрес: " + "1553 W Grand River Ave, Ист-Лансинг, Мичиган, США" + ".",
            "Открывая Сервис и делая ставки, вы подтверждаете, что прочитали и приняли это соглашение, Политику конфиденциальности и Правила ответственной игры.",
          ] },
          { h: "2. Возраст и юрисдикция", p: [
            "Сервис доступен только лицам, достигшим 18 лет или возраста совершеннолетия в их стране, если он выше.",
            "Вы самостоятельно проверяете, разрешено ли участие в азартных играх онлайн там, где вы находитесь. Если это запрещено, пользоваться Сервисом нельзя. Мы вправе ограничить доступ из отдельных стран.",
          ] },
          { h: "3. Аккаунт", p: [
            "Аккаунт создаётся автоматически по вашему аккаунту Telegram. Один человек — один аккаунт. Мультиаккаунты, передача аккаунта третьим лицам и использование чужих аккаунтов запрещены.",
            "Вы отвечаете за безопасность своего аккаунта Telegram и за все действия, совершённые через него.",
          ] },
          { h: "4. Звёзды и игровой баланс", p: [
            "Пополнение выполняется звёздами Telegram через встроенную оплату Telegram. Звёзды зачисляются на игровой баланс Сервиса после подтверждения платежа.",
            "Игровой баланс используется только для ставок в Сервисе. Мы можем устанавливать минимальные и максимальные суммы пополнения, ставки и выигрыша; актуальные лимиты показаны в приложении.",
          ] },
          { h: "5. Игры и честность", p: [
            "Исход каждой ставки определяется алгоритмом provably fair: хэш серверного сида публикуется до ставки, а сам сид раскрывается после смены пары. Описание алгоритма — в разделе «Честная игра».",
            "В каждой игре заложено преимущество казино, указанное в описании игры. В случае технического сбоя ставка может быть аннулирована с возвратом суммы ставки.",
          ] },
          { h: "6. Вывод средств", p: [
            "Вывод доступен после отыгрыша: сумма ставок должна быть не меньше суммы пополнений, умноженной на коэффициент, указанный в приложении.",
            "Заявки на вывод обрабатываются вручную или автоматически, в зависимости от выбранного способа. Мы вправе запросить подтверждение личности и отказать в выводе при нарушении соглашения. Невыплаченная сумма возвращается на баланс.",
          ] },
          { h: "7. Реферальная программа и бонусы", p: [
            "Реферальные начисления и бонусы предоставляются по условиям, опубликованным в приложении. Злоупотребление (самоприглашение, мультиаккаунты, сговор) ведёт к аннулированию начислений и блокировке.",
          ] },
          { h: "8. Запрещённые действия", p: [
            "Запрещены: использование ботов и скриптов для игры, эксплуатация ошибок, сговор, отмывание денег, мошенничество с платежами, оскорбления и спам в чате.",
            "При нарушении мы вправе ограничить доступ, аннулировать ставки и выигрыши, полученные с нарушением, и заблокировать аккаунт.",
          ] },
          { h: "9. Ответственная игра", p: [
            "В настройках можно установить дневной лимит пополнений и взять перерыв в игре. Если вы чувствуете, что теряете контроль, воспользуйтесь этими инструментами и обратитесь за помощью — контакты в разделе «Ответственная игра».",
          ] },
          { h: "10. Ограничение ответственности", p: [
            "Сервис предоставляется «как есть». Мы не отвечаем за перебои в работе Telegram, сетей связи и сторонних сервисов, а также за убытки, возникшие из-за нарушения вами этого соглашения.",
          ] },
          { h: "11. Изменения соглашения", p: [
            "Мы можем изменять соглашение. Новая редакция действует с момента публикации в приложении. Продолжая пользоваться Сервисом, вы принимаете изменения.",
          ] },
          { h: "12. Контакты", p: [
            "Вопросы по соглашению и платежам — через команду /paysupport в боте. Почтовый адрес: " + "1553 W Grand River Ave, Ист-Лансинг, Мичиган, США" + ".",
          ] },
        ],
      },
      privacy: {
        title: "Политика конфиденциальности",
        sections: [
          { h: "1. Какие данные мы получаем", p: [
            "От Telegram: идентификатор пользователя, имя, username, язык интерфейса и ссылку на фото профиля — только то, что Telegram передаёт мини-приложению.",
            "В Сервисе: игровой никнейм, ставки и их результаты, операции с балансом, заявки на вывод, сообщения в чате, технические данные запросов (время, ошибки).",
          ] },
          { h: "2. Зачем мы их используем", p: [
            "Чтобы вести ваш аккаунт и баланс, проводить платежи и выплаты, проверять честность игр, предотвращать мошенничество и злоупотребления, отвечать в поддержке и соблюдать требования закона.",
          ] },
          { h: "3. Кому мы их передаём", p: [
            "Telegram — для обработки платежей звёздами. Платёжным и выплатным сервисам — в объёме, необходимом для выплаты. Государственным органам — только по законному требованию.",
            "Мы не продаём персональные данные и не передаём их для рекламы.",
          ] },
          { h: "4. Хранение", p: [
            "Данные об операциях и ставках хранятся столько, сколько требуется для учёта и проверок, но не дольше, чем это необходимо по закону. Сообщения чата могут удаляться модераторами.",
          ] },
          { h: "5. Ваши права", p: [
            "Вы можете запросить копию своих данных, исправление или удаление аккаунта через /paysupport. Удаление может быть отложено, если данные нужны для завершения выплат или по требованию закона.",
          ] },
          { h: "6. Хранилище на устройстве", p: [
            "Настройки приложения (язык, тема, звук) хранятся на вашем устройстве и в облачном хранилище Telegram для этого бота.",
          ] },
          { h: "7. Несовершеннолетние", p: [
            "Сервис не предназначен для лиц младше 18 лет. Если мы узнаём, что аккаунт принадлежит несовершеннолетнему, он блокируется.",
          ] },
          { h: "8. Изменения и контакты", p: [
            "Мы сообщим об изменениях политики в приложении. Вопросы — через /paysupport. Адрес: " + "1553 W Grand River Ave, Ист-Лансинг, Мичиган, США" + ".",
          ] },
        ],
      },
      responsible: {
        title: "Ответственная игра",
        sections: [
          { h: "Игра — это развлечение", p: [
            "Ставки не способ заработать. Решите заранее, сколько готовы потратить, и воспринимайте эту сумму как плату за развлечение.",
          ] },
          { h: "Простые правила", p: [
            "Не играйте на деньги, нужные для жизни. Не пытайтесь отыграться. Делайте перерывы. Не играйте, когда расстроены, устали или выпили. Следите за временем в игре.",
          ] },
          { h: "Инструменты в приложении", p: [
            "Настройки → Ответственная игра: дневной лимит пополнений и перерыв в игре на 24 часа, 7 или 30 дней. Во время перерыва ставки и пополнения недоступны, отменить перерыв досрочно нельзя.",
          ] },
          { h: "Тревожные признаки", p: [
            "Вы тратите больше, чем планировали; занимаете деньги на игру; скрываете игру от близких; думаете об игре постоянно; раздражаетесь, когда не можете играть.",
          ] },
          { h: "Где получить помощь", p: [
            "США и Мичиган: национальная линия помощи 1-800-GAMBLER, круглосуточно и конфиденциально.",
            "Группы «Анонимные игроки» (Gamblers Anonymous) работают во многих странах: gamblersanonymous.org.",
            "Если вы хотите закрыть аккаунт навсегда, напишите в /paysupport.",
          ] },
        ],
      },
      fair: {
        title: "Честная игра (provably fair)",
        sections: [
          { h: "Как это работает", p: [
            "Для каждого игрока есть пара сидов: секретный server seed и ваш client seed. До ставки вы видите sha256(server seed) — изменить сид после этого нельзя, иначе хэш не совпадёт.",
            "Каждая ставка получает номер nonce: 0, 1, 2… Случайные числа считаются так: HMAC_SHA256(server_seed, \"client_seed:nonce:cursor\"), каждые 4 байта дают число от 0 до 1.",
          ] },
          { h: "Как проверить ставку", p: [
            "Откройте «Профиль → Честная игра» и смените пару сидов — старый server seed раскроется. Затем откройте ставку в истории и нажмите «Проверить честность»: исход пересчитается и сравнится с результатом.",
          ] },
          { h: "Преимущество казино", p: [
            "Во всех играх заложено преимущество казино 3%: в среднем на длинной дистанции возвращается 97% ставок. Конкретный выигрыш или проигрыш при этом случаен.",
          ] },
        ],
      },
    },
    chatRules: [
      "Будьте вежливы: без оскорблений, угроз и дискриминации.",
      "Без спама, флуда и рекламы — в том числе других казино и каналов.",
      "Не выпрашивайте звёзды и не предлагайте «схемы» заработка.",
      "Не публикуйте ссылки на сторонние сайты и боты.",
      "Не делитесь личными данными — своими и чужими.",
      "Администрация никогда не пишет первой и не просит перевести звёзды.",
      "За нарушения — удаление сообщений, мут или блокировка аккаунта.",
    ],
    faq: [
      { q: "Как пополнить баланс?", a: "Нажмите «+» рядом с балансом вверху, выберите сумму и оплатите звёздами Telegram. Звёзды зачисляются сразу после оплаты." },
      { q: "Где купить звёзды Telegram?", a: "Звёзды покупаются в самом Telegram: в окне оплаты, если звёзд не хватает, Telegram предложит докупить их." },
      { q: "Как вывести выигрыш?", a: "Профиль → Баланс → «Вывести». Укажите сумму и создайте заявку. Сумма сразу резервируется, а после обработки заявки вы получите уведомление в боте." },
      { q: "Почему вывод недоступен?", a: "Перед выводом нужно отыграть пополнения: сделать ставок на сумму не меньше пополнений. Сколько осталось, видно в разделе вывода." },
      { q: "Игры правда честные?", a: "Да, и это можно проверить. Хэш серверного сида показывается до ставки, а после смены пары сид раскрывается — любую ставку можно пересчитать. Подробнее — «О нас → Честная игра»." },
      { q: "Что такое привилегии?", a: "Уровни за сумму ставок: Новичок, Культист, Жрец, Глубоководный, Древний. Чем выше уровень, тем больше бонусов. Прогресс — в профиле." },
      { q: "Как работает реферальная программа?", a: "Поделитесь своей ссылкой из профиля. Когда приглашённый пополняет баланс, вы получаете процент от суммы пополнения." },
      { q: "Можно ли сменить никнейм?", a: "Да, в профиле нажмите на карандаш рядом с ником. ID и Telegram ID изменить нельзя." },
      { q: "Как поставить лимит или сделать перерыв?", a: "Настройки → Ответственная игра. Там можно задать дневной лимит пополнений и перерыв в игре." },
      { q: "Ставка зависла или не зачислился платёж", a: "Напишите в поддержку командой /paysupport в боте: укажите время, сумму и что пошло не так." },
    ],
    news: [
      { id: "welcome", title: "Глубина зовёт", text: "Пополняйте звёздами Telegram и играйте без лишних шагов.", cta: "Пополнить", route: "wallet", art: "tentacles" },
      { id: "slots", title: "Три новых слота", text: "Ктулху, Фрукты и Сокровища — пять линий выплат в каждом.", cta: "К слотам", route: "slots", art: "reels" },
      { id: "fair", title: "Проверьте любую ставку", text: "Хэш сида виден до игры. Пересчитайте исход сами.", cta: "Как это работает", route: "doc/fair", art: "eye" },
      { id: "ref", title: "Зовите друзей", text: "Получайте процент с каждого пополнения приглашённых.", cta: "Моя ссылка", route: "profile", art: "gift" },
    ],
    chatBots: [
      "всем привет 👋", "mines сегодня щедрый", "поймал x12 в плинко!", "кто в слоты?", "удачи всем",
      "limbo на x2 держу стратегию 😄", "ктулху-слот дал три осьминога", "дайс 50/50 туда-сюда", "ну что, по маленькой?",
      "проверил ставку через provably fair — всё сходится", "вывел, всё пришло 👍", "ставлю 10, иду ва-банк… шучу",
    ],
  };

  const en = {
    address: ADDRESS,
    disclaimer: "18+. Gambling is meant to be entertainment. Remember that every bet puts your money at risk. Never spend more than you can afford to lose.",
    about: {
      title: "About us",
      text: [
        "Cthulhu is a casino inside a Telegram mini app. You top up with Telegram Stars, and every game uses a provably fair algorithm, so you can recalculate the outcome of any bet yourself.",
        "We keep things transparent: the house edge is stated for each game, your bet and balance history is always at hand, and you can set limits or take a break in Settings.",
      ],
      contacts: "Support: send /paysupport to the bot. We reply within 24 hours.",
    },
    docs: {
      terms: {
        title: "Terms of Service",
        sections: [
          { h: "1. General", p: [
            "These terms govern your use of the Cthulhu mini app in Telegram (the “Service”). The Service is operated by Cthulhu, " + ADDRESS + ".",
            "By opening the Service and placing bets you confirm that you have read and accepted these terms, the Privacy Policy and the Responsible Gaming rules.",
          ] },
          { h: "2. Age and jurisdiction", p: [
            "The Service is available only to people aged 18 or older, or the age of majority in their country if higher.",
            "You are responsible for checking whether online gambling is legal where you are. If it is not, you must not use the Service. We may restrict access from certain countries.",
          ] },
          { h: "3. Account", p: [
            "Your account is created automatically from your Telegram account. One person, one account. Multiple accounts, transferring an account and using someone else’s account are prohibited.",
            "You are responsible for the security of your Telegram account and for all actions taken through it.",
          ] },
          { h: "4. Stars and game balance", p: [
            "You top up with Telegram Stars through Telegram’s built-in payments. Stars are added to your game balance once the payment is confirmed.",
            "The game balance can be used only for bets in the Service. We may set minimum and maximum amounts for top-ups, bets and wins; current limits are shown in the app.",
          ] },
          { h: "5. Games and fairness", p: [
            "Every bet is settled by a provably fair algorithm: the server seed hash is published before the bet and the seed itself is revealed after you rotate the pair. See “Fair play” for details.",
            "Each game has a house edge stated in its description. If a technical failure occurs, a bet may be voided and its stake returned.",
          ] },
          { h: "6. Withdrawals", p: [
            "Withdrawals become available once your total bets reach your total top-ups multiplied by the ratio shown in the app.",
            "Withdrawal requests are processed manually or automatically depending on the payout method. We may ask you to verify your identity and refuse a withdrawal if these terms are breached. Any unpaid amount is returned to your balance.",
          ] },
          { h: "7. Referrals and bonuses", p: [
            "Referral rewards and bonuses follow the conditions published in the app. Abuse (self-referral, multiple accounts, collusion) leads to cancelled rewards and account suspension.",
          ] },
          { h: "8. Prohibited conduct", p: [
            "Prohibited: playing with bots or scripts, exploiting bugs, collusion, money laundering, payment fraud, abuse and spam in chat.",
            "If you breach these rules we may restrict access, void bets and winnings obtained in breach, and close your account.",
          ] },
          { h: "9. Responsible gaming", p: [
            "In Settings you can set a daily top-up limit and take a break from playing. If you feel you are losing control, use these tools and seek help — contacts are in “Responsible gaming”.",
          ] },
          { h: "10. Limitation of liability", p: [
            "The Service is provided “as is”. We are not liable for outages of Telegram, networks or third-party services, or for losses caused by your breach of these terms.",
          ] },
          { h: "11. Changes", p: [
            "We may update these terms. The new version applies once published in the app. By continuing to use the Service you accept the changes.",
          ] },
          { h: "12. Contact", p: [
            "Questions about these terms or payments: send /paysupport to the bot. Postal address: " + ADDRESS + ".",
          ] },
        ],
      },
      privacy: {
        title: "Privacy Policy",
        sections: [
          { h: "1. Data we receive", p: [
            "From Telegram: your user ID, name, username, interface language and profile photo link — only what Telegram passes to the mini app.",
            "In the Service: your game nickname, bets and results, balance transactions, withdrawal requests, chat messages and technical request data (time, errors).",
          ] },
          { h: "2. How we use it", p: [
            "To run your account and balance, process payments and payouts, verify game fairness, prevent fraud and abuse, answer support requests and meet legal requirements.",
          ] },
          { h: "3. Who we share it with", p: [
            "Telegram, to process Star payments. Payment and payout providers, only as needed for a payout. Public authorities, only on a lawful request.",
            "We do not sell personal data or share it for advertising.",
          ] },
          { h: "4. Retention", p: [
            "Transaction and bet records are kept as long as needed for accounting and checks, and no longer than the law requires. Moderators may delete chat messages.",
          ] },
          { h: "5. Your rights", p: [
            "You can request a copy of your data, a correction or account deletion via /paysupport. Deletion may be delayed if the data is needed to complete payouts or by law.",
          ] },
          { h: "6. On-device storage", p: [
            "App settings (language, theme, sound) are stored on your device and in Telegram’s cloud storage for this bot.",
          ] },
          { h: "7. Minors", p: [
            "The Service is not intended for anyone under 18. If we learn that an account belongs to a minor, we close it.",
          ] },
          { h: "8. Changes and contact", p: [
            "We will announce policy changes in the app. Questions: /paysupport. Address: " + ADDRESS + ".",
          ] },
        ],
      },
      responsible: {
        title: "Responsible gaming",
        sections: [
          { h: "Gambling is entertainment", p: [
            "Betting is not a way to make money. Decide in advance how much you are willing to spend and treat it as the price of entertainment.",
          ] },
          { h: "Simple rules", p: [
            "Never bet money you need to live on. Don’t chase losses. Take breaks. Don’t play when upset, tired or after drinking. Keep track of your time.",
          ] },
          { h: "Tools in the app", p: [
            "Settings → Responsible gaming: a daily top-up limit and a break from playing for 24 hours, 7 or 30 days. During a break you can’t bet or top up, and the break can’t be ended early.",
          ] },
          { h: "Warning signs", p: [
            "You spend more than planned; borrow money to gamble; hide gambling from people close to you; think about gambling all the time; get irritable when you can’t play.",
          ] },
          { h: "Where to get help", p: [
            "USA and Michigan: the national helpline 1-800-GAMBLER, confidential and available 24/7.",
            "Gamblers Anonymous groups meet in many countries: gamblersanonymous.org.",
            "If you want to close your account permanently, send /paysupport to the bot.",
          ] },
        ],
      },
      fair: {
        title: "Fair play (provably fair)",
        sections: [
          { h: "How it works", p: [
            "Each player has a pair of seeds: a secret server seed and your client seed. Before you bet you see sha256(server seed), so the seed can’t be changed afterwards without the hash changing.",
            "Every bet gets a nonce: 0, 1, 2… Random numbers are computed as HMAC_SHA256(server_seed, \"client_seed:nonce:cursor\"); every 4 bytes give a number from 0 to 1.",
          ] },
          { h: "How to verify a bet", p: [
            "Open Profile → Fair play and rotate the seed pair; the old server seed is revealed. Then open the bet in your history and tap “Verify”: the outcome is recalculated and compared with the result.",
          ] },
          { h: "House edge", p: [
            "Every game has a 3% house edge: over the long run 97% of stakes are returned on average. Any individual win or loss is still random.",
          ] },
        ],
      },
    },
    chatRules: [
      "Be polite: no insults, threats or discrimination.",
      "No spam, flooding or advertising — including other casinos and channels.",
      "Don’t beg for Stars or offer money-making “schemes”.",
      "Don’t post links to other websites or bots.",
      "Don’t share personal data — yours or anyone else’s.",
      "Staff never message you first and never ask you to send Stars.",
      "Breaking the rules leads to deleted messages, a mute or an account ban.",
    ],
    faq: [
      { q: "How do I top up?", a: "Tap “+” next to your balance at the top, pick an amount and pay with Telegram Stars. Stars are credited right after payment." },
      { q: "Where do I buy Telegram Stars?", a: "Inside Telegram: if you don’t have enough Stars, the payment window offers to buy more." },
      { q: "How do I withdraw?", a: "Profile → Balance → “Withdraw”. Enter the amount and create a request. The amount is reserved immediately and the bot notifies you once the request is processed." },
      { q: "Why can’t I withdraw yet?", a: "You need to wager your top-ups first: your total bets must reach your total top-ups. The withdrawal screen shows how much is left." },
      { q: "Are the games really fair?", a: "Yes, and you can check. The server seed hash is shown before the bet and the seed is revealed after you rotate the pair, so any bet can be recalculated. See About us → Fair play." },
      { q: "What are privileges?", a: "Levels based on your total bets: Novice, Cultist, Priest, Deep One, Great Old One. Higher levels get more perks. Your progress is in your profile." },
      { q: "How does the referral program work?", a: "Share your link from the profile. When someone you invited tops up, you get a percentage of the amount." },
      { q: "Can I change my nickname?", a: "Yes, tap the pencil next to your nickname in the profile. ID and Telegram ID can’t be changed." },
      { q: "How do I set a limit or take a break?", a: "Settings → Responsible gaming. You can set a daily top-up limit and a break from playing." },
      { q: "A bet froze or a payment didn’t arrive", a: "Send /paysupport to the bot with the time, the amount and what went wrong." },
    ],
    news: [
      { id: "welcome", title: "The deep is calling", text: "Top up with Telegram Stars and start playing in seconds.", cta: "Top up", route: "wallet", art: "tentacles" },
      { id: "slots", title: "Three new slots", text: "Cthulhu, Fruits and Treasure — five paylines each.", cta: "See slots", route: "slots", art: "reels" },
      { id: "fair", title: "Verify any bet", text: "The seed hash is shown before you play. Recalculate the outcome yourself.", cta: "How it works", route: "doc/fair", art: "eye" },
      { id: "ref", title: "Invite friends", text: "Earn a share of every top-up your friends make.", cta: "My link", route: "profile", art: "gift" },
    ],
    chatBots: [
      "hi all 👋", "mines is generous today", "hit x12 on plinko!", "anyone on slots?", "good luck everyone",
      "limbo at x2, sticking to it 😄", "three octopuses on the Cthulhu slot", "dice 50/50 back and forth", "small bets tonight",
      "checked my bet with provably fair — it matches", "withdrew, all arrived 👍", "going all in with 10… kidding",
    ],
  };

  return { ru, en, ADDRESS, UPDATED };
})();
