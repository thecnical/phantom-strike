"""
PhantomStrike Rules of Engagement (RoE) Enforcement
Validates every action against operator-defined constraints.
Never crashes the framework — violations are logged and actions are blocked.
"""
from __future__ import annotations
import asyncio
import ipaddress
import logging
from dataclasses import dataclass, field
from datetime import datetime
from fnmatch import fnmatch
from typing import List, Optional, Dict, Any

logger = logging.getLogger("phantom.roe")


@dataclass
class RoEConfig:
    """Rules of Engagement configuration."""
    allowed_targets: List[str] = field(default_factory=list)   # CIDR or hostname patterns
    forbidden_targets: List[str] = field(default_factory=list)
    allowed_techniques: List[str] = field(default_factory=list)  # MITRE IDs or empty = all
    forbidden_techniques: List[str] = field(default_factory=list)
    engagement_start: Optional[datetime] = None
    engagement_end: Optional[datetime] = None
    rate_limit_rps: float = 0.0  # requests per second, 0 = unlimited
    max_concurrent: int = 0  # 0 = unlimited


class RoEViolation(Exception):
    """Raised when an action violates RoE. Never propagates past RoEMiddleware."""
    def __init__(self, reason: str, target: str = "", technique: str = ""):
        self.reason = reason
        self.target = target
        self.technique = technique
        super().__init__(f"RoE Violation: {reason} (target={target}, technique={technique})")


class RoEMiddleware:
    """
    Enforces Rules of Engagement at every action boundary.
    Logs violations and blocks actions — never crashes the framework.
    """

    def __init__(self, config: RoEConfig):
        self.config = config
        self._violation_log: List[Dict[str, Any]] = []
        self._rate_limiter_lock = asyncio.Lock()
        self._last_request_time: float = 0.0
        self._token_bucket: float = 0.0
        self._bucket_capacity: float = max(1.0, config.rate_limit_rps)
        self._refill_rate: float = config.rate_limit_rps

    def check_target(self, target: str) -> bool:
        """
        Check if a target is allowed by RoE.
        Returns True if allowed, False if forbidden or outside engagement window.
        
        Rules:
        - forbidden_targets takes precedence over allowed_targets
        - Supports CIDR matching (ipaddress module) and glob matching (fnmatch)
        - Checks engagement window (engagement_start/end vs datetime.now())
        """
        try:
            # Check engagement window
            now = datetime.now()
            if self.config.engagement_start and now < self.config.engagement_start:
                return False
            if self.config.engagement_end and now > self.config.engagement_end:
                return False

            # Check forbidden list first (takes precedence)
            if self._matches_any_pattern(target, self.config.forbidden_targets):
                return False

            # If allowed list is empty, allow all (except forbidden)
            if not self.config.allowed_targets:
                return True

            # Check allowed list
            return self._matches_any_pattern(target, self.config.allowed_targets)

        except Exception as e:
            logger.error(f"[RoE] Error checking target {target}: {e}")
            return False

    def check_technique(self, technique: str) -> bool:
        """
        Check if a MITRE technique is allowed by RoE.
        Returns True if allowed, False if forbidden.
        
        Rules:
        - If forbidden_techniques contains the technique, return False
        - If allowed_techniques is empty, return True (all allowed)
        - Return True only if technique is in allowed_techniques
        """
        try:
            # Check forbidden list first
            if technique in self.config.forbidden_techniques:
                return False

            # If allowed list is empty, allow all (except forbidden)
            if not self.config.allowed_techniques:
                return True

            # Check allowed list
            return technique in self.config.allowed_techniques

        except Exception as e:
            logger.error(f"[RoE] Error checking technique {technique}: {e}")
            return False

    def check_action(self, target: str, technique: str) -> bool:
        """
        Check if an action (target + technique) is allowed by RoE.
        Logs violations to internal violation log — never raises exceptions.
        Returns True if both checks pass, False otherwise.
        """
        try:
            target_allowed = self.check_target(target)
            technique_allowed = self.check_technique(technique)

            if not target_allowed:
                self._log_violation(
                    reason="Target not allowed or outside engagement window",
                    target=target,
                    technique=technique
                )
                return False

            if not technique_allowed:
                self._log_violation(
                    reason="Technique not allowed",
                    target=target,
                    technique=technique
                )
                return False

            return True

        except Exception as e:
            logger.error(f"[RoE] Error checking action: {e}")
            self._log_violation(
                reason=f"Internal error: {e}",
                target=target,
                technique=technique
            )
            return False

    async def apply_rate_limit(self) -> None:
        """
        Apply rate limiting using asyncio token bucket.
        If rate_limit_rps is 0, return immediately (no limit).
        Suspends the calling coroutine until a token is available.
        """
        if self.config.rate_limit_rps <= 0:
            return

        async with self._rate_limiter_lock:
            now = asyncio.get_event_loop().time()

            # Refill tokens based on time elapsed
            if self._last_request_time > 0:
                elapsed = now - self._last_request_time
                self._token_bucket = min(
                    self._bucket_capacity,
                    self._token_bucket + elapsed * self._refill_rate
                )
            else:
                # First request — start with full bucket
                self._token_bucket = self._bucket_capacity

            self._last_request_time = now

            # Wait until we have at least one token
            while self._token_bucket < 1.0:
                wait_time = (1.0 - self._token_bucket) / self._refill_rate
                await asyncio.sleep(wait_time)

                now = asyncio.get_event_loop().time()
                elapsed = now - self._last_request_time
                self._token_bucket = min(
                    self._bucket_capacity,
                    self._token_bucket + elapsed * self._refill_rate
                )
                self._last_request_time = now

            # Consume one token
            self._token_bucket -= 1.0

    def get_violation_log(self) -> List[Dict[str, Any]]:
        """Return list of all logged violations."""
        return self._violation_log.copy()

    def _matches_any_pattern(self, target: str, patterns: List[str]) -> bool:
        """
        Check if target matches any pattern in the list.
        Supports CIDR notation (for IPs) and glob patterns (for hostnames).
        """
        for pattern in patterns:
            # Try CIDR matching first
            if self._is_cidr(pattern):
                if self._matches_cidr(target, pattern):
                    return True
            # Fall back to glob matching
            elif fnmatch(target.lower(), pattern.lower()):
                return True
        return False

    def _is_cidr(self, pattern: str) -> bool:
        """Check if a pattern is a valid CIDR notation."""
        try:
            ipaddress.ip_network(pattern, strict=False)
            return True
        except ValueError:
            return False

    def _matches_cidr(self, target: str, cidr: str) -> bool:
        """Check if target IP matches CIDR pattern."""
        try:
            target_ip = ipaddress.ip_address(target)
            network = ipaddress.ip_network(cidr, strict=False)
            return target_ip in network
        except ValueError:
            return False

    def _log_violation(self, reason: str, target: str = "", technique: str = ""):
        """Log a RoE violation."""
        violation = {
            "timestamp": datetime.now().isoformat(),
            "reason": reason,
            "target": target,
            "technique": technique
        }
        self._violation_log.append(violation)
        logger.warning(f"[RoE] Violation: {reason} (target={target}, technique={technique})")
