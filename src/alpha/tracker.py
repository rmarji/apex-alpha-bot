"""
Outcome Tracking & Self-Improvement
Logs predictions, checks outcomes, and updates signal weights.
"""

import json
import os
from datetime import datetime, timezone

from . import config as cfg

DATA_DIR = cfg.DATA_DIR
PREDICTIONS_FILE = os.path.join(DATA_DIR, "predictions.json")
ACCURACY_FILE = os.path.join(DATA_DIR, "accuracy_stats.json")
WEIGHTS_FILE = os.path.join(DATA_DIR, "signal_weights.json")


def _ensure_data_dir():
    os.makedirs(DATA_DIR, exist_ok=True)


def _load_json(path: str, default) -> any:
    if os.path.exists(path):
        try:
            with open(path, 'r') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
    return default


def _save_json(path: str, data) -> None:
    _ensure_data_dir()
    with open(path, 'w') as f:
        json.dump(data, f, indent=2)


def log_prediction(prediction: dict) -> None:
    """
    Append a prediction to predictions.json.
    prediction dict should include: timestamp, coin, direction, confidence,
    entry, stop, target1, target2, signals_fired, entry_price, atr
    """
    _ensure_data_dir()
    predictions = _load_json(PREDICTIONS_FILE, [])
    if not isinstance(predictions, list):
        predictions = []
    
    prediction["logged_at"] = datetime.now(timezone.utc).isoformat()
    prediction["outcome"] = None  # Will be filled by check_outcomes()
    predictions.append(prediction)
    
    _save_json(PREDICTIONS_FILE, predictions)


def check_outcomes() -> None:
    """
    For predictions older than 4h, fetch current price and check outcome.
    Updates predictions.json with resolved outcomes.
    """
    from .signals import get_prices
    
    predictions = _load_json(PREDICTIONS_FILE, [])
    if not predictions:
        return
    
    # Fetch current prices
    try:
        current_prices = get_prices()
    except Exception as e:
        print(f"[tracker] Failed to fetch prices: {e}")
        return
    
    now = datetime.now(timezone.utc)
    updated = False
    
    for pred in predictions:
        if pred.get("outcome") is not None:
            continue
        
        # Check if prediction is older than 4h
        try:
            logged_at = datetime.fromisoformat(pred["logged_at"])
            if logged_at.tzinfo is None:
                logged_at = logged_at.replace(tzinfo=timezone.utc)
            age_hours = (now - logged_at).total_seconds() / 3600
        except (KeyError, ValueError):
            continue
        
        if age_hours < 4:
            continue
        
        coin = pred.get("coin", "SOL")
        current_price = current_prices.get(coin)
        if not current_price:
            continue
        
        direction = pred.get("direction")
        entry_price = pred.get("entry_price")
        target1 = pred.get("target1")
        stop = pred.get("stop")
        
        if not all([entry_price, target1, stop]):
            pred["outcome"] = "incomplete_data"
            updated = True
            continue
        
        # Determine outcome
        if direction == "long":
            if current_price >= target1:
                pred["outcome"] = "win"
                pred["outcome_reason"] = "target1_hit"
            elif current_price <= stop:
                pred["outcome"] = "loss"
                pred["outcome_reason"] = "stop_hit"
            else:
                pred["outcome"] = "open"
        elif direction == "short":
            if current_price <= target1:
                pred["outcome"] = "win"
                pred["outcome_reason"] = "target1_hit"
            elif current_price >= stop:
                pred["outcome"] = "loss"
                pred["outcome_reason"] = "stop_hit"
            else:
                pred["outcome"] = "open"
        
        if pred.get("outcome") not in (None, "open"):
            pred["exit_price"] = current_price
            pred["resolved_at"] = now.isoformat()
            updated = True
    
    if updated:
        _save_json(PREDICTIONS_FILE, predictions)
        print(f"[tracker] Updated outcomes for predictions.")
        update_accuracy()


def update_accuracy() -> None:
    """
    Compute win rate per signal type and save to accuracy_stats.json.
    """
    predictions = _load_json(PREDICTIONS_FILE, [])
    
    # Count wins/losses per signal
    signal_stats: dict = {}
    
    for pred in predictions:
        outcome = pred.get("outcome")
        if outcome not in ("win", "loss"):
            continue
        
        signals_fired = pred.get("signals_fired", {})
        for signal_name, fired in signals_fired.items():
            if not fired:
                continue
            if signal_name not in signal_stats:
                signal_stats[signal_name] = {"wins": 0, "losses": 0, "total": 0}
            
            signal_stats[signal_name]["total"] += 1
            if outcome == "win":
                signal_stats[signal_name]["wins"] += 1
            else:
                signal_stats[signal_name]["losses"] += 1
    
    # Compute win rates
    accuracy = {}
    for signal, stats in signal_stats.items():
        total = stats["total"]
        accuracy[signal] = {
            "wins": stats["wins"],
            "losses": stats["losses"],
            "total": total,
            "win_rate": round(stats["wins"] / total, 4) if total > 0 else 0.0,
        }
    
    accuracy["last_updated"] = datetime.now(timezone.utc).isoformat()
    _save_json(ACCURACY_FILE, accuracy)
    print(f"[tracker] Accuracy stats updated for {len(accuracy)-1} signals.")


def optimize_weights() -> None:
    """
    Adjust signal weights based on historical win rates.
    - Win rate > 60%: increase weight by 10%
    - Win rate < 45%: decrease weight by 15%
    Normalizes all weights to sum to 1.0.
    Saves updated weights to signal_weights.json.
    """
    accuracy = _load_json(ACCURACY_FILE, {})
    
    # Load current weights (use saved if available, else defaults)
    saved_weights = _load_json(WEIGHTS_FILE, {})
    weights = dict(cfg.SIGNAL_WEIGHTS)  # Start from defaults
    if isinstance(saved_weights, dict) and saved_weights:
        # Merge saved weights (only for keys that exist in defaults)
        for k in weights:
            if k in saved_weights:
                weights[k] = saved_weights[k]
    
    adjusted = []
    for signal, weight in weights.items():
        stats = accuracy.get(signal)
        if not stats or stats.get("total", 0) < 5:
            # Not enough data — skip adjustment
            continue
        
        win_rate = stats.get("win_rate", 0.5)
        
        if win_rate > 0.60:
            weights[signal] = weight * 1.10  # +10%
            adjusted.append(f"{signal}: +10% (WR={win_rate:.0%})")
        elif win_rate < 0.45:
            weights[signal] = weight * 0.85  # -15%
            adjusted.append(f"{signal}: -15% (WR={win_rate:.0%})")
    
    # Normalize to sum to 1.0
    total = sum(weights.values())
    if total > 0:
        weights = {k: round(v / total, 4) for k, v in weights.items()}
    
    # Re-normalize due to rounding
    total = sum(weights.values())
    if total != 1.0:
        # Adjust the largest weight to fix rounding
        largest = max(weights, key=weights.get)
        weights[largest] = round(weights[largest] + (1.0 - total), 4)
    
    weights["last_updated"] = datetime.now(timezone.utc).isoformat()
    _save_json(WEIGHTS_FILE, weights)
    
    if adjusted:
        print(f"[optimizer] Adjusted: {', '.join(adjusted)}")
    else:
        print(f"[optimizer] No adjustments needed (insufficient data or stable win rates).")
    print(f"[optimizer] Weights saved: {json.dumps({k: v for k, v in weights.items() if k != 'last_updated'}, indent=2)}")


def load_weights() -> dict:
    """Load signal weights (from file if available, else defaults)."""
    saved = _load_json(WEIGHTS_FILE, {})
    weights = dict(cfg.SIGNAL_WEIGHTS)
    if isinstance(saved, dict):
        for k in weights:
            if k in saved and isinstance(saved[k], (int, float)):
                weights[k] = saved[k]
    return weights


def load_accuracy_stats() -> dict:
    """Load accuracy stats."""
    return _load_json(ACCURACY_FILE, {})
