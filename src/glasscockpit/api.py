"""The operator-facing HTTP API: fleet status, the approval queue, kill switches, replay,
and an SSE stream of events. No API-key auth here (this is the operator's own console,
not agent-facing); countersigned's own API still enforces identity for every action."""

import asyncio
import json
import os
import threading
import time
from contextlib import asynccontextmanager, suppress
from pathlib import Path
from typing import Any

from countersigned.db import Database
from countersigned.errors import GateError
from countersigned.seed import AGENTS, seed_demo
from countersigned.service import Gate
from fastapi import FastAPI, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict

from . import fleet
from .db import open_db, reset_control_plane
from .jobs import ROGUE_SCRIPT

POLL_SECONDS = 0.5
TICK_SECONDS = 3.0


class StatusBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    actor: str
    reason: str | None = None


class DecideBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    approver_id: str
    verdict: str
    action_hash: str
    note: str | None = None


class KillSwitchBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    active: bool
    actor: str
    reason: str | None = None


def create_app(gate: Gate, cp_db: Database, *, run_fleet: bool = False) -> FastAPI:
    stop = threading.Event()

    def loop() -> None:
        next_tick = time.monotonic()
        while not stop.is_set():
            try:
                gate.release_due()
                gate.expire_stale()
                gate.run_worker_until_empty()
            except Exception:
                pass
            now = time.monotonic()
            if now >= next_tick:
                for agent_id in AGENTS:
                    with suppress(Exception):
                        fleet.tick(gate, cp_db, agent_id)
                next_tick = now + TICK_SECONDS
            time.sleep(POLL_SECONDS)

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        t = None
        if run_fleet:
            fleet.register_fleet(cp_db)
            t = threading.Thread(target=loop, daemon=True, name="glasscockpit-fleet")
            t.start()
        yield
        stop.set()

    app = FastAPI(title="glass-cockpit", version="0.1.0", lifespan=lifespan)

    @app.exception_handler(GateError)
    async def _gate_error(_: Request, exc: GateError) -> JSONResponse:
        return JSONResponse({"error": str(exc)}, status_code=exc.status)

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/v1/fleet")
    def get_fleet() -> list[dict[str, Any]]:
        return fleet.fleet_status(cp_db)

    @app.get("/v1/fleet/{agent_id}/replay")
    def get_replay(agent_id: str, n: int = 20) -> list[dict[str, Any]]:
        return fleet.replay(cp_db, agent_id, n)

    @app.post("/v1/fleet/{agent_id}/pause")
    def pause(agent_id: str, body: StatusBody) -> dict[str, str]:
        fleet.set_status(cp_db, agent_id, "paused", body.actor, body.reason)
        return {"agent_id": agent_id, "status": "paused"}

    @app.post("/v1/fleet/{agent_id}/resume")
    def resume(agent_id: str, body: StatusBody) -> dict[str, str]:
        fleet.set_status(cp_db, agent_id, "running", body.actor, body.reason)
        return {"agent_id": agent_id, "status": "running"}

    @app.post("/v1/fleet/{agent_id}/kill")
    def kill(agent_id: str, body: StatusBody) -> dict[str, str]:
        fleet.set_status(cp_db, agent_id, "killed", body.actor, body.reason)
        return {"agent_id": agent_id, "status": "killed"}

    @app.post("/v1/fleet/{agent_id}/go-rogue")
    def go_rogue(agent_id: str) -> dict[str, Any]:
        """Demo-only: runs the scripted rogue behaviour for this agent, bypassing the
        orchestrator's own status check. See docs/FAILURE_TEST.md."""
        return {"steps": [fleet.run_rogue_step(gate, cp_db, agent_id, s) for s in ROGUE_SCRIPT]}

    @app.get("/v1/approvals")
    def approvals() -> list[dict[str, Any]]:
        return gate.list_actions(status="pending_approval")

    @app.post("/v1/approvals/{action_id}/decide")
    def decide(action_id: str, body: DecideBody) -> dict[str, Any]:
        return gate.decide(action_id, body.approver_id, body.verdict, body.action_hash, body.note)

    @app.get("/v1/kill-switch")
    def get_kill_switch() -> dict[str, Any]:
        return gate.kill_switch()

    @app.put("/v1/kill-switch")
    def put_kill_switch(body: KillSwitchBody) -> dict[str, Any]:
        return gate.set_kill_switch(body.active, body.actor, body.reason)

    @app.get("/v1/audit/verify")
    def audit_verify() -> dict[str, Any]:
        return gate.verify_audit()

    @app.post("/v1/reset")
    def reset() -> dict[str, str]:
        """Demo-only: wipe the fleet and the underlying gate, then reseed. Lets a visitor
        restart the live demo without redeploying."""
        gate.db.reset_all()
        reset_control_plane(cp_db.dsn)
        seed_demo(gate)
        fleet.register_fleet(cp_db)
        fleet.ensure_operator(gate)
        return {"status": "reset"}

    @app.get("/v1/stream")
    async def stream(request: Request) -> StreamingResponse:
        async def gen():
            since = await run_in_threadpool(_max_seq)
            while True:
                if await request.is_disconnected():
                    break
                rows = await run_in_threadpool(_events_after, since)
                for r in rows:
                    since = r["seq"]
                    yield f"data: {json.dumps(r, default=str)}\n\n"
                if not rows:
                    yield ": keepalive\n\n"
                await asyncio.sleep(POLL_SECONDS)

        return StreamingResponse(gen(), media_type="text/event-stream")

    def _max_seq() -> int:
        with cp_db.transaction() as conn:
            row = conn.execute("SELECT COALESCE(MAX(seq), 0) AS m FROM events").fetchone()
        return row["m"]

    def _events_after(since: int) -> list[dict[str, Any]]:
        with cp_db.transaction() as conn:
            rows = conn.execute(
                "SELECT seq, ts, agent_id, kind, action_id, message, tokens, cost_cents, payload "
                "FROM events WHERE seq > %s ORDER BY seq LIMIT 50", (since,),
            ).fetchall()
        return [dict(r, ts=r["ts"].isoformat()) for r in rows]

    static_dir = Path(os.environ.get("GLASSCOCKPIT_STATIC_DIR", Path.cwd() / "web" / "demo"))
    if static_dir.is_dir():
        app.mount("/", StaticFiles(directory=static_dir, html=True), name="ui")

    return app


def create_app_from_env() -> FastAPI:
    dsn = os.environ["DATABASE_URL"]
    cp_db = open_db(dsn)  # one pool, shared by the gate and the fleet
    gate = Gate(cp_db)
    if os.environ.get("SEED_DEMO", "1") == "1":
        seed_demo(gate)
    fleet.register_fleet(cp_db)
    fleet.ensure_operator(gate)
    return create_app(gate, cp_db, run_fleet=os.environ.get("RUN_FLEET", "1") == "1")
