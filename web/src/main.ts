import { api, type Agent, type Action, type Event, type KillSwitch } from "./api";
import { driftLabel, formatCents, formatTokens, kindLabel, timeAgo } from "./format";

const OPERATOR = "pooja"; // the one human at this console

const fleetEl = document.querySelector<HTMLDivElement>("#fleet")!;
const approvalsEl = document.querySelector<HTMLDivElement>("#approvals")!;
const streamEl = document.querySelector<HTMLDivElement>("#stream")!;
const killSwitchEl = document.querySelector<HTMLDivElement>("#kill-switch")!;
const replayEl = document.querySelector<HTMLDivElement>("#replay")!;
const toastEl = document.querySelector<HTMLDivElement>("#toast")!;

let agents: Agent[] = [];
let approvals: Action[] = [];

function toast(message: string): void {
  toastEl.textContent = message;
  toastEl.hidden = false;
  setTimeout(() => (toastEl.hidden = true), 3000);
}

function el(tag: string, className: string, html?: string): HTMLElement {
  const node = document.createElement(tag);
  node.className = className;
  if (html !== undefined) node.innerHTML = html;
  return node;
}

function renderFleet(): void {
  fleetEl.replaceChildren(
    ...agents.map((a) => {
      const card = el("div", `agent status-${a.status}`);
      card.dataset.agent = a.agent_id;
      card.innerHTML = `
        <div class="agent-head">
          <b>${a.label}</b>
          <span class="pill pill-${a.status}">${a.status}</span>
        </div>
        <div class="agent-meta">
          <span>drift: <b class="drift-${driftLabel(a.drift)}">${driftLabel(a.drift)}</b> (${a.drift})</span>
          <span>last tick: ${timeAgo(a.last_tick_at)}</span>
          <span>${formatTokens(a.tokens)} tokens · ${formatCents(a.cost_cents)}</span>
        </div>
        ${a.reason ? `<div class="agent-reason">${a.reason}</div>` : ""}
        <ul class="agent-recent">
          ${a.recent.map((e) => `<li class="k-${e.kind}">${kindLabel(e.kind)} — ${e.message}</li>`).join("")}
        </ul>
        <div class="agent-controls">
          ${a.status === "running" ? `<button data-act="pause">pause</button>` : ""}
          ${a.status !== "running" ? `<button data-act="resume">resume</button>` : ""}
          ${a.status !== "killed" ? `<button data-act="kill" class="danger">kill</button>` : ""}
          <button data-act="replay">replay</button>
          ${a.agent_id === "support-bot" ? `<button data-act="go-rogue" class="danger ghost">simulate rogue</button>` : ""}
        </div>`;
      return card;
    }),
  );
  if (agents.length === 0) fleetEl.replaceChildren(el("p", "empty-note", "No agents registered yet."));
}

function renderApprovals(): void {
  approvalsEl.replaceChildren(
    ...approvals.map((a) => {
      const row = el("div", "approval");
      row.dataset.action = a.id;
      row.dataset.hash = a.action_hash;
      row.innerHTML = `
        <div><b>${a.agent_id}</b> — ${a.operation}</div>
        <div class="mono">${JSON.stringify(a.params)}</div>
        <div class="approval-why">risk ${a.decision.risk_score} · confidence ${a.decision.confidence} — ${a.decision.reasons[0] ?? ""}</div>
        <div class="row">
          <button data-verdict="approve">approve</button>
          <button data-verdict="reject" class="ghost">reject</button>
        </div>`;
      return row;
    }),
  );
  if (approvals.length === 0) approvalsEl.replaceChildren(el("p", "empty-note", "Queue is empty."));
}

function renderKillSwitch(ks: KillSwitch): void {
  killSwitchEl.innerHTML = `
    <button id="ks-toggle" class="${ks.active ? "danger" : ""}">${ks.active ? "kill switch ON — release" : "global kill switch"}</button>
    ${ks.active ? `<span class="agent-reason">${ks.reason ?? ""}</span>` : ""}`;
  document.querySelector("#ks-toggle")!.addEventListener("click", async () => {
    if (ks.active) {
      await api.setKillSwitch(false, OPERATOR);
    } else {
      const reason = prompt("Reason for the global kill switch:") ?? "operator intervention";
      await api.setKillSwitch(true, OPERATOR, reason);
    }
    await refreshKillSwitch();
  });
}

function appendStreamEvent(e: Event): void {
  const row = el(
    "div",
    `stream-row k-${e.kind}`,
    `<span class="mono">${new Date(e.ts).toLocaleTimeString()}</span> <b>${kindLabel(e.kind)}</b> ${e.message}`,
  );
  streamEl.prepend(row);
  while (streamEl.children.length > 200) streamEl.lastChild?.remove();
}

async function refreshFleet(): Promise<void> {
  agents = await api.fleet();
  renderFleet();
}

async function refreshApprovals(): Promise<void> {
  approvals = await api.approvals();
  renderApprovals();
}

async function refreshKillSwitch(): Promise<void> {
  renderKillSwitch(await api.killSwitch());
}

async function showReplay(agentId: string): Promise<void> {
  const events = await api.replay(agentId, 20);
  replayEl.hidden = false;
  replayEl.innerHTML = `
    <div class="replay-head"><b>${agentId}</b> — last ${events.length} steps <button id="replay-close" class="ghost">close</button></div>
    <ol class="replay-list">
      ${events.map((e) => `<li class="k-${e.kind}"><span class="mono">${new Date(e.ts).toLocaleTimeString()}</span> ${kindLabel(e.kind)} — ${e.message}${e.tokens ? ` <span class="mono">(${e.tokens} tok)</span>` : ""}</li>`).join("")}
    </ol>`;
  document.querySelector("#replay-close")!.addEventListener("click", () => (replayEl.hidden = true));
}

fleetEl.addEventListener("click", async (ev) => {
  const btn = (ev.target as HTMLElement).closest<HTMLButtonElement>("button[data-act]");
  if (!btn) return;
  const agentId = btn.closest<HTMLElement>(".agent")!.dataset.agent!;
  try {
    switch (btn.dataset.act) {
      case "pause":
        await api.pause(agentId, OPERATOR);
        break;
      case "resume":
        await api.resume(agentId, OPERATOR);
        break;
      case "kill":
        await api.kill(agentId, OPERATOR, prompt("Reason for killing this agent:") ?? "operator intervention");
        break;
      case "go-rogue":
        await api.goRogue(agentId);
        toast(`${agentId} is simulating rogue behaviour — watch the stream`);
        break;
      case "replay":
        await showReplay(agentId);
        return;
    }
    await refreshFleet();
  } catch (e) {
    toast(String(e));
  }
});

approvalsEl.addEventListener("click", async (ev) => {
  const btn = (ev.target as HTMLElement).closest<HTMLButtonElement>("button[data-verdict]");
  if (!btn) return;
  const row = btn.closest<HTMLElement>(".approval")!;
  try {
    await api.decide(row.dataset.action!, OPERATOR, btn.dataset.verdict as "approve" | "reject", row.dataset.hash!);
    await refreshApprovals();
    await refreshFleet();
  } catch (e) {
    toast(String(e));
  }
});

document.querySelector("#reset")!.addEventListener("click", async () => {
  await api.reset();
  streamEl.replaceChildren();
  await Promise.all([refreshFleet(), refreshApprovals(), refreshKillSwitch()]);
  toast("Fleet reset");
});

function connectStream(): void {
  const source = new EventSource("/v1/stream");
  source.onmessage = (ev) => {
    const e = JSON.parse(ev.data) as Event;
    appendStreamEvent(e);
    if (e.kind !== "reasoning") {
      void refreshFleet();
      void refreshApprovals();
    }
  };
  source.onerror = () => {
    source.close();
    setTimeout(connectStream, 2000);
  };
}

async function init(): Promise<void> {
  await Promise.all([refreshFleet(), refreshApprovals(), refreshKillSwitch()]);
  connectStream();
  setInterval(refreshFleet, 8000); // fallback in case the stream drops silently
}

void init();
