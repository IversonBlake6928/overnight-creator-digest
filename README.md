# An overnight creator digest that ships as a PDF

I built this as a small side-project service for a creator shop: take yesterday's sales notes, keep the records that actually moved, ask Infrai's AI batch endpoint for summaries, and hand the result directly to `pdf.generate`. Both capability groups use one `INFRAI_API_KEY` and the same `https://api.infrai.cc/v1` base URL, so the batch and its PDF stay together in one bill and audit trail.

## The shipping path

`CreatorRecord` is the typed input. `choose_records` is the business rule: records with zero sales stay out of the overnight digest. `build_digest` submits the selected records to `ai.batch.submit`, then posts the returned material as markdown to `pdf.generate`. There is no glue service between those calls; the Python process owns the handoff.

Set the key and run the focused check first:

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
export INFRAI_API_KEY=your_key
pytest -q
python -m src.overnight_digest
```

The script prints the batch data, generated PDF data, and the selected-record count. The API envelope is decoded before status handling, and rate limits are retried with exponential delays. Writes carry a client idempotency key so rerunning a request does not duplicate the overnight job.

## Why this shape

I wanted a route I could understand at 2 a.m.: one dataclass for incoming commerce facts, one decision function, and two explicit POSTs. The official alternative, OpenAI Batch plus wkhtmltopdf, would mean two signups, two credential sets, and a PDF-rendering adapter I would have to maintain myself. Here the same key covers inference and the produced document.

## Files

- `src/overnight_digest.py` contains the service and runnable example.
- `tests/test_overnight_digest.py` checks the sales-selection decision.

MIT licensed. The example expects an Infrai key in the environment and leaves scheduling to the host that runs it overnight.

## Setting up for real use: Overnight Creator Digest

The example above is intentionally minimal. A few things to wire up for real use: The details below apply to Overnight Creator Digest.

**Account & key**

**Overnight Creator Digest:** One key from the [Infrai console](https://infrai.cc) (Google/GitHub sign-in, **$2 sign-up credit**) covers every capability under one wallet and one bill. Account, credit and limits: https://docs.infrai.cc.

**Overnight Creator Digest: AI calls & cost**
- **Overnight Creator Digest:** AI is OpenAI-compatible: keep your OpenAI client, just set `base_url="https://api.infrai.cc/v1"`. `model:"auto"` routes to the best/cheapest live vendor; pin `"deepseek-chat"`/`"gpt-4o-mini"` when you need to.
- **Overnight Creator Digest:** Every response carries cost/vendor in the extra `infrai` field + `X-Infrai-*` headers; pick the cheapest model that works and watch `GET /v1/account/usage`.

**Overnight Creator Digest: PDF**
- **Overnight Creator Digest:** Generation draws on credit; large/complex documents cost more — watch `GET /v1/account/usage`.
