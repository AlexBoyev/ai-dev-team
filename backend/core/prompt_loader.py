from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml
from jinja2 import BaseLoader, Environment, StrictUndefined, Undefined

logger = logging.getLogger(__name__)

PROMPTS_DIR = Path(__file__).parent.parent / "prompts"


@dataclass
class Prompt:
    name: str
    version: int
    model: str
    max_tokens: int
    temperature: float
    system: str
    user_template: str

    def render(self, **variables: Any) -> tuple[str | None, str]:
        """
        Render the prompt with given variables.
        Returns (system, user_message) ready to pass to llm_client.complete().
        """
        env = Environment(
            loader=BaseLoader(),
            undefined=StrictUndefined,
            trim_blocks=True,
            lstrip_blocks=True,
        )

        try:
            user_message = env.from_string(self.user_template).render(**variables)
        except Exception as e:
            raise ValueError(
                f"Failed to render prompt '{self.name}' v{self.version}: {e}\n"
                f"Available variables: {list(variables.keys())}"
            ) from e

        system = self.system.strip() if self.system else None
        return system, user_message.strip()


# Module-level cache: { "scan_and_report:1": Prompt, ... }
_cache: dict[str, Prompt] = {}


def _cache_key(name: str, version: int) -> str:
    return f"{name}:{version}"


def _load_from_disk(name: str, version: int) -> Prompt:
    filename = f"{name}_v{version}.yaml"
    path = PROMPTS_DIR / filename

    if not path.exists():
        raise FileNotFoundError(
            f"Prompt file not found: {path}\n"
            f"Expected location: {PROMPTS_DIR / filename}"
        )

    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    return Prompt(
        name=data["name"],
        version=int(data["version"]),
        model=data.get("model", "claude-3-5-haiku-20241022"),
        max_tokens=int(data.get("max_tokens", 2000)),
        temperature=float(data.get("temperature", 0.2)),
        system=data.get("system", ""),
        user_template=data["user_template"],
    )


def get(name: str, version: int = 1) -> Prompt:
    """
    Load a prompt by name and version. Cached after first load.

    Usage:
        from backend.core import prompt_loader

        prompt = prompt_loader.get("scan_and_report", version=1)
        system, user_msg = prompt.render(
            target_subdir=target_subdir,
            project_type=intelligence["project_type"],
            languages=intelligence["languages"],
            ...
        )
        result = llm_client.complete(
            db=db,
            system=system,
            messages=[{"role": "user", "content": user_msg}],
            model=prompt.model,
            max_tokens=prompt.max_tokens,
            temperature=prompt.temperature,
            run_id=run_id,
            agent_key="dev_1",
        )
    """
    key = _cache_key(name, version)
    if key not in _cache:
        _cache[key] = _load_from_disk(name, version)
        logger.debug(f"Prompt loaded: {name} v{version} (model={_cache[key].model})")
    return _cache[key]


def reload(name: str, version: int = 1) -> Prompt:
    """Force reload from disk — useful during development."""
    key = _cache_key(name, version)
    _cache.pop(key, None)
    return get(name, version)


def list_available() -> list[dict]:
    """Return all prompt YAML files found in the prompts directory."""
    result = []
    for path in sorted(PROMPTS_DIR.glob("*.yaml")):
        try:
            with path.open("r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
            result.append({
                "name":    data.get("name"),
                "version": data.get("version"),
                "model":   data.get("model"),
                "file":    path.name,
            })
        except Exception:
            pass
    return result
