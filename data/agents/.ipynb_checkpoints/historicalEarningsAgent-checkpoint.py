import json
from openai import OpenAI
from neo4j import GraphDatabase
from langchain_openai import OpenAIEmbeddings

class HistoricalEarningsAgent:
    def __init__(self, credentials_file="credentials.json", model="gpt-3.5-turbo"):
        """
        Initializes the HistoricalEarningsAgent by loading credentials, setting up OpenAI, Neo4j, and an embedder.
        """
        # --- Load credentials ---
        try:
            with open(credentials_file, "r") as f:
                creds = json.load(f)
        except FileNotFoundError:
            raise FileNotFoundError("❌ Missing credentials.json file. Please ensure it exists.")

        # --- OpenAI setup ---
        self.api_key = creds["openai_api_key"]
        self.client = OpenAI(api_key=self.api_key)
        self.model = model

        # --- Neo4j setup ---
        self.driver = GraphDatabase.driver(
            creds["neo4j_uri"],
            auth=(creds["neo4j_username"], creds["neo4j_password"])
        )

        # --- Embedder setup ---
        self.embedder = OpenAIEmbeddings(openai_api_key=self.api_key)

    def search_similar_facts(self, query_text, ticker, current_quarter, top_k=100):
        """
        Search facts using the fulltext index 'fact_fulltext_index' based on the query_text.
        Filters results by ticker and optionally by quarter.
        """
        
        with self.driver.session() as session:
            print(f"🚀 Fetching all facts for ticker: {ticker}")
        
            result = session.run("""
                MATCH (f:Fact)
                WHERE f.ticker = $ticker
                RETURN f.uuid AS uuid,
                       f.metric AS metric,
                       f.value AS value,
                       f.reason AS reason,
                       f.text AS text,
                       f.ticker AS ticker,
                       f.quarter AS quarter
                ORDER BY f.quarter DESC
                LIMIT $topK
            """, {
                "ticker": ticker,
                "topK": top_k
            })
        
            rows = [row for row in result]
        
            # --- Deduplicate by (metric, value, reason) ---
            seen = set()
            deduped_facts = []
            for row in rows:
                key = (
                    row.get("metric", "").strip().lower(),
                    row.get("value", "").strip().lower(),
                    row.get("reason", "").strip().lower()
                )
                if key not in seen:
                    seen.add(key)
                    deduped_facts.append({
                        "uuid": row["uuid"],
                        "metric": row["metric"],
                        "value": row["value"],
                        "reason": row["reason"],
                        "text": row["text"],
                        "ticker": row["ticker"],
                        "quarter": row["quarter"]
                    })
        
            return deduped_facts



    
    def callAgent(self, fact, related_facts):
        """
        Calls the LLM with the fact and its related facts from the company's past earnings calls.
        """
        prompt = f"""
You are analyzing a company’s earnings call transcript alongside facts from its own past earnings calls.

The current fact is:
{json.dumps(fact, indent=2)}

Here is a JSON list of related facts from the firm's previous earnings calls:
{json.dumps(related_facts, indent=2)}

Your task is:
- Explain in a sentence or two how these materials are predictive of the stock’s likely direction and intensity of movement **one trading day after the call**.
- Keep your analysis under 2 sentences in length. Only output your analysis without any other text.
- Cite factual evidence from historical calls (eg. The company's revenue growth accelerated to 12% this quarter compared to 5% last quarter)
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
            return f"❌ Exception: {str(e)}"

    def run(self, fact, ticker, current_quarter, top_k=50):
        """
        Runs the HistoricalEarningsAgent on a single parsed fact.
        Formats a combined query string using metric, value, and reason for better semantic search.
        """
        metric = fact.get("metric", "").strip()
        value = fact.get("value", "").strip()
        reason = fact.get("reason", "").strip()
    
        # --- Step 1: Build a nicely formatted query text ---
        components = []
        if metric:
            components.append(f"Metric: {metric}")
        if value:
            components.append(f"Value: {value}")
        if reason:
            components.append(f"Reason: {reason}")
    
        query_text = " | ".join(components)  # Join components with a separator
        
        if not query_text:
            return "❌ No meaningful query text found in fact to search similar nodes."
    
        # --- Step 2: Search for related facts ---
        related_facts = self.search_similar_facts(
            query_text=query_text,
            ticker=ticker,
            current_quarter=current_quarter,
            top_k=top_k
        )
    
        print(f"\n🔎 Found {len(related_facts)} related facts.")
    
        # --- Step 3: Analyze using the LLM ---
        output = self.callAgent(fact, related_facts)
    
        return output
