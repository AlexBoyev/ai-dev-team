import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()


def require_env(name: str) -> str:
    value = os.getenv(name)

    if value is None:
        raise RuntimeError(f"Missing required environment variable: {name}")

    return value


class LLMConfig:
    API_KEY = require_env("ANTHROPIC_API_KEY")
    MODEL_CHEAP = require_env("LLM_MODEL_CHEAP")
    MODEL_STRONG = require_env("LLM_MODEL_STRONG")
    MAX_TOKENS = int(require_env("LLM_MAX_TOKENS"))
    TEMPERATURE = float(require_env("LLM_TEMPERATURE"))
    DAILY_TOKEN_LIMIT = int(require_env("LLM_DAILY_TOKEN_LIMIT"))
    MIN_SECONDS_BETWEEN_CALLS = float(require_env("LLM_MIN_SECONDS_BETWEEN_CALLS"))
    MAX_CALLS_PER_MINUTE = int(require_env("LLM_MAX_CALLS_PER_MINUTE"))
    USAGE_FILE = Path(require_env("LLM_USAGE_FILE"))