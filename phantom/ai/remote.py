"""
PhantomStrike Remote AI Client
When backend_enabled=True, AI calls go through the creator's deployed backend
instead of using local API keys. Users need ZERO API keys.
"""
from __future__ import annotations
import asyncio
import logging
import time
from dataclasses import dataclass
from typing import Optional

import httpx

logger = logging.getLogger("phantom.ai.remote")


@dataclass
class RemoteAIResponse:
    """Response from remote backend AI endpoint."""
    content: str = ""
    provider: str = "remote"
    model: str = "backend"
    tokens_used: int = 0
    latency_ms: float = 0.0
    cached: bool = False


class RemoteAIClient:
    """
    Proxy AI client that routes all AI requests through
    the creator's Render backend. Users need NO API keys.

    Flow: User CLI → HTTP → Creator Backend (Render) → AI Providers → Response
    """

    def __init__(self, backend_url: str, timeout: int = 120):
        self.backend_url = backend_url.rstrip("/")
        self.timeout = timeout
        self._client: Optional[httpx.AsyncClient] = None
        self._request_count = 0
        self._total_latency = 0.0

    async def _ensure_client(self):
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=self.timeout,
                headers={"User-Agent": "PhantomStrike-CLI/1.0"},
            )

    async def query(self, prompt: str, system_prompt: str = None,
                    provider: str = None) -> RemoteAIResponse:
        """Send AI query to remote backend."""
        await self._ensure_client()
        start = time.time()

        try:
            response = await self._client.post(
                f"{self.backend_url}/api/ai/query",
                json={
                    "prompt": prompt,
                    "system_prompt": system_prompt or "",
                    "provider": provider or "",
                },
            )
            response.raise_for_status()
            data = response.json()
            latency = (time.time() - start) * 1000

            self._request_count += 1
            self._total_latency += latency

            return RemoteAIResponse(
                content=data.get("content", ""),
                provider=data.get("provider", "remote"),
                model=data.get("model", "backend"),
                tokens_used=data.get("tokens_used", 0),
                latency_ms=latency,
            )
        except httpx.HTTPStatusError as e:
            logger.error(f"Backend AI error: {e.response.status_code}")
            return RemoteAIResponse(content=f"Backend error: {e.response.status_code}")
        except Exception as e:
            logger.error(f"Remote AI connection error: {e}")
            return RemoteAIResponse(content=f"Connection error: {e}")

    async def plan_attack(self, target: str) -> dict:
        """Get AI attack plan from remote backend."""
        await self._ensure_client()
        try:
            response = await self._client.post(
                f"{self.backend_url}/api/ai/plan",
                json={"target": target, "options": {"target": target}},
            )
            response.raise_for_status()
            return response.json().get("attack_plan", {})
        except Exception as e:
            logger.error(f"Remote plan error: {e}")
            return {"error": str(e)}

    def get_status(self) -> dict:
        """Get remote status info."""
        return {
            "remote": {
                "active": True,
                "model": "backend-proxy",
                "requests_today": self._request_count,
                "daily_limit": 999999,
                "blocked": False,
                "backend_url": self.backend_url,
            }
        }

    async def close(self):
        if self._client:
            await self._client.aclose()
            self._client = None
