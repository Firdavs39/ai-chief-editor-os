"""Text normalization, hashing, Jaccard similarity, cluster assignment."""

from __future__ import annotations

import hashlib
import re
from collections.abc import Iterable
from dataclasses import dataclass

_URL_RE = re.compile(r"https?://\S+|www\.\S+|t\.me/\S+")
_NON_WORD_RE = re.compile(r"[^0-9a-zA-Zа-яА-ЯёЁ\s]")
_WHITESPACE_RE = re.compile(r"\s+")

_STOP_RU = {
    "и", "в", "на", "с", "по", "за", "это", "что", "как", "к", "у", "о",
    "не", "из", "от", "до", "для", "же", "бы", "но", "или", "так", "то",
}
_STOP_EN = {
    "the", "and", "for", "with", "this", "that", "from", "have", "are",
    "was", "but", "you", "your", "our", "their", "they", "its", "into",
}


def normalize(text: str) -> str:
    text = text.lower()
    text = _URL_RE.sub(" ", text)
    text = _NON_WORD_RE.sub(" ", text)
    text = _WHITESPACE_RE.sub(" ", text).strip()
    return text


def tokens(text: str) -> set[str]:
    norm = normalize(text)
    return {
        t for t in norm.split() if len(t) >= 3 and t not in _STOP_RU and t not in _STOP_EN
    }


def text_hash(text: str) -> str:
    norm = normalize(text)
    return hashlib.sha1(norm.encode("utf-8")).hexdigest()


def jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    inter = len(a & b)
    union = len(a | b)
    return inter / union if union else 0.0


@dataclass
class ClusterMatch:
    cluster_id: str
    similarity: float


def assign_cluster(
    item_text: str,
    candidates: Iterable[tuple[str, str]],
    threshold: float = 0.35,
) -> ClusterMatch | None:
    """Return the best-matching cluster or None.

    `candidates` is an iterable of (cluster_id, representative_text).
    Lower threshold than 0.5 because Russian text + tokens dropping stop-words
    makes Jaccard naturally smaller than English.
    """
    item_tokens = tokens(item_text)
    best: ClusterMatch | None = None
    for cluster_id, rep in candidates:
        sim = jaccard(item_tokens, tokens(rep))
        if sim >= threshold and (best is None or sim > best.similarity):
            best = ClusterMatch(cluster_id=cluster_id, similarity=sim)
    return best
