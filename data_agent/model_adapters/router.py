"""Model router: determines which model role(s) to call for each data type and mode."""
from __future__ import annotations

from .base import TaskContext

_ROUTING_TABLE: dict[str, dict[str, list[str]]] = {
    "sample_metadata": {
        "local": [],
        "cloud": [],
        "auto": [],
    },
    "raw_numeric": {
        "local": [],
        "cloud": [],
        "auto": [],
    },
    "raw_spectral": {
        "local": [],
        "cloud": [],
        "auto": [],
    },
    "chart_image_input": {
        "local": ["local_stub"],
        "cloud": ["ocr", "vision"],
        "auto": ["ocr", "vision"],
    },
    "visual_image": {
        "local": ["local_vision_stub"],
        "cloud": ["vision", "ocr"],
        "auto": ["vision", "ocr"],
    },
    "descriptive_observation_text": {
        "local": [],
        "cloud": ["fast"],
        "auto": ["fast"],
    },
    "structured_observation": {
        "local": [],
        "cloud": [],
        "auto": [],
    },
}


def route_model_calls(ctx: TaskContext) -> list[str]:
    data_type_rules = _ROUTING_TABLE.get(ctx.data_type, {})
    roles = data_type_rules.get(ctx.model_mode, [])
    return list(roles)


_DEFAULT_FALLBACKS: dict[str, list[str]] = {
    "ocr": ["local_ocr_stub", "local_stub"],
    "vision": ["local_stub"],
    "fast": ["local_stub"],
    "best": ["fast", "local_stub"],
}


def get_fallback_chain(role: str, profiles: dict) -> list[str]:
    if role in profiles:
        profile = profiles[role]
        if profile.fallback:
            return list(profile.fallback)
    return _DEFAULT_FALLBACKS.get(role, ["local_stub"])
