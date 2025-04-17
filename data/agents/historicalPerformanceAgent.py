import json
import re
from openai import OpenAI

class HistoricalPerformanceAgent:
    def __init__(self, credentials_file="credentials.json", model="gpt-3.5-turbo"):
        """
        Initializes the HistoricalPerformanceAgent by loading credentials and setting up OpenAI.
        """
        # --- Load credentials from JSON file ---
        try:
            with open(credentials_file, "r") as f:
                creds = json.load(f)
        except FileNotFoundError:
            raise FileNotFoundError("❌ Missing credentials.json file. Please ensure it exists.")

        # --- OpenAI setup ---
        self.api_key = creds["openai_api_key"]
        self.client = OpenAI(api_key=self.api_key)
        self.model = model

    def _pretty_json(self, json_like):
        """
        Formats JSON-like strings into pretty-printed JSON.
        """
        if not json_like or json_like == "[]":
            return "[]"
        try:
            if isinstance(json_like, str):
                obj = json.loads(json_like)
            else:
                obj = json_like
            return json.dumps(obj, indent=2)
        except Exception:
            return str(json_like)

    def callAgent(self, fact,row):
        """
        Calls the LLM to compare the current fact with the firm's past financial statements.
        
        Args:
            row (dict or pd.Series): A row from the DataFrame containing historical financials.
            fact (dict): A parsed fact dictionary.

        Returns:
            str: The model's generated analysis text.
        """
        try:
            # Load prior financials
            prior_income = self._pretty_json(row.get("prior_income_statement", "[]"))
            prior_balance = self._pretty_json(row.get("prior_balance_sheet", "[]"))
            prior_cash = self._pretty_json(row.get("prior_cash_flow_statement", "[]"))

            prompt = f"""
You are analyzing a company’s earnings call transcript alongside its past statement, balance sheet, and cash flow statement.

Fact:
{json.dumps(fact, indent=2)}

Your task is to:
- Compare the firm's performance this quarter with its past performance.
- In a sentence or two, describe how this comparison may predict the stock’s likely direction and intensity of movement **one trading day after the call**.

A list of income statements from past quarters:
{prior_income}

A list of balance sheets from past quarters:
{prior_balance}

A list of cash flow statements from past quarters:
{prior_cash}

- Keep your analysis under 2 sentences in length. Only output your analysis without any other text.

"""

            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a financial forecasting assistant."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0
            )

            raw_output = response.choices[0].message.content.strip()
            return raw_output

        except Exception as e:
            return f"❌ Exception: {str(e)}"
