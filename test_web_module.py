#!/usr/bin/env python3
"""Test Web Module with Playwright on real target."""

import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from phantom.modules.web.enhanced_engine import EnhancedWebEngine
from phantom.core.config import load_config


async def test_web_module():
    """Test web scanning against httpbin.org (safe target)."""
    print("=" * 70)
    print("🔥 PHANTOMSTRIKE WEB MODULE TEST")
    print("=" * 70)
    
    # Load config
    config = load_config()
    
    # Create engine
    print("\n📦 Initializing EnhancedWebEngine...")
    engine = EnhancedWebEngine(config)
    
    # Test target (safe - httpbin.org is a testing service)
    target = "https://httpbin.org"
    
    print(f"\n🎯 Target: {target}")
    print("🚀 Starting web scan...")
    print("-" * 70)
    
    try:
        # Run scan
        result = await engine.run(target)
        
        # Analyze results
        print("\n✅ SCAN COMPLETE!")
        print("=" * 70)
        
        # Display findings
        vulnerabilities = result.get("vulnerabilities", [])
        
        if vulnerabilities:
            print(f"\n🚨 VULNERABILITIES FOUND: {len(vulnerabilities)}")
            for i, vuln in enumerate(vulnerabilities[:5], 1):  # Show first 5
                print(f"\n  {i}. {vuln.get('type', 'Unknown').upper()}")
                print(f"     Severity: {vuln.get('severity', 'unknown')}")
                print(f"     URL: {vuln.get('url', 'N/A')[:60]}...")
        else:
            print("\n✓ No critical vulnerabilities detected")
        
        # Show scan metadata
        print(f"\n📊 Scan Results:")
        print(f"   Status: {result.get('status', 'unknown')}")
        print(f"   Duration: {result.get('duration', 0):.2f} seconds")
        print(f"   Findings: {result.get('findings_count', 0)}")
        
        # Show crawled pages
        crawled = result.get("crawled_urls", [])
        print(f"\n🕷️  Crawled URLs ({len(crawled)}):")
        for url in crawled[:5]:  # Show first 5
            print(f"   - {url}")
        
        # Show forms found
        forms = result.get("forms_found", [])
        print(f"\n📝 Forms Found: {len(forms)}")
        
        # Show API endpoints
        apis = result.get("api_endpoints", [])
        print(f"\n🔌 API Endpoints: {len(apis)}")
        for api in apis[:5]:
            print(f"   - {api.get('method', 'GET')} {api.get('endpoint', 'N/A')}")
        
        # Check Playwright usage
        print("\n" + "=" * 70)
        print("🎭 PLAYWRIGHT STATUS:")
        print("=" * 70)
        
        browser_used = result.get("browser_used", False)
        js_executed = result.get("js_scripts_executed", 0)
        
        if browser_used or js_executed > 0:
            print(f"   ✅ Playwright Browser: ACTIVE")
            print(f"   ✅ JavaScript Executed: {js_executed} scripts")
        else:
            print(f"   ⚠️  Playwright: Limited usage (target may not need JS)")
        
        print("\n" + "=" * 70)
        print("✅ WEB MODULE TEST COMPLETE!")
        print("=" * 70)
        
        return result
        
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return None


if __name__ == "__main__":
    result = asyncio.run(test_web_module())
    sys.exit(0 if result else 1)
