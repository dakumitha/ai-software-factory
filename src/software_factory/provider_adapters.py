"""Explicit, approval-gated interface for future external API adapters.

No dynamic plugin loading, network calls, or provider invocation occurs here.
"""
from __future__ import annotations
from typing import Any, Protocol, runtime_checkable
from .api_registry import ApiRegistry

class AdapterError(ValueError):
    """Adapter registration or lookup violates the trust policy."""

@runtime_checkable
class ProviderAdapter(Protocol):
    @property
    def provider_key(self) -> str:
        """Stable, code-defined adapter identifier."""
    @property
    def supported_operations(self) -> frozenset[str]:
        """Explicit allowlist of operation names."""
    def invoke(self, operation: str, payload: dict[str, Any], *, timeout_seconds: int) -> dict[str, Any]:
        """Invoke a supported operation. This module never calls it."""

class AdapterRegistry:
    """Bind approved catalogue records to explicitly constructed trusted objects."""
    def __init__(self, api_registry: ApiRegistry):
        self._api_registry = api_registry
        self._adapters: dict[int, ProviderAdapter] = {}

    @staticmethod
    def _validate(adapter: ProviderAdapter) -> frozenset[str]:
        key = getattr(adapter, "provider_key", None)
        operations = getattr(adapter, "supported_operations", None)
        if not isinstance(key, str) or not key.strip() or len(key) > 120:
            raise AdapterError("provider_key must be a non-empty string of at most 120 characters.")
        if not isinstance(operations, (set, frozenset)) or not operations:
            raise AdapterError("supported_operations must be a non-empty set or frozenset.")
        if any(not isinstance(op, str) or not op.strip() or len(op) > 100 for op in operations):
            raise AdapterError("Each operation must be a non-empty string of at most 100 characters.")
        if not callable(getattr(adapter, "invoke", None)):
            raise AdapterError("Adapter must implement invoke().")
        return frozenset(operations)

    def register(self, candidate_id: int, adapter: ProviderAdapter) -> None:
        """Register trusted application code only against a currently approved record."""
        candidate = self._api_registry.get(candidate_id)
        if not candidate:
            raise AdapterError("API candidate does not exist.")
        if candidate["approval_status"] != "APPROVED":
            raise AdapterError("API candidate must be approved before adapter registration.")
        self._validate(adapter)
        if candidate_id in self._adapters:
            raise AdapterError("An adapter is already registered for this candidate.")
        self._adapters[candidate_id] = adapter

    def resolve(self, candidate_id: int, operation: str) -> ProviderAdapter:
        """Resolve only while current approval and operation allowlist both pass."""
        candidate = self._api_registry.get(candidate_id)
        if not candidate:
            raise AdapterError("API candidate does not exist.")
        if candidate["approval_status"] != "APPROVED":
            raise AdapterError("API candidate is not currently approved.")
        adapter = self._adapters.get(candidate_id)
        if adapter is None:
            raise AdapterError("No explicitly registered adapter exists for this candidate.")
        operations = self._validate(adapter)
        if operation not in operations:
            raise AdapterError("Operation is not allowlisted by this adapter.")
        return adapter

    def registered_candidates(self) -> list[int]:
        """Return candidate IDs with in-process adapter objects, including blocked ones."""
        return sorted(self._adapters)
