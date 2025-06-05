# --- Imports ---
from agents.mainAgent import MainAgent
from agents.comparativeAgent import ComparativeAgent
from agents.historicalPerformanceAgent import HistoricalPerformanceAgent
from agents.historicalEarningsAgent import HistoricalEarningsAgent
from utils.indexFacts import IndexFacts
import pandas as pd
import pprint
import json
import os
import concurrent
import concurrent.futures

# --- Load your data ---
df = pd.read_excel("final_with_future_open_returns.xlsx")
LOG_PATH = "incremental_log.csv"
######################################################################

indexer                      = IndexFacts(credentials_file="credentials.json")
indexer.create_fact_metric_index()  # Creates the vector index
comparative_agent            = ComparativeAgent(credentials_file="credentials.json")
historical_performance_agent = HistoricalPerformanceAgent(credentials_file="credentials.json")
historical_earnings_agent    = HistoricalEarningsAgent(credentials_file="credentials.json")

# --- Initialise main agent --------------------------------------------
main_agent = MainAgent(
    credentials_file   = "credentials.json",
    comparative_agent  = comparative_agent,
    financials_agent   = historical_performance_agent,
    past_calls_agent   = historical_earnings_agent,
)

# --- Load existing incremental log (if any) ---------------------------
if os.path.exists(LOG_PATH):
    processed_df = pd.read_csv(LOG_PATH)
    print(f"📄 Loaded existing {LOG_PATH} with {len(processed_df)} rows.")
else:
    processed_df = pd.DataFrame(columns=["ticker", "q", "parsed_and_analyzed_facts", "error"])
    # Ensure the file exists so we can rely on append-with-header logic later
    processed_df.to_csv(LOG_PATH, index=False)
    print(f"🆕 Created fresh {LOG_PATH}.")

# --- Quick helper ------------------------------------------------------
def already_done(ticker: str, quarter: str) -> bool:
    return ((processed_df["ticker"] == ticker) & (processed_df["q"] == quarter)).any()

def append_to_log(row_dict: dict) -> None:
    """
    Append exactly one row *directly* to incremental_log.csv
    without rewriting the whole file.
    """
    pd.DataFrame([row_dict]).to_csv(
        LOG_PATH,
        mode   = "a",
        header = False,            # header already present
        index  = False,
    )
    # Keep the in-memory set in sync so skip-logic works
    global processed_df
    processed_df = pd.concat([processed_df, pd.DataFrame([row_dict])], ignore_index=True)

# --- Ticker appearance counter ----------------------------------------
ticker_counter: dict[str, int] = {}

TIMEOUT_SEC = 300          # 5 minutes

def process_transcript_with_timeout(indexer, *, transcript, ticker, quarter,
                                    timeout: int = TIMEOUT_SEC):
    """
    Call indexer.process_transcript but give up after <timeout> seconds.
    Returns the triples list, or None if the call timed out.
    """
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        fut = pool.submit(
            indexer.process_transcript,
            transcript=transcript,
            ticker=ticker,
            quarter=quarter,
        )
        try:
            return fut.result(timeout=timeout)
        except concurrent.futures.TimeoutError:
            print(f"⏱️  Indexing {ticker} / {quarter} exceeded {timeout}s – skipped.")
            # Best effort: try to stop the work if it’s still running
            fut.cancel()
            return None
            
# --- Main loop ---------------------------------------------------------
for idx, row in df.iterrows():
    ticker   : str = row["ticker"]
    quarter  : str = row["q"]

    if already_done(ticker, quarter):
        ticker_counter[ticker] = ticker_counter.get(ticker, 0) + 1
        print(f"⚡ Already processed {ticker} / {quarter}, skipping.")
        continue

    try:
        print(f"\n🚀 Processing {ticker} / {quarter} …")

        # -- Track how often we've seen this ticker ---------------------
        ticker_counter[ticker] = ticker_counter.get(ticker, 0) + 1
        current_count = ticker_counter[ticker]

        parsed_and_analyzed_facts = []

        # -- First appearance -> index only -----------------------------
        if current_count == 1:
            print(f"🔵 First appearance for {ticker} — indexing only (no LLM parsing).")
        else:
            # -- Attempt to run main_agent.run(row) with a 5-minute timeout.
            print(f"🧠 Parsing facts for {ticker} (appearance {current_count}) …")
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(main_agent.run, row)
                try:
                    parsed_and_analyzed_facts = future.result(timeout=300)  # 5 minutes
                except concurrent.futures.TimeoutError:
                    print("🛑 `main_agent.run` took over 5 minutes. Skipping parsing for this row.")
                    parsed_and_analyzed_facts = []

        # -- Always index -------------------------------------------------------
        triples = process_transcript_with_timeout(
            indexer,
            transcript=row["transcript"],
            ticker=ticker,
            quarter=quarter,
        )
        
        # If we timed-out, normalise to an empty list so later code is unchanged
        triples = triples or []

        # -- Successful log record --------------------------------------
        append_to_log({
            "ticker"                   : ticker,
            "q"                        : quarter,
            "parsed_and_analyzed_facts": json.dumps(parsed_and_analyzed_facts),
            "error"                    : "",
        })

        print(f"✅ Completed {ticker} / {quarter} – "
              f"{len(parsed_and_analyzed_facts)} facts parsed, "
              f"{len(triples)} triples indexed.")

    except Exception as e:
        print(f"❌ Error processing {ticker} / {quarter}: {e}")

        append_to_log({
            "ticker"                   : ticker,
            "q"                        : quarter,
            "parsed_and_analyzed_facts": "[]",
            "error"                    : str(e),
        })

print("\n🎯 All transcripts processed!")