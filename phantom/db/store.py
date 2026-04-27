"""
PhantomStrike Database Layer — SQLite-backed persistence.
Stores scan results, credentials, sessions, and evidence.
"""
from __future__ import annotations
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

import aiosqlite

logger = logging.getLogger("phantom.db")

DEFAULT_DB_PATH = Path.home() / ".phantom-strike" / "phantom.db"

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS scans (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    target TEXT NOT NULL,
    module TEXT NOT NULL,
    operation TEXT DEFAULT '',
    status TEXT DEFAULT 'running',
    findings_count INTEGER DEFAULT 0,
    data TEXT DEFAULT '{}',
    started_at TEXT NOT NULL,
    completed_at TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS vulnerabilities (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    scan_id INTEGER REFERENCES scans(id),
    target TEXT NOT NULL,
    vuln_type TEXT NOT NULL,
    severity TEXT DEFAULT 'medium',
    url TEXT DEFAULT '',
    payload TEXT DEFAULT '',
    description TEXT DEFAULT '',
    mitre_technique TEXT DEFAULT '',
    remediation TEXT DEFAULT '',
    confirmed INTEGER DEFAULT 0,
    exploited INTEGER DEFAULT 0,
    data TEXT DEFAULT '{}',
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS credentials (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    scan_id INTEGER REFERENCES scans(id),
    target TEXT NOT NULL,
    username TEXT DEFAULT '',
    password TEXT DEFAULT '',
    hash_value TEXT DEFAULT '',
    hash_type TEXT DEFAULT '',
    source TEXT DEFAULT '',
    valid INTEGER DEFAULT 0,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS agents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    agent_id TEXT UNIQUE NOT NULL,
    hostname TEXT DEFAULT '',
    ip_address TEXT DEFAULT '',
    os_info TEXT DEFAULT '',
    username TEXT DEFAULT '',
    privileges TEXT DEFAULT 'user',
    status TEXT DEFAULT 'active',
    channel TEXT DEFAULT 'https',
    first_seen TEXT DEFAULT (datetime('now')),
    last_seen TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS agent_commands (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    agent_id TEXT REFERENCES agents(agent_id),
    command TEXT NOT NULL,
    args TEXT DEFAULT '{}',
    status TEXT DEFAULT 'pending',
    output TEXT DEFAULT '',
    issued_at TEXT DEFAULT (datetime('now')),
    completed_at TEXT
);

CREATE TABLE IF NOT EXISTS evidence (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    scan_id INTEGER REFERENCES scans(id),
    vuln_id INTEGER REFERENCES vulnerabilities(id),
    evidence_type TEXT DEFAULT 'screenshot',
    file_path TEXT DEFAULT '',
    description TEXT DEFAULT '',
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    target TEXT NOT NULL,
    report_type TEXT DEFAULT 'html',
    file_path TEXT NOT NULL,
    total_vulns INTEGER DEFAULT 0,
    critical_count INTEGER DEFAULT 0,
    high_count INTEGER DEFAULT 0,
    medium_count INTEGER DEFAULT 0,
    low_count INTEGER DEFAULT 0,
    risk_score REAL DEFAULT 0.0,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_scans_session ON scans(session_id);
CREATE INDEX IF NOT EXISTS idx_scans_target ON scans(target);
CREATE INDEX IF NOT EXISTS idx_vulns_target ON vulnerabilities(target);
CREATE INDEX IF NOT EXISTS idx_vulns_severity ON vulnerabilities(severity);
CREATE INDEX IF NOT EXISTS idx_creds_target ON credentials(target);
CREATE INDEX IF NOT EXISTS idx_agents_status ON agents(status);
"""


class PhantomDB:
    """Async SQLite database for PhantomStrike."""

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or DEFAULT_DB_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._db: Optional[aiosqlite.Connection] = None

    async def connect(self):
        """Connect and initialize schema."""
        self._db = await aiosqlite.connect(str(self.db_path))
        self._db.row_factory = aiosqlite.Row
        await self._db.executescript(SCHEMA_SQL)
        await self._db.commit()
        logger.info(f"[DB] Connected: {self.db_path}")

    async def close(self):
        """Close connection."""
        if self._db:
            await self._db.close()
            logger.info("[DB] Closed")

    # ─── Scan CRUD ────────────────────────────────────────────

    async def insert_scan(self, session_id: str, target: str, module: str,
                          operation: str = "") -> int:
        """Insert a new scan record. Returns scan_id."""
        async with self._db.execute(
            "INSERT INTO scans (session_id, target, module, operation, started_at) VALUES (?, ?, ?, ?, ?)",
            (session_id, target, module, operation, datetime.now().isoformat()),
        ) as cursor:
            await self._db.commit()
            return cursor.lastrowid

    async def update_scan(self, scan_id: int, status: str = "completed",
                          findings_count: int = 0, data: dict = None):
        """Update scan status and results."""
        await self._db.execute(
            "UPDATE scans SET status=?, findings_count=?, data=?, completed_at=? WHERE id=?",
            (status, findings_count, json.dumps(data or {}, default=str),
             datetime.now().isoformat(), scan_id),
        )
        await self._db.commit()

    async def get_scans(self, target: str = None, limit: int = 50) -> list[dict]:
        """Get recent scans."""
        if target:
            query = "SELECT * FROM scans WHERE target=? ORDER BY id DESC LIMIT ?"
            params = (target, limit)
        else:
            query = "SELECT * FROM scans ORDER BY id DESC LIMIT ?"
            params = (limit,)
        async with self._db.execute(query, params) as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]

    # ─── Vulnerability CRUD ───────────────────────────────────

    async def insert_vuln(self, scan_id: int, target: str, vuln_type: str,
                          severity: str = "medium", url: str = "",
                          payload: str = "", description: str = "",
                          mitre_technique: str = "", data: dict = None) -> int:
        """Insert a vulnerability finding."""
        async with self._db.execute(
            """INSERT INTO vulnerabilities
               (scan_id, target, vuln_type, severity, url, payload, description, mitre_technique, data)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (scan_id, target, vuln_type, severity, url, payload,
             description, mitre_technique, json.dumps(data or {}, default=str)),
        ) as cursor:
            await self._db.commit()
            return cursor.lastrowid

    async def get_vulns(self, target: str = None, severity: str = None,
                        limit: int = 100) -> list[dict]:
        """Get vulnerabilities with optional filters."""
        conditions, params = [], []
        if target:
            conditions.append("target=?")
            params.append(target)
        if severity:
            conditions.append("severity=?")
            params.append(severity)
        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        query = f"SELECT * FROM vulnerabilities {where} ORDER BY id DESC LIMIT ?"
        params.append(limit)
        async with self._db.execute(query, params) as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]

    async def get_vuln_stats(self, target: str = None) -> dict:
        """Get vulnerability count by severity."""
        where = "WHERE target=?" if target else ""
        params = (target,) if target else ()
        async with self._db.execute(
            f"SELECT severity, COUNT(*) as cnt FROM vulnerabilities {where} GROUP BY severity",
            params,
        ) as cursor:
            rows = await cursor.fetchall()
            stats = {r["severity"]: r["cnt"] for r in rows}
        return stats

    # ─── Credential CRUD ──────────────────────────────────────

    async def insert_cred(self, scan_id: int, target: str, username: str = "",
                          password: str = "", hash_value: str = "",
                          hash_type: str = "", source: str = "",
                          valid: bool = False) -> int:
        """Insert a found credential."""
        async with self._db.execute(
            """INSERT INTO credentials
               (scan_id, target, username, password, hash_value, hash_type, source, valid)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (scan_id, target, username, password, hash_value, hash_type, source, int(valid)),
        ) as cursor:
            await self._db.commit()
            return cursor.lastrowid

    async def get_creds(self, target: str = None, limit: int = 50) -> list[dict]:
        """Get found credentials."""
        if target:
            query = "SELECT * FROM credentials WHERE target=? ORDER BY id DESC LIMIT ?"
            params = (target, limit)
        else:
            query = "SELECT * FROM credentials ORDER BY id DESC LIMIT ?"
            params = (limit,)
        async with self._db.execute(query, params) as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]

    # ─── Agent CRUD ───────────────────────────────────────────

    async def upsert_agent(self, agent_id: str, hostname: str = "",
                           ip_address: str = "", os_info: str = "",
                           username: str = "", status: str = "active"):
        """Insert or update a C2 agent."""
        await self._db.execute(
            """INSERT INTO agents (agent_id, hostname, ip_address, os_info, username, status)
               VALUES (?, ?, ?, ?, ?, ?)
               ON CONFLICT(agent_id) DO UPDATE SET
               status=excluded.status, last_seen=datetime('now')""",
            (agent_id, hostname, ip_address, os_info, username, status),
        )
        await self._db.commit()

    async def get_agents(self, status: str = None) -> list[dict]:
        """Get C2 agents."""
        if status:
            query = "SELECT * FROM agents WHERE status=? ORDER BY last_seen DESC"
            params = (status,)
        else:
            query = "SELECT * FROM agents ORDER BY last_seen DESC"
            params = ()
        async with self._db.execute(query, params) as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]

    # ─── Report CRUD ──────────────────────────────────────────

    async def insert_report(self, session_id: str, target: str, file_path: str,
                            report_type: str = "html", total_vulns: int = 0,
                            critical: int = 0, high: int = 0,
                            medium: int = 0, low: int = 0,
                            risk_score: float = 0.0) -> int:
        """Insert a generated report."""
        async with self._db.execute(
            """INSERT INTO reports
               (session_id, target, report_type, file_path, total_vulns,
                critical_count, high_count, medium_count, low_count, risk_score)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (session_id, target, report_type, file_path, total_vulns,
             critical, high, medium, low, risk_score),
        ) as cursor:
            await self._db.commit()
            return cursor.lastrowid

    async def get_reports(self, limit: int = 20) -> list[dict]:
        """Get generated reports."""
        async with self._db.execute(
            "SELECT * FROM reports ORDER BY id DESC LIMIT ?", (limit,),
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]
