import os
from pathlib import Path
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / "backend" / ".env")

DATABASE_URL   = os.getenv("DATABASE_URL", "postgresql://argus:argus@localhost:5432/argusx")
NEO4J_URI      = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USERNAME = os.getenv("NEO4J_USERNAME", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "password")

MODEL_PATH          = os.getenv("MODEL_PATH", "models/anomaly_model.joblib")
MODEL_METADATA_PATH = os.getenv("MODEL_METADATA_PATH", "models/model_metadata.json")
RISK_CONFIG_PATH    = os.getenv("RISK_CONFIG_PATH", "ai_engine/config/risk_config.yaml")

FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173")
LOG_LEVEL    = os.getenv("LOG_LEVEL", "INFO")