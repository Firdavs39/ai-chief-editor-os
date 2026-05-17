"""Deterministic mock collector. Returns realistic Russian-first items."""

from __future__ import annotations

import hashlib
import random
from datetime import timedelta

from ..models import Source
from ..time_utils import utcnow
from .base import CollectedItem, Collector

_TG_CORPUS = [
    {
        "title": "Микроформат коротких заметок в Telegram",
        "body": (
            "Авторы малых каналов начали публиковать заметки длиной 200–400 символов "
            "вместо лонгридов. Просмотры растут на 30%, дочитываемость на 60%. "
            "Алгоритм поднимает короткие посты с высоким досмотром."
        ),
        "keywords": ["telegram", "коротко", "форматы", "досматриваемость"],
        "engagement": {"views": 18400, "reactions": 612, "comments": 84, "shares": 73},
    },
    {
        "title": "Threads-first стратегия для русскоязычных авторов",
        "body": (
            "Несколько ru-каналов начали тестировать публикацию сначала в Threads, "
            "затем кросс-постинг в Telegram. Threads даёт ранний сигнал реакции "
            "аудитории и позволяет переписать заголовок для TG до основной публикации."
        ),
        "keywords": ["threads", "стратегия", "кросс-постинг", "русскоязычный"],
        "engagement": {"views": 24100, "reactions": 980, "comments": 145, "shares": 210},
    },
    {
        "title": "AI-агенты как редакторы контента",
        "body": (
            "Появились первые работающие пайплайны, где LLM играет роль редактора: "
            "не пишет с нуля, а правит черновики автора, сохраняя голос. Эффект — "
            "ускорение выхода материала в 3 раза без потери стиля."
        ),
        "keywords": ["AI", "редактор", "пайплайн", "голос автора"],
        "engagement": {"views": 31200, "reactions": 1450, "comments": 232, "shares": 287},
    },
    {
        "title": "Падение охватов в Instagram у русскоязычных авторов",
        "body": (
            "За последние две недели охваты у крупных русскоязычных авторов в "
            "Instagram упали на 15–25%. Сообщество обсуждает миграцию контента в "
            "Telegram и Threads. Threads выглядит сильнее из-за алгоритма."
        ),
        "keywords": ["instagram", "охваты", "миграция", "threads"],
        "engagement": {"views": 15800, "reactions": 520, "comments": 198, "shares": 64},
    },
]

_REDDIT_CORPUS = [
    {
        "title": "Creator economy 2026: AI co-authors are now a baseline expectation",
        "body": (
            "Я опросил 40 авторов с аудиторией 50k+. У 32 из них в воркфлоу уже встроены "
            "AI-помощники: для черновиков, ресерча и переписывания. Это перестало быть "
            "конкурентным преимуществом — теперь это базовая гигиена."
        ),
        "keywords": ["creator", "ai", "workflow", "baseline"],
        "engagement": {"upvotes": 1240, "comments": 312, "score_ratio": 0.94},
    },
    {
        "title": "Telegram premium-каналы: модель подписки без воды",
        "body": (
            "Эксперимент: 3 канала перевели часть контента в платную подписку через TG "
            "Boost. Через 30 дней конверсия в платных подписчиков — 4.2%, при этом "
            "охваты бесплатной части не просели. Гипотеза: эксклюзивность повышает "
            "ценность всего канала."
        ),
        "keywords": ["telegram", "premium", "подписка", "boost"],
        "engagement": {"upvotes": 870, "comments": 154, "score_ratio": 0.91},
    },
    {
        "title": "Threads vs X для b2b-контента: первые цифры",
        "body": (
            "Сравнил неделю публикаций одинаковых тезисов в Threads и X. Threads — "
            "в 2.3 раза больше реакций, X — в 1.7 раз больше переходов на сайт. "
            "Threads сильнее в discovery, X сильнее в конверсии."
        ),
        "keywords": ["threads", "x", "b2b", "discovery", "conversion"],
        "engagement": {"upvotes": 540, "comments": 98, "score_ratio": 0.88},
    },
]

_RSS_CORPUS = [
    {
        "title": "Postiz публикует roadmap на Threads API",
        "body": (
            "В новом релизе Postiz появилась прямая интеграция с официальным Threads API. "
            "Это закрывает последний пробел в кросс-постинговых платформах для "
            "русскоязычных авторов. Поддержка scheduling и аналитики."
        ),
        "keywords": ["postiz", "threads", "api", "roadmap"],
        "engagement": {"views": 6200, "shares": 84, "comments": 0},
    },
    {
        "title": "Anthropic выпустила Claude Opus 4.7 — упор на длинный контекст",
        "body": (
            "Новая модель Anthropic ориентирована на работу с большими корпусами "
            "и длинными цепочками рассуждений. Для контент-команд это значит, что "
            "можно загружать всю историю канала и просить редактуру на её основе."
        ),
        "keywords": ["anthropic", "claude", "opus", "context"],
        "engagement": {"views": 12400, "shares": 312, "comments": 0},
    },
    {
        "title": "Sprout Social купила Tagger Media за $140M",
        "body": (
            "Сделка консолидирует influencer-аналитику и social-suite. Сигнал: рынок "
            "движется в сторону единых платформ, где мониторинг, генерация и публикация "
            "находятся в одной воронке."
        ),
        "keywords": ["sprout social", "m&a", "consolidation", "social suite"],
        "engagement": {"views": 8900, "shares": 156, "comments": 0},
    },
]


def _corpus_for(source: Source) -> list[dict]:
    if source.kind == "telegram":
        return _TG_CORPUS
    if source.kind == "reddit":
        return _REDDIT_CORPUS
    return _RSS_CORPUS


def _stable_external_id(handle: str, idx: int, title: str) -> str:
    raw = f"{handle}|{idx}|{title}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]


class MockCollector(Collector):
    name = "mock"

    async def fetch(self, source: Source, limit: int = 50) -> list[CollectedItem]:
        corpus = _corpus_for(source)
        rng = random.Random(hashlib.sha1(source.handle.encode()).hexdigest())
        items: list[CollectedItem] = []
        now = utcnow()
        for idx, entry in enumerate(corpus[:limit]):
            hours_ago = rng.uniform(0.5, 36.0)
            posted_at = now - timedelta(hours=hours_ago)
            jitter = 0.9 + rng.random() * 0.4
            engagement = {k: int(v * jitter) if isinstance(v, (int | float)) else v
                          for k, v in entry["engagement"].items()}
            items.append(
                CollectedItem(
                    external_id=_stable_external_id(source.handle, idx, entry["title"]),
                    title=entry["title"],
                    body=entry["body"],
                    url=f"{source.url or 'mock://' + source.handle}/p/{idx}",
                    lang="ru",
                    engagement=engagement,
                    posted_at=posted_at,
                )
            )
        return items
