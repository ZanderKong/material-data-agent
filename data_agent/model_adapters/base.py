"""Model adapter base interface: Pydantic models for the model service layer."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field


class ModelProfile(BaseModel):
    name: str
    role: str
    provider: str
    base_url_env: str = ""
    api_key_env: str = ""
    model_env: str = ""
    enabled: bool = True
    priority: int = 100
    fallback: list[str] = Field(default_factory=list)
    timeout_seconds: int = 60
    cost_tier: str = "medium"
    supports_vision: bool = False
    supports_json: bool = True


class TaskContext(BaseModel):
    task_id: str
    data_type: str
    subtype: str = ""
    file_ext: str = ""
    file_size_bytes: int = 0
    has_image: bool = False
    has_text: bool = False
    model_mode: str = "local"
    priority: str = "quality"
    needs_vision: bool = False
    user_requested_quality: str = ""
    enabled_escalation: bool = False


class ModelResult(BaseModel):
    success: bool
    role: str
    provider: str
    model: str = ""
    mode: str = "local"
    input_type: str = ""
    output_json: dict[str, Any] = Field(default_factory=dict)
    raw_text: str = ""
    raw_response: dict[str, Any] = Field(default_factory=dict)
    confidence: float = 0.0
    warnings: list[str] = Field(default_factory=list)
    error: str = ""
    fallback_used: bool = False
    fallback_from: str = ""
    latency_ms: int = 0
    token_usage: dict[str, Any] = Field(default_factory=dict)
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    schema_version: str = "model_result_v1"
    prompt_version: str = ""
