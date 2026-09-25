import os
import tempfile
from pathlib import Path

_root = Path(tempfile.mkdtemp(prefix="aquarius-tests-"))
os.environ["APP_MODE"] = "demo"
os.environ["DATABASE_URL"] = f"sqlite:///{_root}/test.db"
os.environ["DATA_DIR"] = str(_root)
os.environ["MARKET_DATA_PROVIDER"] = "synthetic"
os.environ["REDIS_URL"] = ""
os.environ["PAPER_TRADING_ENABLED"] = "false"

os.environ["RESEARCH_PROVIDER"] = "curated"
os.environ["LLM_API_KEY"] = ""
os.environ["LLM_MODEL"] = ""
