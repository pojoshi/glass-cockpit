"""Synthetic cost per step. No model runs here (see proposers.py in countersigned-actions
for why); this estimates what a real call would have cost, for the per-agent cost panel.

Flat reasoning overhead plus a per-character rate on the params a real prompt would
have to describe, at prices roughly in line with a small current model.
"""

import json
from typing import Any

BASE_TOKENS = 180          # system + task framing, per step
CHARS_PER_TOKEN = 4
PRICE_PER_1K_TOKENS_CENTS = 0.3


def estimate(operation: str, params: dict[str, Any]) -> tuple[int, int]:
    """(tokens, cost_cents) for one reasoning-and-proposal step."""
    body_chars = len(operation) + len(json.dumps(params, separators=(",", ":")))
    tokens = BASE_TOKENS + body_chars // CHARS_PER_TOKEN
    cost_cents = round(tokens / 1000 * PRICE_PER_1K_TOKENS_CENTS, 3)
    return tokens, cost_cents
