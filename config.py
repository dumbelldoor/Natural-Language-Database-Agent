import os
import json
from dotenv import load_dotenv

load_dotenv(override=True)

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "mcp_config.json")

def load_config() -> dict:
    if not os.path.exists(CONFIG_PATH):
        raise FileNotFoundError(f"Configuration file {CONFIG_PATH} not found.")
    with open(CONFIG_PATH, "r") as f:
        return json.load(f)

# Global Config Object
CONFIG = load_config()

# Helper accessors
LLM_CONFIG = CONFIG.get("llm", {})
DB_CONFIG = CONFIG.get("database", {})
RAG_CONFIG = CONFIG.get("rag", {})
