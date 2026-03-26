#!/usr/bin/env python3
"""
measure_metric.py — Trading Bot Fitness Function
=================================================
Evaluates the current config.py against historical live trade data.
Used by the auto-optimizer loop as the scalar metric.

OUTPUTS: single float to stdout (higher = better)
Composite score = profit_factor * 0.5 + win_rate * 0.3 + (1/max_drawdown_factor) * 0.2

Profit factor: gross_wins / gross_losses (target > 1.0, currently ~0.50)
Win rate: wins / total (target > 0.60)
Max drawdown factor: worst single loss / avg win (target < 2.0)

Usage:
    python3 measure_metric.py           # uses data/live_trades.json
    python3 measure_metric.py --verbose # detailed breakdown
"""

import json
import sys
import os
from pathlib import Path

DATA_DIR = Path(__file__).parent / "data"
TRADES_FILE = DATA_DIR / "live_trades.json"
PREDICTIONS_FILE = DATA_DIR / "predictions.json"


def load_trades():
    if not TRADES_FILE.exists():
        return []
    with open(TRADES_FILE) as f:
        data = json.load(f)
    return data.get("trades", data) if isinstance(data, dict) else data


def load_predictions():
    if not PREDICTIONS_FILE.exists():
        return []
    with open(PREDICTIONS_FILE) as f:
        data = json.load(f)
    return data if isinstance(data, list) else []


def compute_score(trades: list, verbose: bool = False) -> float:
    if not trades:
        if verbose:
            print("No trades found. Score: 0.0")
        return 0.0

    wins = [t for t in trades if t.get("pnl", 0) > 0]
    losses = [t for t in trades if t.get("pnl", 0) < 0]

    total = len(trades)
    n_wins = len(wins)
    n_losses = len(losses)

    gross_wins = sum(t["pnl"] for t in wins) if wins else 0
    gross_losses = abs(sum(t["pnl"] for t in losses)) if losses else 0.001

    # ── Core metrics ────────────────────────────────────────────────────────
    profit_factor = gross_wins / gross_losses if gross_losses > 0 else 0.0
    win_rate = n_wins / total if total > 0 else 0.0
    avg_win = gross_wins / n_wins if n_wins > 0 else 0.0
    avg_loss = gross_losses / n_losses if n_losses > 0 else 0.001

    # Ratio of avg loss to avg win — lower is better
    loss_win_ratio = avg_loss / avg_win if avg_win > 0 else 10.0
    loss_win_score = max(0, 1.0 - (loss_win_ratio / 5.0))  # normalized 0-1

    # ── Regime analysis ─────────────────────────────────────────────────────
    extreme_trades = [t for t in trades if t.get("regime") == "extreme"]
    non_extreme = [t for t in trades if t.get("regime") != "extreme"]
    extreme_pnl = sum(t.get("pnl", 0) for t in extreme_trades)
    non_extreme_pnl = sum(t.get("pnl", 0) for t in non_extreme)

    # Penalize for extreme regime losses
    regime_penalty = max(0, -extreme_pnl / 50.0)  # normalized

    # ── Hold time analysis ───────────────────────────────────────────────────
    long_hold_losses = [t for t in trades if t.get("hold_time_hours", 0) > 12 and t.get("pnl", 0) < 0]
    hold_penalty = len(long_hold_losses) / max(total, 1)

    # ── Max single loss (catastrophic loss prevention) ───────────────────────
    worst_loss = min((t.get("pnl", 0) for t in trades), default=0)
    catastrophic_penalty = max(0, -worst_loss / 20.0)  # normalized, -$20 = 1.0 penalty

    # ── Composite score ──────────────────────────────────────────────────────
    score = (
        profit_factor   * 0.40 +   # primary: are we making money?
        win_rate        * 0.25 +   # secondary: how often right?
        loss_win_score  * 0.20 -   # RR quality
        regime_penalty  * 0.05 -   # penalize extreme regime losses
        hold_penalty    * 0.05 -   # penalize stale trades
        catastrophic_penalty * 0.05  # penalize blowout losses
    )

    score = max(0.0, round(score, 4))

    if verbose:
        print(f"\n{'='*50}")
        print(f"  TRADING BOT METRIC REPORT")
        print(f"{'='*50}")
        print(f"  Trades:         {total} ({n_wins}W / {n_losses}L)")
        print(f"  Win rate:       {win_rate*100:.1f}%")
        print(f"  Profit factor:  {profit_factor:.3f}  (target: >1.0)")
        print(f"  Avg win:        ${avg_win:.2f}")
        print(f"  Avg loss:      -${avg_loss:.2f}")
        print(f"  Realized RR:    {avg_win/avg_loss:.2f}x  (target: >1.5x)")
        print(f"  Worst loss:    ${worst_loss:.2f}")
        print(f"  Extreme regime: {len(extreme_trades)} trades, ${extreme_pnl:.2f} PnL")
        print(f"  Stale (>12h):   {len(long_hold_losses)} losing trades")
        print(f"  Non-extreme PnL: ${non_extreme_pnl:.2f}")
        print(f"\n  Penalties:")
        print(f"    Regime:       -{regime_penalty:.3f}")
        print(f"    Hold time:    -{hold_penalty:.3f}")
        print(f"    Catastrophic: -{catastrophic_penalty:.3f}")
        print(f"\n  ► COMPOSITE SCORE: {score:.4f}")
        print(f"    (current baseline ~0.20 | target >0.50)")
        print(f"{'='*50}\n")

    return score


def simulate_with_config(trades: list, config_path: str = None) -> float:
    """
    Simulate trades with modified config parameters.
    Applies config constraints to filter/adjust the historical trades.
    Requires >=5 simulated trades to return a meaningful score.
    """
    if config_path is None:
        config_path = str(Path(__file__).parent / "src" / "alpha" / "config.py")

    import importlib.util
    import importlib
    # Force fresh load — clear any cached module
    if "config" in sys.modules:
        del sys.modules["config"]
    spec = importlib.util.spec_from_file_location("config", config_path)
    cfg = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(cfg)
    except Exception as e:
        print(f"Config load error: {e}", file=sys.stderr)
        return 0.0

    max_loss = getattr(cfg, "MAX_LOSS_PER_TRADE_USD", 999)
    max_hold = getattr(cfg, "MAX_HOLD_HOURS", 999)
    risk_per_trade = getattr(cfg, "RISK_PER_TRADE", 0.015)
    # NOTE: We do NOT apply regime_skip to historical data.
    # The regime filter is a forward-looking guard for new trades.
    # For backtesting config params, we simulate what the risk controls
    # WOULD have done to our existing trade P&L.

    orig_risk = 0.015  # original RISK_PER_TRADE at time of trades
    simulated = []
    for t in trades:
        pnl = t.get("pnl", 0)
        hold_h = t.get("hold_time_hours", 0)
        t2 = dict(t)

        # Time stop: close losers after max_hold hours at flat cost
        if hold_h > max_hold and pnl < 0:
            t2["pnl"] = -0.30
            t2["hold_time_hours"] = max_hold

        # Hard max loss cap: largest losses get capped
        if t2["pnl"] < -max_loss:
            t2["pnl"] = -max_loss

        # Risk scaling: proportionally adjust all PnL if risk_per_trade changed
        if risk_per_trade != orig_risk and orig_risk > 0:
            t2["pnl"] = t2["pnl"] * (risk_per_trade / orig_risk)

        simulated.append(t2)

    return compute_score(simulated)


if __name__ == "__main__":
    verbose = "--verbose" in sys.argv or "-v" in sys.argv
    use_sim = "--simulate" in sys.argv  # apply config constraints to historical data

    trades = load_trades()

    if not trades:
        print("0.0")
        if verbose:
            print("No trade data found.", file=sys.stderr)
        sys.exit(0)

    if use_sim:
        score = simulate_with_config(trades)
    else:
        score = compute_score(trades, verbose=verbose)

    if not verbose:
        print(score)
