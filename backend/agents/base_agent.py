from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict

import anthropic
from sqlalchemy import func

from backend.core import prompt_loader
from backend.db.models import AgentLog, LLMCall
from backend.tools.tool_registry import ToolContext, run_tool

logger = logging.getLogger(__name__)
from backend.core.config import LLMConfig

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
        self._log_event(
            ctx,
            event_type="task_start",
            data={
                "task_name": task_name,
                "payload_keys": sorted(list(payload.keys())),
            },
        )
        try:
            result = self._run(task_name=task_name, ctx=ctx, payload=payload)
            self._log_event(
                ctx,
                event_type="task_complete",
                data={
                    "task_name": task_name,
                    "result_keys": sorted(list(result.keys())),
                    "result_message": str(result.get("result_message", "")),
                },
            )
            return result
        except Exception as e:
            self._log_event(
                ctx,
                event_type="task_error",
                data={
                    "task_name": task_name,
                    "error": str(e),
                },
            )
            raise

    def _run(self, task_name: str, ctx: ToolContext, payload: Dict[str, Any]) -> Dict[str, Any]:
        raise NotImplementedError

    def _tool(self, ctx: ToolContext, tool_name: str, **kwargs: Any) -> Any:
        self._log_event(
            ctx,
            event_type="tool_call",
            data={
                "tool_name": tool_name,
                "kwargs": kwargs,
            },
        )
        result = run_tool(tool_name, ctx, **kwargs)
        self._log_event(
            ctx,
            event_type="tool_result",
            data={
                "tool_name": tool_name,
                "result_type": type(result).__name__,
                "result_preview": self._preview_value(result),
            },
        )
        return result

    def _call_llm(
        self,
        prompt_name: str,
        context: Dict[str, Any],
        ctx: ToolContext,
        version: int = 1,
    ) -> str:
        api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
        if not api_key:
            logger.warning(
                f"_call_llm: ANTHROPIC_API_KEY not set — skipping LLM call for {prompt_name}"
            )
            self._log_event(
                ctx,
                event_type="llm_skipped",
                data={"prompt_name": prompt_name, "reason": "missing_api_key"},
            )
            return ""

        self._check_budget(ctx)

        prompt = prompt_loader.get(prompt_name, version=version)
        system_text, user_text = prompt.render(**context)

        self._log_event(
            ctx,
            event_type="llm_call",
            data={
                "prompt_name": prompt_name,
                "model": prompt.model,
                "max_tokens": prompt.max_tokens,
                "temperature": prompt.temperature,
            },
        )

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

        prompt_tokens = response.usage.input_tokens
        completion_tokens = response.usage.output_tokens
        total_tokens = prompt_tokens + completion_tokens
        cost_usd = self._estimate_cost(prompt.model, prompt_tokens, completion_tokens)
        response_text = response.content[0].text if response.content else ""

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

        self._log_event(
            ctx,
            event_type="llm_result",
            data={
                "prompt_name": prompt_name,
                "model": prompt.model,
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": total_tokens,
                "cost_usd": cost_usd,
                "response_preview": response_text[:300],
            },
        )

        logger.info(
            f"LLM call | agent={self.profile.agent_id} prompt={prompt_name} "
            f"tokens={total_tokens} cost=${cost_usd:.6f}"
        )
        return response_text

    def _check_budget(self, ctx: ToolContext) -> None:
        if ctx.db is None or not ctx.run_id:
            return

        limit_usd = float(os.environ.get("MAX_COST_PER_RUN_USD", "2.00"))
        spent = (
            ctx.db.query(func.sum(LLMCall.cost_usd))
            .filter(LLMCall.run_id == ctx.run_id)
            .scalar()
            or 0
        )
        spent = float(spent)
        if spent >= limit_usd:
            raise RuntimeError(
                f"Run cost limit reached: spent=${spent:.4f}, limit=${limit_usd:.2f}"
            )

    def _log_event(self, ctx: ToolContext, event_type: str, data: Dict[str, Any]) -> None:
        if ctx.db is None or not ctx.run_id:
            return
        try:
            import uuid
            row = AgentLog(
                id=uuid.uuid4(),
                run_id=ctx.run_id,
                task_id=ctx.task_id,
                agent_key=self.profile.agent_id,
                event_type=event_type,
                data_json=json.dumps(data, ensure_ascii=False),
                ts=datetime.now(timezone.utc),
            )
            ctx.db.add(row)
            ctx.db.commit()
        except Exception as e:
            logger.warning(f"_log_event failed (non-fatal): {e}")

    @staticmethod
    def _preview_value(value: Any) -> Any:
        if isinstance(value, str):
            return value[:200]
        if isinstance(value, list):
            return {"type": "list", "size": len(value)}
        if isinstance(value, dict):
            return {"type": "dict", "keys": sorted(list(value.keys()))[:20]}
        return str(value)[:200]

    @staticmethod
    def _estimate_cost(model: str, prompt_tokens: int, completion_tokens: int) -> float:
        PRICING = {
            LLMConfig.MODEL_CHEAP: (0.80, 4.00),
            "claude-3-haiku-20240307": (0.25, 1.25),
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
        if ctx.db is None:
            return
        try:
            import uuid
            row = LLMCall(
                id=uuid.uuid4(),
                run_id=ctx.run_id,
                task_id=ctx.task_id,
                agent_key=agent_key,
                prompt_name=prompt_name,
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
