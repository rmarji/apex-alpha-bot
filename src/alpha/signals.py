"""
Signal Collection - Fetch live data from Hyperliquid and compute signals.
Uses only stdlib (urllib.request, json).
"""

import urllib.request
import json
from datetime import datetime, timedelta

HYPERLIQUID_API = "https://api.hyperliquid.xyz/info"
FNG_API = "https://api.alternative.me/fng/"


def _post_hl(data: dict) -> dict:
    """POST to Hyperliquid API."""
    req = urllib.request.Request(
        HYPERLIQUID_API,
        data=json.dumps(data).encode('utf-8'),
        headers={'Content-Type': 'application/json'}
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read().decode('utf-8'))


def get_prices() -> dict:
    """Get current prices for SOL, ETH, BTC."""
    data = _post_hl({"type": "allMids"})
    # Returns: {"SOL": "123.45", "ETH": "2345.67", ...}
    return {
        "SOL": float(data.get("SOL", 0)),
        "ETH": float(data.get("ETH", 0)),
        "BTC": float(data.get("BTC", 0)),
    }


def _get_meta_and_ctxs() -> tuple:
    """
    Fetch metaAndAssetCtxs and return (name_to_idx, ctxs).
    meta = data[0] = dict with 'universe' key (list of {name, ...})
    ctxs = data[1] = list of context dicts (funding, oi, markPx, ...)
    """
    data = _post_hl({"type": "metaAndAssetCtxs"})
    name_to_idx = {}
    ctxs = []
    if isinstance(data, list) and len(data) >= 2:
        meta = data[0]
        ctxs = data[1] if isinstance(data[1], list) else []
        # meta is a dict with 'universe' key containing list of asset dicts
        if isinstance(meta, dict):
            universe = meta.get("universe", [])
        elif isinstance(meta, list):
            universe = meta
        else:
            universe = []
        for i, asset in enumerate(universe):
            if isinstance(asset, dict):
                name = asset.get("name", "")
                name_to_idx[name] = i
    return name_to_idx, ctxs


def get_funding_rates() -> dict:
    """Get funding rates for SOL, ETH."""
    name_to_idx, ctxs = _get_meta_and_ctxs()
    funding = {}
    for coin in ["SOL", "ETH"]:
        idx = name_to_idx.get(coin)
        if idx is not None and idx < len(ctxs):
            ctx = ctxs[idx]
            if isinstance(ctx, dict):
                fr = ctx.get("funding")
                if fr is not None:
                    funding[coin] = float(fr)
    return funding


def get_open_interest() -> dict:
    """Get open interest for SOL, ETH."""
    name_to_idx, ctxs = _get_meta_and_ctxs()
    oi = {}
    for coin in ["SOL", "ETH"]:
        idx = name_to_idx.get(coin)
        if idx is not None and idx < len(ctxs):
            ctx = ctxs[idx]
            if isinstance(ctx, dict):
                open_interest = ctx.get("openInterest") or ctx.get("open_interest")
                if open_interest is not None:
                    oi[coin] = float(open_interest)
    return oi


def get_candles(coin: str, interval: str, lookback_days: int) -> list:
    """
    Get OHLCV candles for a coin.
    interval: '1m', '5m', '15m', '1h', '4h', '1d'
    Returns: list of {o, h, l, c, v, t} sorted by time ascending
    """
    end_time = int(datetime.utcnow().timestamp() * 1000)
    start_time = int((datetime.utcnow() - timedelta(days=lookback_days)).timestamp() * 1000)
    
    resp = _post_hl({
        "type": "candleSnapshot",
        "req": {
            "coin": coin,
            "interval": interval,
            "startTime": start_time,
            "endTime": end_time,
        }
    })
    
    candles = []
    if isinstance(resp, list):
        for c in resp:
            if isinstance(c, dict):
                candles.append({
                    "t": c.get("t", 0),
                    "o": float(c.get("o", 0)),
                    "h": float(c.get("h", 0)),
                    "l": float(c.get("l", 0)),
                    "c": float(c.get("c", 0)),
                    "v": float(c.get("v", 0)),
                })
    # Sort by time ascending
    candles.sort(key=lambda x: x["t"])
    return candles


def compute_rsi(closes: list, period: int = 14) -> float:
    """
    Compute Wilder's smoothed RSI.
    Returns RSI value (0-100), or 50 if insufficient data.
    """
    if len(closes) < period + 1:
        return 50.0
    
    # Calculate price changes
    changes = [closes[i] - closes[i-1] for i in range(1, len(closes))]
    
    # Initial averages
    gains = [c if c > 0 else 0 for c in changes[:period]]
    losses = [-c if c < 0 else 0 for c in changes[:period]]
    
    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period
    
    # Wilder's smoothing for remaining periods
    for i in range(period, len(changes)):
        change = changes[i]
        if change > 0:
            avg_gain = (avg_gain * (period - 1) + change) / period
            avg_loss = avg_loss * (period - 1) / period
        else:
            avg_gain = avg_gain * (period - 1) / period
            avg_loss = (avg_loss * (period - 1) - change) / period
    
    if avg_loss == 0:
        return 100.0
    
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return rsi


def compute_ema(closes: list, period: int) -> float:
    """
    Compute EMA value.
    Returns last EMA value.
    """
    if len(closes) < period:
        return closes[-1] if closes else 0
    
    multiplier = 2 / (period + 1)
    ema = sum(closes[:period]) / period  # Start with SMA
    
    for price in closes[period:]:
        ema = (price - ema) * multiplier + ema
    
    return ema


def compute_atr(candles: list, period: int = 14) -> float:
    """
    Compute Average True Range.
    Returns ATR value.
    """
    if len(candles) < period + 1:
        return 0.0
    
    true_ranges = []
    for i in range(1, len(candles)):
        high = candles[i]["h"]
        low = candles[i]["l"]
        prev_close = candles[i-1]["c"]
        
        tr = max(
            high - low,
            abs(high - prev_close),
            abs(low - prev_close)
        )
        true_ranges.append(tr)
    
    if len(true_ranges) < period:
        return sum(true_ranges) / len(true_ranges) if true_ranges else 0
    
    # Initial ATR is SMA of TR
    atr = sum(true_ranges[:period]) / period
    
    # Smooth remaining
    for tr in true_ranges[period:]:
        atr = (atr * (period - 1) + tr) / period
    
    return atr


def check_ttm_squeeze(candles: list) -> dict:
    """
    Check TTM Squeeze status.
    Returns: {
        "state": "on" | "off" | "firing",
        "direction": "long" | "short" | None,
        "momentum": float
    }
    TTM Squeeze = Bollinger Band (20, 2) inside Keltner Channel (20, 1.5)
    """
    if len(candles) < 20:
        return {"state": "off", "direction": None, "momentum": 0}
    
    closes = [c["c"] for c in candles]
    
    # Bollinger Bands (20, 2)
    sma20 = sum(closes[-20:]) / 20
    std = (sum((c - sma20) ** 2 for c in closes[-20:]) / 20) ** 0.5
    bb_upper = sma20 + 2 * std
    bb_lower = sma20 - 2 * std
    
    # Keltner Channel (20, 1.5) - need ATR
    atr = compute_atr(candles, period=14)
    kc_upper = sma20 + 1.5 * atr
    kc_lower = sma20 - 1.5 * atr
    
    # Squeeze ON when BB inside KC
    squeeze_on = (bb_upper < kc_upper) and (bb_lower > kc_lower)
    
    # Momentum (LinReg slope of close over last 20 bars)
    n = 20
    x = list(range(n))
    y = closes[-n:]
    x_mean = sum(x) / n
    y_mean = sum(y) / n
    slope = sum((xi - x_mean) * (yi - y_mean) for xi, yi in zip(x, y)) / sum((xi - x_mean) ** 2 for xi in x)
    
    # Check if firing (just exited squeeze)
    if len(candles) >= 21:
        prev_closes = [c["c"] for c in candles[-21:-1]]
        prev_sma = sum(prev_closes[-20:]) / 20
        prev_std = (sum((c - prev_sma) ** 2 for c in prev_closes[-20:]) / 20) ** 0.5
        prev_bb_upper = prev_sma + 2 * prev_std
        prev_bb_lower = prev_sma - 2 * prev_std
        prev_atr = compute_atr(candles[-21:], period=14)
        prev_kc_upper = prev_sma + 1.5 * prev_atr
        prev_kc_lower = prev_sma - 1.5 * prev_atr
        prev_squeeze = (prev_bb_upper < prev_kc_upper) and (prev_bb_lower > prev_kc_lower)
        
        firing = prev_squeeze and not squeeze_on
    else:
        firing = False
    
    state = "firing" if firing else ("on" if squeeze_on else "off")
    direction = "long" if slope > 0 else ("short" if slope < 0 else None)
    
    return {
        "state": state,
        "direction": direction,
        "momentum": slope
    }


def get_fear_greed() -> dict:
    """
    Get Fear & Greed index from alternative.me API.
    Returns: {"value": int, "classification": str}
    """
    try:
        req = urllib.request.Request(FNG_API, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            if data.get("data") and len(data["data"]) > 0:
                fg = data["data"][0]
                return {
                    "value": int(fg.get("value", 50)),
                    "classification": fg.get("value_classification", "Neutral")
                }
    except Exception:
        pass
    return {"value": 50, "classification": "Neutral"}


def get_all_signals() -> dict:
    """Fetch all signal data and return aggregated dict."""
    prices = get_prices()
    funding = get_funding_rates()
    oi = get_open_interest()
    fg = get_fear_greed()
    
    result = {
        "timestamp": datetime.utcnow().isoformat(),
        "prices": prices,
        "funding_rates": funding,
        "open_interest": oi,
        "fear_greed": fg,
        "assets": {}
    }
    
    for coin in ["SOL", "ETH"]:
        try:
            candles = get_candles(coin, "1d", 30)
            closes = [c["c"] for c in candles]
            
            result["assets"][coin] = {
                "candles": candles,
                "rsi": compute_rsi(closes, 14),
                "ema20": compute_ema(closes, 20),
                "ema50": compute_ema(closes, 50),
                "atr": compute_atr(candles, 14),
                "ttm_squeeze": check_ttm_squeeze(candles),
            }
        except Exception as e:
            result["assets"][coin] = {"error": str(e)}
    
    return result