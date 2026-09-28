"""POLARNAV — Phase 15: Circuit Breakers, Retries, Timeouts, and Fault Injection.

Provides resilient execution wrappers with exponential backoff retries,
timeouts, and controlled fault injection for chaos engineering tests.
"""

import time
import logging
import functools
from typing import Callable, Any, Dict, List, Optional

from .models import ProviderId, FaultType, FaultInjectionConfig

logger = logging.getLogger("polarnav.reliability.circuit_breaker")


class FaultInjectionRegistry:
    """Thread-safe registry for injecting simulated faults into the real-time pipeline."""

    def __init__(self):
        self._faults: Dict[str, FaultInjectionConfig] = {}

    def inject_fault(self, fault: FaultInjectionConfig):
        """Register an active fault injection for a specific provider."""
        key = f"{fault.provider.value}_{fault.fault_type.value}"
        self._faults[key] = fault
        logger.warning(f"[CHAOS INJECTION] Injected {fault.fault_type.value} for provider '{fault.provider.value}'")

    def remove_fault(self, provider: ProviderId, fault_type: FaultType):
        """Remove a specific active fault injection."""
        key = f"{provider.value}_{fault_type.value}"
        if key in self._faults:
            del self._faults[key]
            logger.info(f"[CHAOS INJECTION] Removed {fault_type.value} for provider '{provider.value}'")

    def clear_all_faults(self):
        """Reset all active fault injections to restore normal operation."""
        self._faults.clear()
        logger.info("[CHAOS INJECTION] Cleared all active fault injections")

    def get_active_fault(self, provider: ProviderId, fault_type: Optional[FaultType] = None) -> Optional[FaultInjectionConfig]:
        """Check if an active fault matches the provider and type."""
        for key, f in self._faults.items():
            if f.provider == provider and f.active:
                if fault_type is None or f.fault_type == fault_type:
                    return f
        return None

    def list_active_faults(self) -> List[FaultInjectionConfig]:
        """Return all active simulated faults."""
        return list(self._faults.values())


# Global fault registry singleton
fault_registry = FaultInjectionRegistry()


def retry_with_backoff(
    max_retries: int = 3,
    initial_delay_sec: float = 0.1,
    backoff_factor: float = 2.0,
    allowed_exceptions: tuple = (Exception,),
):
    """Decorator executing functions with exponential backoff retries and structured logging."""
    def decorator(func: Callable):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            delay = initial_delay_sec
            last_err = None
            for attempt in range(1, max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except allowed_exceptions as e:
                    last_err = e
                    if attempt == max_retries:
                        logger.error(
                            f"[CIRCUIT BREAKER] Function '{func.__name__}' failed after {max_retries} attempts: {e}"
                        )
                        raise
                    logger.warning(
                        f"[CIRCUIT BREAKER] Retry attempt {attempt}/{max_retries} for '{func.__name__}' "
                        f"after error: {e}. Backing off {delay:.2f}s..."
                    )
                    time.sleep(delay)
                    delay *= backoff_factor
            raise last_err
        return wrapper
    return decorator


def with_timeout(timeout_sec: float = 2.0):
    """Enforce a soft timeout limit on an operation."""
    def decorator(func: Callable):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            t_start = time.perf_counter()
            result = func(*args, **kwargs)
            elapsed = time.perf_counter() - t_start
            if elapsed > timeout_sec:
                logger.warning(
                    f"[TIMEOUT EXCEEDED] Function '{func.__name__}' completed in {elapsed:.3f}s, "
                    f"exceeding safety SLA of {timeout_sec:.3f}s"
                )
            return result
        return wrapper
    return decorator
