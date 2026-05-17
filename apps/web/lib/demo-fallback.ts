// Visual fallback dataset so the dashboard never looks empty even before
// the API is reachable / the seed has run.

import type {
  AnalyticsResponse,
  CalendarEntry,
  Candidate,
  PublishJob,
  Source,
  StyleProfile,
  Trend,
} from "./types";

const now = () => new Date().toISOString();
const future = (h: number) =>
  new Date(Date.now() + h * 3_600_000).toISOString();
const past = (h: number) =>
  new Date(Date.now() - h * 3_600_000).toISOString();

export const demoSources: Source[] = [
  {
    id: "s1",
    kind: "telegram",
    handle: "@durov",
    url: "https://t.me/durov",
    title: "Pavel Durov",
    weight: 9.0,
    enabled: true,
    last_collected_at: past(0.5),
    health: { ok: true },
    created_at: past(72),
  },
  {
    id: "s2",
    kind: "telegram",
    handle: "@TechProRu",
    url: "https://t.me/TechProRu",
    title: "TechPro RU",
    weight: 7.5,
    enabled: true,
    last_collected_at: past(0.2),
    health: { ok: true },
    created_at: past(70),
  },
  {
    id: "s3",
    kind: "reddit",
    handle: "r/creatoreconomy",
    url: "https://reddit.com/r/creatoreconomy",
    title: "Creator Economy",
    weight: 7.0,
    enabled: true,
    last_collected_at: past(1),
    health: { ok: true },
    created_at: past(70),
  },
  {
    id: "s4",
    kind: "reddit",
    handle: "r/socialmedia",
    url: "https://reddit.com/r/socialmedia",
    title: "Social Media",
    weight: 6.5,
    enabled: true,
    last_collected_at: past(2),
    health: { ok: true },
    created_at: past(70),
  },
  {
    id: "s5",
    kind: "rss",
    handle: "anthropic-news",
    url: "https://www.anthropic.com/news/rss.xml",
    title: "Anthropic News",
    weight: 8.5,
    enabled: true,
    last_collected_at: past(0.1),
    health: { ok: true },
    created_at: past(60),
  },
  {
    id: "s6",
    kind: "rss",
    handle: "vc-ru-tech",
    url: "https://vc.ru/rss/tech",
    title: "VC.ru — Tech",
    weight: 6.0,
    enabled: false,
    last_collected_at: past(20),
    health: { ok: false, note: "feed temporarily unavailable" },
    created_at: past(50),
  },
];

export const demoTrends: Trend[] = [
  {
    id: "t1",
    representative_text:
      "Threads-first стратегия для русскоязычных авторов: тестируем заголовки до выхода в Telegram",
    keywords: ["threads", "стратегия", "русскоязычный", "telegram"],
    category: "ru",
    signal_count: 14,
    first_seen_at: past(20),
    last_seen_at: past(0.4),
    score_breakdown: {
      recency: 0.92,
      engagement: 0.78,
      source_weight: 0.78,
      novelty: 0.71,
      controversy: 0.05,
      usefulness: 0.82,
      style_fit: 0.83,
      total: 0.79,
    },
    total_score: 0.79,
    sources_summary: [
      { handle: "@TechProRu", count: 6 },
      { handle: "@durov", count: 4 },
      { handle: "anthropic-news", count: 2 },
      { handle: "r/socialmedia", count: 2 },
    ],
  },
  {
    id: "t2",
    representative_text:
      "AI-агенты как редакторы контента: пайплайны, где LLM правит черновики автора, а не пишет с нуля",
    keywords: ["AI", "редактор", "пайплайн", "голос"],
    category: "ru",
    signal_count: 11,
    first_seen_at: past(28),
    last_seen_at: past(1),
    score_breakdown: {
      recency: 0.85,
      engagement: 0.82,
      source_weight: 0.7,
      novelty: 0.66,
      controversy: 0.02,
      usefulness: 0.88,
      style_fit: 0.79,
      total: 0.74,
    },
    total_score: 0.74,
    sources_summary: [
      { handle: "anthropic-news", count: 4 },
      { handle: "@TechProRu", count: 4 },
      { handle: "r/creatoreconomy", count: 3 },
    ],
  },
  {
    id: "t3",
    representative_text:
      "Микроформат коротких заметок (200–400 символов) в Telegram даёт +30% просмотров и +60% досмотров",
    keywords: ["telegram", "коротко", "форматы", "досматриваемость"],
    category: "ru",
    signal_count: 9,
    first_seen_at: past(18),
    last_seen_at: past(0.3),
    score_breakdown: {
      recency: 0.94,
      engagement: 0.74,
      source_weight: 0.75,
      novelty: 0.5,
      controversy: 0,
      usefulness: 0.78,
      style_fit: 0.81,
      total: 0.7,
    },
    total_score: 0.7,
    sources_summary: [
      { handle: "@TechProRu", count: 5 },
      { handle: "@durov", count: 2 },
      { handle: "r/socialmedia", count: 2 },
    ],
  },
  {
    id: "t4",
    representative_text:
      "Падение охватов в Instagram у русскоязычных авторов на 15–25% — миграция в Telegram и Threads",
    keywords: ["instagram", "охваты", "миграция", "threads"],
    category: "ru",
    signal_count: 8,
    first_seen_at: past(36),
    last_seen_at: past(3),
    score_breakdown: {
      recency: 0.78,
      engagement: 0.7,
      source_weight: 0.65,
      novelty: 0.6,
      controversy: 0.25,
      usefulness: 0.72,
      style_fit: 0.74,
      total: 0.66,
    },
    total_score: 0.66,
    sources_summary: [
      { handle: "@TechProRu", count: 3 },
      { handle: "r/socialmedia", count: 3 },
      { handle: "vc-ru-tech", count: 2 },
    ],
  },
  {
    id: "t5",
    representative_text:
      "Postiz публикует roadmap на Threads API: scheduling + аналитика для русскоязычных авторов",
    keywords: ["postiz", "threads", "api", "roadmap"],
    category: "ru",
    signal_count: 7,
    first_seen_at: past(22),
    last_seen_at: past(0.8),
    score_breakdown: {
      recency: 0.9,
      engagement: 0.6,
      source_weight: 0.85,
      novelty: 0.78,
      controversy: 0,
      usefulness: 0.69,
      style_fit: 0.76,
      total: 0.69,
    },
    total_score: 0.69,
    sources_summary: [
      { handle: "anthropic-news", count: 2 },
      { handle: "@TechProRu", count: 3 },
      { handle: "r/creatoreconomy", count: 2 },
    ],
  },
  {
    id: "t6",
    representative_text:
      "Creator economy 2026: AI co-authors теперь базовое требование, а не преимущество",
    keywords: ["creator", "ai", "workflow", "baseline"],
    category: "en",
    signal_count: 12,
    first_seen_at: past(30),
    last_seen_at: past(2),
    score_breakdown: {
      recency: 0.7,
      engagement: 0.88,
      source_weight: 0.65,
      novelty: 0.55,
      controversy: 0.1,
      usefulness: 0.74,
      style_fit: 0.65,
      total: 0.65,
    },
    total_score: 0.65,
    sources_summary: [
      { handle: "r/creatoreconomy", count: 7 },
      { handle: "r/socialmedia", count: 3 },
    ],
  },
];

export const demoCandidates: Candidate[] = [
  {
    id: "c1",
    cluster_id: "t1",
    topic: "Threads-first для русскоязычных авторов",
    source_summary:
      "За последние сутки несколько ru-каналов начали публиковать сначала в Threads, потом кросс-постить в TG. Сигналы пересекаются по словам: threads, стратегия, заголовки.",
    why_it_matters:
      "Threads даёт ранний сигнал реакции аудитории и позволяет переписать заголовок до основной публикации в TG.",
    psychology_hook: "Никто не говорит об этом вслух, но",
    tg_version:
      "Никто не говорит об этом вслух, но топ-ru-авторы перешли на Threads-first.\n\nСхема: сначала короткий тезис в Threads → смотрят, какой заголовок выстрелил → только потом разворачивают в полноценный TG-пост.\n\nПочему это работает: Threads даёт быстрый и дешевый A/B по заголовкам. Алгоритм Telegram любит готовый, отполированный хук. Если совмещать — выигрыш в охватах +20-40%.\n\nСохрани схему, попробуй на следующем посте — увидишь сам.",
    threads_version:
      "Топ-ru-авторы перешли на Threads-first. Сначала тестируют тезис здесь, потом разворачивают в TG. Дешёвый A/B по заголовкам — и +20-40% к охватам. Кто заметил это у себя в ленте?",
    reddit_version:
      "Russian-speaking creators have started testing Threads-first publishing. The pattern: post a short take on Threads, watch which headline lands, then expand into a full Telegram post. Threads becomes a cheap A/B-testing layer for headlines.",
    cta: "Сохрани схему, попробуй на следующем посте — увидишь сам.",
    style_match_score: 0.86,
    viral_score: 0.78,
    slop_risk: 0.12,
    controversy_risk: 0.05,
    recommendation: "approve",
    critic_notes: [
      {
        check: "weak_cta",
        severity: "low",
        note: "CTA сильный, но можно сделать ещё конкретнее: «попробуй сегодня и сравни охваты».",
      },
    ],
    status: "draft",
    version: 1,
    created_at: past(2),
  },
  {
    id: "c2",
    cluster_id: "t2",
    topic: "AI-редактор, не AI-писатель",
    source_summary:
      "Появились первые рабочие пайплайны, где LLM не пишет с нуля, а правит черновики автора, сохраняя голос.",
    why_it_matters:
      "Главный сдвиг: AI перестал быть генератором, стал редактором. Это меняет роль автора, а не заменяет её.",
    psychology_hook: "Самое неудобное наблюдение недели:",
    tg_version:
      "Самое неудобное наблюдение недели: AI-редактор работает в 3 раза лучше, чем AI-писатель.\n\nКогда LLM пишет с нуля — получается водянистый, среднестатистический текст. Когда LLM правит ваш черновик с инструкцией «не меняй голос, убери только слабое» — выходит ваш текст, только острее.\n\nПрактически: пишите как обычно. Прогоняйте через AI-редактора с конкретными правками. Не доверяйте «улучшить весь текст» — это убивает голос.\n\nПопробуй на следующем посте: напиши черновик, потом дай AI задачу «убери три самых слабых предложения».",
    threads_version:
      "AI-редактор работает в 3 раза лучше, чем AI-писатель. Пиши сам, потом проси AI вырезать самое слабое — и голос остаётся твой, а текст становится острее.",
    reddit_version:
      "Spotted the same pattern across multiple creator workflows: LLMs are way better as editors than as generators. Write yourself, then ask the model to remove the weakest sentences — your voice stays, the text gets sharper.",
    cta: "Попробуй на следующем посте: напиши черновик, потом дай AI задачу «убери три самых слабых предложения».",
    style_match_score: 0.91,
    viral_score: 0.82,
    slop_risk: 0.08,
    controversy_risk: 0.02,
    recommendation: "approve",
    critic_notes: [],
    status: "draft",
    version: 1,
    created_at: past(3),
  },
  {
    id: "c3",
    cluster_id: "t3",
    topic: "Короткий формат TG: 200-400 символов",
    source_summary:
      "Микроформат в Telegram даёт +30% просмотров и +60% досматриваемости. Алгоритм поднимает короткие посты с высоким досмотром.",
    why_it_matters:
      "Короткий формат меняет экономику канала: меньше времени на пост, больше охвата, выше частота публикаций.",
    psychology_hook: "Тихая революция, которую все пропустили:",
    tg_version:
      "Тихая революция, которую все пропустили: короткие посты в Telegram (200-400 символов) обгоняют лонгриды по охватам на 30%, а по досмотру — на 60%.\n\nЛогика проста: алгоритм поднимает то, что дочитывают. Короткий пост дочитывают почти все. Лонгрид — единицы.\n\nЭто не значит «больше не пишите длинные». Это значит: одна большая мысль в неделю + 4-5 коротких ежедневно.\n\nСохрани, если планируешь пересмотреть контент-план.",
    threads_version:
      "Короткие посты (200-400 символов) в TG обгоняют лонгриды на +30% по охвату и +60% по досмотру. Алгоритм поднимает то, что дочитывают.",
    reddit_version:
      "Russian-language Telegram channels are noticing micro-format posts (200-400 chars) outperforming long-form by ~30% on reach and 60% on read-through. The algorithm prefers content that gets finished.",
    cta: "Сохрани, если планируешь пересмотреть контент-план.",
    style_match_score: 0.84,
    viral_score: 0.74,
    slop_risk: 0.14,
    controversy_risk: 0,
    recommendation: "approve",
    critic_notes: [
      {
        check: "factual_uncertainty",
        severity: "medium",
        note: "Цифры 30%/60% выглядят сильными — добавь источник или собственный замер.",
      },
    ],
    status: "draft",
    version: 1,
    created_at: past(5),
  },
  {
    id: "c4",
    cluster_id: "t6",
    topic: "AI co-authors стали обязательной гигиеной",
    source_summary:
      "Опрос 40 авторов с аудиторией 50k+ — у 32 уже встроен AI в воркфлоу.",
    why_it_matters:
      "AI больше не преимущество, а базовое требование. Кто не встроил — отстаёт по скорости и качеству.",
    psychology_hook: "Если коротко, индустрия снова сделала разворот —",
    tg_version:
      "Если коротко, индустрия снова сделала разворот — AI-соавторы из «преимущества» стали «гигиеной».\n\n80% авторов с аудиторией 50k+ уже встроили AI в свой workflow. Не для того, чтобы писать за них. Для ресерча, переписывания и убирания самого слабого.\n\nЕсли вы всё ещё думаете «нужен ли мне AI» — вы уже отстали. Вопрос теперь другой: «как встроить так, чтобы не потерять голос».\n\nСохрани и обсуди с командой на следующем созвоне.",
    threads_version:
      "AI-соавторы перестали быть преимуществом. У 80% авторов с аудиторией 50k+ они уже встроены в workflow. Не для замены — для ускорения и редактуры.",
    reddit_version:
      "I surveyed 40 creators with 50k+ audiences. 32 already have AI assistants embedded in their workflow — for research, rewriting, and trimming. AI co-authorship has shifted from competitive edge to baseline hygiene.",
    cta: "Сохрани и обсуди с командой на следующем созвоне.",
    style_match_score: 0.78,
    viral_score: 0.71,
    slop_risk: 0.18,
    controversy_risk: 0.08,
    recommendation: "revise",
    critic_notes: [
      {
        check: "too_generic",
        severity: "medium",
        note: "Часть про «вы уже отстали» звучит банально — переформулируйте мягче.",
      },
    ],
    status: "draft",
    version: 1,
    created_at: past(7),
  },
  {
    id: "c5",
    cluster_id: "t4",
    topic: "Миграция авторов из Instagram",
    source_summary:
      "Охваты в Instagram у крупных ru-авторов упали на 15-25%. Threads сильнее TG как канал миграции.",
    why_it_matters:
      "Threads выигрывает у TG в discovery: алгоритм даёт холодную аудиторию даже маленьким авторам.",
    psychology_hook: "Закономерность, которую видно только если смотреть на цифры:",
    tg_version:
      "Закономерность, которую видно только если смотреть на цифры: ru-авторы массово уходят из Instagram, но идут не в Telegram — а в Threads.\n\nПричина проста: TG требует, чтобы тебя уже знали. Threads даёт холодную аудиторию даже маленьким каналам через алгоритм.\n\nПрактический вывод: если у тебя <10k подписчиков и ты пытаешься расти — Threads сейчас дешевле и быстрее, чем Telegram.\n\nПерешли тому, кто всё ещё думает, что Threads — это «twitter-лайт».",
    threads_version:
      "Ru-авторы уходят из Instagram, но идут не в TG, а сюда. Threads даёт холодную аудиторию, TG требует, чтобы тебя уже знали. Логичный выбор для маленьких каналов.",
    reddit_version:
      "Russian creators are leaving Instagram (-15-25% reach over two weeks). They're not migrating to Telegram — they're going to Threads. Threads gives cold audience via its algorithm; Telegram requires existing distribution.",
    cta: "Перешли тому, кто всё ещё думает, что Threads — это «twitter-лайт».",
    style_match_score: 0.82,
    viral_score: 0.76,
    slop_risk: 0.1,
    controversy_risk: 0.18,
    recommendation: "approve",
    critic_notes: [],
    status: "approved",
    version: 2,
    created_at: past(10),
  },
  {
    id: "c6",
    cluster_id: "t5",
    topic: "Postiz Threads API",
    source_summary:
      "Postiz выпустил интеграцию с официальным Threads API: scheduling и аналитика.",
    why_it_matters:
      "Закрыт последний пробел в кросс-постинговых платформах для русскоязычных авторов.",
    psychology_hook: "Если коротко, индустрия снова сделала разворот —",
    tg_version:
      "Если коротко, индустрия снова сделала разворот — теперь Threads можно публиковать через Postiz с расписанием и аналитикой, как любую другую платформу.\n\nЭто закрывает последний пробел в кросс-постинговых тулзах. До этого Threads приходилось публиковать вручную — теперь его можно держать в общем pipeline с Telegram, X, и Reddit.\n\nПерешли в команду — особенно тем, кто отвечает за расписание контента.",
    threads_version:
      "Postiz теперь поддерживает официальный Threads API: scheduling и аналитика. Threads встаёт в общий pipeline с TG, X и Reddit. Последний пробел в кросс-постинге закрыт.",
    reddit_version:
      "Postiz just shipped an official Threads API integration with scheduling and analytics. This closes the last gap in cross-posting tooling for Russian-speaking creators who already use Postiz for TG/X/Reddit.",
    cta: "Перешли в команду — особенно тем, кто отвечает за расписание контента.",
    style_match_score: 0.75,
    viral_score: 0.62,
    slop_risk: 0.16,
    controversy_risk: 0,
    recommendation: "approve",
    critic_notes: [],
    status: "published",
    version: 1,
    created_at: past(20),
  },
  {
    id: "c7",
    cluster_id: "t1",
    topic: "Алгоритм Threads ru-сегмента",
    source_summary: "Threads показывает русскоязычные треды англоязычной аудитории.",
    why_it_matters: "Это открывает русскоязычным авторам доступ к глобальному рынку без перевода.",
    psychology_hook: "Возможно, кажется, наверное, AI-агенты в редактуре",
    tg_version:
      "Возможно, кажется, наверное, AI-агенты в редактуре могут быть полезны.",
    threads_version: "Возможно AI поможет.",
    reddit_version: "Maybe AI agents can help with editorial.",
    cta: "интересно",
    style_match_score: 0.34,
    viral_score: 0.22,
    slop_risk: 0.72,
    controversy_risk: 0.04,
    recommendation: "reject",
    critic_notes: [
      { check: "weak_hook", severity: "high", note: "Слишком много hedge-слов." },
      { check: "weak_cta", severity: "high", note: "CTA не содержит действия." },
      { check: "too_generic", severity: "medium", note: "Нет конкретики." },
    ],
    status: "rejected",
    version: 1,
    created_at: past(24),
  },
];

export const demoCalendar: CalendarEntry[] = [
  {
    job_id: "j1",
    candidate_id: "c5",
    topic: "Миграция авторов из Instagram",
    platform: "telegram",
    scheduled_at: future(2),
    status: "pending",
    cta: "Перешли тому, кто всё ещё думает, что Threads — это «twitter-лайт».",
    tg_preview:
      "Закономерность, которую видно только если смотреть на цифры: ru-авторы уходят из Instagram в Threads…",
    threads_preview:
      "Ru-авторы уходят из Instagram, но идут не в TG, а сюда…",
  },
  {
    job_id: "j2",
    candidate_id: "c2",
    topic: "AI-редактор, не AI-писатель",
    platform: "threads",
    scheduled_at: future(18),
    status: "pending",
    cta: "Попробуй на следующем посте.",
    tg_preview: "Самое неудобное наблюдение недели: AI-редактор работает в 3 раза лучше…",
    threads_preview: "AI-редактор работает в 3 раза лучше, чем AI-писатель.",
  },
  {
    job_id: "j3",
    candidate_id: "c6",
    topic: "Postiz Threads API",
    platform: "telegram",
    scheduled_at: past(4),
    status: "done",
    cta: "Перешли в команду.",
    tg_preview: "Если коротко, индустрия снова сделала разворот — Postiz + Threads API…",
    threads_preview: "Postiz теперь поддерживает официальный Threads API.",
  },
  {
    job_id: "j4",
    candidate_id: "c3",
    topic: "Короткий формат TG",
    platform: "threads",
    scheduled_at: future(40),
    status: "pending",
    cta: "Сохрани, если планируешь пересмотреть контент-план.",
    tg_preview: "Тихая революция, которую все пропустили: короткие посты в Telegram…",
    threads_preview: "Короткие посты обгоняют лонгриды на +30% и +60%.",
  },
  {
    job_id: "j5",
    candidate_id: "c1",
    topic: "Threads-first стратегия",
    platform: "reddit",
    scheduled_at: future(62),
    status: "pending",
    cta: "Сохрани схему.",
    tg_preview: "Никто не говорит вслух: топ-ru-авторы перешли на Threads-first.",
    threads_preview: "Топ-ru-авторы перешли на Threads-first.",
  },
];

export const demoJobs: PublishJob[] = demoCalendar.map((c) => ({
  id: c.job_id,
  candidate_id: c.candidate_id,
  approval_id: "a-mock",
  platform: c.platform as PublishJob["platform"],
  scheduled_at: c.scheduled_at,
  status: c.status as PublishJob["status"],
  idempotency_key: "k-" + c.job_id,
  created_at: past(48),
}));

export const demoStyle: StyleProfile = {
  id: "style-1",
  name: "default",
  lang_primary: "ru",
  tone: "Экспертно, по-человечески, без воды. Прямой разговор с думающим читателем.",
  audience: "Создатели контента и продактовые маркетологи 24-40 лет, ru-RU.",
  banned_phrases: [
    "в эпоху технологий",
    "давайте погрузимся",
    "не секрет, что",
    "в современном мире",
    "стоит отметить",
  ],
  example_posts: [
    "Я перестал верить в большие охваты. Маленькая, но горячая аудитория монетизируется в 8 раз лучше — и не выгорает.",
    "Threads — это новый ru-Twitter, только без токсичности и с алгоритмом, который любит длинные мысли. Кто заметил это раньше всех, уже собирает аудиторию бесплатно.",
    "AI-редактор — не тот, кто пишет за тебя. Это тот, кто говорит «здесь скучно» — и заставляет переписать сцену.",
  ],
  writing_rules:
    "1) Первые 80 символов — крючок, не вступление. 2) Один пост — одна мысль. 3) Цифры или конкретный пример обязательны. 4) Никаких канцеляризмов и ИИ-штампов. 5) CTA — повелительный глагол, не вопрос.",
  target_topics: [
    "AI и контент",
    "creator economy",
    "Telegram-рост",
    "Threads",
    "монетизация контента",
    "редактура",
    "stylometry",
  ],
  voice_sliders: { expert: 0.85, playful: 0.4, contrarian: 0.7, warm: 0.6 },
  updated_at: past(48),
};

export const demoAnalytics: AnalyticsResponse = {
  totals: {
    candidates: 24,
    approved: 11,
    rejected: 5,
    scheduled: 4,
    published: 7,
    sources: 6,
  },
  by_hook_type: [
    { hook_type: "contrarian", posts: 8, viral_avg: 0.82, reach_avg: 0.86 },
    { hook_type: "observation", posts: 9, viral_avg: 0.74, reach_avg: 0.79 },
    { hook_type: "instructional", posts: 4, viral_avg: 0.68, reach_avg: 0.71 },
    { hook_type: "question", posts: 3, viral_avg: 0.55, reach_avg: 0.62 },
  ],
  by_source: [
    { source: "@TechProRu", posts: 9, avg_engagement: 4820, avg_style_match: 0.88 },
    { source: "@durov", posts: 5, avg_engagement: 3940, avg_style_match: 0.82 },
    { source: "anthropic-news", posts: 4, avg_engagement: 2730, avg_style_match: 0.76 },
    { source: "r/creatoreconomy", posts: 4, avg_engagement: 2180, avg_style_match: 0.71 },
    { source: "r/socialmedia", posts: 2, avg_engagement: 1640, avg_style_match: 0.65 },
  ],
  best_patterns: [
    {
      title: "Лучше всего работают «контрарные» крючки",
      detail: "средний viral score: 0.82",
      kind: "hook",
    },
    {
      title: "Источник @TechProRu даёт лучший отклик",
      detail: "avg engagement: 4820",
      kind: "source",
    },
    { title: "Approval rate", detail: "68% утверждено", kind: "ratio" },
  ],
  learning_timeline: Array.from({ length: 14 }).map((_, i) => ({
    date: new Date(Date.now() - (13 - i) * 86_400_000).toISOString().slice(0, 10),
    posts: 1 + Math.floor(Math.random() * 4),
    avg_engagement: Math.round(2000 + Math.random() * 4000),
  })),
};

export const demoFallbacks = {
  status: {
    ok: true,
    app_env: "dev",
    mock_mode: true,
    llm_provider: "mock",
    timezone: "Asia/Tashkent",
    adapters: {
      anthropic: false,
      openai: false,
      telethon: false,
      reddit: false,
      telegram_publish: false,
      postiz: false,
    },
  },
  sources: demoSources,
  trends: demoTrends,
  candidates: demoCandidates,
  calendar: demoCalendar,
  jobs: demoJobs,
  style: demoStyle,
  analytics: demoAnalytics,
};
