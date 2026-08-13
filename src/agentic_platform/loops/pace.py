"""PACE anytime-valid keep gate (C6). Pure functions — no I/O."""

from __future__ import annotations


def wealth_update(wealth: float, won: bool, lam: float) -> float:
    if lam <= 0 or lam >= 1:
        raise ValueError("lambda must be in (0, 1)")
    return wealth * ((1.0 + lam) if won else (1.0 - lam))


def can_still_reach(wealth: float, remaining: int, lam: float, alpha: float) -> bool:
    """True if winning every remaining pair could still exceed 1/alpha."""
    if remaining < 0:
        remaining = 0
    return wealth * ((1.0 + lam) ** remaining) > (1.0 / alpha)


def should_keep(wealth: float, n_pairs: int, n_min: int, alpha: float) -> bool:
    return n_pairs >= n_min and wealth > (1.0 / alpha)
