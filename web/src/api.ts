// Thin client for the glass-cockpit API. Same origin as the page, so no base URL needed.

export interface Event {
  seq: number;
  ts: string;
  kind: string;
  message: string;
  action_id: string | null;
  tokens?: number | null;
  cost_cents?: number | null;
  payload?: Record<string, unknown>;
}

export interface Agent {
  agent_id: string;
  label: string;
  status: "running" | "paused" | "killed";
  reason: string | null;
  last_tick_at: string | null;
  drift: number;
  cost_cents: number;
  tokens: number;
  recent: Event[];
}

export interface Action {
  id: string;
  agent_id: string;
  operation: string;
  params: Record<string, unknown>;
  action_hash: string;
  status: string;
  decision: { outcome: string; risk_score: number; confidence: number; reasons: string[] };
}

export interface KillSwitch {
  active: boolean;
  reason: string | null;
  set_by: string | null;
  set_at: string | null;
}

async function req<T>(method: string, path: string, body?: unknown): Promise<T> {
  const res = await fetch(path, {
    method,
    headers: body ? { "content-type": "application/json" } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) throw new Error(`${method} ${path} -> ${res.status}: ${await res.text()}`);
  return res.json() as Promise<T>;
}

export const api = {
  fleet: () => req<Agent[]>("GET", "/v1/fleet"),
  replay: (agentId: string, n = 20) => req<Event[]>("GET", `/v1/fleet/${agentId}/replay?n=${n}`),
  pause: (agentId: string, actor: string, reason?: string) =>
    req("POST", `/v1/fleet/${agentId}/pause`, { actor, reason }),
  resume: (agentId: string, actor: string) => req("POST", `/v1/fleet/${agentId}/resume`, { actor }),
  kill: (agentId: string, actor: string, reason?: string) =>
    req("POST", `/v1/fleet/${agentId}/kill`, { actor, reason }),
  goRogue: (agentId: string) => req<{ steps: unknown[] }>("POST", `/v1/fleet/${agentId}/go-rogue`),
  approvals: () => req<Action[]>("GET", "/v1/approvals"),
  decide: (actionId: string, approverId: string, verdict: "approve" | "reject", actionHash: string) =>
    req<Action>("POST", `/v1/approvals/${actionId}/decide`, { approver_id: approverId, verdict, action_hash: actionHash }),
  killSwitch: () => req<KillSwitch>("GET", "/v1/kill-switch"),
  setKillSwitch: (active: boolean, actor: string, reason?: string) =>
    req<KillSwitch>("PUT", "/v1/kill-switch", { active, actor, reason }),
  auditVerify: () => req<{ ok: boolean }>("GET", "/v1/audit/verify"),
  reset: () => req<{ status: string }>("POST", "/v1/reset"),
};
