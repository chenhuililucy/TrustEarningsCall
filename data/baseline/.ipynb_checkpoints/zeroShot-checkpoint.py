#!/usr/bin/env python3
"""
baseline_orchestrator.py ─ Minimal LLM baseline
================================================
• Uses OpenAI Chat Completions.
• Sends the entire transcript through `baseline_prompt(..)` on every appearance
  after the first time we see a given ticker.
• Keeps an incremental CSV log exactly like the original orchestrator.
"""

# --- Imports -----------------------------------------------------------
import os
import json
import pandas as pd
import openai                      # pip install openai>=1.0.0
from typing import List, Dict
from pathlib import Path
from prompts import baseline_prompt

# --- Config ------------------------------------------------------------
credentials_file = "credentials.json"
creds = json.loads(Path(credentials_file).read_text())

DATA_PATH  = "final_with_future_returns.xlsx"
LOG_PATH   = "baseline_log.csv"
MODEL      = "gpt-4o-mini"         # pick your favourite model

openai.api_key = creds["openai_api_key"]   # ← set in your shell

# --- Load earnings-call metadata --------------------------------------
df = pd.read_excel(DATA_PATH)

# --- Existing log ------------------------------------------------------
if os.path.exists(LOG_PATH):
    processed_df = pd.read_csv(LOG_PATH)
    print(f"📄 Loaded {LOG_PATH} with {len(processed_df)} rows.")
else:
    processed_df = pd.DataFrame(
        columns=["ticker", "q", "analysis", "error"]
    ).to_csv(LOG_PATH, index=False)
    processed_df = pd.read_csv(LOG_PATH)
    print(f"🆕 Created fresh {LOG_PATH}.")

def already_done(ticker: str, quarter: str) -> bool:
    return ((processed_df["ticker"] == ticker) & (processed_df["q"] == quarter)).any()

def append_to_log(row_dict: Dict) -> None:
    pd.DataFrame([row_dict]).to_csv(
        LOG_PATH,
        mode="a",
        header=False,
        index=False,
    )
    # keep in-memory copy current
    global processed_df
    processed_df = pd.concat([processed_df, pd.DataFrame([row_dict])],
                             ignore_index=True)

def call_gpt(prompt: str) -> str:
    resp = openai.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0)
    return resp.choices[0].message.content.strip()

# --- Main loop ---------------------------------------------------------
ticker_counter: Dict[str, int] = {}

for _, row in df.iterrows():
    ticker  = row["ticker"]
    quarter = row["q"]

    if already_done(ticker, quarter):
        print(f"⚡ {ticker}/{quarter} already processed, skipping.")
        continue

    ticker_counter[ticker] = ticker_counter.get(ticker, 0) + 1
    appearance            = ticker_counter[ticker]

    try:
        if appearance == 1:
            print(f"🔵 ({ticker}/{quarter}) first appearance – indexing only.")
            analysis = ""     # nothing generated
        else:
            print(f"🧠 ({ticker}/{quarter}) appearance {appearance} – calling GPT …")
            prompt   = baseline_prompt(row["transcript"])
            analysis = call_gpt(prompt)

        append_to_log({
            "ticker"  : ticker,
            "q"       : quarter,
            "analysis": analysis,
            "error"   : "",
        })

        print(f"✅ {ticker}/{quarter} logged "
              f"({'no GPT' if appearance == 1 else 'with GPT'})")

    except Exception as e:
        print(f"❌ Error on {ticker}/{quarter}: {e!s}")

        append_to_log({
            "ticker"  : ticker,
            "q"       : quarter,
            "analysis": "",
            "error"   : str(e),
        })

print("\n🎯 Baseline processing done!")
