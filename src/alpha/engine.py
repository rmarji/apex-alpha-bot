"""
Alpha Engine Core
Orchestrates signal fetching, scoring, position sizing, and alert generation.

Improvements (2026-03-26):
  - Hard max loss cap per trade (2R absolute, prevents account-threatening losses)
  - Regime gate: skip/reduce in extreme volatility (where fills and stops fail)
  - Time stop: close stale trades after 8h if no 1R profit hit
  - MiroFish as entry veto: skip trade if social simulation contradicts technicals
  - MiroFish as confidence booster: add boost when simulation confirms direction
  - Weight optimizer: auto-adjusts signal weights after each MiroFish run
"""

import os
import json
import threading
from datetime import datetime, timezone

from . import config as cfg
from .signals import get_all_signals, compute_atr
from .tracker import log_prediction, load_weights, load_accuracy_stats
from .formatter import format_alert


def _get_sizing_multiplier(confidence: float) -> float:
    """Get size multiplier based on confidence tier."""
    for (low, high), mult in cfg.SIZING_TIERS.items():
        if low <= confidence < high:
            return mult
    return 1.0


def _evaluate_signals(coin: str, data: dict, weights: dict) -> dict:
    """
    Evaluate all signals for a single coin.
    Returns dict with: scores, fired, direction_votes, labels
    """
    prices = data.get("prices", {})
    funding_rates = data.get("funding_rates", {})
    fg = data.get("fear_greed", {})
    asset = data.get("assets", {}).get(coin, {})

    price = prices.get(coin, 0)
    funding = funding_rates.get(coin, None)
    rsi = asset.get("rsi", 50)
    ema20 = asset.get("ema20", price)
    ema50 = asset.get("ema50", price)
    ttm = asset.get("ttm_squeeze", {})
    fg_value = fg.get("value", 50)

    scores = {}
    fired = {}
    direction_votes = []
    labels = []

    # ── 1. Funding Extreme ──────────────────────────────────────────────────
    threshold = cfg.FUNDING_EXTREME_THRESHOLD
    if funding is not None and abs(funding) >= threshold:
        score = min(1.0, abs(funding) / (threshold * 3))
        scores["funding_extreme"] = score
        fired["funding_extreme"] = True
        if funding > 0:
            direction_votes.append("short")
            labels.append("Crowded Longs")
        else:
            direction_votes.append("long")
            labels.append("Crowded Shorts")
    else:
        scores["funding_extreme"] = 0
        fired["funding_extreme"] = False

    # ── 2. RSI Extreme ──────────────────────────────────────────────────────
    if rsi <= cfg.RSI_OVERSOLD:
        score = (cfg.RSI_OVERSOLD - rsi) / cfg.RSI_OVERSOLD
        scores["rsi_extreme"] = min(1.0, score)
        fired["rsi_extreme"] = True
        direction_votes.append("long")
        labels.append(f"RSI Oversold ({rsi:.0f})")
    elif rsi >= cfg.RSI_OVERBOUGHT:
        score = (rsi - cfg.RSI_OVERBOUGHT) / (100 - cfg.RSI_OVERBOUGHT)
        scores["rsi_extreme"] = min(1.0, score)
        fired["rsi_extreme"] = True
        direction_votes.append("short")
        labels.append(f"RSI Overbought ({rsi:.0f})")
    else:
        scores["rsi_extreme"] = 0
        fired["rsi_extreme"] = False

    # ── 3. TTM Squeeze ──────────────────────────────────────────────────────
    ttm_state = ttm.get("state", "off")
    ttm_dir = ttm.get("direction")

    if ttm_state == "firing":
        scores["ttm_squeeze"] = 1.0
        fired["ttm_squeeze"] = True
        if ttm_dir:
            direction_votes.append(ttm_dir)
        labels.append("TTM Firing")
    elif ttm_state == "on":
        scores["ttm_squeeze"] = 0.5
        fired["ttm_squeeze"] = True
        if ttm_dir:
            direction_votes.append(ttm_dir)
        labels.append("TTM Building")
    else:
        scores["ttm_squeeze"] = 0
        fired["ttm_squeeze"] = False

    # ── 4. Whale Activity (price vs EMA50 divergence proxy) ─────────────────
    if price > 0 and ema50 > 0:
        price_vs_ema50 = (price - ema50) / ema50
        if abs(price_vs_ema50) > 0.05:
            score = min(1.0, abs(price_vs_ema50) / 0.15)
            scores["whale_activity"] = score
            fired["whale_activity"] = True
            direction_votes.append("long" if price_vs_ema50 < 0 else "short")
            labels.append("Accumulation" if price_vs_ema50 < 0 else "Distribution")
        else:
            scores["whale_activity"] = 0
            fired["whale_activity"] = False
    else:
        scores["whale_activity"] = 0
        fired["whale_activity"] = False

    # ── 5. Fear & Greed Extreme ─────────────────────────────────────────────
    if fg_value <= cfg.FG_EXTREME_FEAR:
        score = (cfg.FG_EXTREME_FEAR - fg_value) / cfg.FG_EXTREME_FEAR
        scores["fear_greed_extreme"] = min(1.0, score)
        fired["fear_greed_extreme"] = True
        direction_votes.append("long")
        labels.append(f"Extreme Fear ({fg_value})")
    elif fg_value >= cfg.FG_EXTREME_GREED:
        score = (fg_value - cfg.FG_EXTREME_GREED) / (100 - cfg.FG_EXTREME_GREED)
        scores["fear_greed_extreme"] = min(1.0, score)
        fired["fear_greed_extreme"] = True
        direction_votes.append("short")
        labels.append(f"Extreme Greed ({fg_value})")
    else:
        scores["fear_greed_extreme"] = 0
        fired["fear_greed_extreme"] = False

    # ── 6. EMA Trend ────────────────────────────────────────────────────────
    if ema20 > 0 and ema50 > 0:
        if ema20 > ema50 and price > ema20:
            scores["ema_trend"] = 0.8
            fired["ema_trend"] = True
            direction_votes.append("long")
            labels.append("Uptrend")
        elif ema20 < ema50 and price < ema20:
            scores["ema_trend"] = 0.8
            fired["ema_trend"] = True
            direction_votes.append("short")
            labels.append("Downtrend")
        else:
            scores["ema_trend"] = 0
            fired["ema_trend"] = False
    else:
        scores["ema_trend"] = 0
        fired["ema_trend"] = False

    return {
        "scores": scores,
        "fired": fired,
        "direction_votes": direction_votes,
        "labels": labels,
        "rsi": rsi,
        "funding": funding,
        "price": price,
        "ema20": ema20,
        "ema50": ema50,
        "ttm_state": ttm_state,
        "ttm_direction": ttm_dir,
    }


def _compute_confidence(scores: dict, weights: dict) -> float:
    """Compute weighted confidence score."""
    total_weight = 0
    weighted_score = 0
    for signal, score in scores.items():
        w = weights.get(signal, 0)
        weighted_score += w * score
        total_weight += w
    if total_weight == 0:
        return 0
    return weighted_score / total_weight


def _determine_direction(direction_votes: list) -> str:
    """Majority vote on direction."""
    if not direction_votes:
        return "neutral"
    long_votes = direction_votes.count("long")
    short_votes = direction_votes.count("short")
    if long_votes > short_votes:
        return "long"
    elif short_votes > long_votes:
        return "short"
    return "neutral"


def _get_regime(data: dict, coin: str) -> str:
    """
    Return current volatility regime for a coin.
    Reads from asset data or falls back to 'unknown'.
    """
    asset = data.get("assets", {}).get(coin, {})
    return asset.get("regime", "unknown")


def _calculate_position(coin: str, price: float, direction: str, atr: float, confidence: float) -> dict:
    """
    Calculate position size and levels.
    Stop = 2x ATR from entry.
    Hard cap: max loss = 2R absolute (MAX_LOSS_PER_TRADE_USD in config).
    """
    atr_stop = atr * 2 if atr > 0 else price * 0.03

    if direction == "long":
        entry = price
        stop = entry - atr_stop
        target1 = entry + (atr_stop * 1.5)
        target2 = entry + (atr_stop * 3.0)
        entry_low = entry * 0.99
        entry_high = entry * 1.01
    elif direction == "short":
        entry = price
        stop = entry + atr_stop
        target1 = entry - (atr_stop * 1.5)
        target2 = entry - (atr_stop * 3.0)
        entry_low = entry * 0.99
        entry_high = entry * 1.01
    else:
        return {}

    risk_per_unit = abs(entry - stop)
    if risk_per_unit == 0:
        return {}

    base_risk = cfg.ACCOUNT_SIZE * cfg.RISK_PER_TRADE
    size_mult = _get_sizing_multiplier(confidence)
    risk_amount = base_risk * size_mult

    # ── Hard max loss cap ───────────────────────────────────────────────────
    # Never risk more than MAX_LOSS_PER_TRADE_USD regardless of sizing tier.
    # This is the fix for the -$17 single-trade blowout.
    max_loss = getattr(cfg, "MAX_LOSS_PER_TRADE_USD", risk_amount)
    risk_amount = min(risk_amount, max_loss)

    size_units = risk_amount / risk_per_unit
    size_usd = size_units * price
    risk_pct = (risk_amount / cfg.ACCOUNT_SIZE) * 100

    # Hard stop price = entry ± (max_loss / size_units)
    hard_stop_distance = risk_amount / size_units if size_units > 0 else atr_stop
    if direction == "long":
        hard_stop = entry - hard_stop_distance
    else:
        hard_stop = entry + hard_stop_distance

    return {
        "entry": entry,
        "entry_low": entry_low,
        "entry_high": entry_high,
        "stop": stop,
        "hard_stop": hard_stop,
        "target1": target1,
        "target2": target2,
        "size_units": size_units,
        "size_usd": size_usd,
        "risk_usd": risk_amount,
        "risk_pct": risk_pct,
        "atr": atr,
        "max_hold_hours": getattr(cfg, "MAX_HOLD_HOURS", 8),
    }


def _run_mirofish_async(coin: str, direction: str, fired: dict, result_store: dict) -> None:
    """
    Run MiroFish pipeline in background thread.
    Stores result in result_store dict (thread-safe via GIL for dict writes).
    """
    try:
        from .mirofish_runner import main as mirofish_main, check_conditions
        ok, reason = check_conditions(force=False)
        if not ok:
            result_store["skipped"] = reason
            return
        from .mirofish_runner import run_pipeline, parse_actions
        detail = run_pipeline()
        result = parse_actions(detail)
        result_store["result"] = result

        # Auto-update weights based on MiroFish direction vs fired signals
        from .weight_updater import update_weights
        signal_dirs = {}
        for sig, fired_bool in fired.items():
            if not fired_bool:
                continue
            # Map each signal's direction vote
            # We use direction as a proxy — if the overall direction matches, signal agreed
            signal_dirs[sig] = direction
        update_weights(result["direction"], signal_dirs)

    except Exception as e:
        result_store["error"] = str(e)


def run_scan() -> str | None:
    """
    Run a full alpha scan across all configured assets.

    Pipeline:
      1. Fetch market data
      2. Score 6 signals per coin, compute weighted confidence
      3. Regime gate: skip extreme-volatility trades (they bleed)
      4. If confidence > MIROFISH_CONFIDENCE_THRESHOLD: run MiroFish (async)
         - If MiroFish contradicts direction → veto trade (skip)
         - If MiroFish confirms → boost confidence by result["confidence_boost"]
      5. Alert if final confidence >= MIN_CONFIDENCE
      6. Log prediction + run weight optimizer in background

    Returns formatted alert string, or None if no signal qualifies.
    """
    os.makedirs(cfg.DATA_DIR, exist_ok=True)

    weights = load_weights()
    accuracy_stats = load_accuracy_stats()

    try:
        data = get_all_signals()
    except Exception:
        return None

    best_alert = None
    best_confidence = 0

    for coin in cfg.ASSETS:
        asset_data = data.get("assets", {}).get(coin, {})
        if asset_data.get("error"):
            continue

        eval_result = _evaluate_signals(coin, data, weights)
        scores = eval_result["scores"]
        fired = eval_result["fired"]
        direction_votes = eval_result["direction_votes"]
        labels = eval_result["labels"]

        confidence = _compute_confidence(scores, weights)
        direction = _determine_direction(direction_votes)

        # ── Regime gate ─────────────────────────────────────────────────────
        # Extreme volatility = bad fills, stops get ripped through.
        # The data shows: 36 trades in 'extreme' regime, only 47% WR, -$20 PnL.
        # Skip extreme regime entirely; reduce size in 'high'.
        regime = _get_regime(data, coin)
        if regime == "extreme":
            # Skip trade — don't alert
            continue
        elif regime == "high":
            # Reduce confidence (forces smaller size tier)
            confidence *= 0.8

        # ── MiroFish integration (optional, async) ──────────────────────────
        mirofish_enabled = getattr(cfg, "MIROFISH_ENABLED", False)
        mirofish_threshold = getattr(cfg, "MIROFISH_CONFIDENCE_THRESHOLD", 0.50)
        mf_result = None

        if mirofish_enabled and confidence >= mirofish_threshold and direction != "neutral":
            mf_store = {}
            mf_thread = threading.Thread(
                target=_run_mirofish_async,
                args=(coin, direction, fired, mf_store),
                daemon=True,
            )
            mf_thread.start()
            # Wait up to 10 min for MiroFish (pipeline takes 5-8 min)
            mf_thread.join(timeout=600)
            mf_result = mf_store.get("result")

            if mf_result:
                mf_direction = mf_result.get("direction", "neutral")
                mf_boost = mf_result.get("confidence_boost", 0)

                if mf_direction != "neutral" and mf_direction != direction:
                    # ── VETO: MiroFish contradicts technicals → skip ─────────
                    labels.append(f"⛔ MiroFish veto ({mf_direction})")
                    continue  # Don't alert this coin
                elif mf_direction == direction:
                    # ── CONFIRM: boost confidence ────────────────────────────
                    confidence = min(1.0, confidence + mf_boost)
                    labels.append(f"🧠 MiroFish confirmed (+{mf_boost:.2f})")

        # ── Position sizing ─────────────────────────────────────────────────
        price = eval_result["price"]
        atr = asset_data.get("atr", price * 0.02)
        position = _calculate_position(coin, price, direction if direction != "neutral" else "long", atr, confidence)
        if not position:
            continue

        # ── Build prediction record ─────────────────────────────────────────
        prediction = {
            "coin": coin,
            "direction": direction,
            "confidence": round(confidence, 4),
            "entry_price": price,
            "price": price,
            "funding_rate": eval_result.get("funding"),
            "rsi": eval_result.get("rsi"),
            "regime": regime,
            "entry_low": position["entry_low"],
            "entry_high": position["entry_high"],
            "stop": position["stop"],
            "hard_stop": position.get("hard_stop"),
            "target1": position["target1"],
            "target2": position["target2"],
            "size_units": position["size_units"],
            "size_usd": position["size_usd"],
            "risk_usd": position["risk_usd"],
            "risk_pct": position["risk_pct"],
            "max_hold_hours": position.get("max_hold_hours", 8),
            "signal_labels": " + ".join(labels) if labels else "Mixed Signals",
            "signals_fired": fired,
            "signal_scores": {k: round(v, 4) for k, v in scores.items()},
            "atr": atr,
            "mirofish": mf_result,
            "timestamp": data.get("timestamp", datetime.now(timezone.utc).isoformat()),
        }

        try:
            log_prediction(prediction)
        except Exception:
            pass

        if confidence >= cfg.MIN_CONFIDENCE:
            if confidence > best_confidence:
                best_confidence = confidence
                best_alert = format_alert(prediction, accuracy_stats if accuracy_stats else None)

    return best_alert
