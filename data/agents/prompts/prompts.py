'''prompts.py
Utility functions that return structured prompt templates for various analysis agents
used in an earnings‑call RAG pipeline.
'''
from __future__ import annotations

import json
from typing import Any, Dict, List

__all__ = [
    "comparative_agent_prompt",
    "historical_earnings_agent_prompt",
    "main_agent_prompt",
    "facts_extraction_prompt",
]

def comparative_agent_prompt(fact: Dict[str, Any], related_facts: List[Dict[str, Any]]) -> str:
    """Return the prompt for the *Comparative Peers* analysis agent.

    Parameters
    ----------
    fact
        A single fact extracted from the current firm's earnings call.
    related_facts
        A list of facts from comparable peer firms.
    """
    return f"""
You are analyzing a company’s earnings call transcript alongside statements made by similar firms.

The specific fact about the firm is:
{json.dumps(fact, indent=2)}

Comparable firms discuss the fact in the following way:
{json.dumps(related_facts, indent=2)}

Your task is:
- Describe how the firm's reasoning about their own performance differ from other firms.

- Cite factual evidence from historical calls
""".strip()


def historical_earnings_agent_prompt(
    fact: Dict[str, Any],
    related_facts: List[Dict[str, Any]],
    current_quarter: str
) -> str:
    """
    Return the prompt for the *Historical Earnings* analysis agent.

    Parameters
    ----------
    fact : dict
        The current fact from the firm's latest earnings call.
    related_facts : list of dict
        A list of related facts drawn from the firm's own previous calls.
    current_quarter : str
        The current fiscal quarter (e.g., 'Q2 2025').
    """
    return f"""
You are analyzing a company’s earnings call transcript alongside facts from its own past earnings calls.

The list of current facts are:
{json.dumps(fact, indent=2)}

It is reported in the quarter {current_quarter}

Here is a JSON list of related facts from the firm's previous earnings calls:
{json.dumps(related_facts, indent=2)}

Your task is:
- Discuss how the forward-looking statements that the firm made in the past correspond to the firm's actual performance in {current_quarter}.

- Cite factual evidence from historical calls (e.g., The company's revenue growth accelerated to 12% this quarter compared to 5% last quarter).
""".strip()


def financials_statement_agent_prompt(
    fact: Dict[str, Any],
    prior_income: str,
    prior_balance: str,
    prior_cash: str,
) -> str:
    """Prompt template for analysing the current fact in the context of past
    income statements, balance sheets, and cash‑flow statements."""
    return f"""
You are analyzing a company’s earnings call transcript alongside its past income statements, balance sheets, and cash‑flow statements.

Fact:
{json.dumps(fact, indent=2)}

Your task is to:
- Compare the firm's performance this quarter with how it performed in the past in a sentence or two.

A list of income statements from past quarters:
{prior_income}

A list of balance sheets from past quarters:
{prior_balance}

A list of cash‑flow statements from past quarters:
{prior_cash}

""".strip()


################################################################################################

def main_agent_prompt(notes) -> str:
    """Prompt for the *Main* decision-making agent, requesting just an 
    Up/Down call plus a confidence score (0-100)."""
    return f"""
You are a portfolio manager. Using the three research notes below,
decide whether the stock price is likely to **increase (“Up”) or decrease (“Down”)**
one trading day after the earnings call, and assign a **Direction score** from -100 to 100.

---
Financials-vs-History note:
{notes['financials']}

Historical-Calls note:
{notes['past']}

Peer-Comparison note:
{notes['peers']}

Focus on bottom line performance of the firm (eg. EBITDA). 
Keep your ratings conservative (eg. A small increase in revenue <3% may still yield a neutral response)
---

Instructions:
1. Evaluate all three notes together.
2. Choose **Up** if you expect the price to rise, **Down** if you expect it to fall.
3. Assign a confidence score (-100 = strong conviction of decline, 0 = neutral, 100 = strong conviction of rise).

Respond in **exactly** this format:

<Couple of sentences of Explanation>
Direction : <-100-100>

""".strip()

    
def facts_extraction_prompt(transcript_chunk: str) -> str:
    """
    Build the LLM prompt that asks for four specific data classes
    (Facts, Forward-Looking, Risk Disclosures, and Sentiment)
    from a single earnings-call transcript chunk.
    """
    return f"""
You are a senior equity-research analyst.

### TASK
Extract **only** the following four classes from the transcript below.
Ignore moderator chatter, safe-harbor boiler-plate, and anything that doesn’t match one of these classes.

1. **Fact** – already-achieved financial or operating results  
2. **Forward-Looking** – any explicit future projection, target, plan, or guidance  
3. **Risk Disclosure** – statements highlighting current or expected obstacles  
   (e.g., FX headwinds, supply-chain issues, regulation)  
4. **Sentiment** – management’s overall tone (Positive, Neutral, or Negative);
   cite key wording that informs your judgment.
5. **Macro** - discussion on how the macro-economics landscape is impacting the firm

The transcript is {transcript_chunk}

Output as many facts as you can find, ideally 20-70. You MUST output more than 20 facts.
Do not include [ORG] in your response. 
---

### OUTPUT RULES  
* Use the exact markdown block below for **every** extracted item.  
* Increment the item number sequentially (1, 2, 3 …).  
* One metric per block; never combine multiple metrics.  

Example output:
### Fact No. 1  
- **Type:** <Fact | Forward-Looking | Risk Disclosure | Sentiment | Macro>
- **Metric:** FY-2025 Operating EPS  
- **Value:** “at least $14.00”  
- **Reason:** Company reaffirmed full-year earnings guidance.

"""
    
def facts_delegation_prompt(facts: List) -> str:
    """Return the prompt used for extracting individual facts from a transcript chunk.

    Parameters
    ----------
    transcript_chunk
        A chunk of the earnings‑call transcript to be analysed.
    """
    return f""" You are the RAG-orchestration analyst for an earnings-call workflow.

## Objective
For **each fact** listed below, decide **which (if any) of the three tools** will
help you gauge its potential impact on the company’s share price **one trading
day after the call**.

### Available Tools
1. **InspectPastStatements**  
   • Retrieves historical income-statement, balance-sheet, and cash-flow data  
   • **Use when** the fact cites a standard, repeatable line-item
     (e.g., revenue, EBITDA, free cash flow, margins)

2. **QueryPastCalls**  
   • Fetches the same metric or statement from prior earnings calls  
   • **Use when** comparing management’s current commentary with its own
     previous statements adds context

3. **CompareWithPeers**
   • Provides the same metric from peer companies’ calls or filings  
   • **Use when** competitive benchmarking clarifies whether the fact signals
     outperformance, underperformance, or parity

---
The facts are: {facts}

Output your answers in the following form:

InspectPastStatements: Fact No <2, 4, 6>
CompareWithPeers:  Fact No <10>
QueryPastCalls: Fact No <1, 3, 5>

*One fact may appear under multiple tools if multiple comparisons are helpful.*

"""
peer_discovery_ticker_prompt = """
You are a financial analyst. Based on the company with ticker {ticker}, list 5 close peer companies that are in the same or closely related industries.

Only output a Python-style list of tickers, like:
["AAPL", "GOOGL", "AMZN", "MSFT", "ORCL"]
"""

######################################################################################


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