"""
PhantomStrike Multi-Provider AI Engine
Smart failover across 9 FREE AI providers (Groq #1). Never pay a single rupee.
All providers use OpenAI-compatible API format for unified access.
Groq LPU provides 500+ tokens/sec — world's fastest inference.
"""
from __future__ import annotations
import asyncio
import time
import logging
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Optional, AsyncIterator

from openai import AsyncOpenAI

from phantom.core.config import (
    AIProviderConfig,
    AIProviderType,
    PhantomStrikeConfig,
)

logger = logging.getLogger("phantom.ai")


@dataclass
class RateLimitTracker:
    """Track rate limits per provider to enable smart failover."""
    requests_this_minute: int = 0
    requests_today: int = 0
    minute_start: float = field(default_factory=time.time)
    day_start: float = field(default_factory=time.time)
    consecutive_failures: int = 0
    last_failure_time: float = 0.0
    is_blocked: bool = False
    block_until: float = 0.0

    def can_make_request(self, rpm_limit: int, daily_limit: int) -> bool:
        now = time.time()
        # Reset minute counter
        if now - self.minute_start >= 60:
            self.requests_this_minute = 0
            self.minute_start = now
        # Reset daily counter
        if now - self.day_start >= 86400:
            self.requests_today = 0
            self.day_start = now
        # Check block
        if self.is_blocked and now < self.block_until:
            return False
        elif self.is_blocked:
            self.is_blocked = False
            self.consecutive_failures = 0
        return (
            self.requests_this_minute < rpm_limit
            and self.requests_today < daily_limit
        )

    def record_request(self):
        self.requests_this_minute += 1
        self.requests_today += 1
        self.consecutive_failures = 0

    def record_failure(self):
        self.consecutive_failures += 1
        self.last_failure_time = time.time()
        if self.consecutive_failures >= 3:
            self.is_blocked = True
            self.block_until = time.time() + (60 * self.consecutive_failures)


@dataclass
class AIResponse:
    """Standardized AI response across all providers."""
    content: str
    provider: str
    model: str
    tokens_used: int = 0
    latency_ms: float = 0.0
    cached: bool = False


class PhantomAIEngine:
    """
    Multi-provider AI engine with smart failover.
    Cycles through 8 free providers — if one hits rate limit,
    automatically switches to next. Zero cost, maximum power.
    """

    def __init__(self, config: PhantomStrikeConfig):
        self.config = config
        self._clients: dict[str, AsyncOpenAI] = {}
        self._rate_trackers: dict[str, RateLimitTracker] = defaultdict(RateLimitTracker)
        self._response_cache: dict[str, AIResponse] = {}
        self._lock = asyncio.Lock()
        self._initialized = False

    async def initialize(self) -> list[str]:
        """Initialize all configured AI provider clients. Returns list of active providers."""
        active = []
        for name, provider_config in self.config.ai_providers.items():
            if not provider_config.enabled or not provider_config.api_key:
                continue
            try:
                client = AsyncOpenAI(
                    api_key=provider_config.api_key,
                    base_url=provider_config.base_url,
                    timeout=provider_config.timeout,
                )
                self._clients[name] = client
                active.append(name)
                logger.info(f"[AI] Provider '{name}' initialized ({provider_config.model})")
            except Exception as e:
                logger.warning(f"[AI] Failed to init provider '{name}': {e}")
        self._initialized = True
        logger.info(f"[AI] {len(active)} providers active: {active}")
        return active

    def _get_sorted_providers(self) -> list[tuple[str, AIProviderConfig]]:
        """Get providers sorted by priority, filtering unavailable ones."""
        available = []
        for name, pcfg in self.config.ai_providers.items():
            if name not in self._clients:
                continue
            tracker = self._rate_trackers[name]
            if tracker.can_make_request(pcfg.rate_limit_rpm, pcfg.rate_limit_daily):
                available.append((name, pcfg))
        available.sort(key=lambda x: x[1].priority)
        return available

    async def query(
        self,
        prompt: str,
        system_prompt: str = "",
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        force_provider: Optional[str] = None,
    ) -> AIResponse:
        """
        Send query to AI with smart failover across all free providers.
        Tries each provider in priority order until one succeeds.
        """
        if not self._initialized:
            await self.initialize()

        # Check cache
        cache_key = f"{prompt[:100]}_{system_prompt[:50]}"
        if self.config.ai_cache_responses and cache_key in self._response_cache:
            cached = self._response_cache[cache_key]
            return AIResponse(
                content=cached.content, provider=cached.provider,
                model=cached.model, cached=True,
            )

        # Build messages
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        # Get available providers
        if force_provider:
            providers = [(force_provider, self.config.ai_providers[force_provider])]
        else:
            providers = self._get_sorted_providers()

        if not providers:
            raise RuntimeError(
                "[AI] No AI providers available! All rate-limited or unconfigured. "
                "Set API keys in .env file or phantom.yaml"
            )

        last_error = None
        for name, pcfg in providers:
            try:
                start = time.time()
                client = self._clients[name]
                response = await client.chat.completions.create(
                    model=pcfg.model,
                    messages=messages,
                    temperature=temperature or pcfg.temperature,
                    max_tokens=max_tokens or pcfg.max_tokens,
                )
                latency = (time.time() - start) * 1000

                content = response.choices[0].message.content or ""
                tokens = response.usage.total_tokens if response.usage else 0

                self._rate_trackers[name].record_request()

                result = AIResponse(
                    content=content, provider=name, model=pcfg.model,
                    tokens_used=tokens, latency_ms=latency,
                )

                if self.config.ai_cache_responses:
                    self._response_cache[cache_key] = result

                logger.info(
                    f"[AI] Response from {name} ({pcfg.model}) "
                    f"in {latency:.0f}ms, {tokens} tokens"
                )
                return result

            except Exception as e:
                self._rate_trackers[name].record_failure()
                last_error = e
                logger.warning(f"[AI] Provider '{name}' failed: {e}. Trying next...")
                continue

        raise RuntimeError(f"[AI] All providers failed. Last error: {last_error}")

    async def stream(
        self,
        prompt: str,
        system_prompt: str = "",
    ) -> AsyncIterator[str]:
        """Stream response tokens for real-time output."""
        if not self._initialized:
            await self.initialize()

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        providers = self._get_sorted_providers()
        for name, pcfg in providers:
            try:
                client = self._clients[name]
                stream = await client.chat.completions.create(
                    model=pcfg.model,
                    messages=messages,
                    stream=True,
                )
                async for chunk in stream:
                    if chunk.choices and chunk.choices[0].delta.content:
                        yield chunk.choices[0].delta.content
                self._rate_trackers[name].record_request()
                return
            except Exception as e:
                self._rate_trackers[name].record_failure()
                logger.warning(f"[AI] Stream failed on '{name}': {e}")
                continue

    async def analyze_vulnerability(self, vuln_data: dict) -> AIResponse:
        """AI-powered vulnerability analysis and exploit suggestion."""
        system = (
            "You are PhantomStrike AI — an elite offensive security analyst. "
            "Analyze the vulnerability data and provide: "
            "1) Severity assessment 2) Exploit strategy 3) Attack chain possibilities "
            "4) Evasion recommendations 5) MITRE ATT&CK technique mapping. "
            "Be precise, technical, and actionable."
        )
        prompt = f"Analyze this vulnerability:\n{vuln_data}"
        return await self.query(prompt, system_prompt=system)

    async def plan_attack_chain(self, recon_data: dict) -> AIResponse:
        """AI plans optimal multi-step attack chain from recon data."""
        system = (
            "You are PhantomStrike AI — an autonomous attack path planner. "
            "Given reconnaissance data, identify ALL possible attack paths "
            "and rank them by: success probability, stealth level, impact. "
            "Output a structured attack chain with exact steps."
        )
        prompt = f"Plan attack chain from this recon data:\n{recon_data}"
        return await self.query(prompt, system_prompt=system)

    async def generate_payload(self, target_info: dict) -> AIResponse:
        """AI generates context-aware, evasive payloads."""
        system = (
            "You are PhantomStrike AI — a payload engineering specialist. "
            "Generate polymorphic payloads that evade detection. "
            "Consider the target's WAF, IDS, EDR, and AV. "
            "Provide multiple variants with encoding options."
        )
        prompt = f"Generate evasive payload for:\n{target_info}"
        return await self.query(prompt, system_prompt=system)

    def get_status(self) -> dict:
        """Get status of all AI providers."""
        status = {}
        for name, pcfg in self.config.ai_providers.items():
            tracker = self._rate_trackers.get(name, RateLimitTracker())
            status[name] = {
                "active": name in self._clients,
                "model": pcfg.model,
                "requests_today": tracker.requests_today,
                "daily_limit": pcfg.rate_limit_daily,
                "blocked": tracker.is_blocked,
                "failures": tracker.consecutive_failures,
            }
        return status

    async def shutdown(self):
        """Cleanup all provider clients."""
        for client in self._clients.values():
            await client.close()
        self._clients.clear()
        logger.info("[AI] All providers shut down")
