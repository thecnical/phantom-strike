"""
PhantomStrike Report Engine — Auto-generates professional pentest reports.
HTML reports with MITRE ATT&CK mapping, risk scoring, and remediation.
"""
from __future__ import annotations
import json
import logging
from datetime import datetime
from pathlib import Path

from phantom.modules.base import BaseModule, ModuleResult, ModuleStatus
from phantom.core.events import EventBus

logger = logging.getLogger("phantom.report")

MITRE_TECHNIQUE_MAP = {
    "sqli": {"technique": "T1190", "tactic": "Initial Access", "name": "Exploit Public-Facing App"},
    "xss": {"technique": "T1189", "tactic": "Initial Access", "name": "Drive-by Compromise"},
    "lfi": {"technique": "T1083", "tactic": "Discovery", "name": "File and Directory Discovery"},
    "ssrf": {"technique": "T1190", "tactic": "Initial Access", "name": "Server-Side Request Forgery"},
    "rce": {"technique": "T1059", "tactic": "Execution", "name": "Command and Scripting Interpreter"},
    "open_s3_bucket": {"technique": "T1530", "tactic": "Collection", "name": "Data from Cloud Storage"},
    "jwt_none_algorithm": {"technique": "T1134", "tactic": "Privilege Escalation", "name": "Access Token Manipulation"},
    "jwt_weak_secret": {"technique": "T1110", "tactic": "Credential Access", "name": "Brute Force"},
    "path_bypass": {"technique": "T1548", "tactic": "Defense Evasion", "name": "Abuse Elevation Control"},
    "password_spray": {"technique": "T1110.003", "tactic": "Credential Access", "name": "Password Spraying"},
}

REPORT_HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>PhantomStrike — Penetration Test Report</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background: #0a0e17; color: #e0e6ed; line-height: 1.6; }}
        .container {{ max-width: 1200px; margin: 0 auto; padding: 20px; }}
        .header {{ background: linear-gradient(135deg, #1a1f2e 0%, #0d1117 100%); border: 1px solid #ff4444; border-radius: 12px; padding: 40px; margin-bottom: 30px; text-align: center; }}
        .header h1 {{ color: #ff4444; font-size: 2.5em; margin-bottom: 10px; }}
        .header .tagline {{ color: #888; font-style: italic; }}
        .section {{ background: #1a1f2e; border-radius: 8px; padding: 25px; margin-bottom: 20px; border-left: 4px solid #00d4ff; }}
        .section h2 {{ color: #00d4ff; margin-bottom: 15px; }}
        .critical {{ border-left-color: #ff4444 !important; }}
        .high {{ border-left-color: #ff8800 !important; }}
        .medium {{ border-left-color: #ffcc00 !important; }}
        .low {{ border-left-color: #00cc66 !important; }}
        table {{ width: 100%; border-collapse: collapse; margin: 15px 0; }}
        th {{ background: #0d1117; color: #00d4ff; padding: 12px; text-align: left; }}
        td {{ padding: 10px; border-bottom: 1px solid #2d333b; }}
        .badge {{ display: inline-block; padding: 3px 10px; border-radius: 4px; font-size: 0.8em; font-weight: bold; }}
        .badge-critical {{ background: #ff4444; color: white; }}
        .badge-high {{ background: #ff8800; color: white; }}
        .badge-medium {{ background: #ffcc00; color: black; }}
        .badge-low {{ background: #00cc66; color: white; }}
        .score {{ font-size: 3em; font-weight: bold; text-align: center; padding: 20px; }}
        .score.danger {{ color: #ff4444; }}
        .score.warning {{ color: #ff8800; }}
        .score.safe {{ color: #00cc66; }}
        code {{ background: #0d1117; padding: 2px 6px; border-radius: 3px; font-family: monospace; }}
        .footer {{ text-align: center; color: #555; padding: 20px; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🔥 PHANTOM STRIKE</h1>
            <p class="tagline">"See Everything. Strike Anywhere. Leave Nothing."</p>
            <p style="margin-top: 15px; color: #aaa;">Penetration Test Report — {target}</p>
            <p style="color: #666;">Generated: {date} | Session: {session_id}</p>
        </div>

        <div class="section">
            <h2>📊 Executive Summary</h2>
            <div style="display: flex; justify-content: space-around; text-align: center;">
                <div>
                    <div class="score danger">{critical_count}</div>
                    <span class="badge badge-critical">CRITICAL</span>
                </div>
                <div>
                    <div class="score warning">{high_count}</div>
                    <span class="badge badge-high">HIGH</span>
                </div>
                <div>
                    <div class="score" style="color:#ffcc00">{medium_count}</div>
                    <span class="badge badge-medium">MEDIUM</span>
                </div>
                <div>
                    <div class="score safe">{low_count}</div>
                    <span class="badge badge-low">LOW</span>
                </div>
            </div>
            <p style="margin-top: 20px; text-align: center;">
                Overall Risk Score: <strong class="score danger" style="font-size: 1.5em;">{risk_score}/10</strong>
            </p>
        </div>

        {vulnerability_sections}

        <div class="section">
            <h2>🗺️ MITRE ATT&CK Mapping</h2>
            <table>
                <tr><th>Technique ID</th><th>Technique Name</th><th>Tactic</th><th>Found In</th></tr>
                {mitre_rows}
            </table>
        </div>

        <div class="footer">
            <p>Generated by PhantomStrike v1.0.0-alpha | Authorized Testing Only</p>
            <p>⚠️ This report contains sensitive security information. Handle with care.</p>
        </div>
    </div>
</body>
</html>"""


class ReportEngine(BaseModule):
    """Auto-generates professional HTML/JSON pentest reports."""

    @property
    def name(self) -> str:
        return "phantom-report"

    @property
    def description(self) -> str:
        return "Reporting — auto-gen HTML reports with MITRE ATT&CK mapping"

    @property
    def category(self) -> str:
        return "reporting"

    async def _setup(self):
        self._output_dir = Path.home() / ".phantom-strike" / "reports"
        self._output_dir.mkdir(parents=True, exist_ok=True)

    async def run(self, target: str, options: dict = None) -> ModuleResult:
        """Generate a report from scan results."""
        options = options or {}
        start_time = datetime.now()
        self.status = ModuleStatus.RUNNING

        scan_results = options.get("results", {})
        session_id = options.get("session_id", "unknown")

        report_path = await self._generate_html_report(target, scan_results, session_id)

        # Also save JSON
        json_path = report_path.with_suffix(".json")
        with open(json_path, "w") as f:
            json.dump(scan_results, f, indent=2, default=str)

        self.status = ModuleStatus.COMPLETED
        return ModuleResult(
            module_name=self.name, operation="generate_report",
            success=True,
            data={"html_path": str(report_path), "json_path": str(json_path)},
            start_time=start_time, end_time=datetime.now(),
        )

    async def _generate_html_report(self, target: str, results: dict, session_id: str) -> Path:
        """Generate a stunning HTML report."""
        # Count vulnerabilities by severity
        all_vulns = self._extract_all_vulns(results)
        critical = [v for v in all_vulns if v.get("severity") == "critical"]
        high = [v for v in all_vulns if v.get("severity") == "high"]
        medium = [v for v in all_vulns if v.get("severity") == "medium"]
        low = [v for v in all_vulns if v.get("severity") in ("low", "info")]

        # Calculate risk score
        risk_score = min(10, len(critical) * 3 + len(high) * 2 + len(medium) * 0.5)

        # Generate vulnerability sections
        vuln_html = ""
        for vuln in all_vulns:
            sev = vuln.get("severity", "medium")
            mitre = MITRE_TECHNIQUE_MAP.get(vuln.get("type", ""), {})
            vuln_html += f"""
            <div class="section {sev}">
                <h2>{self._severity_icon(sev)} {vuln.get('type', 'Unknown').upper()}</h2>
                <table>
                    <tr><td><strong>Severity</strong></td><td><span class="badge badge-{sev}">{sev.upper()}</span></td></tr>
                    <tr><td><strong>URL</strong></td><td><code>{vuln.get('url', 'N/A')}</code></td></tr>
                    <tr><td><strong>Payload</strong></td><td><code>{vuln.get('payload', 'N/A')}</code></td></tr>
                    <tr><td><strong>MITRE ATT&CK</strong></td><td>{mitre.get('technique', 'N/A')} — {mitre.get('name', 'N/A')}</td></tr>
                    <tr><td><strong>Remediation</strong></td><td>{self._get_remediation(vuln.get('type', ''))}</td></tr>
                </table>
            </div>"""

        # MITRE mapping rows
        mitre_techniques = set()
        mitre_rows = ""
        for vuln in all_vulns:
            mitre = MITRE_TECHNIQUE_MAP.get(vuln.get("type", ""), {})
            tech_id = mitre.get("technique", "")
            if tech_id and tech_id not in mitre_techniques:
                mitre_techniques.add(tech_id)
                mitre_rows += f"<tr><td>{tech_id}</td><td>{mitre.get('name', '')}</td><td>{mitre.get('tactic', '')}</td><td>{vuln.get('type', '')}</td></tr>"

        html = REPORT_HTML_TEMPLATE.format(
            target=target,
            date=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            session_id=session_id,
            critical_count=len(critical),
            high_count=len(high),
            medium_count=len(medium),
            low_count=len(low),
            risk_score=f"{risk_score:.1f}",
            vulnerability_sections=vuln_html,
            mitre_rows=mitre_rows or "<tr><td colspan='4'>No MITRE mappings</td></tr>",
        )

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_path = self._output_dir / f"phantom_report_{target.replace('.', '_')}_{timestamp}.html"
        report_path.write_text(html, encoding="utf-8")

        logger.info(f"[REPORT] 📊 Report saved: {report_path}")
        return report_path

    def _extract_all_vulns(self, results: dict) -> list[dict]:
        """Extract all vulnerabilities from scan results."""
        vulns = []
        for module_name, module_data in results.items():
            if isinstance(module_data, dict):
                data = module_data.get("data", module_data)
                for key in ["sqli", "xss", "lfi", "ssrf", "rce", "jwt_vulns",
                             "auth_bypass", "s3_buckets", "misconfigurations",
                             "valid_credentials", "headers_issues"]:
                    if key in data:
                        for item in data[key]:
                            if isinstance(item, dict):
                                if "type" not in item:
                                    item["type"] = key
                                vulns.append(item)
        return vulns

    def _severity_icon(self, severity: str) -> str:
        icons = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🟢", "info": "🔵"}
        return icons.get(severity, "⚪")

    def _get_remediation(self, vuln_type: str) -> str:
        remediations = {
            "sqli": "Use parameterized queries/prepared statements. Implement input validation.",
            "xss": "Implement Content-Security-Policy. Sanitize all user inputs. Use output encoding.",
            "lfi": "Validate and whitelist file paths. Disable unnecessary file inclusions.",
            "ssrf": "Implement URL allowlisting. Block requests to internal/cloud metadata IPs.",
            "rce": "Never pass user input to system commands. Use safe APIs. Implement sandboxing.",
            "open_s3_bucket": "Set bucket ACL to private. Enable S3 Block Public Access.",
            "jwt_none_algorithm": "Reject 'none' algorithm. Use strong signing keys. Validate all JWT claims.",
            "jwt_weak_secret": "Use a cryptographically strong secret (256+ bits). Rotate secrets regularly.",
            "path_bypass": "Implement proper authorization checks. Don't rely on URL-based access control.",
        }
        return remediations.get(vuln_type, "Review and apply security best practices.")
