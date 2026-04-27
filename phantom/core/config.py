"""
PhantomStrike Core Configuration System
Manages all settings: AI providers, modules, threading, attack profiles.
"""
from __future__ import annotations
import os
from enum import Enum
from pathlib import Path
from typing import Optional
import yaml
from pydantic import BaseModel, Field, field_validator
from pydantic_settings import BaseSettings


class AIProviderType(str, Enum):
    GROQ = "groq"              # 🥇 FASTEST — 500+ tokens/sec, LPU hardware
    OPENROUTER = "openrouter"  # 🥈 Auto-routes to best free model
    GEMINI = "gemini"          # 🥉 Most generous free tier
    CEREBRAS = "cerebras"      # Ultra-fast inference
    MISTRAL = "mistral"        # 1B tokens/month FREE
    TOGETHER = "together"      # Open-source model variety
    HUGGINGFACE = "huggingface" # Thousands of models
    NVIDIA_NIM = "nvidia_nim"  # GPU-optimized
    SAMBANOVA = "sambanova"    # Custom hardware speed
    OLLAMA = "ollama"          # Optional local fallback


class AIProviderConfig(BaseModel):
    provider_type: AIProviderType
    api_key: str = ""
    base_url: str = ""
    model: str = ""
    max_tokens: int = 4096
    temperature: float = 0.3
    enabled: bool = True
    priority: int = 0
    rate_limit_rpm: int = 20
    rate_limit_daily: int = 200
    timeout: int = 60

    @field_validator("api_key", mode="before")
    @classmethod
    def resolve_env_var(cls, v: str) -> str:
        if isinstance(v, str) and v.startswith("${") and v.endswith("}"):
            return os.environ.get(v[2:-1], "")
        return v


DEFAULT_AI_PROVIDERS: dict[AIProviderType, AIProviderConfig] = {
    # 🥇 GROQ — World's fastest AI inference (LPU hardware, 500+ tokens/sec)
    # FREE: No credit card required. Sign up: https://console.groq.com
    AIProviderType.GROQ: AIProviderConfig(
        provider_type=AIProviderType.GROQ,
        api_key="${GROQ_API_KEY}",
        base_url="https://api.groq.com/openai/v1",
        model="llama-3.3-70b-versatile",
        priority=0,  # HIGHEST PRIORITY — fastest in the world
        rate_limit_rpm=30, rate_limit_daily=1000,
        max_tokens=8192,
    ),
    AIProviderType.OPENROUTER: AIProviderConfig(
        provider_type=AIProviderType.OPENROUTER,
        api_key="${OPENROUTER_API_KEY}",
        base_url="https://openrouter.ai/api/v1",
        # Upgraded to best OpenRouter Free models!
        # Other great free options: 'deepseek/deepseek-r1:free', 'meta-llama/llama-3.3-70b-instruct:free', 'qwen/qwen-2.5-coder-32b-instruct:free'
        model="google/gemini-2.5-pro:free", 
        priority=1, rate_limit_rpm=20, rate_limit_daily=200,
    ),
    AIProviderType.GEMINI: AIProviderConfig(
        provider_type=AIProviderType.GEMINI,
        api_key="${GEMINI_API_KEY}",
        base_url="https://generativelanguage.googleapis.com/v1beta",
        model="gemini-2.5-flash",
        priority=2, rate_limit_rpm=60, rate_limit_daily=1500,
    ),
    AIProviderType.CEREBRAS: AIProviderConfig(
        provider_type=AIProviderType.CEREBRAS,
        api_key="${CEREBRAS_API_KEY}",
        base_url="https://api.cerebras.ai/v1",
        model="llama3.3-70b",
        priority=3, rate_limit_rpm=30, rate_limit_daily=500,
    ),
    AIProviderType.MISTRAL: AIProviderConfig(
        provider_type=AIProviderType.MISTRAL,
        api_key="${MISTRAL_API_KEY}",
        base_url="https://api.mistral.ai/v1",
        model="mistral-large-latest",
        priority=4, rate_limit_rpm=2, rate_limit_daily=1000,
    ),
    AIProviderType.TOGETHER: AIProviderConfig(
        provider_type=AIProviderType.TOGETHER,
        api_key="${TOGETHER_API_KEY}",
        base_url="https://api.together.xyz/v1",
        model="meta-llama/Llama-3.3-70B-Instruct-Turbo-Free",
        priority=5, rate_limit_rpm=20, rate_limit_daily=200,
    ),
    AIProviderType.HUGGINGFACE: AIProviderConfig(
        provider_type=AIProviderType.HUGGINGFACE,
        api_key="${HUGGINGFACE_API_KEY}",
        base_url="https://api-inference.huggingface.co/v1",
        model="meta-llama/Llama-3.3-70B-Instruct",
        priority=6, rate_limit_rpm=10, rate_limit_daily=100,
    ),
    AIProviderType.NVIDIA_NIM: AIProviderConfig(
        provider_type=AIProviderType.NVIDIA_NIM,
        api_key="${NVIDIA_API_KEY}",
        base_url="https://integrate.api.nvidia.com/v1",
        model="nvidia/nemotron-4-340b-instruct",
        priority=7, rate_limit_rpm=10, rate_limit_daily=100,
    ),
    AIProviderType.SAMBANOVA: AIProviderConfig(
        provider_type=AIProviderType.SAMBANOVA,
        api_key="${SAMBANOVA_API_KEY}",
        base_url="https://api.sambanova.ai/v1",
        model="Meta-Llama-3.1-405B-Instruct",
        priority=8, rate_limit_rpm=10, rate_limit_daily=50,
    ),
}


class ThreadingConfig(BaseModel):
    max_scan_threads: int = Field(default=100, ge=1, le=500)
    max_exploit_threads: int = Field(default=20, ge=1, le=100)
    max_brute_threads: int = Field(default=50, ge=1, le=200)
    max_osint_threads: int = Field(default=30, ge=1, le=100)
    max_web_threads: int = Field(default=40, ge=1, le=150)
    max_ai_threads: int = Field(default=5, ge=1, le=20)
    max_workers: int = Field(default=10, ge=1, le=100)
    use_uvloop: bool = True
    event_loop_workers: int = Field(default=4, ge=1, le=32)
    connection_pool_size: int = Field(default=200, ge=10, le=1000)
    connect_timeout: float = 10.0
    read_timeout: float = 30.0
    requests_per_second: int = Field(default=50, ge=1, le=1000)


class PlaywrightConfig(BaseModel):
    enabled: bool = True
    browser_type: str = "chromium"
    headless: bool = True
    timeout: int = 30000
    stealth_mode: bool = True
    max_browser_instances: int = 5
    screenshot_on_vuln: bool = True
    intercept_requests: bool = True
    capture_cookies: bool = True
    capture_storage: bool = True
    ignore_https_errors: bool = True


class AttackProfile(str, Enum):
    STEALTH = "stealth"
    NORMAL = "normal"
    AGGRESSIVE = "aggressive"
    CHAOS = "chaos"


class AttackConfig(BaseModel):
    profile: AttackProfile = AttackProfile.NORMAL
    auto_exploit: bool = False
    auto_chain: bool = True
    mitre_mapping: bool = True
    evidence_collection: bool = True
    safe_mode: bool = True
    scope_enforcement: bool = True
    max_depth: int = 5
    target_domains: list[str] = []
    excluded_domains: list[str] = []


class PhantomStrikeConfig(BaseSettings):
    project_name: str = "PhantomStrike"
    version: str = "1.0.0-alpha"
    data_dir: Path = Path.home() / ".phantom-strike"
    log_level: str = "INFO"

    # ── Backend Connection (Users connect to creator's deployed API) ──
    # Hardcoded to True so users don't need any API keys or --backend flags!
    backend_url: str = "https://phantom-strike.onrender.com"  
    backend_enabled: bool = True  # True = AI calls ALWAYS go through backend by default

    # ── AI Providers (Only needed on backend/creator side) ──
    ai_providers: dict[str, AIProviderConfig] = {}
    ai_primary_provider: AIProviderType = AIProviderType.GROQ
    ai_fallback_enabled: bool = True
    ai_cache_responses: bool = False

    threading: ThreadingConfig = ThreadingConfig()
    playwright: PlaywrightConfig = PlaywrightConfig()
    attack: AttackConfig = AttackConfig()
    modules: dict[str, dict] = {}
    report_format: str = "html"
    proxy: Optional[str] = None
    tor_enabled: bool = False

    class Config:
        env_prefix = "PHANTOM_"
        env_file = ".env"
        env_file_encoding = "utf-8"

    def model_post_init(self, __context) -> None:
        if not self.ai_providers:
            for ptype, pconfig in DEFAULT_AI_PROVIDERS.items():
                self.ai_providers[ptype.value] = pconfig
        self.data_dir.mkdir(parents=True, exist_ok=True)


def load_config(config_path: Optional[Path] = None) -> PhantomStrikeConfig:
    config_data = {}
    if config_path and config_path.exists():
        with open(config_path, "r") as f:
            config_data = yaml.safe_load(f) or {}
    else:
        for p in [Path.cwd() / "phantom.yaml", Path.home() / ".phantom-strike" / "config.yaml"]:
            if p.exists():
                with open(p, "r") as f:
                    config_data = yaml.safe_load(f) or {}
                break
    return PhantomStrikeConfig(**config_data)
