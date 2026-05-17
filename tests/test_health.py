def test_health_endpoint(client) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True


def test_status_endpoint(client) -> None:
    response = client.get("/status")
    assert response.status_code == 200
    body = response.json()
    assert body["mock_mode"] is True
    assert body["llm_provider"] == "mock"
    assert "adapters" in body
    assert set(body["adapters"].keys()) >= {"anthropic", "openai"}


def test_demo_seed_endpoint_runs(client) -> None:
    response = client.post("/demo/seed")
    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["summary"]["sources"] >= 1
    assert body["summary"]["candidates"] >= 1


def test_trends_endpoint_returns_list(client) -> None:
    client.post("/demo/seed")
    response = client.get("/trends")
    assert response.status_code == 200
    body = response.json()
    assert isinstance(body, list)
    if body:
        first = body[0]
        for key in ("score_breakdown", "total_score", "representative_text"):
            assert key in first


def test_candidates_endpoint(client) -> None:
    client.post("/demo/seed")
    response = client.get("/candidates")
    assert response.status_code == 200
    body = response.json()
    assert isinstance(body, list)


def test_full_flow_blocks_publish_without_approval(client) -> None:
    client.post("/demo/seed")
    candidates = client.get("/candidates").json()
    draft = next((c for c in candidates if c["status"] == "draft"), None)
    if draft is None:
        return
    res = client.post(
        "/publishing/jobs",
        json={"candidate_id": draft["id"], "platform": "telegram"},
    )
    assert res.status_code == 409
    assert "approved" in res.json()["detail"].lower()
