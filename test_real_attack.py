#!/usr/bin/env python3
"""
PhantomStrike REAL Attack Test
Verifies the enhanced engine works against real targets.
Run: python test_real_attack.py [target]
"""
import asyncio
import sys
import json
from datetime import datetime

# Test targets
TEST_TARGETS = [
    "jio.com",
    "httpbin.org",
    "example.com",
]

async def test_osint_module(engine, target):
    """Test OSINT module."""
    print(f"\n🔍 Testing OSINT on {target}...")
    result = await engine.execute_module("phantom-osint", target)
    
    if result.get("success"):
        data = result.get("data", {})
        subdomains = len(data.get("subdomains", []))
        emails = len(data.get("emails", []))
        tech = len(data.get("technologies", []))
        print(f"  ✓ Found: {subdomains} subdomains, {emails} emails, {tech} technologies")
        return True
    else:
        print(f"  ✗ Failed: {result.get('error')}")
        return False


async def test_network_module(engine, target):
    """Test Network scanner."""
    print(f"\n🌐 Testing Network scan on {target}...")
    result = await engine.execute_module("phantom-network", target)
    
    if result.get("success"):
        data = result.get("data", {})
        ports = len(data.get("open_ports", []))
        print(f"  ✓ Found: {ports} open ports")
        for port in data.get("open_ports", [])[:5]:
            print(f"    - Port {port['port']}: {port['service']}")
        return True
    else:
        print(f"  ✗ Failed: {result.get('error')}")
        return False


async def test_web_module(engine, target):
    """Test Web vulnerability scanner."""
    print(f"\n🕷️ Testing Web scan on {target}...")
    
    # Make sure target has protocol
    if not target.startswith(("http://", "https://")):
        target = f"https://{target}"
    
    result = await engine.execute_module("phantom-web", target)
    
    if result.get("success"):
        data = result.get("data", {})
        sqli = len(data.get("sqli", []))
        xss = len(data.get("xss", []))
        lfi = len(data.get("lfi", []))
        blind_sqli = len(data.get("blind_sqli", []))
        stored_xss = len(data.get("stored_xss", []))
        
        print(f"  ✓ Found: {sqli} SQLi, {blind_sqli} Blind SQLi, {xss} XSS, {stored_xss} Stored XSS, {lfi} LFI")
        
        # Print found vulnerabilities
        for vuln in data.get("sqli", []):
            print(f"    🔴 SQLi: {vuln.get('url', 'N/A')[:80]}")
        for vuln in data.get("blind_sqli", []):
            print(f"    🔴 Blind SQLi: {vuln.get('url', 'N/A')[:80]}")
        
        return True
    else:
        print(f"  ✗ Failed: {result.get('error')}")
        return False


async def test_cloud_module(engine, target):
    """Test Cloud scanner."""
    print(f"\n☁️ Testing Cloud scan on {target}...")
    result = await engine.execute_module("phantom-cloud", target)
    
    if result.get("success"):
        data = result.get("data", {})
        s3 = len(data.get("s3_buckets", []))
        azure = len(data.get("azure_blobs", []))
        gcp = len(data.get("gcp_buckets", []))
        
        print(f"  ✓ Found: {s3} S3 buckets, {azure} Azure blobs, {gcp} GCP buckets")
        
        for bucket in data.get("s3_buckets", []):
            print(f"    🔴 S3: {bucket.get('bucket')} ({bucket.get('status')})")
        
        return True
    else:
        print(f"  ✗ Failed: {result.get('error')}")
        return False


async def test_ai_engine(engine):
    """Test AI engine."""
    print(f"\n🧠 Testing AI Engine...")
    
    if not engine.ai_engine:
        print("  ✗ AI Engine not available")
        return False
    
    try:
        status = engine.ai_engine.get_status()
        active_providers = [p for p, s in status.items() if s.get("active")]
        
        print(f"  ✓ AI Engine: {len(active_providers)} providers configured")
        
        for pid, pstatus in status.items():
            print(f"    - {pstatus['name']}: {'✓ Active' if pstatus['active'] else '✗ No API key'}")
        
        if active_providers:
            # Test a simple query
            response = await engine.ai_engine.query(
                "Generate a SQL injection payload for MySQL",
                temperature=0.7
            )
            print(f"  ✓ AI Response from {response.provider}: {response.content[:100]}...")
            return True
        else:
            print("  ⚠ No active AI providers. Set GROQ_API_KEY environment variable.")
            return False
            
    except Exception as e:
        print(f"  ✗ AI test failed: {e}")
        return False


async def test_full_kill_chain(engine, target):
    """Test full kill chain."""
    print(f"\n🔥 Testing FULL KILL CHAIN on {target}...")
    print("  This will run all phases: Recon → Vuln → AI Plan → Payload → Exploit → Post → Report")
    
    try:
        results = await engine.execute_full_chain(target)
        
        # Count findings
        critical = 0
        high = 0
        total = 0
        
        for module_name, module_results in results.items():
            if isinstance(module_results, dict):
                data = module_results.get("data", module_results)
                for key in ["sqli", "xss", "lfi", "ssrf", "rce", "blind_sqli", "stored_xss", "s3_buckets"]:
                    if key in data and isinstance(data[key], list):
                        for vuln in data[key]:
                            total += 1
                            if isinstance(vuln, dict):
                                if vuln.get("severity") == "critical":
                                    critical += 1
                                elif vuln.get("severity") == "high":
                                    high += 1
        
        print(f"\n  ✅ Kill chain complete!")
        print(f"     Critical: {critical}")
        print(f"     High: {high}")
        print(f"     Total findings: {total}")
        
        # Check for report
        if "report" in results:
            report = results["report"]
            print(f"\n     Report generated:")
            print(f"       HTML: {report.get('html_path', 'N/A')}")
            print(f"       JSON: {report.get('json_path', 'N/A')}")
        
        return True
        
    except Exception as e:
        print(f"  ✗ Kill chain failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """Main test function."""
    print("=" * 70)
    print("🔥 PHANTOMSTRIKE REAL ATTACK TEST")
    print("=" * 70)
    print(f"Time: {datetime.now().isoformat()}")
    print()
    
    # Get target from command line
    target = sys.argv[1] if len(sys.argv) > 1 else "jio.com"
    print(f"Target: {target}")
    print()
    
    # Initialize engine
    print("⚡ Initializing Enhanced PhantomStrike Engine...")
    
    try:
        from phantom.core.enhanced_engine import EnhancedPhantomEngine
        from phantom.core.config import load_config
        
        config = load_config()
        engine = EnhancedPhantomEngine(config)
        await engine.start()
        
    except Exception as e:
        print(f"✗ Failed to initialize engine: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    print("✓ Engine started successfully!")
    print()
    
    # Run tests
    results = {
        "osint": False,
        "network": False,
        "web": False,
        "cloud": False,
        "ai": False,
        "kill_chain": False,
    }
    
    # Test 1: OSINT
    try:
        results["osint"] = await test_osint_module(engine, target)
    except Exception as e:
        print(f"OSINT test error: {e}")
    
    # Test 2: Network
    try:
        results["network"] = await test_network_module(engine, target)
    except Exception as e:
        print(f"Network test error: {e}")
    
    # Test 3: Web
    try:
        results["web"] = await test_web_module(engine, target)
    except Exception as e:
        print(f"Web test error: {e}")
    
    # Test 4: Cloud
    try:
        results["cloud"] = await test_cloud_module(engine, target)
    except Exception as e:
        print(f"Cloud test error: {e}")
    
    # Test 5: AI
    try:
        results["ai"] = await test_ai_engine(engine)
    except Exception as e:
        print(f"AI test error: {e}")
    
    # Test 6: Full Kill Chain (only if basic tests passed)
    if results["osint"] or results["web"]:
        try:
            results["kill_chain"] = await test_full_kill_chain(engine, target)
        except Exception as e:
            print(f"Kill chain test error: {e}")
    else:
        print("\n⚠ Skipping kill chain test (basic tests failed)")
    
    # Shutdown
    print("\n" + "=" * 70)
    print("Shutting down...")
    await engine.stop()
    
    # Print summary
    print("\n" + "=" * 70)
    print("📊 TEST SUMMARY")
    print("=" * 70)
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    for test_name, passed_test in results.items():
        status = "✓ PASS" if passed_test else "✗ FAIL"
        print(f"  {status}: {test_name}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 All tests passed! PhantomStrike is fully operational.")
        return 0
    elif passed >= total / 2:
        print(f"\n⚠ {total - passed} tests failed. Core functionality available.")
        return 0
    else:
        print(f"\n✗ Most tests failed. Check configuration and dependencies.")
        return 1


if __name__ == "__main__":
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user.")
        sys.exit(130)
    except Exception as e:
        print(f"\n\nFatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
