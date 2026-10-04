from src.overnight_digest import CreatorRecord, DigestRequest, build_digest, choose_records


def test_digest_only_keeps_records_with_sales():
    request = DigestRequest([
        CreatorRecord("Mina", "Presets", 3, "launch"),
        CreatorRecord("Jo", "Prompts", 0, "draft"),
    ])
    assert [record.creator for record in choose_records(request)] == ["Mina"]


def test_digest_fetches_non_inline_batch_results(monkeypatch):
    calls = []

    def fake_request(method, url, json=None, headers=None, timeout=None):
        calls.append((method, url, json))
        if url.endswith("/ai/batch/submit"):
            data = {"batch_id": "batch-test"}
        elif url.endswith("/ai/batch/status/batch-test"):
            data = {"state": "completed"}
        elif url.endswith("/ai/batch/results/batch-test"):
            data = {"items": [{"result": {"content": "Sales grew"}}]}
        else:
            assert url.endswith("/pdf/generate")
            assert "Sales grew" in json["markdown"]
            data = {"url": "test.pdf"}

        class Response:
            status_code = 200

            def json(self):
                return {"ok": True, "data": data}

        return Response()

    monkeypatch.setattr("src.overnight_digest.requests.request", fake_request)
    output = build_digest(DigestRequest([CreatorRecord("Mina", "Presets", 3, "launch")]), "test-key")
    assert output["pdf"] == {"url": "test.pdf"}
    assert "model" not in calls[0][2]
    assert [call[0] for call in calls] == ["POST", "GET", "GET", "POST"]
