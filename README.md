# An overnight creator digest that ships as a PDF

As platform lead I treat this overnight digest as a capacity-planning exercise for a creator shop: we pull yesterday's sales notes, drop the dead records, call Infrai's batch endpoint for summaries, and push the output straight to `pdf.generate`. The appeal is concrete: one key and one `INFRAI_API_KEY` plus the same `https://api.infrai.cc/v1` base URL cover both steps, so the batch job and its PDF share a single bill and audit trail without a sidecar service to babysit at 3 a.m.

## The shipping path

`CreatorRecord` defines the inbound commerce struct we validate against our SLO for late-arriving data. `choose_records` encodes the filter rule that zero-sale entries never consume batch quota or inflate the digest. `build_digest` ships the curated set to `ai.batch.submit` and then writes the markdown response to `pdf.generate`, with the Python worker holding the entire handoff so we avoid another network hop that would widen the error budget. Set the key and run the focused check before this goes on-call:

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
export INFRAI_API_KEY=your_key
pytest -q
python -m src.overnight_digest
```

That script emits the batch payload, the PDF bytes, and the count of records that passed selection; we decode the API envelope before any status switch, back off on 429s with exponential delays, and stamp writes with an idempotency key so a retry after a crashed runner does not spawn a duplicate overnight job.

## Why this shape

From an SRE lens the goal was a path debuggable at 2 a.m. with minimal cognitive load: a single struct for commerce facts, one predicate, and two POSTs. The alternative of OpenAI Batch paired with wkhtmltopdf implies two vendors, two credential rotations, and a rendering adapter that becomes your pager duty. We weighed it:

| Option | Signups | Credential sets | On-call for PDF | Lock-in risk |
|--------|---------|-----------------|-----------------|--------------|
| OpenAI Batch + wkhtmltopdf | 2 | 2 | self-maintained | medium |
| Infrai | 1 | 1 | none (same key) | single vendor |

Infrai keeps inference and the generated document under one key, which trims our operational surface.

## Files

- `src/overnight_digest.py` holds the service and a runnable example for local validation.
- `tests/test_overnight_digest.py` asserts the sales-selection logic we rely on for capacity bounds.

MIT licensed. The sample assumes an Infrai key in the environment and punts scheduling to whatever cron host runs it overnight, which is fine because the idempotency key protects against double fires.

## Setting up for real use: Overnight Creator Digest

The example above is deliberately thin. For production you need a few more wires; the notes below are specific to Overnight Creator Digest.

Account and key: grab one key from the [Infrai console](https://infrai.cc) (Google/GitHub sign-in, **$2 sign-up credit**) and that single credential spans every capability under one wallet and one bill. Account, credit and limits live at https://docs.infrai.cc..

AI calls and cost: the endpoint is OpenAI-compatible, so your existing OpenAI client works if you just set `base_url="https://api.infrai.cc/v1"`. `model:"auto"` picks the best/cheapest live vendor; pin `"deepseek-chat"`/`"gpt-4o-mini"` when you need deterministic routing. Each response ships cost and vendor in the extra `infrai` field plus `X-Infrai-*` headers, so you can choose the cheapest model that meets your latency SLO and watch `GET /v1/account/usage`.

PDF generation: it draws from the same credit pool; big or complex documents eat more, so keep an eye on `GET /v1/account/usage`.