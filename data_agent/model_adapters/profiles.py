"""Model profile loader: reads model_profiles.yaml and resolves env vars."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

import yaml

from .base import ModelProfile


def load_profiles(config_path: Optional[Path] = None) -> dict[str, ModelProfile]:
    if config_path is None:
        config_path = Path("model_profiles.yaml")
    if not config_path.exists():
        return {}
    with open(config_path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}
    profiles: dict[str, ModelProfile] = {}
    raw_profiles = raw.get("profiles", {}) or {}
    for name, cfg in raw_profiles.items():
        profiles[name] = ModelProfile(name=name, **{k: v for k, v in cfg.items() if k != "name"})
    return profiles


def resolve_profile_env(profile: ModelProfile) -> dict[str, str]:
    resolved: dict[str, str] = {}
    if profile.base_url_env:
        resolved["base_url"] = os.environ.get(profile.base_url_env, "")
    if profile.api_key_env:
        resolved["api_key"] = os.environ.get(profile.api_key_env, "")
    if profile.model_env:
        resolved["model"] = os.environ.get(profile.model_env, "")
    return resolved


def is_profile_available(profile: ModelProfile) -> bool:
    if not profile.enabled:
        return False
    env = resolve_profile_env(profile)
    return bool(env.get("base_url") and env.get("api_key") and env.get("model"))


def list_profile_status(profile: ModelProfile, show_values: bool = False) -> dict[str, str]:
    env = resolve_profile_env(profile)
    status: dict[str, str] = {
        "name": profile.name,
        "role": profile.role,
        "provider": profile.provider,
        "enabled": str(profile.enabled),
    }
    for key in ("base_url", "api_key", "model"):
        env_key = getattr(profile, f"{key}_env", "")
        if show_values:
            status[key] = env.get(key, "")
        elif env.get(key):
            status[key] = "configured"
        else:
            status[key] = "missing"
    return status
