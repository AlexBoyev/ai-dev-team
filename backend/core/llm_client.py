from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy.orm import Session

from backend.db.models import LLMCall
from backend.core.pricing import get_price
from backend.core.config import LLMConfig
DEFAULT_MODEL = LLMConfig.MODEL_CHEAP


def _calc_cost(model: str, prompt_tokens: int, completion_tokens: int) -> Decimal:
    rates = get_price(model)
    cost = (prompt_tokens / 1000 * rates["prompt"]) + \
           (completion_tokens / 1000 * rates["completion"])
    return Decimal(str(round(cost, 6)))


def check_budget(db: Session) -> tuple[bool, float, float]:
    """Returns (is_within_budget, spent_usd, budget_usd)."""
    from sqlalchemy import func, extract

    budget = float(os.environ.get("LLM_BUDGET_USD", "15.00"))
    now = datetime.now(timezone.utc)

    spent = db.query(func.sum(LLMCall.cost_usd)).filter(
        extract("year",  LLMCall.ts) == now.year,
        extract("month", LLMCall.ts) == now.month,
    ).scalar() or Decimal("0")

    return float(spent) < budget, float(spent), budget


class BudgetExceededError(Exception):
    def __init__(self, spent: float, budget: float):
        self.spent = spent
        self.budget = budget
        super().__init__(
            f"Monthly LLM budget exceeded: ${spent:.4f} spent of ${budget:.2f} limit"
        )


def complete(
    *,
    db: Session,
    messages: list[dict],
    system: str | None = None,
    model: str = DEFAULT_MODEL,
    run_id: str | None = None,
    task_id: str | None = None,
    agent_key: str | None = None,
    max_tokens: int = 2000,
    temperature: float = 0.2,
) -> str:
    """
    Call Anthropic, log tokens + cost to DB, enforce monthly budget.
    Returns assistant message content string.

    Example:
        from backend.core import llm_client
        text = llm_client.complete(
            db=db,
            system="You are a senior engineer...",
            messages=[{"role": "user", "content": "Analyze this repo..."}],
            model="claude-3-5-sonnet-20241022",
            run_id=run_id,
            task_id=task_id,
            agent_key="dev_1",
        )
    """
    import anthropic

    within_budget, spent, budget = check_budget(db)
    if not within_budget:
        raise BudgetExceededError(spent, budget)

    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    kwargs: dict = dict(
        model=model,
        max_tokens=max_tokens,
        messages=messages,
    )
    if system:
        kwargs["system"] = system

    response = client.messages.create(**kwargs)

    prompt_tokens     = response.usage.input_tokens
    completion_tokens = response.usage.output_tokens
    total_tokens      = prompt_tokens + completion_tokens
    cost              = _calc_cost(model, prompt_tokens, completion_tokens)

    db.add(LLMCall(
        id=uuid.uuid4(),
        run_id=uuid.UUID(run_id)   if run_id  else None,
        task_id=uuid.UUID(task_id) if task_id else None,
        agent_key=agent_key,
        model=model,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total_tokens,
        cost_usd=cost,
        ts=datetime.now(timezone.utc),
    ))
    db.commit()

    return response.content[0].text
