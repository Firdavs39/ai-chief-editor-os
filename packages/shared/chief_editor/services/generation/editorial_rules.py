"""Editorial rules — banned phrases, hook patterns, emotion taxonomy.

Phase Q (Quality Hardening, May 2026): synthesized from three research
passes against the May 2026 Russian-content state of play. The rules
here are CONSTANTS — they're embedded into LLM prompts and consulted by
the deterministic AI-tells detector in `ai_tells.py`.

Sources synthesized:
- humanizer-ru v2.1 (Ilya Utov, vc.ru) — phrase blacklist + structural fingerprints
- Habr "Ваш текст воняет GPT. 12 мест" (Apr 2026)
- Wikipedia ru "Признаки сгенерированности текста"
- Gramota.ru stylometry summary
- vc.ru / sostav SMM playbooks (Salimova, Лоцманов, Юкович)
- Mailfit "Не ChatGPT. Тренды в текстах 2026"
- Anthropic engineering posts on multi-agent + context engineering
- Sage / PNAS Nexus 2025-2026 persuasion-reactance meta-analyses
- CMI 2026 "Perfection is the Enemy of Trust"

Convergent findings (all three research agents agreed):
- Open with a specific scene or number, NEVER with "в современном мире".
- Personal authored voice beats editorial commentary.
- Em-dash flood is the #1 statistical AI tell in Russian.
- Triple-parallel symmetric lists ("X, Y, и Z") + "не X, а Y" + wrap-up
  paragraphs collectively account for ~40% of human-editor detection.
- Engagement-optimal TG length is 800-1500 chars, NOT the 4096 platform max.
- 2026 readers reject "cognitive-bias-lever" injection — the right model
  is "name the half-thought the reader already had".
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# BANNED TELLS — phrases that immediately mark text as AI-generated.
# Tiered by severity (Tier 1 = instant fail, Tier 6 = strong code-smell).
# ---------------------------------------------------------------------------

# Tier 1 — empty openings / temporal generalisations.
# Any Tier-1 hit in the FIRST sentence of a draft is auto-fail.
BANNED_TELLS_TIER_1: tuple[str, ...] = (
    "в современном мире",
    "в современном динамично развивающемся мире",
    "в настоящее время",
    "на сегодняшний день",
    "в эпоху",
    "в условиях",
    "не секрет, что",
    "ни для кого не секрет",
    "многим кажется",
    "многие считают",
    "некоторые эксперты полагают",
)

# Tier 2 — AI hedging / meta-commentary.
BANNED_TELLS_TIER_2: tuple[str, ...] = (
    "стоит отметить",
    "важно отметить",
    "важно понимать, что",
    "следует учитывать",
    "следует помнить",
    "следует отметить",
    "нельзя не заметить",
    "необходимо учитывать",
    "стоит подчеркнуть",
    "можно с уверенностью сказать",
)

# Tier 3 — wrap-up paragraphs / closers. Cuttable entirely.
BANNED_TELLS_TIER_3: tuple[str, ...] = (
    "подводя итог",
    "подытоживая",
    "в заключение",
    "таким образом",
    "вкратце",
    "можно сделать вывод",
    "перспективы на будущее",
    "резюмируя сказанное",
)

# Tier 4 — over-trained parallelism / contrast patterns.
# Once per post max for ALL of these combined. Detector flags 2+.
BANNED_TELLS_TIER_4: tuple[str, ...] = (
    "играет ключевую роль",
    "играет важную роль",
    "ключевой момент",
    "ключевое значение",
    "поворотный момент",
    "имеет важное значение",
)

# Tier 5 — bureaucratese / translation-calque syntax.
BANNED_TELLS_TIER_5: tuple[str, ...] = (
    "представляет собой",
    "это позволяет",
    "обеспечивает возможность",
    "выступает в качестве",
    "служит основой",
    "оказание услуг по",
)

# Tier 6 — didactic / chatbot artifacts.
BANNED_TELLS_TIER_6: tuple[str, ...] = (
    "давайте погрузимся",
    "давайте разберёмся",
    "давайте рассмотрим",
    "разберёмся вместе",
    "конечно, расскажу",
    "раскрыть потенциал",
    "комплексный подход",
    "открывает новые горизонты",
    "в самом сердце",
    "уникальная возможность",
    "ключевые особенности",
    "потрясающий функционал",
)

ALL_BANNED_TELLS: tuple[str, ...] = (
    BANNED_TELLS_TIER_1
    + BANNED_TELLS_TIER_2
    + BANNED_TELLS_TIER_3
    + BANNED_TELLS_TIER_4
    + BANNED_TELLS_TIER_5
    + BANNED_TELLS_TIER_6
)


# ---------------------------------------------------------------------------
# HOOK PATTERNS — 8 named openers that consistently stop the scroll in 2026.
# Each pattern has 2-3 example openers Kimi can use as worked examples.
# ---------------------------------------------------------------------------

HOOK_PATTERNS: dict[str, dict[str, object]] = {
    "number_as_reframe": {
        "ru_name": "Цифра + ярлык",
        "skeleton": "Дать конкретное число (не круглое), затем переименовать его в одну сжатую идею.",
        "when": "Когда у тебя есть проверяемая цифра из источника и противоинтуитивное толкование.",
        "examples": (
            "71% продактов в России не пишут спецификации. Это не лень. Это симптом.",
            "4 секунды. За это время читатель решает, листать дальше или сохранить пост.",
            "76,3% открытий лендинга — без скролла. Это не плохой текст. Это плохой первый экран.",
        ),
    },
    "second_person_scene": {
        "ru_name": "Сцена во втором лице",
        "skeleton": "Поместить читателя внутрь узнаваемой сцены (время, действие, конкретный объект).",
        "when": "Когда тема — про повседневный профессиональный опыт. Самый сильный паттерн в 2026.",
        "examples": (
            "Ты в созвоне с продакт-менеджером. Он сейчас даст сроки на следующий спринт.",
            "Открываешь Notion в понедельник. 14 задач от прошлой недели.",
            "Пятница, 19:47. Слак не успокаивается. CEO написал в личку слово «обсудим».",
        ),
    },
    "contrarian_inversion": {
        "ru_name": "Инверсия очевидного",
        "skeleton": "Взять принимаемое сообществом позитивное X и перевернуть в негатив (или наоборот).",
        "when": "Когда у тебя есть narrow disagreement с консенсусом. Не путать с broad contrarianism.",
        "examples": (
            "Если у вас в команде нет конфликтов — это не здоровая культура. Это страх.",
            "Чем понятнее ваш OKR, тем меньше вы понимаете продукт.",
            "Хорошо написанный продакт-док — первый признак, что продукт уже мёртв.",
        ),
    },
    "social_threat_diagnostic": {
        "ru_name": "Социальная угроза / диагностика",
        "skeleton": "«Если в вашей компании X — скорее всего Y». Читатель сразу проверяет на себе.",
        "when": "Для diagnostic-постов. Высокий save-rate.",
        "examples": (
            "Если в офисе появился психолог — твою команду уже сжигают.",
            "Если ваш дизайнер чаще говорит «покрасил» чем «поправил иерархию» — у вас нет дизайн-системы.",
            "Если на ревью кода никто не оставляет комментариев в первые сутки — код не читают.",
        ),
    },
    "mini_cliffhanger": {
        "ru_name": "Мини-клиффхэнгер",
        "skeleton": "«Я думал X. Оказалось Y.» Personal recognition + reframe в одной формуле.",
        "when": "Для personal-experience постов (2026 algo favours).",
        "examples": (
            "Я три года думал, что наша главная проблема — найм. Оказалось, найм был последним.",
            "Считал, что мы плохо продаём. Посмотрел на воронку — мы вообще не продаём.",
            "Думал, что выгораю от объёма. Открыл календарь — выгораю от того, что половина встреч идёт не туда.",
        ),
    },
    "insider_artifact": {
        "ru_name": "Инсайдер-артефакт",
        "skeleton": "«Это слайд из закрытого X, прислали с пометкой Y».",
        "when": "Когда у тебя ЕСТЬ настоящий артефакт (скриншот, лог, цитата). Подделывать НЕЛЬЗЯ.",
        "examples": (
            "Это слайд из закрытого квартального отчёта одного из топ-3 банков. Посмотрите на 3-ю строку.",
            "В метриках Threads есть параметр, который Meta не показывает в дашборде. Возвращается только в API.",
        ),
    },
    "confession_opener": {
        "ru_name": "Признание / vulnerable specificity",
        "skeleton": "«Я три месяца X неправильно». Costly signal — admission = credibility.",
        "when": "Для постов, где надо завоевать доверие до технического тезиса.",
        "examples": (
            "Я три месяца считал retention неправильно — учитывал re-activations как новых.",
            "Я почти отказался от этой задачи. До сих пор не уверен, что прав.",
            "Поделюсь тем, что мне самому стыдно — я полгода тратил рекламный бюджет на сегмент, который не возвращался.",
        ),
    },
    "anti_universal": {
        "ru_name": "Анти-универсалия",
        "skeleton": "«Вам НЕ нужно X». Обратная сторона стандартного листикла.",
        "when": "Для contrarian-постов про то, что аудитория делает «по дефолту».",
        "examples": (
            "Вам не нужен ещё один шаблон Notion для OKR.",
            "Не нужно учить промпт-инжиниринг. Нужно один раз переписать ТЗ так, чтобы его понял стажёр.",
        ),
    },
}


# ---------------------------------------------------------------------------
# EMOTION TAXONOMY — 15 specific emotional states drafts can target in 2026.
# Replaces the vague "конструктивное беспокойство" output of the old prompt.
# ---------------------------------------------------------------------------

EMOTION_TAXONOMY: dict[str, dict[str, str]] = {
    "validated_cynicism": {
        "ru_name": "Подтверждённый цинизм",
        "when": "Подозрение читателя, что система сломана — оправдывается данными.",
        "opener_example": "Подозрение, что половина onboarding-метрик подкручена, — оправданное. Вот разбор по 4 компаниям.",
    },
    "recognized_exhaustion": {
        "ru_name": "Узнанное истощение",
        "when": "«Да, это объективно сложно». Disarms без жалости.",
        "opener_example": "Если вы третий месяц переписываете один и тот же лендинг — вы не плохой маркетолог. У задачи нет короткого пути.",
    },
    "belonging_via_frustration": {
        "ru_name": "Принадлежность через общую боль",
        "when": "«Мы немногие, кто замечает это». Использовать редко.",
        "opener_example": "Все, кто хоть раз объяснял заказчику разницу между MAU и DAU, понимают, почему я сегодня устал.",
    },
    "permission_to_be_specific": {
        "ru_name": "Разрешение быть конкретным",
        "when": "«Можно любить X и при этом считать Y». Лицензия на критику без хейта.",
        "opener_example": "Можно любить Notion и при этом считать, что их новый AI-search — это шаг назад.",
    },
    "stolen_look_insight": {
        "ru_name": "Подсмотренный инсайт",
        "when": "«Вам это видеть не полагалось». Только при наличии настоящего артефакта.",
        "opener_example": "Это слайд из закрытого квартального отчёта одного из топ-3 банков.",
    },
    "casual_mastery": {
        "ru_name": "Спокойное мастерство",
        "when": "Автор относится легко к сложной вещи — сигналит компетенцию.",
        "opener_example": "Поднять postgres-реплику в новом регионе — час-полтора, если не забыть pg_hba.",
    },
    "specific_outrage": {
        "ru_name": "Конкретное возмущение",
        "when": "Гнев на названный конкретный объект, не на абстракцию.",
        "opener_example": "Стоп, давайте перечитаем 4-й пункт оферты Yandex Cloud — там за ночь поменялась формулировка про egress.",
    },
    "sober_ambition": {
        "ru_name": "Трезвая амбиция",
        "when": "«Да, вы это хотите. Вот сколько это реально стоит».",
        "opener_example": "Хотите канал на 50К? Реалистично — 18 месяцев и около 600К рублей в посевы. Вот разбивка.",
    },
    "tribal_warmth": {
        "ru_name": "Тёплая принадлежность",
        "when": "«Мы понимаем — остальные нет». Узкая группа, не общая.",
        "opener_example": "Если вы продакт в финтехе, вы знаете, что значит «согласовали с комплаенсом за один созвон».",
    },
    "useful_guilt": {
        "ru_name": "Полезная вина",
        "when": "«Ты знал и не делал. Вот первый шаг за вечер». Не shame.",
        "opener_example": "Вы знали, что у вас нет бэкапа production-базы. Я тоже знал. Вот скрипт на 12 строк, который это закрывает.",
    },
    "earned_curiosity": {
        "ru_name": "Заслуженное любопытство",
        "when": "Реальный gap + быстрый payoff в том же посте. Не clickbait.",
        "opener_example": "В метриках Threads есть параметр engagement_decay, который Meta не показывает в дашборде. Что это — ниже.",
    },
    "vulnerable_specificity": {
        "ru_name": "Уязвимая конкретность",
        "when": "Автор признаёт свою конкретную ошибку. Costly signal.",
        "opener_example": "Я три месяца считал retention неправильно — учитывал re-activations как новых.",
    },
    "quiet_competence": {
        "ru_name": "Тихая компетентность под давлением",
        "when": "Без паники о тяжёлой ситуации. Operational/incident-контекст.",
        "opener_example": "В пятницу в 19:40 у нас лёг payment gateway. Команда из 4 человек подняла резерв за 23 минуты.",
    },
    "permissioned_disagreement": {
        "ru_name": "Разрешённое несогласие",
        "when": "Назвать консенсус ДО того, как с ним поспорить. Reactance avoidance.",
        "opener_example": "Все правы, что product-led growth работает. Для B2B-инфраструктуры в РФ — нет, и вот в каком моменте ломается.",
    },
    "reader_recognition": {
        "ru_name": "Узнавание читателя",
        "when": "Назвать недовысказанную мысль читателя. Самый недооценённый рычаг 2026.",
        "opener_example": "Большая часть встреч «обсудить стратегию» — это коллективный страх принимать решение.",
    },
}

EMOTION_TAXONOMY_KEYS: tuple[str, ...] = tuple(EMOTION_TAXONOMY.keys())


# ---------------------------------------------------------------------------
# DEAD / DEGRADED LEVERS — never name these in audience_psychology output.
# ---------------------------------------------------------------------------

DEAD_LEVERS: tuple[str, ...] = (
    "FOMO",
    "social proof",
    "social_proof",
    "round-number social proof",
    "curiosity gap",
    "curiosity_gap",
    "manufactured scarcity",
    "scarcity",
    "sunk cost",
    "sunk_cost",
    "shame-threat",
    "shame_threat",
    "broad contrarianism",
    "round-number virality",
    "clickbait",
)


# ---------------------------------------------------------------------------
# EVASION RULES — 10 imperatives embedded in platform_writer prompts.
# ---------------------------------------------------------------------------

EVASION_RULES: tuple[str, ...] = (
    # 1. Open with concrete detail
    "Открой пост конкретной деталью: имя, число, место или дата. Запрещены любые «в современном мире», «не секрет», «давайте разберём».",
    # 2. Vary sentence length
    "Минимум одно предложение до 6 слов и одно от 25 слов в посте. Внутри абзаца длины должны отличаться. Цель: stdev длин ≥ 0.6 × mean.",
    # 3. Concrete anchor
    "Минимум одна «неловкая» конкретика, которой нет в обучающих данных: имя коллеги, название кафе, цифра с дробью («76,3% по выборке из 47 кампаний», не «75%»), погода в день созвона.",
    # 4. Self-correction
    "Минимум одно само-прерывание или коррекция в середине поста: «то есть нет, не так — скорее», «сначала думал X, потом понял что наоборот», «до сих пор не уверен».",
    # 5. No symmetric triples
    "Запрещены симметричные списки из трёх. Давай 2, 4 или 5 пунктов. Если три — длины должны отличаться минимум втрое (одно слово / целое предложение).",
    # 6. Side-quest paragraph
    "Один абзац-боковая мысль, который слегка подкапывает основной тезис или уходит в сторону. Не возвращайся к нему, не подвязывай.",
    # 7. No wrap-up
    "Запрещены концовки-суммирования. Последний абзац НЕ пересказывает тезис, НЕ начинается с «таким образом / подводя итог / в заключение». Лучшая концовка — обрывистая фраза или личная реплика.",
    # 8. Second-person address
    "Конкретное обращение во втором лице с привязкой к ситуации: «ты сейчас читаешь это в перерыве созвона», «если ты PM и у тебя завтра ретро». Не «уважаемый читатель».",
    # 9. Em-dash discipline
    "Не более двух тире (—) на 500 слов. В большинстве мест — запятая или точка. После двоеточия — строчная буква (правило русского, не английского).",
    # 10. First-person stake
    "Одно признанное мнение, эмоция или недостаток от первого лица: «я почти отказался», «меня бесит, когда», «я не разбираюсь в X, но». Запрещён тон «вежливого помощника».",
)


# ---------------------------------------------------------------------------
# DETERMINISTIC THRESHOLDS — used by ai_tells.py and the critic prompt.
# These are calibrated from research; bumping them weakens detection.
# ---------------------------------------------------------------------------

EM_DASH_PER_1000_LIMIT: float = 3.5
SENTENCE_VARIANCE_MIN: float = 0.45  # stdev / mean of sentence word-counts
CONNECTOR_PARAGRAPH_RATIO_LIMIT: float = 0.40
TRIPLE_PARALLEL_LIMIT_PER_400_WORDS: int = 2

# Phase Q v6 thresholds, derived from R2 (RU viral content benchmarks May 2026).
# These are the detector rules R2 identified that I had not yet enforced.
FIRST_CHARS_ANCHOR_WINDOW: int = 100  # named entity + decimal in first N chars
SCREENSHOT_PHRASE_MAX_CHARS: int = 60  # at least one sentence ≤N chars (screenshottable)
SCREENSHOT_PHRASE_MIN_WORDS: int = 3   # but not a single word

# Vague time markers that signal "недавно" instead of a concrete date.
# Top RU posts use specific dates ("С 1 сентября 2025", "16 мая", "Q1 2026").
VAGUE_TIME_MARKERS: tuple[str, ...] = (
    "недавно",
    "в последнее время",
    "сейчас",  # only flagged in opener context where it replaces a date
    "на днях",
    "в наши дни",
    "за последнее время",
    "в скором времени",
    "в ближайшее время",
)

# Anti-CTA patterns — generic subscribe/buy that low-performers ALWAYS have
# and high-performers NEVER have. R2 anti-example finding.
ANTI_CTA_PATTERNS: tuple[str, ...] = (
    "подпишись",
    "подпишитесь",
    "подписывайтесь",
    "ставьте лайк",
    "поделитесь с друзьями",
    "пишите ваше мнение в комментариях",
    "сохраняйте, чтобы не потерять",
    "купите",
    "оформите подписку",
    "промокод",  # in CTA context
    "по моей ссылке",
    "регистрируйтесь",
    "записывайтесь на курс",
)

# Sentence-start connector phrases the detector counts.
# Most are valid Russian — they're not banned individually, only flagged
# when >40% of paragraphs start with one (mechanical "AI flow").
SENTENCE_START_CONNECTORS: tuple[str, ...] = (
    "при этом",
    "тем не менее",
    "однако",
    "также",
    "кроме того",
    "в связи с этим",
    "также стоит",
    "более того",
    "вместе с тем",
    "помимо этого",
    "наряду с этим",
    "в то же время",
)


# ---------------------------------------------------------------------------
# PLATFORM LENGTH SWEET SPOTS (in characters)
# These are ENGAGEMENT-optimal, NOT the platform hard caps. Hard caps live in
# the Pydantic artifact models.
# ---------------------------------------------------------------------------

LENGTH_SWEET_SPOT: dict[str, tuple[int, int]] = {
    "telegram_body": (800, 1500),       # was 600-1500; engagement curve drops fast >1500
    "telegram_long": (1500, 3000),       # acceptable for "лонгрид" topics
    "telegram_hook_first_chars": (0, 120),  # first impressions zone
    "threads_body": (180, 380),          # platform cap 500; engagement-optimal lower
    "reddit_title": (60, 90),
    "reddit_body": (800, 2000),
}


# ---------------------------------------------------------------------------
# CTA RULES — when CTA helps vs hurts; what works in 2026.
# ---------------------------------------------------------------------------

CTA_GUIDANCE: str = (
    "CTA в 2026 чаще мешает, чем помогает. Правила:\n"
    "- Personal-experience пост: CTA НЕ ставить — пост сам себе share-trigger.\n"
    "- Diagnostic / checklist пост: можно save-CTA, формат «Сохрани, если узнал N из M».\n"
    "- Contrarian / inversion пост: спрашивай, не инструктируй («А у вас как?» — да, "
    "«Поделитесь в комментариях» — нет).\n"
    "- Social-threat пост: forward-CTA («Перешли тому, кто на эту тему отмалчивается»).\n"
    "Длина CTA — 1 строка, максимум 2. Запрещены generic фразы «делитесь с друзьями», "
    "«пишите ваше мнение», «сохраняйте, чтобы не потерять полезную информацию»."
)


__all__ = [
    "ALL_BANNED_TELLS",
    "ANTI_CTA_PATTERNS",
    "BANNED_TELLS_TIER_1",
    "BANNED_TELLS_TIER_2",
    "BANNED_TELLS_TIER_3",
    "BANNED_TELLS_TIER_4",
    "BANNED_TELLS_TIER_5",
    "BANNED_TELLS_TIER_6",
    "CONNECTOR_PARAGRAPH_RATIO_LIMIT",
    "CTA_GUIDANCE",
    "DEAD_LEVERS",
    "EM_DASH_PER_1000_LIMIT",
    "EMOTION_TAXONOMY",
    "EMOTION_TAXONOMY_KEYS",
    "EVASION_RULES",
    "FIRST_CHARS_ANCHOR_WINDOW",
    "HOOK_PATTERNS",
    "LENGTH_SWEET_SPOT",
    "SCREENSHOT_PHRASE_MAX_CHARS",
    "SCREENSHOT_PHRASE_MIN_WORDS",
    "SENTENCE_START_CONNECTORS",
    "SENTENCE_VARIANCE_MIN",
    "TRIPLE_PARALLEL_LIMIT_PER_400_WORDS",
    "VAGUE_TIME_MARKERS",
]
