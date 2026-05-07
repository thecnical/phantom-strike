"""
PhantomStrike Remote AI Client
Routes ALL AI calls through the deployed Render backend.
Users need ZERO local API keys — backend has everything configured.

Flow: User CLI → HTTPS → Render Backend → AI Providers → Response
"""
from __future__ import annotations
import logging
import time
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List

import httpx

logger = logging.getLogger("phantom.ai.remote")


@dataclass
class AIResponse:
    """Standardized AI response — same interface as EnhancedPhantomAIEngine."""
    content: str = ""
    provider: str = "remote-backend"
    model: str = "backend"
    tokens_used: int = 0
    latency_ms: float = 0.0
    cached: bool = False
    raw_response: Dict = field(default_factory=dict)


# Alias for backwards compatibility
RemoteAIResponse = AIResponse


class RemoteAIClient:
    """
    Drop-in replacement for EnhancedPhantomAIEngine.
    Routes all AI requests through the Render backend.
    Same interface — swap transparently.
    """

    def __init__(self, backend_url: str, timeout: int = 120):
        self.backend_url = backend_url.rstrip("/")
        self.timeout = timeout
        self._client: Optional[httpx.AsyncClient] = None
        self._request_count = 0
        self._total_latency = 0.0
        self._initialized = False

    async def _ensure_client(self):
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(self.timeout),
                headers={
                    "User-Agent": "PhantomStrike-CLI/2.0",
                    "Content-Type": "application/json",
                },
                follow_redirects=True,
            )

    async def initialize(self) -> List[str]:
        """Initialize — verify backend is reachable."""
        await self._ensure_client()
        try:
            resp = await self._client.get(f"{self.backend_url}/health", timeout=10)
            if resp.status_code == 200:
                self._initialized = True
                logger.debug(f"[RemoteAI] Backend reachable: {self.backend_url}")
                return ["remote-backend"]
            else:
                logger.warning(f"[RemoteAI] Backend returned {resp.status_code}")
                return []
        except Exception as e:
            logger.warning(f"[RemoteAI] Backend unreachable: {e}")
            # Still mark as initialized — will try on each query
            self._initialized = True
            return ["remote-backend"]

    async def query(
        self,
        prompt: str,
        system_prompt: str = "",
        temperature: float = 0.7,
        max_tokens: int = 4096,
        force_provider: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,  # accepted but unused — backend handles context
        messages: Optional[List[Dict]] = None,      # accepted for chat-style calls
    ) -> AIResponse:
        """Send AI query to remote backend."""
        await self._ensure_client()
        start = time.time()

        try:
            response = await self._client.post(
                f"{self.backend_url}/api/ai/query",
                json={
                    "prompt": prompt,
                    "system_prompt": system_prompt or "",
                    "provider": force_provider or "",
                },
            )
            response.raise_for_status()
            data = response.json()
            latency = (time.time() - start) * 1000
            self._request_count += 1
            self._total_latency += latency

            return AIResponse(
                content=data.get("content", "No response from backend"),
                provider=data.get("provider", "remote-backend"),
                model=data.get("model", "backend"),
                tokens_used=data.get("tokens_used", 0),
                latency_ms=latency,
            )

        except httpx.HTTPStatusError as e:
            logger.error(f"[RemoteAI] HTTP error {e.response.status_code}")
            return AIResponse(
                content=f"Backend error {e.response.status_code}. Check {self.backend_url}/health",
                provider="error",
                model="error",
            )
        except httpx.ConnectError:
            return AIResponse(
                content=f"Cannot connect to backend at {self.backend_url}. Is Render deployed?",
                provider="error",
                model="error",
            )
        except Exception as e:
            logger.error(f"[RemoteAI] Query error: {e}")
            return AIResponse(
                content=f"Remote AI error: {e}",
                provider="error",
                model="error",
            )

    async def chat(self, messages: List[Dict]) -> str:
        """
        Chat-style interface: accepts a list of {role, content} dicts.
        Extracts the last user message as the prompt and any system message
        as the system_prompt, then routes through query().
        Returns the response content string directly.
        """
        prompt = ""
        system_prompt = ""
        for msg in messages:
            role = msg.get("role", "")
            content = msg.get("content", "")
            if role == "system":
                system_prompt = content
            elif role == "user":
                prompt = content  # last user message wins

        if not prompt:
            return ""

        response = await self.query(prompt=prompt, system_prompt=system_prompt)
        return response.content

    async def analyze_vulnerability(self, vuln_data: Dict) -> AIResponse:
        """AI vulnerability analysis via backend."""
        prompt = (
            f"Analyze this vulnerability for exploitation:\n"
            f"Type: {vuln_data.get('type', 'Unknown')}\n"
            f"URL: {vuln_data.get('url', 'N/A')}\n"
            f"Parameter: {vuln_data.get('parameter', 'N/A')}\n"
            f"Payload: {vuln_data.get('payload', 'N/A')}\n"
            f"Evidence: {vuln_data.get('evidence', 'N/A')}\n\n"
            f"Provide: 1) Severity 2) Exploit steps 3) MITRE ATT&CK ID 4) Remediation"
        )
        system = (
            "You are PhantomStrike AI — elite offensive security analyst. "
            "Provide technical, actionable vulnerability analysis."
        )
        return await self.query(prompt, system_prompt=system, temperature=0.8)

    async def plan_attack_chain(self, recon_data: Dict) -> AIResponse:
        """AI attack chain planning via backend."""
        import json
        prompt = (
            f"Design a complete attack chain from this recon data:\n"
            f"{json.dumps(recon_data, indent=2, default=str)[:2000]}\n\n"
            f"Include: entry point, exploitation steps, privilege escalation, persistence."
        )
        system = (
            "You are PhantomStrike AI Attack Planner. "
            "Design realistic multi-step attack chains with specific commands."
        )
        return await self.query(prompt, system_prompt=system, temperature=0.9)

    async def generate_evasive_payload(self, target_info: Dict) -> AIResponse:
        """Generate evasive payloads via backend."""
        import json
        prompt = (
            f"Generate 5 polymorphic WAF-evading payloads for:\n"
            f"{json.dumps(target_info, indent=2, default=str)}"
        )
        system = (
            "You are PhantomStrike Payload Engineer. "
            "Generate polymorphic, WAF-evading payloads with encoding bypass."
        )
        return await self.query(prompt, system_prompt=system, temperature=0.85)

    def get_status(self) -> Dict[str, Any]:
        """Get status — shows as active since backend handles everything."""
        return {
            "remote-backend": {
                "name": "Render Backend",
                "active": True,
                "api_key_set": True,
                "model": "multi-provider (Groq/Gemini/OpenRouter)",
                "requests_today": self._request_count,
                "daily_limit": 999999,
                "blocked": False,
                "failures": 0,
                "backend_url": self.backend_url,
            }
        }

    async def shutdown(self):
        """Cleanup HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None

    async def close(self):
        """Alias for shutdown."""
        await self.shutdown()
