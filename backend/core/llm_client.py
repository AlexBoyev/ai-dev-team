import json
import time
from dataclasses import dataclass
from datetime import date
from typing import Optional
from dotenv import load_dotenv
from backend.core.config import LLMConfig
from anthropic import Anthropic

load_dotenv()


# ---------- Config ----------
DEFAULT_MAX_TOKENS = LLMConfig.MAX_TOKENS
DEFAULT_TEMPERATURE = LLMConfig.TEMPERATURE
DAILY_TOKEN_LIMIT = LLMConfig.DAILY_TOKEN_LIMIT
MIN_SECONDS_BETWEEN_CALLS = LLMConfig.MIN_SECONDS_BETWEEN_CALLS
MAX_CALLS_PER_MINUTE = LLMConfig.MAX_CALLS_PER_MINUTE
MODEL_CHEAP = LLMConfig.MODEL_CHEAP
MODEL_STRONG = LLMConfig.MODEL_STRONG
USAGE_FILE = LLMConfig.USAGE_FILE

client = Anthropic(api_key=LLMConfig.API_KEY)


@dataclass
class LLMRequest:
    prompt: str
    purpose: str = "general"  # e.g. "tests", "refactor", "architecture", "bugfix"
    max_tokens: int = DEFAULT_MAX_TOKENS
    temperature: float = DEFAULT_TEMPERATURE
    force_model: Optional[str] = None


class LLMGuardrails:
    """
    - Daily token budget (estimated)
    - Call throttling (min spacing + calls/min)
    """

    def __init__(self) -> None:
        self._last_call_ts = 0.0
        self._call_timestamps = []  # epoch seconds for last minute
        self._ensure_usage_file()

    def _ensure_usage_file(self) -> None:
        if not USAGE_FILE.exists():
            self._write_usage({"date": str(date.today()), "tokens_est": 0, "calls": 0})

    def _read_usage(self) -> dict:
        try:
            return json.loads(USAGE_FILE.read_text(encoding="utf-8"))
        except Exception:
            # If file is corrupted, reset safely
            return {"date": str(date.today()), "tokens_est": 0, "calls": 0}

    def _write_usage(self, data: dict) -> None:
        USAGE_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def _rollover_if_new_day(self, usage: dict) -> dict:
        today = str(date.today())
        if usage.get("date") != today:
            usage = {"date": today, "tokens_est": 0, "calls": 0}
            self._write_usage(usage)
        return usage

    @staticmethod
    def estimate_tokens(text: str) -> int:
        """
        Rough heuristic: ~4 chars per token in English on average.
        This is an estimate. Good enough for budget guarding.
        """
        return max(1, len(text) // 4)

    def enforce_daily_budget(self, prompt: str, max_tokens: int) -> None:
        usage = self._rollover_if_new_day(self._read_usage())

        # estimate: prompt tokens + expected output tokens
        est_prompt = self.estimate_tokens(prompt)
        est_total = est_prompt + max_tokens

        if usage["tokens_est"] + est_total > DAILY_TOKEN_LIMIT:
            raise RuntimeError(
                f"Daily LLM token limit reached. "
                f"Used(est)={usage['tokens_est']}, Request(est)={est_total}, Limit={DAILY_TOKEN_LIMIT}."
            )

    def record_usage(self, prompt: str, max_tokens: int) -> None:
        usage = self._rollover_if_new_day(self._read_usage())
        est_prompt = self.estimate_tokens(prompt)
        est_total = est_prompt + max_tokens

        usage["tokens_est"] += est_total
        usage["calls"] += 1
        self._write_usage(usage)

    def throttle(self) -> None:
        # 1) Minimum spacing
        now = time.time()
        elapsed = now - self._last_call_ts
        if elapsed < MIN_SECONDS_BETWEEN_CALLS:
            time.sleep(MIN_SECONDS_BETWEEN_CALLS - elapsed)

        # 2) Calls per minute
        now = time.time()
        one_minute_ago = now - 60
        self._call_timestamps = [t for t in self._call_timestamps if t > one_minute_ago]

        if len(self._call_timestamps) >= MAX_CALLS_PER_MINUTE:
            # sleep until we're below the cap
            oldest = min(self._call_timestamps)
            sleep_for = (oldest + 60) - now
            if sleep_for > 0:
                time.sleep(sleep_for)

        self._call_timestamps.append(time.time())
        self._last_call_ts = time.time()


guard = LLMGuardrails()


def choose_model(purpose: str) -> str:
    """
    Simple model switching policy:
    - cheap for routine tasks
    - strong for architecture/refactor/complex bugfix
    """
    purpose = (purpose or "general").lower()

    if purpose in {"architecture", "refactor", "complex_bugfix", "design"}:
        return MODEL_STRONG

    if purpose in {"tests", "docs", "general", "lint", "simple_bugfix"}:
        return MODEL_CHEAP

    # default
    return MODEL_CHEAP


def ask_claude(req: LLMRequest) -> str:
    model = req.force_model or choose_model(req.purpose)

    # Guardrails BEFORE calling API
    guard.enforce_daily_budget(req.prompt, req.max_tokens)
    guard.throttle()

    resp = client.messages.create(
        model=model,
        max_tokens=req.max_tokens,
        temperature=req.temperature,
        messages=[{"role": "user", "content": req.prompt}],
    )

    # Record (estimated) usage AFTER call
    guard.record_usage(req.prompt, req.max_tokens)

    # Anthropic SDK returns content list; take first text chunk.
    return resp.content[0].text