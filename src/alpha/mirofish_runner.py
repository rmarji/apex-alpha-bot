"""
MiroFish Runner — Smart conditional trigger for MiroFish simulation pipeline.
Max 4 runs/day, 4h cooldown, confidence > 0.50 required (bypass with --force).
"""

import argparse
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

BASE_URL = "http://localhost:5001"
STATE_FILE = "/data/workspace-crypto/data/mirofish_state.json"
LOG_DIR = "/data/workspace-crypto/logs"
MAX_RUNS_PER_DAY = 4
COOLDOWN_HOURS = 4


# ---------------------------------------------------------------------------
# State helpers
# ---------------------------------------------------------------------------

def load_state() -> dict:
    if Path(STATE_FILE).exists():
        with open(STATE_FILE) as f:
            return json.load(f)
    return {"last_run_ts": 0, "runs_today": 0, "today_date": "", "last_result": None}


def save_state(state: dict):
    Path(STATE_FILE).parent.mkdir(parents=True, exist_ok=True)
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


def check_conditions(force: bool = False) -> tuple[bool, str]:
    """Return (ok, reason). If force=True, skip cooldown/confidence checks."""
    state = load_state()
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    # Reset daily counter if new day
    if state.get("today_date") != today:
        state["runs_today"] = 0
        state["today_date"] = today
        save_state(state)

    if not force:
        # Cooldown check
        elapsed_h = (time.time() - state.get("last_run_ts", 0)) / 3600
        if elapsed_h < COOLDOWN_HOURS:
            return False, f"last run was {elapsed_h:.1f}h ago (need >{COOLDOWN_HOURS}h)"

    # Daily limit (always enforced)
    if state.get("runs_today", 0) >= MAX_RUNS_PER_DAY:
        return False, f"max {MAX_RUNS_PER_DAY} runs/day reached"

    if not force:
        # Confidence check — try to read latest alpha engine confidence
        confidence = get_alpha_confidence()
        if confidence is not None and confidence <= 0.50:
            return False, f"alpha confidence {confidence:.2f} ≤ 0.50"

    return True, "ok"


def get_alpha_confidence() -> float | None:
    """Try to get current alpha engine confidence from latest signal output."""
    try:
        tracker_file = "/data/workspace-crypto/data/last_signal.json"
        if Path(tracker_file).exists():
            with open(tracker_file) as f:
                data = json.load(f)
            return data.get("confidence")
    except Exception:
        pass
    return None  # Unknown → allow run


# ---------------------------------------------------------------------------
# MiroFish backend management
# ---------------------------------------------------------------------------

def ensure_backend_running():
    try:
        r = requests.get(f"{BASE_URL}/health", timeout=5)
        if r.status_code == 200:
            print("[mirofish] Backend already running ✓")
            return
    except Exception:
        pass

    print("[mirofish] Starting backend...")
    subprocess.Popen(
        "cd /data/workspace-crypto/mirofish/backend && "
        "nohup .venv/bin/python run.py >> /data/workspace-crypto/logs/mirofish.log 2>&1 &",
        shell=True,
    )
    time.sleep(8)
    print("[mirofish] Backend started, waited 8s")


# ---------------------------------------------------------------------------
# API helpers
# ---------------------------------------------------------------------------

def _unwrap(resp: dict) -> dict:
    """Unwrap {success, data} envelope if present."""
    if isinstance(resp, dict) and "data" in resp and resp.get("success") is not False:
        return resp["data"]
    return resp


def api_post(path: str, timeout: int = 300, **kwargs) -> dict:
    r = requests.post(f"{BASE_URL}{path}", timeout=timeout, **kwargs)
    r.raise_for_status()
    return _unwrap(r.json())


def api_get(path: str) -> dict:
    r = requests.get(f"{BASE_URL}{path}", timeout=30)
    r.raise_for_status()
    return _unwrap(r.json())


def poll(path: str, done_key: str, done_val: str, interval: int = 5, max_wait: int = 300,
         method: str = "GET", body: dict | None = None) -> dict:
    """Poll endpoint until done_key == done_val."""
    deadline = time.time() + max_wait
    while time.time() < deadline:
        data = api_post(path, json=body) if method == "POST" else api_get(path)
        status = data.get(done_key) or data.get("status") or data.get("runner_status")
        if status == done_val:
            return data
        print(f"  polling {path} … {done_key}={status}")
        time.sleep(interval)
    raise TimeoutError(f"Timed out polling {path} for {done_key}=={done_val}")


# ---------------------------------------------------------------------------
# Simulation pipeline
# ---------------------------------------------------------------------------

MARKET_SEED = """Crypto market sentiment analysis - March 2026.

Key market participants and their recent activity:
- Michael Saylor (MicroStrategy CEO): Continues buying BTC, tweeted "Bitcoin is the ultimate store of value"
- Vitalik Buterin (Ethereum founder): Posted about ETH staking upgrades and L2 scaling progress
- CZ (Binance founder): Commented on crypto regulatory clarity improving in Asia
- Arthur Hayes (BitMEX founder): Wrote bearish macro piece warning about liquidity withdrawal
- Coinbase (exchange): Announced institutional trading volume up 40% QoQ
- Binance (exchange): Facing regulatory scrutiny but spot volumes remain strong
- BlackRock (asset manager): Bitcoin ETF AUM crossed $20B, adding positions
- Jump Trading (market maker): Reduced crypto exposure citing volatility
- Pantera Capital (VC fund): Bullish on Solana ecosystem, new fund raised
- CoinTelegraph (media): Reporting on ETH ETF approval rumors
- The Block (media): Published analysis showing retail fear at extreme levels
- Crypto Twitter community: Divided between bulls citing accumulation and bears citing macro risks
- SOL: Trading at $91, near key support after 30% correction from highs
- ETH: At $2,160, ETF approval rumors driving institutional interest
- BTC: At $70,600, consolidating after recent volatility, funding rates neutral
"""


def run_pipeline() -> dict:
    print("[mirofish] Step 1: Generate ontology…")
    files = {"files": ("market_seed.txt", MARKET_SEED, "text/plain")}
    data = {
        "simulation_requirement": "Simulate how crypto market influencers, traders, institutions and media will react to current market conditions. Predict which direction (bullish/bearish) the dominant narrative will shift in the next 24-48 hours based on social media dynamics between key participants.",
        "project_name": f"alpha_run_{int(time.time())}",
    }
    onto = api_post("/api/graph/ontology/generate", data=data, files=files)
    project_id = onto.get("project_id") or onto.get("id")
    if not project_id:
        raise ValueError(f"No project_id in ontology response: {onto}")
    print(f"  project_id={project_id}")

    print("[mirofish] Step 2: Build graph…")
    build = api_post("/api/graph/build", json={"project_id": project_id})
    print(f"  build response keys: {list(build.keys())}")
    task_id = build.get("task_id") or build.get("id")
    graph_id = build.get("graph_id")
    if task_id and not graph_id:
        completed = poll(f"/api/graph/task/{task_id}", "status", "completed")
        graph_id = (completed.get("graph_id") or
                    (completed.get("result") or {}).get("graph_id") or
                    completed.get("id"))
    if not graph_id:
        graph_id = build.get("id")
    print(f"  graph_id={graph_id}")

    print("[mirofish] Step 3: Create simulation…")
    sim = api_post("/api/simulation/create", json={"project_id": project_id, "graph_id": graph_id})
    sim_id = sim.get("simulation_id") or sim.get("id")
    print(f"  simulation_id={sim_id}")

    print("[mirofish] Step 4: Prepare simulation…")
    prep = api_post("/api/simulation/prepare", json={"simulation_id": sim_id, "max_rounds": 8})
    prep_task_id = prep.get("task_id")
    if prep.get("status") != "ready":
        poll("/api/simulation/prepare/status", "status", "ready",
             method="POST", body={"simulation_id": sim_id, "task_id": prep_task_id},
             max_wait=600)

    print("[mirofish] Step 5: Start simulation…")
    api_post("/api/simulation/start", json={"simulation_id": sim_id, "platform": "parallel", "max_rounds": 8})

    print("[mirofish] Step 6: Polling run status…")
    poll(f"/api/simulation/{sim_id}/run-status", "runner_status", "completed", max_wait=600)

    print("[mirofish] Step 7: Fetching actions…")
    detail = api_get(f"/api/simulation/{sim_id}/run-status/detail")
    return detail


# ---------------------------------------------------------------------------
# Parse actions
# ---------------------------------------------------------------------------

def parse_actions(detail: dict) -> dict:
    all_actions = detail.get("all_actions") or detail.get("actions") or []
    if isinstance(all_actions, str):
        all_actions = [all_actions]

    votes = {"bullish": 0, "bearish": 0, "neutral": 0}
    algo_probs: list[float] = []
    key_levels: dict = {}
    summary_lines: list[str] = []

    for action in all_actions:
        text = str(action).lower()
        raw = str(action)

        # Whale wallets
        if any(w in text for w in ["whale", "large wallet", "smart money"]):
            if any(w in text for w in ["accumulation", "buying", "deploying", "accumulate"]):
                votes["bullish"] += 2
                summary_lines.append("🐋 Whales: accumulating (bullish)")
            elif any(w in text for w in ["distributing", "selling", "shorting", "distribute"]):
                votes["bearish"] += 2
                summary_lines.append("🐋 Whales: distributing (bearish)")

        # Algorithmic traders — extract UP% probability
        if any(w in text for w in ["algo", "algorithmic", "quant", "systematic"]):
            pcts = re.findall(r"(\d+(?:\.\d+)?)\s*%", raw)
            for p in pcts:
                val = float(p) / 100
                if 0.3 <= val <= 0.9:
                    algo_probs.append(val)
                    if val > 0.55:
                        votes["bullish"] += 1
                    elif val < 0.45:
                        votes["bearish"] += 1

        # Retail — inverse signal
        if any(w in text for w in ["retail", "degen", "small trader"]):
            if any(w in text for w in ["panic", "selling", "done", "capitulate", "fear"]):
                votes["bullish"] += 1  # inverse: retail panic = buy signal
                summary_lines.append("👥 Retail: panic (contrarian bullish)")
            elif any(w in text for w in ["euphoria", "fomo", "all in", "moon"]):
                votes["bearish"] += 1  # inverse: retail euphoria = sell signal
                summary_lines.append("👥 Retail: euphoria (contrarian bearish)")

        # Extract price levels
        levels = re.findall(r"\$?([\d,]+(?:\.\d+)?)\s*(?:support|resistance|level|target|stop)", raw, re.IGNORECASE)
        for lvl in levels:
            val = float(lvl.replace(",", ""))
            if val > 100:  # sanity: likely a real price
                key_levels[str(int(val))] = val

    # Determine direction
    total = votes["bullish"] + votes["bearish"] + votes["neutral"]
    if total == 0:
        direction = "neutral"
        confidence_boost = 0.0
    else:
        if votes["bullish"] > votes["bearish"] * 1.3:
            direction = "long"
        elif votes["bearish"] > votes["bullish"] * 1.3:
            direction = "short"
        else:
            direction = "neutral"

        dominance = max(votes["bullish"], votes["bearish"]) / max(total, 1)
        confidence_boost = round(min(0.15, dominance * 0.20), 3)

    # Algo probability override
    if algo_probs:
        avg_prob = sum(algo_probs) / len(algo_probs)
        if avg_prob > 0.58:
            if direction == "neutral":
                direction = "long"
            confidence_boost = min(0.15, confidence_boost + 0.03)
        elif avg_prob < 0.42:
            if direction == "neutral":
                direction = "short"
            confidence_boost = min(0.15, confidence_boost + 0.03)
        summary_lines.append(f"🤖 Algo avg UP prob: {avg_prob:.0%}")

    summary = " | ".join(summary_lines) if summary_lines else "No clear agent signals parsed"

    return {
        "direction": direction,
        "confidence_boost": confidence_boost,
        "key_levels": key_levels,
        "votes": votes,
        "summary": summary,
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="MiroFish Runner")
    parser.add_argument("--force", action="store_true", help="Bypass 4h cooldown and confidence check")
    args = parser.parse_args()

    Path(LOG_DIR).mkdir(parents=True, exist_ok=True)

    ok, reason = check_conditions(force=args.force)
    if not ok:
        print(f"SKIP: {reason}")
        sys.exit(0)

    ensure_backend_running()

    try:
        detail = run_pipeline()
        result = parse_actions(detail)
    except Exception as e:
        print(f"[mirofish] Pipeline error: {e}")
        raise

    # Update state
    state = load_state()
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    if state.get("today_date") != today:
        state["runs_today"] = 0
        state["today_date"] = today
    state["last_run_ts"] = time.time()
    state["runs_today"] = state.get("runs_today", 0) + 1
    state["last_result"] = result
    save_state(state)

    print("\n[mirofish] ═══ RESULT ═══")
    print(json.dumps(result, indent=2))
    return result


if __name__ == "__main__":
    main()
