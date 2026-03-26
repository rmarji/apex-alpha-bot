#!/usr/bin/env python3
"""
Trading Bot Config Auto-Optimizer
===================================
Runs the Karpathy loop on src/alpha/config.py using the 44 live trades as ground truth.
Each experiment tweaks one parameter, measures composite score, keeps improvements.

Usage:
    python3 optimize_config.py --iterations 20
    python3 optimize_config.py --dry-run    # show baseline only
"""

import subprocess, sys, random, shutil, json
from pathlib import Path
from datetime import datetime, timezone

CONFIG = Path("/data/workspace-crypto/src/alpha/config.py")
METRIC = Path("/data/workspace-crypto/measure_metric.py")
RESULTS = Path("/data/workspace-crypto/data/optimizer_results.tsv")
REPO = Path("/data/workspace-crypto")
VENV_PY = Path("/data/workspace-crypto/.venv/bin/python")

ITERS = 20
DRY_RUN = "--dry-run" in sys.argv
if "--iterations" in sys.argv:
    idx = sys.argv.index("--iterations")
    ITERS = int(sys.argv[idx + 1])

def run_metric():
    r = subprocess.run(
        [str(VENV_PY), str(METRIC), "--simulate"],
        capture_output=True, text=True, cwd=str(REPO)
    )
    try:
        return float(r.stdout.strip().split("\n")[-1])
    except Exception:
        return 0.0

def git_commit(msg):
    subprocess.run(["git", "add", "src/alpha/config.py"], cwd=str(REPO), capture_output=True)
    subprocess.run(["git", "commit", "-m", msg], cwd=str(REPO), capture_output=True)

def git_revert():
    subprocess.run(["git", "checkout", "--", "src/alpha/config.py"], cwd=str(REPO), capture_output=True)

def apply(old_str, new_str):
    content = CONFIG.read_text()
    if old_str not in content:
        return False
    CONFIG.write_text(content.replace(old_str, new_str, 1))
    return True

# ── Experiment pool ─────────────────────────────────────────────────────────
EXPERIMENTS = [
    {
        "desc": "Add 'high' to REGIME_SKIP — skip high-volatility trades entirely",
        "hypothesis": "High regime trades likely have poor fills too; skipping them should improve quality",
        "old": 'REGIME_SKIP = ["extreme"]',
        "new": 'REGIME_SKIP = ["extreme", "high"]',
    },
    {
        "desc": "Lower MAX_HOLD_HOURS 8→5 — cut stale trades faster",
        "hypothesis": "Data shows >12h = 0% WR; cutting to 5h removes slow bleeders earlier",
        "old": "MAX_HOLD_HOURS = 8",
        "new": "MAX_HOLD_HOURS = 5",
    },
    {
        "desc": "Lower MAX_LOSS_PER_TRADE_USD 10→6 — tighter hard cap",
        "hypothesis": "The -$17 loss was catastrophic; a $6 cap prevents any single trade from wiping multiple winners",
        "old": "MAX_LOSS_PER_TRADE_USD = 10.0",
        "new": "MAX_LOSS_PER_TRADE_USD = 6.0",
    },
    {
        "desc": "Raise MIN_CONFIDENCE 0.55→0.62 — fewer but higher-quality signals",
        "hypothesis": "Lower-confidence signals had worse outcomes; raising threshold filters noise",
        "old": "MIN_CONFIDENCE = 0.55",
        "new": "MIN_CONFIDENCE = 0.62",
    },
    {
        "desc": "Lower REGIME_REDUCE_FACTOR 0.80→0.55 — more aggressive size cut in high vol",
        "hypothesis": "High regime trades were still too large; 45% size reduction prevents overexposure",
        "old": "REGIME_REDUCE_FACTOR = 0.80",
        "new": "REGIME_REDUCE_FACTOR = 0.55",
    },
    {
        "desc": "Lower RISK_PER_TRADE 0.015→0.010 — reduce base position size",
        "hypothesis": "Smaller base size reduces absolute loss on bad trades while keeping good ones profitable",
        "old": "RISK_PER_TRADE = 0.015",
        "new": "RISK_PER_TRADE = 0.010",
    },
    {
        "desc": "Raise RSI_OVERSOLD 30→35 and RSI_OVERBOUGHT 70→65 — tighter RSI extremes",
        "hypothesis": "Only trade on more extreme RSI readings to improve signal quality",
        "old": "RSI_OVERSOLD = 30\nRSI_OVERBOUGHT = 70",
        "new": "RSI_OVERSOLD = 35\nRSI_OVERBOUGHT = 65",
    },
    {
        "desc": "Lower FG_EXTREME_FEAR 25→18 — only trade on extreme fear, not moderate fear",
        "hypothesis": "Very extreme fear (< 18) is a stronger contrarian signal than moderate fear (< 25)",
        "old": "FG_EXTREME_FEAR = 25",
        "new": "FG_EXTREME_FEAR = 18",
    },
    {
        "desc": "Remove over-sizing tier — cap max size multiplier at 1.0",
        "hypothesis": "The 1.25x over-size tier added risk without data showing higher-confidence calls are more accurate",
        "old": "    (0.85, 1.0): 1.25,    # over-size (high-conviction only)",
        "new": "    (0.85, 1.0): 1.0,     # capped at full size",
    },
    {
        "desc": "Tighten FUNDING_EXTREME_THRESHOLD 0.0001→0.00015 — only extreme funding",
        "hypothesis": "Higher funding threshold means only fire on truly crowded positions, reducing false signals",
        "old": "FUNDING_EXTREME_THRESHOLD = 0.0001",
        "new": "FUNDING_EXTREME_THRESHOLD = 0.00015",
    },
    {
        "desc": "Raise MIN_CONFIDENCE 0.55→0.65 — aggressive threshold filter",
        "hypothesis": "Many false signals fire between 0.55-0.65 confidence; cutting them improves overall quality",
        "old": "MIN_CONFIDENCE = 0.55",
        "new": "MIN_CONFIDENCE = 0.65",
    },
    {
        "desc": "Lower MAX_HOLD_HOURS 8→4 — ultra-tight time stop",
        "hypothesis": "Best wins were all <1h; 4h time stop keeps only the fast movers",
        "old": "MAX_HOLD_HOURS = 8",
        "new": "MAX_HOLD_HOURS = 4",
    },
    {
        "desc": "Lower MAX_LOSS_PER_TRADE_USD 10→4 — very tight hard cap",
        "hypothesis": "With 44 trades, avg win is $0.85 — a $4 cap means worst case = 5 winners wiped, not 20",
        "old": "MAX_LOSS_PER_TRADE_USD = 10.0",
        "new": "MAX_LOSS_PER_TRADE_USD = 4.0",
    },
    {
        "desc": "Shrink half-size tier 0.5→0.35 for low confidence trades",
        "hypothesis": "Low-confidence trades (0.55-0.65) should be very small to limit damage when wrong",
        "old": "    (0.55, 0.65): 0.5,    # half size",
        "new": "    (0.55, 0.65): 0.35,   # quarter-ish size",
    },
    {
        "desc": "Lower RISK_PER_TRADE 0.015→0.008 — minimum viable position size",
        "hypothesis": "With current win rate, minimum sizing reduces drawdown while maintaining the learning signal",
        "old": "RISK_PER_TRADE = 0.015",
        "new": "RISK_PER_TRADE = 0.008",
    },
]

random.shuffle(EXPERIMENTS)
tried = set()

print(f"\n{'='*55}")
print(f"  Trading Bot Config Auto-Optimizer")
print(f"  {ITERS} iterations | metric: composite score (higher=better)")
print(f"{'='*55}")

baseline = run_metric()
print(f"\nBaseline score: {baseline:.4f}")

if DRY_RUN:
    print("Dry run — exiting.")
    sys.exit(0)

best_score = baseline
best_iter = 0
kept = 0
reverted = 0
log_rows = []

RESULTS.parent.mkdir(parents=True, exist_ok=True)
with open(RESULTS, "a") as f:
    f.write(f"\n# Run started {datetime.now(timezone.utc).isoformat()} | baseline={baseline:.4f}\n")
    f.write("iter\tscore_before\tscore_after\tkept\tdesc\n")

for i in range(1, ITERS + 1):
    available = [e for j, e in enumerate(EXPERIMENTS) if j not in tried]
    if not available:
        print(f"\nExhausted all {len(EXPERIMENTS)} experiments at iter {i}")
        break

    exp = available[0]
    tried.add(EXPERIMENTS.index(exp))

    print(f"\n── Iter {i}/{ITERS} ─────────────────────────────────────")
    print(f"  Hypothesis: {exp['hypothesis']}")
    print(f"  Change:     {exp['desc']}")

    score_before = run_metric()  # fresh read (accounts for previous kept changes)

    if not apply(exp["old"], exp["new"]):
        print(f"  SKIP — pattern not found (already applied or superseded)")
        continue

    score_after = run_metric()
    improved = score_after > score_before + 0.001  # need meaningful improvement

    if improved:
        print(f"  ✅ KEPT    {score_before:.4f} → {score_after:.4f}  (+{score_after-score_before:.4f})")
        git_commit(f"auto-optimizer iter={i}: {exp['desc'][:70]}")
        best_score = max(best_score, score_after)
        best_iter = i
        kept += 1
    else:
        print(f"  ❌ REVERTED {score_before:.4f} → {score_after:.4f}")
        git_revert()
        reverted += 1

    result = "kept" if improved else "reverted"
    with open(RESULTS, "a") as f:
        f.write(f"{i}\t{score_before:.4f}\t{score_after:.4f}\t{result}\t{exp['desc']}\n")

print(f"\n{'='*55}")
print(f"  DONE: {kept} kept, {reverted} reverted")
print(f"  Baseline:   {baseline:.4f}")
print(f"  Best score: {best_score:.4f}  (iter {best_iter})")
pct = (best_score - baseline) / baseline * 100 if baseline > 0 else 0
print(f"  Gain:       +{best_score - baseline:.4f}  ({pct:.1f}%)")
print(f"{'='*55}\n")

# Push to GitHub
subprocess.run(["git", "push", "origin", "main"], cwd=str(REPO), capture_output=True)
print("Results pushed to GitHub.")
