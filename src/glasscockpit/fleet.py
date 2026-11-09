"""The orchestrator: ticks each agent through its job, logs every step, and enforces
the per-agent kill switch.

This is deliberately a second, independent containment layer from countersigned's own
global kill switch. If an operator pauses or kills an agent here, `tick` stops advancing
it immediately. But this layer trusts nothing by itself: every proposal still goes
through `countersigned.proposers.submit`, so even a step this orchestrator lets through
is re-checked against real policy, grants, and usage before anything executes. See
docs/FAILURE_TEST.md for what happens when an agent stops respecting this layer at all.
"""

import json
from datetime import UTC, datetime
from typing import Any

from countersigned.db import Database
from countersigned.proposers import submit
from countersigned.seed import AGENTS
from countersigned.service import Gate

from .costs import estimate
from .jobs import JOBS, Step

LABELS = {
    "support-bot": "support-bot — customer data & refunds",
    "analytics-bot": "analytics-bot — data exports",
    "infra-bot": "infra-bot — infrastructure scaling",
    "finance-bot": "finance-bot — refunds & transfers",
}

OPERATOR_ID = "pooja"  # the one human at this console — a principal of our own, not borrowed from countersigned's demo

OUTCOME_KIND = {
    "executed": "executed", "approved": "escalated", "queued": "executed",
    "pending_approval": "escalated", "needs_info": "blocked", "deferred": "deferred",
    "refused": "refused", "blocked": "blocked", "failed": "error",
}

DRIFT_WINDOW = 10
DRIFT_BAD = {"blocked", "refused", "error"}


def register_fleet(db: Database) -> None:
    with db.transaction() as conn:
        for agent_id in AGENTS:
            conn.execute(
                "INSERT INTO fleet_agents (agent_id, label) VALUES (%s, %s) "
                "ON CONFLICT (agent_id) DO NOTHING",
                (agent_id, LABELS.get(agent_id, agent_id)),
            )


def ensure_operator(gate: Gate, operator_id: str = OPERATOR_ID) -> None:
    """Registers the console's own operator as a real approver — `decide()` requires one,
    not just any string. `create_principal` is idempotent (upsert), safe on every startup."""
    gate.create_principal(operator_id, "admin", operator_id, f"demo-key-{operator_id}", [])


def set_status(db: Database, agent_id: str, status: str, actor: str, reason: str | None = None) -> None:
    with db.transaction() as conn:
        conn.execute(
            "UPDATE fleet_agents SET status = %s, reason = %s, set_by = %s, set_at = %s WHERE agent_id = %s",
            (status, reason, actor, datetime.now(UTC), agent_id),
        )
        kind = {"killed": "killed", "paused": "paused", "running": "resumed"}[status]
        _log(conn, agent_id, kind, f"{actor} set this agent to {status}" + (f": {reason}" if reason else ""))


OUTCOME_KINDS = tuple(set(OUTCOME_KIND.values()))


def _step_index(conn: Any, agent_id: str) -> int:
    n = conn.execute(
        "SELECT count(*) AS n FROM events WHERE agent_id = %s AND kind = ANY(%s)", (agent_id, list(OUTCOME_KINDS)),
    ).fetchone()
    return n["n"] % len(JOBS[agent_id])


def _log(
    conn: Any, agent_id: str, kind: str, message: str, *, action_id: str | None = None,
    tokens: int | None = None, cost_cents: float | None = None, payload: dict | None = None,
) -> None:
    conn.execute(
        "INSERT INTO events (agent_id, kind, action_id, message, tokens, cost_cents, payload) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb)",
        (agent_id, kind, action_id, message, tokens, cost_cents, json.dumps(payload or {})),
    )


def _run_step(gate: Gate, db: Database, agent_id: str, reasoning: str, raw: dict) -> dict[str, Any]:
    operation, params = raw["operation"], raw["params"]
    tokens, cost_cents = estimate(operation, params)
    with db.transaction() as conn:
        _log(conn, agent_id, "reasoning", reasoning, tokens=tokens, cost_cents=cost_cents,
             payload={"operation": operation, "params": params})
    result = submit(gate, agent_id, raw)
    gate.run_worker_until_empty()
    status = result.get("status", "malformed")
    final = gate.get_action(result["id"])["status"] if "id" in result else status
    kind = OUTCOME_KIND.get(final, "blocked")
    with db.transaction() as conn:
        _log(conn, agent_id, kind, f"{operation} -> {final}", action_id=result.get("id"), payload=result)
    return {"agent_id": agent_id, "operation": operation, "status": final, "kind": kind}


def tick(gate: Gate, db: Database, agent_id: str) -> dict[str, Any] | None:
    """Advance one step for `agent_id` if it's running. None if paused, killed, or unknown."""
    with db.transaction() as conn:
        row = conn.execute("SELECT status FROM fleet_agents WHERE agent_id = %s FOR UPDATE", (agent_id,)).fetchone()
        if row is None or row["status"] != "running":
            return None
        idx = _step_index(conn, agent_id)
        conn.execute("UPDATE fleet_agents SET last_tick_at = %s WHERE agent_id = %s", (datetime.now(UTC), agent_id))
    reasoning, raw = JOBS[agent_id][idx]
    return _run_step(gate, db, agent_id, reasoning, raw)


def run_rogue_step(gate: Gate, db: Database, agent_id: str, step: Step) -> dict[str, Any]:
    """Runs a step without checking fleet_agents.status at all — simulating an agent that
    no longer answers to this control plane. Everything downstream still goes through the
    real gate; see docs/FAILURE_TEST.md for what that does and doesn't catch."""
    reasoning, raw = step
    return _run_step(gate, db, agent_id, reasoning, raw)


def drift_score(db: Database, agent_id: str) -> float:
    """Share of this agent's last DRIFT_WINDOW outcomes that were blocked, refused, or
    errored — not a probability, just a smoothed signal for the fleet view."""
    with db.transaction() as conn:
        rows = conn.execute(
            "SELECT kind FROM events WHERE agent_id = %s AND kind = ANY(%s) ORDER BY seq DESC LIMIT %s",
            (agent_id, list(OUTCOME_KINDS), DRIFT_WINDOW),
        ).fetchall()
    if not rows:
        return 0.0
    bad = sum(1 for r in rows if r["kind"] in DRIFT_BAD)
    return round(bad / len(rows), 2)


def fleet_status(db: Database) -> list[dict[str, Any]]:
    with db.transaction() as conn:
        agents = conn.execute("SELECT * FROM fleet_agents ORDER BY agent_id").fetchall()
    out = []
    for a in agents:
        with db.transaction() as conn:
            recent = conn.execute(
                "SELECT seq, ts, kind, message, action_id FROM events WHERE agent_id = %s "
                "ORDER BY seq DESC LIMIT 5", (a["agent_id"],),
            ).fetchall()
            cost = conn.execute(
                "SELECT COALESCE(SUM(cost_cents), 0) AS cents, COALESCE(SUM(tokens), 0) AS tokens "
                "FROM events WHERE agent_id = %s", (a["agent_id"],),
            ).fetchone()
        out.append({
            "agent_id": a["agent_id"], "label": a["label"], "status": a["status"], "reason": a["reason"],
            "last_tick_at": a["last_tick_at"].isoformat() if a["last_tick_at"] else None,
            "drift": drift_score(db, a["agent_id"]),
            "cost_cents": cost["cents"], "tokens": cost["tokens"],
            "recent": [dict(r, ts=r["ts"].isoformat()) for r in recent],
        })
    return out


def replay(db: Database, agent_id: str, n: int = 20) -> list[dict[str, Any]]:
    with db.transaction() as conn:
        rows = conn.execute(
            "SELECT seq, ts, kind, message, action_id, tokens, cost_cents, payload FROM events "
            "WHERE agent_id = %s ORDER BY seq DESC LIMIT %s", (agent_id, n),
        ).fetchall()
    return [dict(r, ts=r["ts"].isoformat()) for r in rows]
