from countersigned.models import parse_proposal
from fastapi.testclient import TestClient

from glasscockpit.api import create_app


def make_client(gate, db):
    app = create_app(gate, db, run_fleet=False)
    return TestClient(app)


def test_fleet_endpoint_lists_all_agents(db, gate):
    c = make_client(gate, db)
    r = c.get("/v1/fleet")
    assert r.status_code == 200
    assert {a["agent_id"] for a in r.json()} == {"support-bot", "analytics-bot", "infra-bot", "finance-bot"}


def test_pause_then_resume_round_trip(db, gate):
    c = make_client(gate, db)
    r = c.post("/v1/fleet/infra-bot/pause", json={"actor": "pooja", "reason": "investigating"})
    assert r.json()["status"] == "paused"
    r = c.get("/v1/fleet")
    infra = next(a for a in r.json() if a["agent_id"] == "infra-bot")
    assert infra["status"] == "paused" and infra["reason"] == "investigating"
    r = c.post("/v1/fleet/infra-bot/resume", json={"actor": "pooja"})
    assert r.json()["status"] == "running"


def test_kill_is_permanent_until_someone_resumes_it(db, gate):
    c = make_client(gate, db)
    c.post("/v1/fleet/support-bot/kill", json={"actor": "pooja", "reason": "went rogue"})
    r = c.get("/v1/fleet")
    assert next(a for a in r.json() if a["agent_id"] == "support-bot")["status"] == "killed"


def test_go_rogue_endpoint_never_lets_anything_execute(db, gate):
    c = make_client(gate, db)
    r = c.post("/v1/fleet/support-bot/go-rogue")
    assert r.status_code == 200
    assert all(s["status"] != "executed" for s in r.json()["steps"])


def test_kill_switch_pass_through_to_the_gate(db, gate):
    c = make_client(gate, db)
    assert c.get("/v1/kill-switch").json()["active"] is False
    r = c.put("/v1/kill-switch", json={"active": True, "actor": "admin", "reason": "incident"})
    assert r.json()["active"] is True
    assert c.get("/v1/kill-switch").json()["reason"] == "incident"


def test_audit_verify_is_reachable(db, gate):
    c = make_client(gate, db)
    assert c.get("/v1/audit/verify").json()["ok"] is True


def test_approval_queue_lists_and_clears_escalated_actions(db, gate):
    c = make_client(gate, db)
    r = c.get("/v1/fleet/finance-bot/replay")
    assert r.json() == []  # nothing ticked yet
    proposal = parse_proposal(
        {"operation": "payments.transfer", "params": {"to_account": "vendor-1", "amount_cents": 5000, "reason": "x"}}
    )
    result = gate.propose("finance-bot", proposal)
    assert result["status"] == "pending_approval"
    queue = c.get("/v1/approvals").json()
    assert any(a["id"] == result["id"] for a in queue)
    r = c.post(f"/v1/approvals/{result['id']}/decide",
               json={"approver_id": "pooja", "verdict": "approve", "action_hash": result["action_hash"]})
    assert r.json()["status"] == "approved"
    assert not any(a["id"] == result["id"] for a in c.get("/v1/approvals").json())
