# Agent ops as a discipline

Right now, running an AI agent in production means someone's tailing logs. That's where
SRE was before Nagios: real incidents, no shared vocabulary, no tooling built around
intervening mid-flight rather than reading about it after.

The job isn't "watch the agent." It's what SRE already did for distributed systems:
define what healthy looks like, catch drift before it's an incident, give a human a
fast way to step in, and keep a record good enough to debug what you didn't catch.
Agents just make the stakes stranger — the failure mode isn't a stack trace, it's a
plausible-sounding action that happens to be wrong.

Two things I'd call non-negotiable here, because building this forced me to notice I'd
otherwise skip them. First: the kill switch an operator presses and the check the
policy layer runs at execution time have to be *separately* trustworthy — an
operator's intervention can be late, wrong, or aimed at the wrong agent, so the policy
layer has to assume that and check anyway. Second: drift needs a number, not a vibe.
"Seems off" doesn't scale past three agents; a score an operator can watch rise over a
shift does.

Pushing back on my own build: a 10-step rolling window is a cheap signal, not a real
anomaly detector, and synthetic cost estimates stand in for knowing what agents
actually cost. Both are fine for a cockpit meant to be understood in one sitting.
Neither is fine for a real fleet.

In two years, I'd expect the control plane to outlive any one model — agents get
swapped, the operator surface and its audit trail don't. Whoever owns that layer can
answer, under oath if it has to, exactly what their agents were allowed to do and why.
