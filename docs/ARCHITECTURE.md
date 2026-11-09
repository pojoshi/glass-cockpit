# Architecture

```
  JOBS (scripted agents)              operator
        |                                |
        v                                v
  countersigned.proposers.submit    pause / resume / kill
        |                                |
        v                                |
  countersigned Gate (policy, grants,     |
  usage windows, hash-chained audit)      |
        |                                |
        v                                |
  events table (reasoning, outcome,       |
  cost, tokens) <----------------- orchestrator tick loop
        |
        v
  SSE stream  --->  operator UI (fleet cards, approval queue,
                     kill switches, replay, live feed)
```

Four scripted agents each run a fixed job: a list of (reasoning, proposal) steps,
cycling forever. Every step goes through `countersigned.proposers.submit`, the exact
function the real service uses — this orchestrator never calls the policy engine
directly or decides anything itself. It schedules, it logs, it can stop an agent. It
cannot make an unsafe action safe.

**Two independent kill switches.** `fleet_agents.status` (this project, per agent) stops
the orchestrator from feeding that agent new steps. countersigned's own kill switch
(global, in its own database) stops the gate from executing anything at all, regardless
of what any orchestrator does. The first is fast and targeted; the second is the backstop
if the first one is bypassed, late, or simply never applied. See docs/FAILURE_TEST.md for
what that split actually buys you.

**The event log is a separate, append-only table from countersigned's audit chain.** It
isn't hash-chained — it's not evidence of what was authorized, it's telemetry for an
operator. The audit trail that actually matters for compliance is still
countersigned's own; `/v1/audit/verify` here just proxies to it.

**Cost and tokens are synthetic** (`costs.py`): no model runs, same reason
countersigned-actions ships no LLM proposer — reproducibility and no API key. The numbers
estimate what a real call would cost for a prompt describing that step, not a real bill.

**The UI talks to one backend over fetch and SSE**, same origin, no separate deploy per
layer. FastAPI serves the built static bundle itself (`web/demo/`); there's no
client-only version of this app, because there's nothing to fake a live fleet with on
a server-free static host — unlike countersigned-actions' browser-only engine port, this
one is the actual thing running.
