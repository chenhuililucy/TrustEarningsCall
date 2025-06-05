# Baseline prompts
def baseline_prompt(transcript) -> str:
    return f"""
You are a portfolio manager and you are reading an earnings call transcript.
decide whether the stock price is likely to **increase (“Up”) or decrease (“Down”)**
one trading day after the earnings call, and assign a **Direction score** from -100 to 100.

---
{transcript}

Instructions:
1. Assign a confidence score (-100 = strong conviction of decline, 0 = neutral, 100 = strong conviction of rise).

Respond in **exactly** this format:

<Couple of sentences of Explanation>
Direction : <-100-100>

""".strip()