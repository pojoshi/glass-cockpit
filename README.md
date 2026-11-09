# glass-cockpit

**The operator console for a fleet of autonomous agents: live status, an approval queue, per-agent kill switches, and reasoning replay.**

**[Live demo](https://glass-cockpit.onrender.com)** — free-tier hosting, so the first load after it's been idle can take up to a minute to wake up.

Four scripted agents run real jobs against [countersigned-actions](https://github.com/pojoshi/countersigned-actions)' policy gate: deleting customer records, exporting data, scaling infrastructure, moving money. One operator watches all four from one screen, approves what needs a human, kills what's misbehaving, and can replay any agent's last 20 steps to see exactly why it did what it did.

```
support-bot proposes deleting 20 "verified" records → gate: segment actually has 0 → asks
finance-bot proposes a vendor transfer              → gate: transfers always need a human → queued
infra-bot's drift climbs to "elevated"              → operator kills it, replays its last 10 steps
support-bot goes rogue, understates scope 3x         → refused every time, never executes
```

## Why

I spend my days on AI pipelines, not on watching them. The agent is rarely the hard
part: knowing what your fleet is doing right now, and having something faster than
"grep the logs" when one of them does something wrong, is. This is the cockpit I'd want
for that, built on the policy gate I'd already written rather than a new pile of trust.

## How it works

- **The orchestrator never decides anything.** Each agent's job is a scripted list of
  steps; every one goes through `countersigned.proposers.submit`, the real gate, no
  shortcut. The cockpit schedules and logs. It doesn't get to make an unsafe action safe.
- **Two kill switches, on purpose.** A per-agent one here, stopping the orchestrator from
  feeding that agent new work. A global one in countersigned-actions, stopping execution
  regardless of what any orchestrator does. See [docs/FAILURE_TEST.md](docs/FAILURE_TEST.md).
- **Drift is a number, not a vibe.** The share of an agent's last 10 outcomes that were
  blocked, refused, or errored — simple on purpose, see [docs/THESIS.md](docs/THESIS.md)
  for what a real version would need instead.
- **No model calls.** Same reasoning as the gate itself: reproducible, no API key.
  Cost and tokens per step are estimated (`src/glasscockpit/costs.py`), not billed.

More: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md). The rogue-agent scenario, in full:
[docs/FAILURE_TEST.md](docs/FAILURE_TEST.md). Two-year view: [docs/THESIS.md](docs/THESIS.md).

## Running it

**Docker** (Postgres, the API, the fleet, the UI, all in one container):

```bash
git clone https://github.com/pojoshi/glass-cockpit && cd glass-cockpit
docker compose up --build
# open http://localhost:8001
```

**Tests** (needs its own Postgres):

```bash
python -m venv .venv && . .venv/bin/activate && pip install -e '.[dev]'
docker run -d -e POSTGRES_PASSWORD=postgres -e POSTGRES_DB=glasscockpit_test -p 5432:5432 postgres:16
export GLASSCOCKPIT_TEST_DATABASE_URL=postgresql://postgres:postgres@localhost:5432/glasscockpit_test
pytest
cd web && pnpm install --frozen-lockfile && pnpm run check
```

`act -j python` and `act -j web` both pass against the committed CI workflow.

## Layout

```
src/glasscockpit/   fleet.py (orchestrator) · api.py (operator API + SSE) · jobs.py (what each agent does) · costs.py
tests/              orchestrator, rogue containment, API
web/                operator UI: fetch + SSE client, no framework
docs/               architecture, the rogue-agent failure test, notes, two-year thesis
```

Built on [countersigned-actions](https://github.com/pojoshi/countersigned-actions): same author, same policy gate, this time with an operator sitting in front of it.

MIT licensed. See [LICENSE](LICENSE).
