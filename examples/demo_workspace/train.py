"""Tiny CPU trainer — hostile metric; agents may edit hyperparameters only."""
from __future__ import annotations

import math

# === mutable hyperparameters (agent may edit) ===
LR = 0.05
STEPS = 40
HIDDEN = 8
L2 = 0.0
SEED = 0
# === end mutable ===


def main() -> None:
    n = 64
    xs = [(i / n) * 2 - 1 for i in range(n)]
    ys = [math.sin(3 * x) + 0.1 * x for x in xs]

    def rnd(i: int) -> float:
        return math.sin(SEED * 12.9898 + i * 78.233) * 43758.5453 % 1.0

    w1 = [rnd(i) * 0.5 - 0.25 for i in range(HIDDEN)]
    b1 = [rnd(100 + i) * 0.1 for i in range(HIDDEN)]
    w2 = [rnd(200 + i) * 0.5 - 0.25 for i in range(HIDDEN)]
    b2 = rnd(300) * 0.1

    for _ in range(STEPS):
        g_w1 = [0.0] * HIDDEN
        g_b1 = [0.0] * HIDDEN
        g_w2 = [0.0] * HIDDEN
        g_b2 = 0.0
        for x, y in zip(xs, ys):
            h = [math.tanh(w1[j] * x + b1[j]) for j in range(HIDDEN)]
            pred = sum(w2[j] * h[j] for j in range(HIDDEN)) + b2
            err = pred - y
            g_b2 += 2 * err
            for j in range(HIDDEN):
                g_w2[j] += 2 * err * h[j]
                dh = 2 * err * w2[j] * (1 - h[j] * h[j])
                g_w1[j] += dh * x
                g_b1[j] += dh
        scale = LR / n
        for j in range(HIDDEN):
            w1[j] -= scale * (g_w1[j] + 2 * L2 * w1[j])
            b1[j] -= scale * g_b1[j]
            w2[j] -= scale * (g_w2[j] + 2 * L2 * w2[j])
        b2 -= scale * g_b2

    loss = 0.0
    for x, y in zip(xs, ys):
        h = [math.tanh(w1[j] * x + b1[j]) for j in range(HIDDEN)]
        pred = sum(w2[j] * h[j] for j in range(HIDDEN)) + b2
        err = pred - y
        loss += err * err
    val_loss = loss / n + L2 * (sum(w * w for w in w1) + sum(w * w for w in w2))
    print(f"val_loss={val_loss:.6f}")


if __name__ == "__main__":
    main()
