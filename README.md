# Short-Bias Alpha Bot 🐺

Automated trading system for SOL-PERP and ETH-PERP on Hyperliquid — combining technical signal scoring, adaptive weight learning, and optional AI social simulation.

> Built by ApexAlpha. Real money. Real risk. No hype.

---

## What This Does

Most bots trade on price alone. This one scores **6 market signals**, weights them adaptively, and fires alerts only when enough evidence agrees.

**Signal stack:**
- Funding rate extremes (crowded longs/shorts)
- RSI extreme readings (momentum exhaustion)
- TTM Squeeze (volatility breakouts)
- Whale activity (on-chain accumulation/distribution)
- Fear & Greed Index (contrarian sentiment)
- EMA trend alignment (macro direction)

Each signal has a weight. Weights adapt over time. More on that below.

---

## Strategy Logic

**Short-Bias Alpha (SOL/ETH, 15m + 4H)**

Entry requires ALL:
1. HTF Trend Down: 4H close < 200 EMA
2. LTF SuperTrend Bearish: 15m direction = -1
3. Keltner Break: Close < Keltner lower band (EMA 20 ± 2.0 × ATR)
4. Volatility Gate: ATR% > median over 50 bars

Exit:
- Stop Loss: Entry + 2 × ATR
- Take Profit: Entry − 3R
- Trailing Stop: activates after 1R, trails at 0.8 × ATR

**TTM Squeeze (SOL Daily / ETH 4H)**
- Bollinger Bands inside Keltner Channels = compression
- Momentum histogram + EMA alignment = breakout direction
- Separate bot, separate sizing

**Risk:**
- 1% account risk per trade
- Size from stop, not from conviction
- Halt if drawdown exceeds threshold

---

## Setup

```bash
git clone <repo>
cd workspace-crypto

python3 -m venv .venv
source .venv/bin/activate

pip install -r requirements.txt

cp .env.example .env
# Edit .env with your HL key + Telegram bot token
```

---

## Run Live Bot

```bash
# Testnet (default, safe)
python src/bot.py

# Mainnet (real money)
python src/bot.py --mainnet

# Status check
python src/bot.py --status

# Close all positions
python src/bot.py --close-all
```

---

## Alpha Signal Scanner

Scans SOL + ETH across all signals, scores confidence, alerts via Telegram:

```bash
# One-shot scan
python -m src.alpha.run

# Daemon mode (runs every 30min)
python -m src.alpha.run --daemon
```

---

## Adaptive Weight System

Signal weights live in `data/weights.json`. They start balanced and drift based on performance:

```json
{
  "funding_extreme": 0.20,
  "rsi_extreme": 0.15,
  "ttm_squeeze": 0.25,
  "whale_activity": 0.15,
  "fear_greed_extreme": 0.10,
  "ema_trend": 0.15
}
```

After each completed signal cycle, `weight_updater.py` compares which signals fired against actual outcome. Signals that were right get +0.02 (max 0.35). Signals that were wrong get −0.01 (min 0.05). EMA smoothing prevents overreaction to single events.

Over hundreds of cycles, the system learns which indicators actually predict moves — and downweights the noise.

---

## 🧠 MiroFish Integration (Optional)

> MiroFish is an open-source multi-agent social simulation engine.
> GitHub: [github.com/666ghj/MiroFish](https://github.com/666ghj/MiroFish)

The technical signal stack tells you *what the chart is doing*. MiroFish tells you *what the crowd is about to do*.

**How it works:**

You feed MiroFish a seed of real market actors — Michael Saylor, Vitalik, CZ, BlackRock, retail traders, crypto media — and it runs 11+ AI agents through 8 rounds of simulated social interaction (Twitter/Reddit dynamics). Each agent has personality, memory, and decision logic. The simulation surfaces emergent consensus before it appears on-chain.

**What it adds:**

```
Technical signals → confidence: 0.62
MiroFish simulation → direction: LONG, boost: +0.15
Combined confidence: 0.77 → alert fires
```

Without MiroFish, a 0.62 confidence scan might not clear the alert threshold. With it, social confirmation pushes it over. The system only triggers MiroFish when technical confidence is already >50%, and max 4× per day — keeping API costs under $0.15/day.

**MiroFish output (example):**
```json
{
  "direction": "long",
  "confidence_boost": 0.15,
  "votes": { "bullish": 4, "bearish": 0, "neutral": 0 },
  "summary": "Retail: panic (contrarian bullish) × 4"
}
```

**Auto-weight feedback loop:**

After each MiroFish run, `weight_updater.py` compares MiroFish's direction call to which technical signals agreed:
- Signals that agreed with MiroFish → weight +0.02
- Signals that contradicted MiroFish → weight −0.01

This closes the loop: the system learns which technical indicators align with real social dynamics, not just chart patterns.

**To enable MiroFish:**

```bash
# Clone and start MiroFish backend
git clone https://github.com/666ghj/MiroFish
cd MiroFish/backend
cp .env.example .env
# Add your OpenAI-compatible API key (Anthropic recommended)
python run.py  # starts on :5001
```

MiroFish is fully optional. The core signal engine runs without it.

> **Note on LLM compatibility:** MiroFish uses the OpenAI SDK format. Use a non-reasoning model (e.g. `claude-haiku-4-5`, `gpt-4o-mini`). Reasoning models that output to `reasoning_content` instead of `content` will cause silent failures. Do not use `response_format: json_object` — it's OpenAI-specific and breaks on Anthropic's compat layer.

---

## Project Structure

```
├── src/
│   ├── bot.py              # Short-Bias Alpha live bot
│   ├── ttm_squeeze.py      # TTM Squeeze live bot
│   ├── regime.py           # Volatility regime detection
│   └── alpha/
│       ├── engine.py       # Signal orchestrator
│       ├── signals.py      # Data fetchers (funding, RSI, whale, etc.)
│       ├── weight_updater.py # Adaptive weight optimizer
│       ├── mirofish_runner.py # MiroFish pipeline (optional)
│       ├── tracker.py      # Prediction logging
│       └── formatter.py    # Alert formatting
├── data/
│   ├── weights.json        # Live signal weights (auto-updated)
│   └── mirofish_state.json # MiroFish run state + cooldown
├── logs/
├── supervisor.conf         # Process management
├── requirements.txt
└── .env.example
```

---

## Configuration

```python
# src/alpha/config.py
MIN_CONFIDENCE = 0.55      # Alert threshold
ASSETS = ["SOL", "ETH"]    # BTC excluded (consistently underperforms)
RISK_PCT = 1.0             # Risk per trade (%)
ATR_SL_MULT = 2.0          # Stop loss multiplier
```

---

## ⚠️ Risk Warnings

- **This is not financial advice.** Real money, real losses possible.
- **Backtests lie.** No slippage, no partial fills, fantasy execution. Live PnL will differ.
- **Pyramiding shorts is aggressive.** One short squeeze stops all positions.
- **Test on testnet first.** Always. The bot defaults to testnet.
- **MiroFish adds latency.** Full pipeline takes 5-8 min. Don't use it for scalping.

---

## Tested Results

- SOL Daily TTM: 78.6% win rate, lowest drawdown across timeframes
- ETH 4H TTM: outperforms ETH Daily for this strategy
- BTC: excluded — consistently underperforms on all tested strategies

---

*Built by ApexAlpha 🐺 — positive monthly P&L over absolute returns.*
