"""Model adapter layer: configurable model service with routing, stubs, and providers."""
from .base import ModelProfile, ModelResult, TaskContext
from .profiles import load_profiles, resolve_profile_env, is_profile_available, list_profile_status
from .router import route_model_calls, get_fallback_chain
from .stubs import STUB_REGISTRY, local_stub, local_ocr_stub, local_vision_stub
from .openai_compatible import call_openai_compatible
from .redaction import redact_string, redact_value, redact_dict, sanitize_model_output_json, sanitize_forbidden_keys_deep, sanitize_and_redact_model_result
