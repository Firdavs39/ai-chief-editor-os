from chief_editor.services.dedup import assign_cluster, jaccard, normalize, text_hash, tokens


def test_normalize_strips_urls_and_punct() -> None:
    out = normalize("Привет! Посмотри https://t.me/x — это интересно.")
    assert "https" not in out
    assert "—" not in out
    assert "привет" in out


def test_jaccard_overlap() -> None:
    a = tokens("Telegram Premium монетизация контента")
    b = tokens("Premium подписка Telegram монетизация")
    assert 0.3 < jaccard(a, b) < 0.9


def test_text_hash_is_stable() -> None:
    assert text_hash("Telegram запускает!") == text_hash("Telegram запускает!")
    assert text_hash("a") != text_hash("b")


def test_assign_cluster_matches_similar() -> None:
    rep = "Threads Russian creators publishing strategy"
    candidates = [("c1", rep), ("c2", "Reddit gardening tips for fall season")]
    match = assign_cluster(
        "Russian Threads creators announce a new publishing strategy",
        candidates,
        threshold=0.3,
    )
    assert match is not None
    assert match.cluster_id == "c1"


def test_assign_cluster_returns_none_below_threshold() -> None:
    candidates = [("c1", "spaceflight astronomy NASA"), ("c2", "knitting wool craft")]
    match = assign_cluster("Telegram premium monetization", candidates, threshold=0.5)
    assert match is None
