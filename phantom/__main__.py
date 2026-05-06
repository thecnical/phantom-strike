"""
PhantomStrike — Main Entry Point.
Run as CLI or API server.

Auto-activates venv if not already active, so 'phantom' command
works after system restart without manually sourcing the venv.
"""
import sys
import os
import asyncio


def _ensure_venv():
    """
    Auto-activate the PhantomStrike venv if not already inside one.
    This makes 'phantom' work after system restart without manual venv activation.
    """
    # Already inside a venv — nothing to do
    if os.environ.get("VIRTUAL_ENV"):
        return

    # Find the venv
    venv_dir = os.path.join(os.path.expanduser("~"), ".phantom-strike", "venv")
    if not os.path.isdir(venv_dir):
        return  # No venv found — proceed anyway (pipx install or system-wide)

    # Re-exec with the venv's Python if we're not already using it
    venv_python = os.path.join(venv_dir, "bin", "python")
    if not os.path.isfile(venv_python):
        venv_python = os.path.join(venv_dir, "bin", "python3")
    if not os.path.isfile(venv_python):
        return  # No venv python found

    # If current interpreter is not the venv python, re-exec with it
    if os.path.realpath(sys.executable) != os.path.realpath(venv_python):
        # Set VIRTUAL_ENV so the re-exec doesn't loop
        env = os.environ.copy()
        env["VIRTUAL_ENV"] = venv_dir
        env["PATH"] = os.path.join(venv_dir, "bin") + os.pathsep + env.get("PATH", "")
        env.pop("PYTHONHOME", None)
        try:
            os.execve(venv_python, [venv_python, "-m", "phantom"] + sys.argv[1:], env)
        except OSError:
            pass  # execve failed — continue with current interpreter


def main():
    """Entry point for PhantomStrike."""
    # Auto-activate venv so 'phantom' works after system restart
    _ensure_venv()

    # Check Python version
    if sys.version_info < (3, 10):
        print(f"ERROR: Python 3.10+ required. You have {sys.version}")
        sys.exit(1)

    # Check if running as API server
    if len(sys.argv) > 1 and sys.argv[1] == "serve":
        _run_api_server()
    else:
        _run_cli()


def _auto_update():
    """Silently check and pull updates from GitHub before starting."""
    import subprocess
    try:
        result = subprocess.run(
            ["git", "pull", "--rebase", "--autostash"],
            capture_output=True,
            text=True,
            timeout=5,
            cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        )
        if "Updating" in result.stdout:
            print("\n[+] PhantomStrike auto-updated to latest version! 🔥\n")
    except Exception:
        pass


def _run_cli():
    """Run the interactive CLI."""
    _auto_update()

    from phantom.cli.app import PhantomStrikeCLI

    # Extract --backend URL from args if present
    args = sys.argv[1:]
    backend_url = None
    for i, arg in enumerate(args):
        if arg == "--backend" and i + 1 < len(args):
            backend_url = args[i + 1]
            break

    cli = PhantomStrikeCLI()

    try:
        # Use uvloop on Linux for max speed
        try:
            import uvloop
            uvloop.install()
        except ImportError:
            pass

        asyncio.run(cli.run(backend_url))
    except (KeyboardInterrupt, SystemExit):
        print("\nPhantomStrike terminated.")
        sys.exit(0)
    except Exception as e:
        print(f"Fatal error: {e}")
        sys.exit(1)


def _run_api_server():
    """Run the enhanced FastAPI backend server with dashboard."""
    import uvicorn

    try:
        from phantom.api.enhanced_server import app
        enhanced = True
    except Exception as e:
        print(f"⚠ Could not load enhanced server: {e}")
        try:
            from phantom.api.server import app
        except Exception:
            print("ERROR: No API server available.")
            sys.exit(1)
        enhanced = False

    host = "0.0.0.0"
    port = int(sys.argv[2]) if len(sys.argv) > 2 else 10000

    print(f"\n🔥 PhantomStrike {'Enhanced ' if enhanced else ''}API Server")
    print(f"   Dashboard : http://localhost:{port}/")
    print(f"   API Docs  : http://localhost:{port}/docs")
    print(f"   Health    : http://localhost:{port}/health")
    print(f"   WebSocket : ws://localhost:{port}/ws")
    print()

    uvicorn.run(
        "phantom.api.enhanced_server:app" if enhanced else "phantom.api.server:app",
        host=host,
        port=port,
        reload=False,
        workers=1,
        log_level="warning",  # Suppress uvicorn INFO spam
    )


if __name__ == "__main__":
    main()
