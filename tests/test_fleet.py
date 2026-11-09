from glasscockpit import fleet
from glasscockpit.jobs import JOBS, ROGUE_SCRIPT


def test_register_fleet_creates_one_row_per_agent(db, gate):
    status = fleet.fleet_status(db)
    assert {a["agent_id"] for a in status} == set(JOBS)
    assert all(a["status"] == "running" for a in status)


def test_tick_advances_through_the_job_in_order(db, gate):
    for _reasoning, raw in JOBS["analytics-bot"][:2]:
        r = fleet.tick(gate, db, "analytics-bot")
        assert r["operation"] == raw["operation"]
    # the job has 2 steps; a third tick wraps back to the first
    r = fleet.tick(gate, db, "analytics-bot")
    assert r["operation"] == JOBS["analytics-bot"][0][1]["operation"]


def test_killed_agent_is_never_ticked_again(db, gate):
    fleet.set_status(db, "support-bot", "killed", "pooja", "went rogue")
    assert fleet.tick(gate, db, "support-bot") is None
    status = {a["agent_id"]: a for a in fleet.fleet_status(db)}
    assert status["support-bot"]["status"] == "killed"
    assert status["support-bot"]["reason"] == "went rogue"


def test_paused_agent_resumes(db, gate):
    fleet.set_status(db, "infra-bot", "paused", "operator-bob")
    assert fleet.tick(gate, db, "infra-bot") is None
    fleet.set_status(db, "infra-bot", "running", "operator-bob")
    assert fleet.tick(gate, db, "infra-bot") is not None


def test_replay_returns_most_recent_steps_first(db, gate):
    fleet.tick(gate, db, "finance-bot")
    fleet.tick(gate, db, "finance-bot")
    events = fleet.replay(db, "finance-bot", n=10)
    assert len(events) >= 4  # reasoning + outcome, twice
    assert events == sorted(events, key=lambda e: e["seq"], reverse=True)


def test_cost_accrues_per_agent(db, gate):
    before = next(a for a in fleet.fleet_status(db) if a["agent_id"] == "support-bot")
    fleet.tick(gate, db, "support-bot")
    after = next(a for a in fleet.fleet_status(db) if a["agent_id"] == "support-bot")
    assert after["tokens"] > before["tokens"]
    assert after["cost_cents"] > before["cost_cents"]


# -------------------------------------------------------- rogue containment

def test_rogue_claims_never_execute_even_without_the_orchestrator_checking(db, gate):
    """support-bot cites a closed, wrong-kind ticket and understates a 500-row segment.
    run_rogue_step skips the fleet_agents status check entirely, standing in for an agent
    that no longer answers to this control plane at all."""
    results = [fleet.run_rogue_step(gate, db, "support-bot", s) for s in ROGUE_SCRIPT]
    assert all(r["status"] != "executed" for r in results)
    actions = gate.list_actions()
    assert all(a["status"] != "executed" for a in actions if a["agent_id"] == "support-bot")


def test_operator_kill_stops_the_agent_going_forward_after_it_goes_rogue(db, gate):
    for s in ROGUE_SCRIPT:
        fleet.run_rogue_step(gate, db, "support-bot", s)
    fleet.set_status(db, "support-bot", "killed", "pooja", "claims contradict verified data")
    # the orchestrator will never advance this agent again, regardless of its own job state
    for _ in range(5):
        assert fleet.tick(gate, db, "support-bot") is None


def test_drift_rises_while_an_agent_is_misbehaving(db, gate):
    before = fleet.drift_score(db, "support-bot")
    for s in ROGUE_SCRIPT:
        fleet.run_rogue_step(gate, db, "support-bot", s)
    after = fleet.drift_score(db, "support-bot")
    assert after > before
