"""
PhantomStrike Agents package.

Exports BaseAgent, AgentResult, all 13 specialist agents, and PhantomOrchestrator.

Requirements: 9.1
"""

from phantom.agents.base_agent import AgentResult, BaseAgent
from phantom.agents.orchestrator import PhantomOrchestrator

# 13 specialist agents
from phantom.agents.recon_agent import ReconAgent
from phantom.agents.scanner_agent import ScannerAgent
from phantom.agents.web_exploit_agent import WebExploitAgent
from phantom.agents.cloud_agent import CloudAgent
from phantom.agents.cred_agent import CredAgent
from phantom.agents.ad_agent import ADAgent
from phantom.agents.exploit_agent import ExploitAgent
from phantom.agents.post_exploit_agent import PostExploitAgent
from phantom.agents.c2_agent import C2Agent
from phantom.agents.stealth_agent import StealthAgent
from phantom.agents.reverser_agent import ReverserAgent
from phantom.agents.analyst_agent import AnalystAgent
from phantom.agents.report_agent import ReportAgent

__all__ = [
    # Base
    "AgentResult",
    "BaseAgent",
    # Orchestrator
    "PhantomOrchestrator",
    # Specialist agents
    "ReconAgent",
    "ScannerAgent",
    "WebExploitAgent",
    "CloudAgent",
    "CredAgent",
    "ADAgent",
    "ExploitAgent",
    "PostExploitAgent",
    "C2Agent",
    "StealthAgent",
    "ReverserAgent",
    "AnalystAgent",
    "ReportAgent",
]
