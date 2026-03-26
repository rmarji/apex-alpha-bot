"""
Weight Updater — Adjusts alpha signal weights based on MiroFish direction confirmation.
MiroFish confirms signal → +0.02 (max 0.35)
MiroFish contradicts signal → -0.01 (min 0.05)
EMA smoothing: new = 0.9*old + 0.1*adjusted
"""

import json
from pathlib import Path

WEIGHTS_FILE = "/data/workspace-crypto/data/weights.json"

try:
    from src.alpha.config import SIGNAL_WEIGHTS as DEFAULT_WEIGHTS
except ImportError:
    DEFAULT_WEIGHTS = {
        "funding_extreme": 0.20,
        "rsi_extreme": 0.15,
        "ttm_squeeze": 0.25,
        "whale_activity": 0.15,
        "fear_greed_extreme": 0.10,
        "ema_trend": 0.15,
    }

EMA_ALPHA = 0.1  # weight of new observation
MAX_WEIGHT = 0.35
MIN_WEIGHT = 0.05
BOOST = 0.02
REDUCE = 0.01


def load_weights() -> dict:
    if Path(WEIGHTS_FILE).exists():
        with open(WEIGHTS_FILE) as f:
            return json.load(f)
    return dict(DEFAULT_WEIGHTS)


def save_weights(weights: dict):
    Path(WEIGHTS_FILE).parent.mkdir(parents=True, exist_ok=True)
    with open(WEIGHTS_FILE, "w") as f:
        json.dump(weights, f, indent=2)


def update_weights(mirofish_direction: str, fired_signals: dict[str, str]) -> dict:
    """
    fired_signals: {signal_name: "long"/"short"/"neutral"} — the direction each signal indicated.
    mirofish_direction: "long" / "short" / "neutral"
    Returns updated weights dict.
    """
    weights = load_weights()

    if mirofish_direction == "neutral":
        print("[weight_updater] MiroFish neutral — no weight adjustments")
        return weights

    changes = {}
    for signal, signal_dir in fired_signals.items():
        if signal not in weights:
            continue
        old = weights[signal]

        if signal_dir == mirofish_direction:
            # MiroFish confirms this signal
            adjusted = min(MAX_WEIGHT, old + BOOST)
            action = f"+{BOOST}"
        elif signal_dir != "neutral":
            # MiroFish contradicts this signal
            adjusted = max(MIN_WEIGHT, old - REDUCE)
            action = f"-{REDUCE}"
        else:
            continue

        # EMA smoothing
        new = round(0.9 * old + EMA_ALPHA * adjusted, 4)
        weights[signal] = new
        changes[signal] = {"old": old, "adjusted": adjusted, "new": new, "action": action}

    if changes:
        save_weights(weights)
        print("[weight_updater] Weight updates:")
        for sig, c in changes.items():
            print(f"  {sig}: {c['old']:.4f} → {c['new']:.4f} ({c['action']})")
    else:
        print("[weight_updater] No applicable signals to update")

    return weights


if __name__ == "__main__":
    # Demo
    import sys
    direction = sys.argv[1] if len(sys.argv) > 1 else "long"
    demo_signals = {
        "funding_extreme": "long",
        "rsi_extreme": "long",
        "ttm_squeeze": "short",
        "ema_trend": "long",
    }
    print(f"MiroFish direction: {direction}")
    result = update_weights(direction, demo_signals)
    print(json.dumps(result, indent=2))
