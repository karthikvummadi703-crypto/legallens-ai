"""Gemini API key rotation with quota/rate-limit failover.

All Gemini call sites (analysis, RAG chat, general chat, embeddings) obtain
their API key through this module instead of reading
``settings.GEMINI_API_KEY`` directly:

    from app.services.ai.gemini_keys import gemini_key_manager

    for api_key in gemini_key_manager.iter_keys():
        try:
            ... call Gemini with api_key ...
            break  # success
        except Exception as e:
            if gemini_key_manager.is_quota_error(e):
                continue  # try the next key
            raise
    else:
        ... all keys exhausted, use offline fallback ...

Behaviour:
- Round-robin across all keys configured via GEMINI_API_KEY[_2/_3/_S].
- A key that raises a quota / rate-limit / permission error is put on a
  short cooldown so subsequent requests prefer the healthy keys.
- Cooldowns expire automatically, so a key whose quota resets is reused.
- Thread-safe; falls back to offline behaviour when no keys are configured.
"""

import threading
import time
from collections.abc import Iterator

from app.config import get_gemini_keys
from app.core.logging import logger

# A key that fails with a quota-type error is skipped for this long before
# being tried again (quota windows reset over time).
_QUOTA_COOLDOWN_SECONDS = 15 * 60


def _is_quota_error(error: Exception) -> bool:
    """Heuristic detection of quota / rate-limit / exhausted-key failures."""
    text = f"{type(error).__name__}: {error}".lower()
    markers = (
        "429",
        "quota",
        "rate limit",
        "rate-limit",
        "ratelimit",
        "too many requests",
        "resource_exhausted",
        "resource exhausted",
        "exhausted",
        "limit exceeded",
        "billing",
        "permission denied",
        "api key not valid",
        "invalid api key",
        "api_key_invalid",
        "key expired",
    )
    return any(marker in text for marker in markers)


def _is_transient_error(error: Exception) -> bool:
    """Transient server errors (503/500/504) worth retrying on next key."""
    text = f"{type(error).__name__}: {error}".lower()
    markers = (
        "503",
        "500",
        "504",
        "unavailable",
        "overloaded",
        "high demand",
        "try again later",
        "deadline exceeded",
        "internal error",
        "temporarily unavailable",
    )
    return any(marker in text for marker in markers)


class GeminiKeyManager:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._position = 0
        # key -> monotonic timestamp until which the key is skipped
        self._cooldown_until: dict = {}

    def _configured_keys(self) -> list[str]:
        try:
            return get_gemini_keys()
        except Exception as e:
            logger.warning(f"Could not read Gemini keys from config ({e}).")
            return []

    def _prune_cooldowns(self) -> None:
        now = time.monotonic()
        expired = [k for k, until in self._cooldown_until.items() if until <= now]
        for k in expired:
            del self._cooldown_until[k]

    def available_keys(self) -> list[str]:
        """Healthy keys in round-robin order.

        Keys on quota cooldown are skipped while any healthy key exists.
        When every key is cooling down, none are returned so callers fall
        back to the offline engine instantly instead of stalling on a doomed
        round of serial failures; a recovered quota is picked up on retry.
        """
        keys = self._configured_keys()
        if not keys:
            return []
        with self._lock:
            self._prune_cooldowns()
            healthy = [k for k in keys if k not in self._cooldown_until]
            if not healthy:
                # All keys are on cooldown. Do NOT return them all for another
                # doomed round of failures — that stalls every request for the
                # full failover time (all 3 keys failing serially). Return
                # empty so callers fall back to the offline engine instantly.
                return []
            # Rotate the healthy subset for even usage distribution.
            start = self._position % len(healthy)
            return healthy[start:] + healthy[:start]

    def iter_keys(self) -> Iterator[str]:
        """Yield each usable key once, most-preferred first."""
        seen = set()
        for key in self.available_keys():
            if key not in seen:
                seen.add(key)
                yield key
        with self._lock:
            self._position += 1

    def report_quota_failure(self, api_key: str) -> None:
        """Mark a key as exhausted so the next requests prefer other keys."""
        with self._lock:
            self._position += 1
            self._cooldown_until[api_key] = time.monotonic() + _QUOTA_COOLDOWN_SECONDS
        logger.warning(
            f"Gemini API key ending '...{api_key[-6:]}' hit a quota/rate limit; "
            "failing over to the next configured key."
        )

    def report_transient_failure(self, api_key: str) -> None:
        """Short cooldown for transient 503/overloaded — retry quickly."""
        with self._lock:
            self._position += 1
            # Shorter cooldown for transient errors (1 min vs 15 min)
            self._cooldown_until[api_key] = time.monotonic() + 60
        logger.warning(
            f"Gemini API key ending '...{api_key[-6:]}' hit transient error; "
            "failing over to next key."
        )

    def report_success(self, api_key: str) -> None:
        """Clear any cooldown for a key that just worked."""
        with self._lock:
            self._cooldown_until.pop(api_key, None)

    @staticmethod
    def is_quota_error(error: Exception) -> bool:
        # Backward-compat: treat transient 503 as retryable so existing call sites failover correctly.
        return _is_quota_error(error) or _is_transient_error(error)

    @staticmethod
    def is_transient_error(error: Exception) -> bool:
        return _is_transient_error(error)

    @staticmethod
    def is_retryable_error(error: Exception) -> bool:
        return _is_quota_error(error) or _is_transient_error(error)

    def has_keys(self) -> bool:
        return bool(self._configured_keys())


# Shared singleton used by every Gemini call site.
gemini_key_manager = GeminiKeyManager()
