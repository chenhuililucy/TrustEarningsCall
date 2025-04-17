import json
import re
from openai import OpenAI
from neo4j import GraphDatabase
from langchain_openai import OpenAIEmbeddings  # 🆕 real embedder

class ComparativeAgent:
    def __init__(self, credentials_file="credentials.json", model="gpt-3.5-turbo"):
        """
        Initializes the ComparativeAgent by reading credentials and setting up everything internally.
        """
        # --- Load credentials ---
        try:
            with open(credentials_file, "r") as f:
                creds = json.load(f)
        except FileNotFoundError:
            raise FileNotFoundError("❌ Missing credentials.json file. Please ensure it exists.")

        # --- OpenAI Client ---
        self.api_key = creds["openai_api_key"]
        self.client = OpenAI(api_key=self.api_key)
        self.model = model

        # --- Neo4j Driver ---
        self.driver = GraphDatabase.driver(
            creds["neo4j_uri"],
            auth=(creds["neo4j_username"], creds["neo4j_password"])
        )

        # --- Real Embedder using LangChain ---
        self.embedder = OpenAIEmbeddings(openai_api_key=self.api_key)

    def search_similar_facts(self, query_text, ticker, current_quarter, top_k=100):
        """
        Search for similar :Fact nodes with matching ticker and earlier quarters.
        Adds debugging to inspect embedding, query parameters, and raw Neo4j results.
        """
        query_vector = self.embedder.embed_query(query_text)
    
        with self.driver.session() as session:
            print(f"🚀 Running vector search with top_k={top_k}, ticker={ticker}, current_quarter={current_quarter}")
            result = session.run("""
                CALL db.index.vector.queryNodes('searchable-index', $topK, $embedding)
                YIELD node, score
                RETURN node.uuid AS uuid,
                       node.text AS text,
                       node.metric AS metric,
                       node.value AS value,
                       node.reason AS reason,
                       node.ticker AS ticker,
                       node.quarter AS quarter,
                       score
                ORDER BY score DESC
            """, {
                "topK": top_k,
                "embedding": query_vector,
                "ticker": ticker,
                "currentQuarter": current_quarter
            })
    
            rows = [row for row in result]
    
            return [{
                "uuid": row["uuid"],
                "metric": row["metric"],
                "value": row["value"],
                "reason": row["reason"],
                "text": row["text"],
                "ticker": row["ticker"],
                "quarter": row["quarter"],
                "score": row["score"]
            } for row in rows]
    

    def callAgent(self, fact, related_facts):
        """
        Calls the LLM with the firm-specific fact and its related comparables.
        """
        prompt = f"""
You are analyzing a company’s earnings call transcript alongside statements made by similar firms.

The specific fact about the firm is:
{json.dumps(fact, indent=2)}

Here is a JSON list of related facts from comparable firms:
{json.dumps(related_facts, indent=2)}

Your task is:
- Using these materials, in a sentence or two, describe how the firm's performance compares with other firms how this may allow you to predict the stock’s likely direction and intensity of movement.

- Keep your analysis under 2 sentences in length. Only output your analysis without any other text.
- Cite factual evidence from historical calls

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

    def run(self, fact, ticker, current_quarter, top_k=10):
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
        
        # --- Step 3: Analyze using the LLM ---
        output = self.callAgent(fact, related_facts)
    
        return output
