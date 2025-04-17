import json
from openai import OpenAI
from neo4j import GraphDatabase
import re
import pandas as pd

class IndexFacts:
    def __init__(self, credentials_file: str, openai_model: str = "gpt-3.5-turbo"):
        """
        Initializes the IndexFacts class.

        Args:
            credentials_file (str): Path to JSON file containing OpenAI and Neo4j credentials.
            openai_model (str): OpenAI model to use (default 'gpt-3.5-turbo').
        """
        # --- Load credentials from JSON file ---
        with open(credentials_file, 'r') as f:
            creds = json.load(f)

        # --- OpenAI setup ---
        self.client = OpenAI(api_key=creds["openai_api_key"])
        self.model = openai_model

        # --- Neo4j setup ---
        self.driver = GraphDatabase.driver(
            creds["neo4j_uri"],
            auth=(creds["neo4j_username"], creds["neo4j_password"])
        )

    # --- Extract facts from a transcript chunk ---
    def extract_facts(self, transcript_chunk):
        prompt = f"""
Extract all financial facts in the following format:

[
  {{
    "metric": "...",
    "value": "...",
    "reason": "..."
  }}
]

Guidelines:
- Extract only *quantified facts* (e.g., revenue, margin, cost, user metrics, net loss, etc.).
- Include units (e.g., RMB, %, million, billion) in the "value".
- The "reason" should summarize *management's stated or implied cause* of the performance, such as growth drivers, execution, macro trends, or product launches.
- Skip boilerplate or qualitative statements that are not tied to a specific metric and value.

Transcript:
\"\"\"{transcript_chunk}\"\"\"
Facts:
"""
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": "You are a financial information extraction assistant."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.0
        )
        return response.choices[0].message.content.strip()

    # --- Clean the LLM response (remove ``` fencing) ---
    def clean_response(self, response_str):
        return re.sub(r"```(?:json)?\s*([\s\S]*?)\s*```", r"\1", response_str).strip()

    # --- Convert extracted facts to triples ---
    def facts_to_triples(self, facts, ticker, quarter):
        triples = []
        for fact in facts:
            metric = fact["metric"]
            value = fact["value"]
            reason = fact["reason"]
            triples.append({
                "subject": metric,
                "predicate": "has_value",
                "object": value,
                "ticker": ticker,
                "quarter": quarter,
                "value": value,
                "reason": reason
            })
            triples.append({
                "subject": metric,
                "predicate": "attributed_to",
                "object": reason,
                "ticker": ticker,
                "quarter": quarter,
                "value": value,
                "reason": reason
            })
        return triples

    # --- Neo4j transaction helper ---
    @staticmethod
    def create_fact_triplet(tx, subject, predicate, obj, ticker, quarter, value=None, reason=None):
        predicate_clean = predicate.upper().replace(" ", "_")
        base_query = f"""
        MERGE (m:Metric {{name: $subject}})
        MERGE (t:Ticker {{symbol: $ticker}})
        MERGE (q:Quarter {{label: $quarter}})
        MERGE (t)-[:HAS_QUARTER]->(q)

        CREATE (f:Fact {{
            metric: $subject,
            value: $value,
            reason: $reason,
            ticker: $ticker,
            quarter: $quarter
        }})

        MERGE (q)-[:HAS_FACT]->(f)
        """

        if value:
            base_query += "MERGE (f)-[:HAS_VALUE]->(:Value {content: $value})\n"
        if reason:
            base_query += "MERGE (f)-[:ATTRIBUTED_TO]->(:Reason {content: $reason})\n"

        tx.run(base_query, subject=subject, predicate=predicate, obj=obj,
               ticker=ticker, quarter=quarter, value=value, reason=reason)

    # --- Push a batch of facts to Neo4j ---
    def push_facts_to_neo4j(self, facts):
        with self.driver.session() as session:
            for fact in facts:
                session.write_transaction(
                    self.create_fact_triplet,
                    fact["subject"],
                    fact["predicate"],
                    fact["object"],
                    fact["ticker"],
                    fact["quarter"],
                    value=fact["value"],
                    reason=fact["reason"]
                )

    # --- Process a single transcript (text) into Neo4j ---
    def process_transcript(self, transcript_text, ticker, quarter):
        extracted = self.extract_facts(transcript_text)
        if not extracted.strip():
            raise ValueError("Empty response from OpenAI.")

        try:
            facts = json.loads(self.clean_response(extracted))
        except json.JSONDecodeError:
            print("⚠️ Could not parse OpenAI response:")
            print(extracted)
            raise

        triples = self.facts_to_triples(facts, ticker, quarter)
        self.push_facts_to_neo4j(triples)
        return triples

    # --- Process an entire DataFrame ---
    def process_dataframe(self, df):
        for idx, row in df.iterrows():
            transcript = row["transcript"]
            ticker = row["ticker"]
            quarter = row["q"]

            try:
                triples = self.process_transcript(transcript, ticker, quarter)
                print(f"\n✅ Triples inserted for {ticker} / {quarter} ({len(triples)} facts)")
            except Exception as e:
                print(f"❌ Error processing row {idx} ({ticker} / {quarter}): {e}")

    # --- Close the Neo4j driver properly ---
    def close(self):
        self.driver.close()

