// Small pure helpers, kept apart from DOM code so they're easy to test directly.

export function formatCents(cents: number): string {
  return `$${(cents / 100).toFixed(3)}`;
}

export function formatTokens(tokens: number): string {
  return tokens >= 1000 ? `${(tokens / 1000).toFixed(1)}k` : String(tokens);
}

export function driftLabel(drift: number): string {
  if (drift === 0) return "clean";
  if (drift < 0.3) return "minor";
  if (drift < 0.6) return "elevated";
  return "high";
}

export function timeAgo(iso: string | null, now: number = Date.now()): string {
  if (!iso) return "never";
  const seconds = Math.max(0, Math.floor((now - new Date(iso).getTime()) / 1000));
  if (seconds < 5) return "just now";
  if (seconds < 60) return `${seconds}s ago`;
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  return `${Math.floor(minutes / 60)}h ago`;
}

const KIND_LABEL: Record<string, string> = {
  reasoning: "thinking", executed: "executed", escalated: "escalated", deferred: "deferred",
  blocked: "blocked", refused: "refused", error: "error", killed: "killed", paused: "paused", resumed: "resumed",
};

export function kindLabel(kind: string): string {
  return KIND_LABEL[kind] ?? kind;
}
