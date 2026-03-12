from __future__ import annotations

import json
import logging
import threading
import time
from datetime import datetime, timezone
from typing import Optional
from backend.core.config import LLMConfig
import urllib.request

logger = logging.getLogger(__name__)

# Fallback hardcoded prices (USD per 1K tokens)
# Update this only if litellm fetch is completely broken
PRICES = {
    LLMConfig.MODEL_CHEAP:       {"prompt": 0.0008,  "completion": 0.004},
    "claude-3-haiku-20240307":   {"prompt": 0.00025, "completion": 0.00125},
}

# litellm maintains this — updated with every provider price change
_LITELLM_PRICING_URL = (
    "https://raw.githubusercontent.com/BerriAI/litellm/main/model_prices_and_context_window.json"
)

_cache: dict[str, dict[str, float]] = {}
_cache_ts: float = 0.0
_CACHE_TTL = 86400  # 24 hours
_lock = threading.Lock()


def _fetch_from_litellm() -> dict[str, dict[str, float]]:
    """Fetch and parse litellm pricing JSON into our format."""
    req = urllib.request.Request(
        _LITELLM_PRICING_URL,
        headers={"User-Agent": "ai-dev-team/1.0"},
    )
    with urllib.request.urlopen(req, timeout=8) as resp:
        raw: dict = json.loads(resp.read().decode())

    result: dict[str, dict[str, float]] = {}
    for model_id, info in raw.items():
        if not isinstance(info, dict):
            continue
        input_cost  = info.get("input_cost_per_token")
        output_cost = info.get("output_cost_per_token")
        if input_cost is not None and output_cost is not None:
            # litellm stores cost per token — convert to per 1K
            result[model_id] = {
                "prompt":     float(input_cost)  * 1000,
                "completion": float(output_cost) * 1000,
            }
    return result


def get_price(model: str) -> dict[str, float]:
    """
    Return {"prompt": x, "completion": y} cost per 1K tokens for a model.
    Fetches from litellm JSON (cached 24h). Falls back to hardcoded table.
    """
    global _cache, _cache_ts

    now = time.time()
    with _lock:
        if not _cache or (now - _cache_ts) > _CACHE_TTL:
            try:
                fetched = _fetch_from_litellm()
                if fetched:
                    _cache = fetched
                    _cache_ts = now
                    logger.info(f"Pricing refreshed from litellm: {len(fetched)} models loaded")
            except Exception as e:
                logger.warning(f"Could not fetch live pricing from litellm: {e} — using fallback")
                if not _cache:
                    _cache = dict(PRICES)
                    _cache_ts = now

    # Try exact match first, then prefix match (e.g. "claude-3-5-sonnet" → latest)
    if model in _cache:
        return _cache[model]

    for key, val in _cache.items():
        if key.startswith(model):
            return val

    # Final fallback
    logger.warning(f"No pricing found for model '{model}' — using default sonnet rate")
    return PRICES.get(model, {"prompt": 0.003, "completion": 0.015})


def refresh_now() -> int:
    """Force refresh pricing cache. Returns number of models loaded."""
    global _cache, _cache_ts
    try:
        fetched = _fetch_from_litellm()
        with _lock:
            _cache = fetched
            _cache_ts = time.time()
        return len(fetched)
    except Exception as e:
        logger.error(f"Forced pricing refresh failed: {e}")
        return 0
