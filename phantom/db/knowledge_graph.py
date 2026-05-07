"""
PhantomStrike Knowledge Graph — SQLite-backed graph of all engagement findings.

Agents read from it for context and write to it after each action.
Supports node/edge CRUD, deduplication, attack path tracking, high-value target
ranking, ASCII visualization, and JSON export.
"""
from __future__ import annotations

import json
import logging
import sqlite3
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("phantom.db.knowledge_graph")


# ─── Enums ────────────────────────────────────────────────────────────────────


class NodeType(str, Enum):
    HOST = "host"
    VULNERABILITY = "vulnerability"
    CREDENTIAL = "credential"
    SERVICE = "service"
    DOMAIN = "domain"
    USER = "user"
    GROUP = "group"


class EdgeType(str, Enum):
    HAS_VULN = "has_vuln"
    HAS_CRED = "has_cred"
    CONNECTS_TO = "connects_to"
    EXPLOITS = "exploits"
    LATERAL_MOVE = "lateral_move"
    HAS_SERVICE = "has_service"
    MEMBER_OF = "member_of"


# ─── Schema ───────────────────────────────────────────────────────────────────

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS nodes (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    type       TEXT    NOT NULL,
    label      TEXT    NOT NULL,
    properties TEXT    NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS edges (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id   INTEGER NOT NULL REFERENCES nodes(id),
    target_id   INTEGER NOT NULL REFERENCES nodes(id),
    edge_type   TEXT    NOT NULL,
    properties  TEXT    NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS attack_paths (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    path        TEXT    NOT NULL DEFAULT '[]',
    score       REAL    NOT NULL DEFAULT 0.0,
    description TEXT    NOT NULL DEFAULT ''
);

CREATE INDEX IF NOT EXISTS idx_nodes_type    ON nodes(type);
CREATE INDEX IF NOT EXISTS idx_nodes_label   ON nodes(label);
CREATE INDEX IF NOT EXISTS idx_edges_source  ON edges(source_id);
CREATE INDEX IF NOT EXISTS idx_edges_target  ON edges(target_id);
"""


# ─── KnowledgeGraph ───────────────────────────────────────────────────────────


class KnowledgeGraph:
    """
    Persistent SQLite-backed knowledge graph for PhantomStrike engagements.

    Usage (synchronous):
        kg = KnowledgeGraph()
        kg.connect()                          # or kg.connect(":memory:")
        host_id = kg.add_host("10.0.0.1")
        vuln_id = kg.add_vulnerability(host_id, "SQL Injection", severity="high")
        kg.export_to_json()
    """

    def __init__(self, db_path: str = "~/.phantom-strike/kg.db") -> None:
        self.db_path = db_path
        self._conn: Optional[sqlite3.Connection] = None

    # ── Connection ────────────────────────────────────────────────────────────

    def connect(self, db_path: Optional[str] = None) -> None:
        """
        Open (or create) the SQLite database and initialise the schema.

        Parameters
        ----------
        db_path:
            Override the path set in ``__init__``.  Pass ``":memory:"`` for an
            in-memory database (useful for tests).
        """
        if db_path is not None:
            self.db_path = db_path

        # Expand ~ so the default path works without extra setup
        resolved = self.db_path
        if resolved != ":memory:":
            from pathlib import Path
            p = Path(resolved).expanduser()
            p.parent.mkdir(parents=True, exist_ok=True)
            resolved = str(p)

        self._conn = sqlite3.connect(resolved)
        self._conn.row_factory = sqlite3.Row
        # Enable WAL for better concurrent read performance
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.executescript(_SCHEMA_SQL)
        self._conn.commit()
        logger.info("[KG] Connected: %s", resolved)

    def _require_connection(self) -> sqlite3.Connection:
        if self._conn is None:
            raise RuntimeError(
                "KnowledgeGraph is not connected. Call connect() first."
            )
        return self._conn

    def close(self) -> None:
        """Close the database connection."""
        if self._conn:
            self._conn.close()
            self._conn = None
            logger.info("[KG] Closed")

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _insert_node(
        self,
        node_type: NodeType,
        label: str,
        properties: Dict[str, Any],
    ) -> int:
        """Insert a node and return its integer ID."""
        conn = self._require_connection()
        cur = conn.execute(
            "INSERT INTO nodes (type, label, properties) VALUES (?, ?, ?)",
            (node_type.value, label, json.dumps(properties, default=str)),
        )
        conn.commit()
        return cur.lastrowid  # type: ignore[return-value]

    def _find_node_by_label(self, label: str) -> Optional[int]:
        """Return the ID of the first node with the given label, or None."""
        conn = self._require_connection()
        cur = conn.execute(
            "SELECT id FROM nodes WHERE label = ? LIMIT 1", (label,)
        )
        row = cur.fetchone()
        return int(row["id"]) if row else None

    def _find_node_by_props(
        self,
        node_type: NodeType,
        **kwargs: Any,
    ) -> Optional[int]:
        """
        Return the ID of a node whose JSON properties contain all key=value
        pairs in *kwargs*, or None if not found.

        This performs a full-scan filtered by type; only used for small tables.
        """
        conn = self._require_connection()
        cur = conn.execute(
            "SELECT id, properties FROM nodes WHERE type = ?",
            (node_type.value,),
        )
        for row in cur.fetchall():
            props = json.loads(row["properties"])
            if all(props.get(k) == v for k, v in kwargs.items()):
                return int(row["id"])
        return None

    def _insert_edge(
        self,
        source_id: int,
        target_id: int,
        edge_type: EdgeType,
        properties: Dict[str, Any],
    ) -> int:
        """Insert an edge and return its integer ID."""
        conn = self._require_connection()
        cur = conn.execute(
            "INSERT INTO edges (source_id, target_id, edge_type, properties) VALUES (?, ?, ?, ?)",
            (source_id, target_id, edge_type.value, json.dumps(properties, default=str)),
        )
        conn.commit()
        return cur.lastrowid  # type: ignore[return-value]

    # ── Node insertion ────────────────────────────────────────────────────────

    def add_host(
        self,
        ip: str,
        hostname: str = "",
        os: str = "",
        properties: Optional[Dict[str, Any]] = None,
    ) -> int:
        """
        Add a host node.  Deduplicates by IP label — returns the existing ID
        if a host with the same IP already exists.

        Returns
        -------
        int
            The node ID (new or existing).
        """
        existing = self._find_node_by_label(ip)
        if existing is not None:
            return existing

        props: Dict[str, Any] = {"ip": ip, "hostname": hostname, "os": os}
        if properties:
            props.update(properties)

        return self._insert_node(NodeType.HOST, ip, props)

    def add_vulnerability(
        self,
        host_id: int,
        vuln_type: str,
        url: str = "",
        severity: str = "medium",
        cve: str = "",
        properties: Optional[Dict[str, Any]] = None,
    ) -> int:
        """
        Add a vulnerability node linked to *host_id*.

        Deduplicates by (host_id, vuln_type, url) — returns the existing ID if
        the same vulnerability already exists for that host.  Automatically
        inserts a ``HAS_VULN`` edge from the host to the vulnerability.

        Returns
        -------
        int
            The vulnerability node ID (new or existing).
        """
        # Deduplication: look for an existing vuln with matching host_id, type, url
        existing = self._find_node_by_props(
            NodeType.VULNERABILITY,
            host_id=host_id,
            vuln_type=vuln_type,
            url=url,
        )
        if existing is not None:
            return existing

        label = f"{vuln_type}@{host_id}" + (f":{url}" if url else "")
        props: Dict[str, Any] = {
            "host_id": host_id,
            "vuln_type": vuln_type,
            "url": url,
            "severity": severity,
            "cve": cve,
        }
        if properties:
            props.update(properties)

        vuln_id = self._insert_node(NodeType.VULNERABILITY, label, props)
        # Auto-insert HAS_VULN edge
        self._insert_edge(host_id, vuln_id, EdgeType.HAS_VULN, {})
        return vuln_id

    def add_credential(
        self,
        username: str,
        password_hash: str = "",
        plaintext: str = "",
        source_host_id: Optional[int] = None,
        properties: Optional[Dict[str, Any]] = None,
    ) -> int:
        """
        Add a credential node.

        Returns
        -------
        int
            The credential node ID.
        """
        label = username
        props: Dict[str, Any] = {
            "username": username,
            "password_hash": password_hash,
            "plaintext": plaintext,
            "source_host_id": source_host_id,
        }
        if properties:
            props.update(properties)

        return self._insert_node(NodeType.CREDENTIAL, label, props)

    def add_attack_path(
        self,
        path: List[Any],
        score: float,
        description: str = "",
    ) -> int:
        """
        Store an attack path (list of node IDs or labels) with a score.

        Returns
        -------
        int
            The attack_path record ID.
        """
        conn = self._require_connection()
        cur = conn.execute(
            "INSERT INTO attack_paths (path, score, description) VALUES (?, ?, ?)",
            (json.dumps(path, default=str), float(score), description),
        )
        conn.commit()
        return cur.lastrowid  # type: ignore[return-value]

    def link(
        self,
        source_id: int,
        target_id: int,
        edge_type: EdgeType,
        properties: Optional[Dict[str, Any]] = None,
    ) -> int:
        """
        Create an edge between two nodes.

        Returns
        -------
        int
            The edge ID.
        """
        return self._insert_edge(source_id, target_id, edge_type, properties or {})

    # ── Query methods ─────────────────────────────────────────────────────────

    def get_attack_paths(self) -> List[Dict[str, Any]]:
        """
        Return all attack paths sorted by score descending.

        Returns
        -------
        list[dict]
            Each dict has ``id``, ``path`` (list), ``score``, ``description``.
        """
        conn = self._require_connection()
        cur = conn.execute(
            "SELECT id, path, score, description FROM attack_paths ORDER BY score DESC"
        )
        results = []
        for row in cur.fetchall():
            results.append({
                "id": row["id"],
                "path": json.loads(row["path"]),
                "score": row["score"],
                "description": row["description"],
            })
        return results

    def get_high_value_targets(self) -> List[Dict[str, Any]]:
        """
        Return host nodes ranked by a composite score.

        Score formula:
            score = (num_vulns * 2) + (num_creds * 3) + (num_services * 1)

        Returns
        -------
        list[dict]
            Host dicts with an extra ``score`` key, sorted descending.
        """
        conn = self._require_connection()

        # Fetch all hosts
        cur = conn.execute(
            "SELECT id, label, properties FROM nodes WHERE type = ?",
            (NodeType.HOST.value,),
        )
        hosts = [dict(row) for row in cur.fetchall()]

        scored: List[Dict[str, Any]] = []
        for host in hosts:
            host_id = host["id"]

            # Count vulnerabilities (edges of type HAS_VULN from this host)
            cur_v = conn.execute(
                "SELECT COUNT(*) AS cnt FROM edges WHERE source_id = ? AND edge_type = ?",
                (host_id, EdgeType.HAS_VULN.value),
            )
            num_vulns = cur_v.fetchone()["cnt"]

            # Count credentials linked via HAS_CRED edges
            cur_c = conn.execute(
                "SELECT COUNT(*) AS cnt FROM edges WHERE source_id = ? AND edge_type = ?",
                (host_id, EdgeType.HAS_CRED.value),
            )
            num_creds = cur_c.fetchone()["cnt"]

            # Count services linked via HAS_SERVICE edges
            cur_s = conn.execute(
                "SELECT COUNT(*) AS cnt FROM edges WHERE source_id = ? AND edge_type = ?",
                (host_id, EdgeType.HAS_SERVICE.value),
            )
            num_services = cur_s.fetchone()["cnt"]

            score = (num_vulns * 2) + (num_creds * 3) + (num_services * 1)
            entry = {
                "id": host_id,
                "label": host["label"],
                "properties": json.loads(host["properties"]),
                "num_vulns": num_vulns,
                "num_creds": num_creds,
                "num_services": num_services,
                "score": score,
            }
            scored.append(entry)

        scored.sort(key=lambda h: h["score"], reverse=True)
        return scored

    def get_lateral_movement_paths(self) -> List[Dict[str, Any]]:
        """
        Return all edges of type ``LATERAL_MOVE``.

        Returns
        -------
        list[dict]
            Each dict has ``id``, ``source_id``, ``target_id``, ``edge_type``,
            ``properties``.
        """
        conn = self._require_connection()
        cur = conn.execute(
            "SELECT id, source_id, target_id, edge_type, properties "
            "FROM edges WHERE edge_type = ?",
            (EdgeType.LATERAL_MOVE.value,),
        )
        results = []
        for row in cur.fetchall():
            results.append({
                "id": row["id"],
                "source_id": row["source_id"],
                "target_id": row["target_id"],
                "edge_type": row["edge_type"],
                "properties": json.loads(row["properties"]),
            })
        return results

    def query(self, sql: str, params: Tuple = ()) -> List[Dict[str, Any]]:
        """
        Execute a raw SQL query and return results as a list of dicts.

        Parameters
        ----------
        sql:
            SQL statement to execute.
        params:
            Positional parameters for the query.

        Returns
        -------
        list[dict]
        """
        conn = self._require_connection()
        cur = conn.execute(sql, params)
        return [dict(row) for row in cur.fetchall()]

    # ── Export / Visualisation ────────────────────────────────────────────────

    def export_to_json(self) -> Dict[str, Any]:
        """
        Export the full graph as a JSON-serialisable dict.

        Returns
        -------
        dict
            ``{"nodes": [...], "edges": [...], "attack_paths": [...]}``
        """
        conn = self._require_connection()

        nodes_cur = conn.execute("SELECT id, type, label, properties FROM nodes")
        nodes = []
        for row in nodes_cur.fetchall():
            nodes.append({
                "id": row["id"],
                "type": row["type"],
                "label": row["label"],
                "properties": json.loads(row["properties"]),
            })

        edges_cur = conn.execute(
            "SELECT id, source_id, target_id, edge_type, properties FROM edges"
        )
        edges = []
        for row in edges_cur.fetchall():
            edges.append({
                "id": row["id"],
                "source_id": row["source_id"],
                "target_id": row["target_id"],
                "edge_type": row["edge_type"],
                "properties": json.loads(row["properties"]),
            })

        paths_cur = conn.execute(
            "SELECT id, path, score, description FROM attack_paths"
        )
        attack_paths = []
        for row in paths_cur.fetchall():
            attack_paths.append({
                "id": row["id"],
                "path": json.loads(row["path"]),
                "score": row["score"],
                "description": row["description"],
            })

        return {
            "nodes": nodes,
            "edges": edges,
            "attack_paths": attack_paths,
        }

    def visualize_ascii(self) -> str:
        """
        Return a simple ASCII representation of the graph.

        Format::

            [HOST] 192.168.1.1
              └─ [VULN] SQL Injection@1
              └─ [CRED] admin

        Returns
        -------
        str
            Multi-line ASCII string, or a placeholder when the graph is empty.
        """
        conn = self._require_connection()

        # Fetch all hosts
        hosts_cur = conn.execute(
            "SELECT id, label FROM nodes WHERE type = ?",
            (NodeType.HOST.value,),
        )
        hosts = hosts_cur.fetchall()

        if not hosts:
            return "(empty graph)"

        lines: List[str] = []
        for host in hosts:
            host_id = host["id"]
            lines.append(f"[HOST] {host['label']}")

            # Vulnerabilities
            vuln_cur = conn.execute(
                """
                SELECT n.label
                FROM edges e
                JOIN nodes n ON n.id = e.target_id
                WHERE e.source_id = ? AND e.edge_type = ?
                """,
                (host_id, EdgeType.HAS_VULN.value),
            )
            for vuln_row in vuln_cur.fetchall():
                lines.append(f"  └─ [VULN] {vuln_row['label']}")

            # Credentials
            cred_cur = conn.execute(
                """
                SELECT n.label
                FROM edges e
                JOIN nodes n ON n.id = e.target_id
                WHERE e.source_id = ? AND e.edge_type = ?
                """,
                (host_id, EdgeType.HAS_CRED.value),
            )
            for cred_row in cred_cur.fetchall():
                lines.append(f"  └─ [CRED] {cred_row['label']}")

            # Services
            svc_cur = conn.execute(
                """
                SELECT n.label
                FROM edges e
                JOIN nodes n ON n.id = e.target_id
                WHERE e.source_id = ? AND e.edge_type = ?
                """,
                (host_id, EdgeType.HAS_SERVICE.value),
            )
            for svc_row in svc_cur.fetchall():
                lines.append(f"  └─ [SERVICE] {svc_row['label']}")

        return "\n".join(lines)
