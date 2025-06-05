"""compute_returns_and_vol.py – returns + volatility‑surprise helper
===================================================================
Loads 1‑minute files from `1min/<TICKER>.csv`, then for each transcript row:

* `future_1bday_open_to_open_return` – 4‑hour open‑to‑open return starting at
  the first minute after the call.
* `future_3bday_cum_return` – Close(T‑1) → Close(T+1) cumulative return.
* `post_3d_vol` – Realised **close‑to‑close** volatility over those 3 business days.
* `hist_vol` – Historical 60‑day close‑to‑close volatility ending at T‑2.
* `vol_surprise_pct` – Percent deviation of post‑3d volatility from history.

It appends the new columns to `final` and saves an XLSX.
"""

import gc
from pathlib import Path

import pandas as pd
from pandas.tseries.offsets import BDay

# ------------------------------------------------------------------
# Config
# ------------------------------------------------------------------
MINUTE_DIR = Path("/Users/lichenhui/Desktop/Desktop - Lucy's Computer/MorningStarNLP1/MorningStarNLP/1min/1min")
FINAL_CSV = Path("final_transcripts.csv")
OUTPUT_XLSX = Path("final_with_future_returns.xlsx")

# ------------------------------------------------------------------
# Helper – realised vol from Series of close prices
# ------------------------------------------------------------------

def realised_vol(closes: pd.Series) -> float:
    """Annualised stdev of log‑returns (close‑to‑close)."""
    if len(closes) < 2:
        return float("nan")
    rets = closes.pct_change().dropna()
    # daily stdev, then annualise √252
    return rets.std() * (252 ** 0.5)

# ------------------------------------------------------------------
# Function to compute returns + vols for one row
# ------------------------------------------------------------------

def compute_metrics(ticker: str, call_ts: pd.Timestamp):
    file_path = MINUTE_DIR / f"{ticker}.csv"
    if not file_path.exists():
        print(f"⚠️ minute data for {ticker} not found")
        return {k: None for k in [
            "open_to_open", "cum_ret", "post_vol", "hist_vol", "vol_surprise_pct"]}

    df = pd.read_csv(file_path, parse_dates=["DateTime"]).sort_values("DateTime")

    # --- 1. 4‑hour open‑to‑open return ----------------------------------
    after = df[df["DateTime"] > call_ts]
    if after.empty:
        open_to_open = None
    else:
        start_open = after.iloc[0]["Open"]
        end_time = after.iloc[0]["DateTime"] + pd.Timedelta(hours=4)
        end_rows = df[df["DateTime"] >= end_time]
        if end_rows.empty:
            open_to_open = None
        else:
            end_open = end_rows.iloc[0]["Open"]
            open_to_open = (end_open - start_open) / start_open

    # business‑day anchors
    t_minus1 = (call_ts - BDay(1)).normalize()
    t_plus1 = (call_ts + BDay(1)).normalize()
    t_minus2 = (call_ts - BDay(2)).normalize()

    day_close = df.groupby(df["DateTime"].dt.normalize())[["Close"]].last()

    # cumulative return ---------------------------------------------------
    try:
        close_t1 = day_close.loc[t_plus1, "Close"]
        close_tm1 = day_close.loc[t_minus1, "Close"]
        cum_ret = (close_t1 - close_tm1) / close_tm1
    except KeyError:
        cum_ret = None

    # post‑3d volatility --------------------------------------------------
    try:
        closes_post = day_close.loc[[t_minus1, call_ts.normalize(), t_plus1], "Close"]
        post_vol = realised_vol(closes_post)
    except KeyError:
        post_vol = None

    # historical 60‑day vol ending T‑2 -----------------------------------
    try:
        hist_window = day_close.loc[:t_minus2].tail(60)["Close"]
        hist_vol = realised_vol(hist_window)
    except Exception:
        hist_vol = None

    # vol surprise % ------------------------------------------------------
    if post_vol is not None and hist_vol not in (None, 0):
        vol_surprise_pct = (post_vol - hist_vol) / hist_vol * 100.0
    else:
        vol_surprise_pct = None

    # cleanup
    del df
    gc.collect()

    return {
        "open_to_open": open_to_open,
        "cum_ret": cum_ret,
        "post_vol": post_vol,
        "hist_vol": hist_vol,
        "vol_surprise_pct": vol_surprise_pct,
    }

# ------------------------------------------------------------------
# Main driver
# ------------------------------------------------------------------

def main():
    final = pd.read_csv(FINAL_CSV)

    metrics_cols = [
        "future_1bday_open_to_open_return",
        "future_3bday_cum_return",
        "post_3d_vol",
        "hist_vol",
        "vol_surprise_pct",
    ]
    for col in metrics_cols:
        final[col] = None  # initialise

    for idx, row in final.iterrows():
        metrics = compute_metrics(row["ticker"], pd.to_datetime(row["parsed_date"]))
        final.loc[idx, metrics_cols] = [
            metrics["open_to_open"],
            metrics["cum_ret"],
            metrics["post_vol"],
            metrics["hist_vol"],
            metrics["vol_surprise_pct"],
        ]
        if idx % 25 == 0:
            print(f"Processed {idx+1}/{len(final)} transcripts…")

    final.to_excel(OUTPUT_XLSX, index=False)
    print(f"✅ Saved {OUTPUT_XLSX}")


if __name__ == "__main__":
    main()
