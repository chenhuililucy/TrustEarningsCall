import re
import json
import textwrap
from tqdm import tqdm
from openai import OpenAI

class MainAgent:
    def __init__(self, credentials_file: str, model: str = "gpt-3.5-turbo",
                 financials_agent=None, past_calls_agent=None, comparative_agent=None):
        """
        Initializes the MainAgent.

        Args:
            credentials_file (str): Path to the JSON file containing OpenAI credentials.
            model (str): OpenAI model to use (default 'gpt-3.5-turbo').
        """
        # --- Load credentials from JSON file ---
        with open(credentials_file, 'r') as f:
            creds = json.load(f)

        self.client = OpenAI(api_key=creds["openai_api_key"])
        self.model = model
        
        # Helper agents
        self.financials_agent = financials_agent
        self.past_calls_agent = past_calls_agent
        self.comparative_agent = comparative_agent

    def segment_transcript(self, text: str, max_words: int = 350):
        words = text.split()
        return [' '.join(words[i:i + max_words]) for i in range(0, len(words), max_words)]

    def parse_facts(self, output: str):
        facts = []
        pattern = r"### Fact No\. (\d+):\s*"
        blocks = re.split(pattern, output)

        for i in range(1, len(blocks), 2):
            try:
                fact_no = int(blocks[i])
                block = blocks[i + 1]

                metric_match = re.search(r"\*\*Metric:\*\*\s*(.*)", block)
                value_match = re.search(r"\*\*Value:\*\*\s*(.*)", block)
                reason_match = re.search(r"\*\*Reason:\*\*\s*(.*)", block)
                tools_match = re.search(r"\*\*Selected Tools:\*\*\s*\[(.*?)\]", block)

                metric = metric_match.group(1).strip() if metric_match else ""
                value = value_match.group(1).strip() if value_match else ""
                reason = reason_match.group(1).strip() if reason_match else ""

                if tools_match:
                    tools_raw = tools_match.group(1)
                    tools = [t.strip() for t in tools_raw.split(",") if t.strip()]
                else:
                    tools = []

                facts.append({
                    "fact_no": fact_no,
                    "metric": metric,
                    "value": value,
                    "reason": reason,
                    "tools": tools
                })
            except Exception as e:
                print(f"⚠️ Skipping malformed fact block: {e}")

        return facts
    
    def summarizeResults(self, all_facts):
        """
        Summarizes the outputs from the three agents into an overall prediction.
        
        Args:
            agent_results (dict): Dictionary with keys like 'financials_agent', 'past_calls_agent', 'comparative_agent',
                                  each containing their text outputs.
            metric (str): The metric extracted from the fact.
            value (str): The value of the metric extracted.
            reason (str): The reason associated with the metric.
        
        Returns:
            str: Overall LLM-generated evaluation (likely stock movement and reasoning).
        """
        # --- Format agent summaries ---
        fact_summaries = []
        for fact in all_facts:
            metric = fact.get("metric", "")
            value = fact.get("value", "")
            reason = fact.get("reason", "")
            agent_analysis = fact.get("agent_analysis", {})
    
            financials_summary = agent_analysis.get("financials_agent", "No financials agent output.")
            past_calls_summary = agent_analysis.get("past_calls_agent", "No past calls agent output.")
            comparative_summary = agent_analysis.get("comparative_agent", "No comparative agent output.")

        # --- Build the full prompt ---
        prompt = f"""
    You are a financial forecasting expert.
    
    You are given the following fact from the company's earnings call:
    - **Metric:** {metric}
    - **Value:** {value}
    - **Reason:** {reason}
    
    Additionally, you are provided with summaries from three different analysis agents:
    
    ---
    
    **Financials Agent Output:**
    {financials_summary}
    
    **Historical Earnings Agent Output:**
    {past_calls_summary}
    
    **Comparative Peers Agent Output:**
    {comparative_summary}
    
    ---
    
    Based on all these sources:
    - Give a **one sentence** summary evaluating whether the stock price is **likely to increase or decrease** one trading day after the call.
    - Focus on the magnitude and direction of likely movement.
    - Be concise but specific based on the provided analyses.
    
    Output your answer as a clear, short paragraph. Followed by a score from 0 to 100. Be highly critical about your scoring. 
    0 - strong conviction that the firm's T+1 price will decline.
    50 - neutral
    100 - strong conviction that the firm's T+1 price will rise.
    """
    
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a financial forecasting expert."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0  # Set to 0 for consistency in evaluation
            )
            final_summary = response.choices[0].message.content.strip()
            return final_summary
    
        except Exception as e:
            print(f"❌ Error in summarizeResults: {e}")
            return "❌ Summary generation failed."

    def run_agent_on_chunk(self, transcript_chunk: str):
        prompt = f"""
You are tasked with evaluating **individual financial facts** extracted from a company’s latest earnings call. Your objective is to determine how each fact may influence the stock price **one trading day after the call**.

To support your judgment, you will retrieve relevant information using Retrieval-Augmented Generation (RAG). You have access to the following tools:

1. **InspectPastStatements**
2. **QueryPastCalls**
3. **CompareWithPeers**

---

Output facts following this structure:

### Fact No. <N>:

Metric: <string>

Value: <string or number>

Reason: <string>

Selected Tools:

 InspectPastStatements: This allows you to compare the content of the call with past income statement, cash flow statement and balance sheet of the firm.
                        Only use this option if the metric is a common reporting term in these statements.
 QueryPastCalls: This allows you to compare the facts with past facts of the firm. 
 CompareWithPeers (Peers: [<list of peer tickers>]): This allows you to compare the facts with other facts listed by similar firms.

For example:

### Fact No. 1:
- **Metric:** Live Broadcasting Business Growth
- **Value:** Stable growth trajectory
- **Reason:** The company emphasizes a more stable growth model compared to competitors
- **Selected Tools:** [InspectPastStatements, QueryPastCalls, CompareWithPeers (Peers: [<list of peer tickers>])]

Output as many facts as you can find (Ideally more than 15).
Keep only the facts that are relevant to assessing the financial performance of the firm.
Only output the facts — no extra commentary.

Transcript:
\"\"\"{transcript_chunk}\"\"\"
"""
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a financial forecasting assistant."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            print(f"❌ Error in LLM call: {e}")
            return ""

    def process_transcript(self, transcript: str):
        chunks = self.segment_transcript(transcript, max_words=5000)

        all_facts = []
        for chunk in tqdm(chunks, desc="Processing chunks"):
            raw_output = self.run_agent_on_chunk(chunk)
            parsed_facts = self.parse_facts(raw_output)
            all_facts.extend(parsed_facts)

        return all_facts


    def delegate_fact(self, fact, row):
        """
        Delegates a fact to helper agents depending on the selected tools.
        """
        results = {}

        tools = fact.get("tools", [])

        ticker = row["ticker"]
        quarter = row["q"]
        
        # InspectPastStatements ➔ FinancialsAgent
        if any("InspectPastStatements" in tool for tool in tools):
            if self.financials_agent:
                result = self.financials_agent.callAgent(fact, row)
                results["financials_agent"] = result

        # QueryPastCalls ➔ PastCallsAgent
        if any("QueryPastCalls" in tool for tool in tools):
            if self.past_calls_agent:
                result = self.past_calls_agent.run(fact, ticker, quarter)
                results["past_calls_agent"] = result

        # CompareWithPeers ➔ ComparativeAgent
        if any("CompareWithPeers" in tool for tool in tools):
            if self.comparative_agent:
                result = self.comparative_agent.run(fact, ticker, quarter)
                results["comparative_agent"] = result
        
        return results


    def parse_facts(self, output: str, ticker: str):
        """
        Parses raw LLM string output into structured facts,
        then cleans tools and peers fields.
    
        Args:
            output (str): Raw LLM text output (not JSON).
            ticker (str): Firm's ticker (to exclude from peers).
    
        Returns:
            list of dict: Cleaned and parsed facts.
        """
        parsed_facts = []
    
        # --- Step 1: Parse the raw string into a list of facts ---
        facts_list = []
        pattern = r"### Fact No\. (\d+):\s*"
        blocks = re.split(pattern, output)
    
        for i in range(1, len(blocks), 2):
            try:
                fact_no = int(blocks[i])
                block = blocks[i + 1]
    
                metric_match = re.search(r"\*\*Metric:\*\*\s*(.*)", block)
                value_match = re.search(r"\*\*Value:\*\*\s*(.*)", block)
                reason_match = re.search(r"\*\*Reason:\*\*\s*(.*)", block)
                tools_match = re.search(r"\*\*Selected Tools:\*\*\s*\[(.*?)\]", block)
    
                metric = metric_match.group(1).strip() if metric_match else ""
                value = value_match.group(1).strip() if value_match else ""
                reason = reason_match.group(1).strip() if reason_match else ""
    
                if tools_match:
                    tools_raw = tools_match.group(1)
                    tools = [t.strip() for t in tools_raw.split(",") if t.strip()]
                else:
                    tools = []
    
                facts_list.append({
                    "fact_no": fact_no,
                    "metric": metric,
                    "value": value,
                    "reason": reason,
                    "tools": tools
                })
            except Exception as e:
                print(f"⚠️ Skipping malformed fact block: {e}")
    
        # --- Step 2: Clean tools and extract peers ---
        for fact in facts_list:
            tools = fact.get("tools", [])
            peers = []
    
            tools_joined = " ".join(str(tool) for tool in tools)
    
            if "CompareWithPeers" in tools_joined:
                match = re.search(r"Peers:\s*\[([^\]]+)\]", tools_joined)
                if match:
                    peer_str = match.group(1)
                    peers = [p.strip() for p in peer_str.split(",") if p.strip() and p.strip() != ticker]
    
            parsed_facts.append({
                "fact_no": fact.get("fact_no"),
                "metric": fact.get("metric", "").strip(),
                "value": fact.get("value", "").strip(),
                "reason": fact.get("reason", "").strip(),
                "tools": tools,
                "peers": peers
            })
    
        return parsed_facts


    def process_transcript(self, transcript: str, row):

        chunks = self.segment_transcript(transcript, max_words=5000)
        all_facts = []
    
        for chunk in tqdm(chunks, desc="Processing chunks"):
            raw_output = self.run_agent_on_chunk(chunk)
            parsed_facts = self.parse_facts(raw_output, row["ticker"])
            
            for fact in parsed_facts:
                fact_analysis = self.delegate_fact(fact, row)
                fact["agent_analysis"] = fact_analysis
                all_facts.append(fact)
    
        # 🆕 Final summarization after processing all facts
        final_summary = self.summarizeResults(all_facts)
    
        return {
            "all_facts": all_facts,
            "final_summary": final_summary
        }
    
    

    def run(self, row):
        """
        Processes a single row from DataFrame (must have a 'transcript' column).

        Args:
            row (pd.Series): A DataFrame row.

        Returns:
            List[dict]: List of parsed facts.
        """
        transcript = row["transcript"]

        return self.process_transcript(transcript, row)
