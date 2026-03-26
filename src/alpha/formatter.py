"""
Telegram Alert Formatter
Formats Alpha Engine predictions into clean Telegram messages.
"""

from datetime import datetime, timezone


def format_alert(prediction: dict, accuracy_stats: dict = None) -> str:
    """
    Format a prediction dict into a Telegram-ready alert message.
    
    Expected prediction keys:
        coin, price, funding_rate, rsi, direction, confidence,
        entry_low, entry_high, stop, target1, target2,
        size_units, size_usd, risk_usd, risk_pct,
        signal_labels
    """
    coin = prediction.get("coin", "SOL")
    price = prediction.get("price", 0)
    funding_rate = prediction.get("funding_rate", None)
    rsi = prediction.get("rsi", None)
    direction = prediction.get("direction", "neutral")
    confidence = prediction.get("confidence", 0)
    
    entry_low = prediction.get("entry_low", price * 0.98)
    entry_high = prediction.get("entry_high", price * 1.02)
    stop = prediction.get("stop", 0)
    target1 = prediction.get("target1", 0)
    target2 = prediction.get("target2", 0)
    size_units = prediction.get("size_units", 0)
    size_usd = prediction.get("size_usd", 0)
    risk_usd = prediction.get("risk_usd", 0)
    risk_pct = prediction.get("risk_pct", 0)
    signal_labels = prediction.get("signal_labels", "Unknown")
    
    # Date/time header
    now_str = datetime.now(timezone.utc).strftime("%b %d %H:%M UTC")
    
    # Funding rate display
    if funding_rate is not None:
        fr_pct = funding_rate * 100
        fr_sign = "+" if fr_pct >= 0 else ""
        if abs(fr_pct) > 0.01:
            fr_emoji = "🔴" if fr_pct > 0.01 else "🟢"
        else:
            fr_emoji = "⚪"
        fr_str = f"Funding {fr_sign}{fr_pct:.3f}% {fr_emoji}"
    else:
        fr_str = "Funding N/A"
    
    # RSI display
    rsi_str = f"RSI {rsi:.0f}" if rsi is not None else "RSI N/A"
    
    # Direction label
    direction_label = "Long" if direction == "long" else "Short" if direction == "short" else "Neutral"
    signal_emoji = "📈" if direction == "long" else "📉" if direction == "short" else "⚖️"
    
    # Accuracy stats (last 30d if available)
    acc_line = _format_accuracy(accuracy_stats) if accuracy_stats else None
    
    lines = [
        f"📊 ALPHA SCAN | {now_str}",
        "",
        f"{coin} ${price:,.2f} | {fr_str} | {rsi_str}",
        "",
        f"🎯 SIGNAL: {direction_label} ({signal_labels})",
        f"✅ Confidence: {confidence*100:.0f}%",
        "",
        f"💰 TRADE SETUP",
        f"Entry: ${entry_low:,.2f} – ${entry_high:,.2f}",
        f"Stop: ${stop:,.2f} (2x ATR)",
        f"Target 1: ${target1:,.2f} (1.5R)",
        f"Target 2: ${target2:,.2f} (3R)",
        f"Size: {size_units:.2f} {coin} (${size_usd:,.0f})",
        f"Risk: ${risk_usd:,.0f} ({risk_pct:.1f}%)",
    ]
    
    if acc_line:
        lines += ["", f"⚡ {acc_line}"]
    
    return "\n".join(lines)


def _format_accuracy(stats: dict) -> str:
    """Format signal accuracy line for alert footer."""
    if not stats:
        return ""
    
    parts = []
    signal_names = {
        "funding_extreme": "Funding",
        "ttm_squeeze": "TTM",
        "rsi_extreme": "RSI",
        "whale_activity": "Whale",
        "ema_trend": "EMA",
        "fear_greed_extreme": "F&G",
    }
    
    for key, label in signal_names.items():
        if key in stats and stats[key].get("total", 0) >= 3:
            wr = stats[key].get("win_rate", 0) * 100
            parts.append(f"{label} {wr:.0f}%")
    
    if not parts:
        return ""
    
    return "Signal accuracy (30d): " + " | ".join(parts)


def format_heartbeat(assets: list) -> str:
    """Format a heartbeat no-signal message."""
    now_str = datetime.now(timezone.utc).strftime("%b %d %H:%M UTC")
    return f"📊 ALPHA SCAN | {now_str}\n{'|'.join(assets)} — No signal (confidence below threshold)"
