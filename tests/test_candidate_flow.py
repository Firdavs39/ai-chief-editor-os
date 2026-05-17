from chief_editor.models import StyleProfile, TrendCluster
from chief_editor.services.candidate import generate_for_cluster


def test_generate_for_cluster_creates_candidate(session) -> None:
    style = StyleProfile(
        name="default",
        tone="expert",
        audience="creators",
        target_topics=["AI", "контент"],
        example_posts=["AI редактор работает как соавтор."],
    )
    cluster = TrendCluster(
        representative_text="Threads-first стратегия для русскоязычных авторов",
        keywords=["threads", "russian", "creators"],
        category="ru",
        total_score=0.8,
    )
    session.add_all([style, cluster])
    session.commit()

    candidate = generate_for_cluster(session, cluster)
    assert candidate.id
    assert candidate.tg_version
    assert candidate.threads_version
    assert candidate.status == "draft"
    assert isinstance(candidate.critic_notes, list)
