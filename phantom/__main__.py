"""
PhantomStrike — Main Entry Point.
Run as CLI or API server.
"""
import sys
import asyncio


def main():
    """Entry point for PhantomStrike."""
    # Check Python version
    if sys.version_info < (3, 12):
        print(f"ERROR: Python 3.12+ required. You have {sys.version}")
        sys.exit(1)

    # Check if running as API server
    if len(sys.argv) > 1 and sys.argv[1] == "serve":
        _run_api_server()
    else:
        _run_cli()


def _run_cli():
    """Run the interactive CLI."""
    from phantom.cli.app import PhantomStrikeCLI
    
    # Extract backend URL from args if present
    import sys
    args = sys.argv[1:]
    backend_url = None
    i = 0
    while i < len(args):
        if args[i] == "--backend" and i + 1 < len(args):
            backend_url = args[i + 1]
            break
        i += 1
        
    cli = PhantomStrikeCLI()

    try:
        # Use uvloop on Linux for max speed
        try:
            import uvloop
            uvloop.install()
        except ImportError:
            pass

        asyncio.run(cli.run(backend_url))
    except KeyboardInterrupt:
        print("\nPhantomStrike terminated.")
    except Exception as e:
        print(f"Fatal error: {e}")
        sys.exit(1)


def _run_api_server():
    """Run the FastAPI backend server."""
    import uvicorn
    from phantom.api.server import app

    host = "0.0.0.0"
    port = int(sys.argv[2]) if len(sys.argv) > 2 else 10000

    print(f"\n🔥 PhantomStrike API Server starting on {host}:{port}")
    print(f"   Docs: http://localhost:{port}/docs")
    print(f"   Health: http://localhost:{port}/health\n")

    uvicorn.run(
        "phantom.api.server:app",
        host=host,
        port=port,
        reload=False,
        workers=1,
        log_level="info",
    )


if __name__ == "__main__":
    main()
