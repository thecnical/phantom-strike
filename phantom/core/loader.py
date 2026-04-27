"""
PhantomStrike Module Loader — Dynamically discovers and registers all modules.
This is what wires everything together for REAL working execution.
"""
from __future__ import annotations
import logging
from typing import Optional

from phantom.core.events import EventBus
from phantom.modules.base import BaseModule

logger = logging.getLogger("phantom.loader")


async def load_all_modules(event_bus: EventBus) -> dict[str, BaseModule]:
    """
    Load and initialize all offensive modules.
    Returns a dict of module_name -> module_instance.
    """
    modules: dict[str, BaseModule] = {}

    # Import all module engines
    module_classes = []

    try:
        from phantom.modules.osint.engine import OSINTEngine
        module_classes.append(OSINTEngine)
    except ImportError as e:
        logger.warning(f"Could not load OSINT module: {e}")

    try:
        from phantom.modules.network.engine import NetworkEngine
        module_classes.append(NetworkEngine)
    except ImportError as e:
        logger.warning(f"Could not load Network module: {e}")

    try:
        from phantom.modules.web.engine import WebEngine
        module_classes.append(WebEngine)
    except ImportError as e:
        logger.warning(f"Could not load Web module: {e}")

    try:
        from phantom.modules.cloud.engine import CloudEngine
        module_classes.append(CloudEngine)
    except ImportError as e:
        logger.warning(f"Could not load Cloud module: {e}")

    try:
        from phantom.modules.cred.engine import CredEngine
        module_classes.append(CredEngine)
    except ImportError as e:
        logger.warning(f"Could not load Cred module: {e}")

    try:
        from phantom.modules.identity.engine import IdentityEngine
        module_classes.append(IdentityEngine)
    except ImportError as e:
        logger.warning(f"Could not load Identity module: {e}")

    try:
        from phantom.modules.stealth.engine import StealthEngine
        module_classes.append(StealthEngine)
    except ImportError as e:
        logger.warning(f"Could not load Stealth module: {e}")

    try:
        from phantom.modules.exploit.engine import ExploitEngine
        module_classes.append(ExploitEngine)
    except ImportError as e:
        logger.warning(f"Could not load Exploit module: {e}")

    try:
        from phantom.modules.c2.engine import C2Engine
        module_classes.append(C2Engine)
    except ImportError as e:
        logger.warning(f"Could not load C2 module: {e}")

    try:
        from phantom.modules.post.engine import PostExploitEngine
        module_classes.append(PostExploitEngine)
    except ImportError as e:
        logger.warning(f"Could not load Post-Exploit module: {e}")

    try:
        from phantom.modules.report.engine import ReportEngine
        module_classes.append(ReportEngine)
    except ImportError as e:
        logger.warning(f"Could not load Report module: {e}")

    # Instantiate and initialize all modules
    for ModuleClass in module_classes:
        try:
            module = ModuleClass(event_bus=event_bus)
            await module.initialize()
            modules[module.name] = module
            logger.info(f"[Loader] ✅ {module.name} loaded ({module.category})")
        except Exception as e:
            logger.error(f"[Loader] ❌ Failed to init {ModuleClass.__name__}: {e}")

    logger.info(f"[Loader] {len(modules)}/{len(module_classes)} modules loaded successfully")
    return modules
