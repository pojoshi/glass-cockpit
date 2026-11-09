-- Control-plane tables. countersigned-actions owns policy, actions, and the audit chain;
-- this is the orchestration layer on top: which agents are running, and the event stream
-- an operator watches and replays. Applied alongside countersigned's own schema, same database.

CREATE TABLE IF NOT EXISTS fleet_agents (
    agent_id    text PRIMARY KEY,
    label       text NOT NULL,
    status      text NOT NULL DEFAULT 'running' CHECK (status IN ('running', 'paused', 'killed')),
    reason      text,
    set_by      text,
    set_at      timestamptz,
    started_at  timestamptz NOT NULL DEFAULT now(),
    last_tick_at timestamptz
);

CREATE TABLE IF NOT EXISTS events (
    seq        bigserial PRIMARY KEY,
    ts         timestamptz NOT NULL DEFAULT now(),
    agent_id   text NOT NULL,
    kind       text NOT NULL CHECK (kind IN (
        'reasoning', 'executed', 'escalated', 'deferred', 'blocked',
        'refused', 'error', 'killed', 'paused', 'resumed'
    )),
    action_id  text,
    message    text NOT NULL,
    tokens     integer,
    cost_cents double precision,
    payload    jsonb NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS events_agent_seq ON events (agent_id, seq DESC);
