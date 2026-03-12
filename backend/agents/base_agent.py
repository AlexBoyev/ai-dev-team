# backend/agents/base_agent.py
from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import anthropic

from backend.core import prompt_loader
from backend.tools.tool_registry import ToolContext, run_tool

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class AgentProfile:
    agent_id: str
    display_name: str
    role: str


class BaseAgent:
    def __init__(self, profile: AgentProfile) -> None:
        self.profile = profile

    def run_task(
        self,
        task_name: str,
        ctx: ToolContext,
        payload: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        payload = payload or {}
        return self._run(task_name=task_name, ctx=ctx, payload=payload)

    def _run(self, task_name: str, ctx: ToolContext, payload: Dict[str, Any]) -> Dict[str, Any]:
        raise NotImplementedError

    def _tool(self, ctx: ToolContext, tool_name: str, **kwargs: Any) -> Any:
        return run_tool(tool_name, ctx, **kwargs)

    def _call_llm(
        self,
        prompt_name: str,
        context: Dict[str, Any],
        ctx: ToolContext,
        version: int = 1,
    ) -> str:
        """
        Load + render a YAML prompt, call Claude, write cost row to DB, return text.
        Falls back gracefully if ANTHROPIC_API_KEY is not set (returns empty string).
        """
        api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
        if not api_key:
            logger.warning(
                f"_call_llm: ANTHROPIC_API_KEY not set — skipping LLM call for {prompt_name}"
            )
            return ""

        prompt = prompt_loader.get(prompt_name, version=version)
        system_text, user_text = prompt.render(**context)

        client = anthropic.Anthropic(api_key=api_key)

        messages_arg = [{"role": "user", "content": user_text}]
        create_kwargs: Dict[str, Any] = dict(
            model=prompt.model,
            max_tokens=prompt.max_tokens,
            temperature=prompt.temperature,
            messages=messages_arg,
        )
        if system_text:
            create_kwargs["system"] = system_text

        response = client.messages.create(**create_kwargs)

        prompt_tokens      = response.usage.input_tokens
        completion_tokens  = response.usage.output_tokens
        total_tokens       = prompt_tokens + completion_tokens
        cost_usd           = self._estimate_cost(prompt.model, prompt_tokens, completion_tokens)
        response_text      = response.content[0].text if response.content else ""

        self._write_llm_call_row(
            ctx=ctx,
            model=prompt.model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            cost_usd=cost_usd,
            agent_key=self.profile.agent_id,
            prompt_name=prompt_name,
        )

        logger.info(
            f"LLM call | agent={self.profile.agent_id} prompt={prompt_name} "
            f"tokens={total_tokens} cost=${cost_usd:.6f}"
        )
        return response_text

    # ── helpers ──────────────────────────────────────────────────────────

    @staticmethod
    def _estimate_cost(model: str, prompt_tokens: int, completion_tokens: int) -> float:
        PRICING = {
            "claude-3-5-sonnet-20241022": (3.00, 15.00),
            "claude-3-5-haiku-20241022":  (0.80,  4.00),
            "claude-3-opus-20240229":     (15.00, 75.00),
            "claude-3-haiku-20240307":    (0.25,  1.25),
        }
        in_price, out_price = PRICING.get(model, (0.0, 0.0))
        return (prompt_tokens * in_price + completion_tokens * out_price) / 1_000_000

    @staticmethod
    def _write_llm_call_row(
        ctx: ToolContext,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
        total_tokens: int,
        cost_usd: float,
        agent_key: str,
        prompt_name: str,
    ) -> None:
        """Write a row to llm_calls. Silently skips if db is not attached to ctx."""
        if ctx.db is None:
            return
        try:
            from backend.db.models import LLMCall
            import uuid
            row = LLMCall(
                id=uuid.uuid4(),
                run_id=ctx.run_id,
                agent_key=agent_key,
                prompt_name=prompt_name,          # ← NEW
                model=model,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=total_tokens,
                cost_usd=cost_usd,
                ts=datetime.now(timezone.utc),
            )
            ctx.db.add(row)
            ctx.db.commit()
        except Exception as e:
            logger.warning(f"_write_llm_call_row failed (non-fatal): {e}")
