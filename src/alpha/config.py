"""
Alpha Engine Configuration
"""

# Account & Risk
ACCOUNT_SIZE = 5000
RISK_PER_TRADE = 0.015       # 1.5% base risk per trade
MAX_DAILY_RISK = 0.05        # 5% max daily drawdown
ASSETS = ["SOL", "ETH"]     # BTC excluded — consistently underperforms

# ── Hard loss cap ────────────────────────────────────────────────────────────
# Single-trade max loss. Overrides sizing tiers.
# Prevents the -$17 blowout scenario (4 SL hits = -$24.55 total).
MAX_LOSS_PER_TRADE_USD = 6.0  # Hard cap per trade in USD

# ── Time stop ────────────────────────────────────────────────────────────────
# Close stale trades after N hours if 1R profit not hit.
# Data: trades >12h have 0% win rate (-$12.49). Cut them.
MAX_HOLD_HOURS = 8

# ── Regime gating ────────────────────────────────────────────────────────────
# extreme regime: skip entirely (47% WR, -$20 PnL on 36 trades)
# high regime: reduce confidence by 20% (forces smaller size)
# low/medium: trade normally
# Regime is computed in regime.py and stored in asset data.
REGIME_SKIP = ["extreme"]        # Skip these regimes entirely
REGIME_REDUCE = ["high"]         # Reduce confidence in these regimes
REGIME_REDUCE_FACTOR = 0.80      # Multiply confidence by this in 'high'

# Scan interval
SCAN_INTERVAL_MIN = 30

# Signal weights (adaptive — start balanced, engine adjusts over time via weight_updater.py)
SIGNAL_WEIGHTS = {
    "funding_extreme": 0.20,
    "rsi_extreme": 0.15,
    "ttm_squeeze": 0.25,
    "whale_activity": 0.15,
    "fear_greed_extreme": 0.10,
    "ema_trend": 0.15,
}

# Thresholds
FUNDING_EXTREME_THRESHOLD = 0.0001   # ±0.01% funding rate
RSI_OVERSOLD = 30
RSI_OVERBOUGHT = 70
FG_EXTREME_FEAR = 25
FG_EXTREME_GREED = 75
MIN_CONFIDENCE = 0.55                # Don't alert below this

# Sizing rules based on confidence
SIZING_TIERS = {
    (0.55, 0.65): 0.5,    # half size
    (0.65, 0.75): 0.75,   # 3/4 size
    (0.75, 0.85): 1.0,    # full size
    (0.85, 1.0): 1.25,    # over-size (high-conviction only)
}

# ── MiroFish integration (optional) ─────────────────────────────────────────
# Set MIROFISH_ENABLED=True to activate social simulation layer.
# Requires MiroFish backend running on localhost:5001.
# When enabled:
#   - Fires when confidence >= MIROFISH_CONFIDENCE_THRESHOLD
#   - If MiroFish contradicts technicals → trade is VETOED (skipped)
#   - If MiroFish confirms → confidence boosted by result["confidence_boost"]
#   - After each run → weight_updater.py adjusts signal weights automatically
MIROFISH_ENABLED = False                    # Set True to enable
MIROFISH_CONFIDENCE_THRESHOLD = 0.50       # Minimum confidence to trigger MiroFish
MIROFISH_BASE_URL = "http://localhost:5001" # MiroFish backend URL

# Data paths
DATA_DIR = "/data/workspace-crypto/data"
