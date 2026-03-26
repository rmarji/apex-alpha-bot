# Social Media Posts — Alpha Bot Promo

---

## 🐦 Twitter/X — Thread (main post)

**Post 1:**
Built an open-source trading bot for Hyperliquid that actually thinks.

Not another indicator crossover bot. This one scores 6 market signals, weights them adaptively, and optionally runs a social simulation engine to model what the crowd is about to do.

Thread 🧵👇

---

**Post 2:**
The signal stack:
• Funding rate extremes (crowded positions)
• RSI exhaustion
• TTM Squeeze breakouts
• Whale on-chain activity
• Fear & Greed (contrarian)
• EMA trend alignment

Each signal has a weight. Weights drift based on performance. The system learns what actually works.

---

**Post 3:**
The weird part: MiroFish integration (optional)

You feed it real actors — Saylor, Vitalik, CZ, BlackRock, retail traders, crypto media — and it runs AI agents through simulated Twitter/Reddit dynamics.

Output: "4/4 agents bullish. Retail panic = contrarian long signal."

That was at Fear & Greed = 11. 👀

---

**Post 4:**
The self-optimizing loop:

After each MiroFish run, it compares its direction call to which technical signals fired.

Signals that agreed → weight +0.02
Signals that contradicted → weight −0.01

Over hundreds of runs, the bot learns which indicators actually predict moves vs noise.

No manual tuning needed.

---

**Post 5:**
Tested on SOL/ETH only. BTC excluded — it consistently underperforms on this strategy.

SOL Daily TTM Squeeze: 78.6% win rate
ETH 4H: outperforms ETH Daily

Risk: 1% per trade. Size from the stop, not from conviction.

MiroFish is optional. Core bot runs without it.

GitHub: [link]

---

## 🐦 Twitter/X — Single post (short version)

Built an open-source Hyperliquid bot that combines technical signals + AI social simulation.

It scores funding rates, RSI, TTM Squeeze, whale flows, Fear & Greed — then optionally runs MiroFish to simulate how Saylor, CZ, BlackRock and retail will react.

Weights are adaptive. The system learns.

SOL/ETH only. No BTC.

Repo: [link] 🐺

---

## LinkedIn — Professional version

**Headline:** Building self-improving trading systems on Hyperliquid — here's what I've learned

Most algorithmic trading bots are static. They run the same logic with the same parameters indefinitely — until the market regime changes and they blow up.

I've been building something different: a signal-weighted alpha engine that adapts over time.

**The architecture:**

The core scores 6 independent market signals (funding rates, RSI momentum, TTM Squeeze, whale on-chain activity, Fear & Greed, EMA trend). Each signal has a weight. Those weights aren't fixed — they drift based on which signals actually predicted correct outcomes.

The result is a system that continuously reweights toward what works in current market conditions, rather than what worked in the backtest.

**The experiment — MiroFish:**

The most interesting addition is an optional integration with MiroFish, an open-source multi-agent simulation engine. You seed it with real market participants (institutional names, retail behavior patterns, crypto media) and it simulates social media dynamics — surfacing emergent sentiment before it shows up on-chain.

This week at Fear & Greed = 11/100 (extreme fear), the simulation returned: 4/4 agents bullish, driven by contrarian retail panic signal. Consistent with what historically happens at capitulation zones.

After each simulation, the system compares MiroFish's direction call to which technical signals fired — rewarding signals that aligned and penalizing those that contradicted. A self-adjusting feedback loop.

**What I've learned:**
- Adaptive weights beat fixed parameters in trending regimes
- Social simulation adds edge at sentiment extremes
- BTC underperforms SOL/ETH on momentum strategies — exclude it
- Test on testnet for 30+ days before live

Open-sourced on GitHub: [link]

---

## Reddit — r/algotrading or r/hyperliquid

**Title:** Built an open-source Hyperliquid bot with adaptive signal weights + optional AI social simulation — here's how it works

Hey r/algotrading,

Been building a trading system for Hyperliquid (crypto perps DEX) over the past few months and open-sourcing it. Thought it might be interesting here given the adaptive weighting mechanism.

**The core:**
6 signals (funding extremes, RSI, TTM Squeeze, whale flows, Fear & Greed, EMA) each with a weight. Confidence = weighted average. Alert fires if confidence > threshold.

**The adaptive part:**
Weights live in a JSON file and drift over time. After each completed prediction cycle, signals that were correct get +0.02, incorrect get −0.01. EMA-smoothed to prevent overreaction. The system learns which indicators have actual predictive value in current market conditions vs ones that are firing noise.

**The experimental part (optional):**
Integrated with MiroFish (github.com/666ghj/MiroFish) — an open-source multi-agent simulation engine. You seed it with named market participants (Saylor, CZ, BlackRock, retail archetypes, crypto media) and it runs AI agents through simulated social dynamics. Output is a direction signal + confidence boost.

The interesting mechanic: after each MiroFish run, the weight updater rewards technical signals that agreed with MiroFish's call and penalizes those that contradicted. Closes the feedback loop between social simulation and technical weighting.

**Results so far:**
- SOL Daily TTM Squeeze: 78.6% WR in backtests
- ETH 4H TTM: outperforms Daily on ETH
- BTC: excluded (consistently underperforms, unclear why but reproducible)

**Caveats:**
- Backtests are fiction. Live PnL will be worse.
- MiroFish is expensive per run (~$0.10 per full pipeline). Capped at 4x/day.
- Still not wired end-to-end — the feedback loop is the next milestone.

Repo: [link]

Happy to answer questions about the signal weighting design or MiroFish integration.

---

## Telegram / Discord — Short drop

🐺 Open-sourced my Hyperliquid alpha bot

What it does:
→ Scores 6 signals (funding, RSI, TTM Squeeze, whale flows, F&G, EMA)
→ Weights adapt over time based on what actually works
→ Optional: MiroFish integration — simulates how Saylor, CZ, BlackRock and retail react to current market, generates sentiment-based direction signal
→ Self-optimizing feedback loop: signals that agree with MiroFish get rewarded

SOL + ETH only. BTC excluded.
Risk: 1% per trade. Always testnet first.

Repo: [link]

Fear & Greed = 11 right now. System said LONG. You decide what to do with that.

---
