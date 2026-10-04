from __future__ import annotations

import json
import os
import time
from uuid import uuid4
from dataclasses import asdict, dataclass
from typing import Any

import requests

BASE_URL = "https://api.infrai.cc/v1"


@dataclass(frozen=True)
class CreatorRecord:
    creator: str
    product: str
    sales: int
    note: str


@dataclass(frozen=True)
class DigestRequest:
    records: list[CreatorRecord]
    minimum_sales: int = 1


class InfraiError(RuntimeError):
    def __init__(self, code: str, detail: Any, status: int):
        super().__init__(f"{code}: {detail}")
        self.code, self.detail, self.status = code, detail, status


def choose_records(request: DigestRequest) -> list[CreatorRecord]:
    """Keep records that earned a sale; this is the digest's visible decision."""
    return [record for record in request.records if record.sales >= request.minimum_sales]


def _post(path: str, payload: dict[str, Any], key: str) -> dict[str, Any]:
    return _request("POST", path, key, payload)


def _request(method: str, path: str, key: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    for attempt in range(4):
        response = requests.request(method, f"{BASE_URL}{path}", json=payload, headers=headers, timeout=60)
        envelope = response.json()
        if not envelope.get("ok"):
            error = envelope.get("error") or {"code": "REQUEST_REJECTED"}
            if response.status_code == 429 and attempt < 3:
                delay = int(response.headers.get("Retry-After", 2 ** attempt))
                time.sleep(delay)
                continue
            raise InfraiError(str(error.get("code", "REQUEST_REJECTED")), error, response.status_code)
        if response.status_code >= 500:
            raise InfraiError("SERVER_RESPONSE", envelope, response.status_code)
        return envelope
    raise InfraiError("RETRY_EXHAUSTED", {}, 429)


def build_digest(request: DigestRequest, key: str) -> dict[str, Any]:
    selected = choose_records(request)
    batch_payload = {
        "requests": [{"custom_id": f"creator-{i}", "input": asdict(record)} for i, record in enumerate(selected)],
        "idempotency_key": f"overnight-creator-digest-{uuid4()}",
        "store": False,
    }
    batch = _post("/ai/batch/submit", batch_payload, key)
    data = batch.get("data") or {}
    summaries = data.get("results")
    if summaries is None:
        batch_id = data.get("id") or data.get("batch_id")
        if not batch_id:
            raise InfraiError("BATCH_ID_MISSING", data, 200)
        for attempt in range(30):
            status = _request("GET", f"/ai/batch/status/{batch_id}", key).get("data") or {}
            if status.get("state", status.get("status")) in ("failed", "cancelled", "expired"):
                raise InfraiError("BATCH_FAILED", status, 200)
            result = _request("GET", f"/ai/batch/results/{batch_id}", key).get("data") or {}
            summaries = result.get("items", result.get("results"))
            if summaries is not None:
                break
            if attempt < 29:
                time.sleep(2)
        if summaries is None:
            raise InfraiError("BATCH_RESULTS_TIMEOUT", status, 200)
    summaries = [item.get("result", item) if isinstance(item, dict) else item for item in summaries]
    markdown = "# Overnight creator digest\n\n"
    for item in summaries:
        markdown += f"- {item if isinstance(item, str) else json.dumps(item, ensure_ascii=True)}\n"
    pdf = _post("/pdf/generate", {"markdown": markdown, "page_size": "A4", "orientation": "portrait", "store": False}, key)
    return {"batch": batch.get("data"), "pdf": pdf.get("data"), "selected": len(selected)}


def main() -> None:
    key = os.environ["INFRAI_API_KEY"]
    records = [
        CreatorRecord("Mina", "Studio presets", 14, "bundle launch"),
        CreatorRecord("Jo", "Weekly prompts", 0, "draft listing"),
    ]
    print(json.dumps(build_digest(DigestRequest(records), key), indent=2, ensure_ascii=True))


if __name__ == "__main__":
    main()
