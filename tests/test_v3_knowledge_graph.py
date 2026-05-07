"""
PhantomStrike v3.0 — Knowledge Graph Property Tests
Run with: pytest tests/test_v3_knowledge_graph.py -v
"""
import pytest
from hypothesis import given, settings, assume
import hypothesis.strategies as st

from phantom.db.knowledge_graph import KnowledgeGraph


# ─── Helpers ──────────────────────────────────────────────────────────────────

def make_kg() -> KnowledgeGraph:
    """Return a fresh in-memory KnowledgeGraph, ready to use."""
    kg = KnowledgeGraph()
    kg.connect(":memory:")
    return kg


# ─── IP-like string strategy ──────────────────────────────────────────────────

# Generate plausible IP-like strings: four octets joined by dots.
# We keep the range small (0–9) so hypothesis can explore many distinct values
# without generating an enormous search space.
_octet = st.integers(min_value=0, max_value=255).map(str)
_ip_like = st.builds(
    lambda a, b, c, d: f"{a}.{b}.{c}.{d}",
    _octet, _octet, _octet, _octet,
)


# ─── Property 3: KG Node Uniqueness and Deduplication ─────────────────────────
# Validates: Requirements 6.1, 6.2, 6.4


@given(ips=st.lists(_ip_like, min_size=1, max_size=20, unique=True))
@settings(max_examples=200)
def test_distinct_ips_produce_distinct_ids(ips: list[str]):
    """
    **Validates: Requirements 6.1, 6.2**

    Property 3a: KG Node Uniqueness

    For a list of distinct IP addresses, calling add_host() for each one must
    return a unique ID per IP.  No two distinct IPs should share the same node ID.
    """
    kg = make_kg()
    ids = [kg.add_host(ip) for ip in ips]

    assert len(ids) == len(set(ids)), (
        f"Duplicate IDs returned for distinct IPs.\n"
        f"IPs:  {ips}\n"
        f"IDs:  {ids}\n"
        f"Duplicates: {[id_ for id_ in ids if ids.count(id_) > 1]}"
    )


@given(ip=_ip_like)
@settings(max_examples=200)
def test_duplicate_ip_returns_same_id(ip: str):
    """
    **Validates: Requirements 6.2, 6.4**

    Property 3b: KG Node Deduplication

    Calling add_host() twice with the same IP must return the same ID both times
    and must NOT insert a second node into the graph.
    """
    kg = make_kg()

    id_first = kg.add_host(ip)
    id_second = kg.add_host(ip)

    # Same ID returned on both calls
    assert id_first == id_second, (
        f"add_host({ip!r}) returned different IDs on repeated calls: "
        f"{id_first!r} vs {id_second!r}"
    )

    # Only one node exists in the graph for this IP
    rows = kg.query(
        "SELECT COUNT(*) AS cnt FROM nodes WHERE label = ?", (ip,)
    )
    count = rows[0]["cnt"]
    assert count == 1, (
        f"Expected exactly 1 node for IP {ip!r} after two add_host() calls, "
        f"but found {count}."
    )


# ═══════════════════════════════════════════════════════════════════════════════
# Unit Tests for KnowledgeGraph
# Requirements: 6.1–6.8, 7.1–7.6
# ═══════════════════════════════════════════════════════════════════════════════


class TestNodeEdgeCRUD:
    """Test basic node and edge create/read operations. Requirements 6.1–6.7"""

    def test_add_host_returns_integer_id(self):
        """add_host() returns an integer ID. Req 6.1"""
        kg = make_kg()
        host_id = kg.add_host("10.0.0.1")
        assert isinstance(host_id, int)
        assert host_id > 0

    def test_add_host_stores_properties(self):
        """add_host() persists hostname and OS in node properties. Req 6.1"""
        kg = make_kg()
        host_id = kg.add_host("10.0.0.2", hostname="webserver", os="Linux")
        rows = kg.query("SELECT properties FROM nodes WHERE id = ?", (host_id,))
        import json
        props = json.loads(rows[0]["properties"])
        assert props["hostname"] == "webserver"
        assert props["os"] == "Linux"
        assert props["ip"] == "10.0.0.2"

    def test_add_vulnerability_returns_integer_id(self):
        """add_vulnerability() returns an integer ID. Req 6.3"""
        kg = make_kg()
        host_id = kg.add_host("10.0.0.3")
        vuln_id = kg.add_vulnerability(host_id, "SQL Injection", severity="high")
        assert isinstance(vuln_id, int)
        assert vuln_id > 0

    def test_add_vulnerability_creates_has_vuln_edge(self):
        """add_vulnerability() auto-inserts a HAS_VULN edge. Req 6.3"""
        kg = make_kg()
        host_id = kg.add_host("10.0.0.4")
        vuln_id = kg.add_vulnerability(host_id, "XSS", url="http://example.com/search")
        edges = kg.query(
            "SELECT * FROM edges WHERE source_id = ? AND target_id = ? AND edge_type = 'has_vuln'",
            (host_id, vuln_id),
        )
        assert len(edges) == 1

    def test_add_credential_returns_integer_id(self):
        """add_credential() returns an integer ID. Req 6.5"""
        kg = make_kg()
        cred_id = kg.add_credential("admin", password_hash="abc123")
        assert isinstance(cred_id, int)
        assert cred_id > 0

    def test_add_credential_stores_username(self):
        """add_credential() stores the username as the node label. Req 6.5"""
        kg = make_kg()
        cred_id = kg.add_credential("root", plaintext="toor")
        rows = kg.query("SELECT label FROM nodes WHERE id = ?", (cred_id,))
        assert rows[0]["label"] == "root"

    def test_add_attack_path_returns_integer_id(self):
        """add_attack_path() returns an integer ID. Req 6.6"""
        kg = make_kg()
        path_id = kg.add_attack_path([1, 2, 3], score=9.5, description="pivot chain")
        assert isinstance(path_id, int)
        assert path_id > 0

    def test_link_creates_edge(self):
        """link() inserts an edge between two nodes. Req 6.7"""
        from phantom.db.knowledge_graph import EdgeType
        kg = make_kg()
        host_a = kg.add_host("192.168.1.1")
        host_b = kg.add_host("192.168.1.2")
        edge_id = kg.link(host_a, host_b, EdgeType.LATERAL_MOVE)
        assert isinstance(edge_id, int)
        edges = kg.query(
            "SELECT * FROM edges WHERE source_id = ? AND target_id = ? AND edge_type = 'lateral_move'",
            (host_a, host_b),
        )
        assert len(edges) == 1

    def test_link_with_properties(self):
        """link() stores edge properties. Req 6.7"""
        from phantom.db.knowledge_graph import EdgeType
        import json
        kg = make_kg()
        host_a = kg.add_host("192.168.2.1")
        host_b = kg.add_host("192.168.2.2")
        kg.link(host_a, host_b, EdgeType.CONNECTS_TO, properties={"port": 22})
        edges = kg.query(
            "SELECT properties FROM edges WHERE source_id = ? AND target_id = ?",
            (host_a, host_b),
        )
        props = json.loads(edges[0]["properties"])
        assert props["port"] == 22

    def test_query_raw_sql(self):
        """query() executes raw SQL and returns list of dicts."""
        kg = make_kg()
        kg.add_host("10.1.1.1")
        kg.add_host("10.1.1.2")
        rows = kg.query("SELECT COUNT(*) AS cnt FROM nodes WHERE type = 'host'")
        assert rows[0]["cnt"] == 2


class TestDeduplication:
    """Test deduplication logic. Requirements 6.2, 6.4"""

    def test_add_host_same_ip_returns_same_id(self):
        """add_host() with duplicate IP returns existing ID. Req 6.2"""
        kg = make_kg()
        id1 = kg.add_host("172.16.0.1")
        id2 = kg.add_host("172.16.0.1")
        assert id1 == id2

    def test_add_host_same_ip_no_duplicate_node(self):
        """add_host() with duplicate IP does not insert a second node. Req 6.2"""
        kg = make_kg()
        kg.add_host("172.16.0.2")
        kg.add_host("172.16.0.2")
        rows = kg.query("SELECT COUNT(*) AS cnt FROM nodes WHERE label = '172.16.0.2'")
        assert rows[0]["cnt"] == 1

    def test_add_host_different_ips_are_distinct(self):
        """add_host() with different IPs creates separate nodes. Req 6.1"""
        kg = make_kg()
        id1 = kg.add_host("10.10.10.1")
        id2 = kg.add_host("10.10.10.2")
        assert id1 != id2

    def test_add_vulnerability_same_host_type_url_deduplicates(self):
        """add_vulnerability() with same (host_id, vuln_type, url) returns existing ID. Req 6.4"""
        kg = make_kg()
        host_id = kg.add_host("10.20.0.1")
        v1 = kg.add_vulnerability(host_id, "SQLi", url="http://target.com/login")
        v2 = kg.add_vulnerability(host_id, "SQLi", url="http://target.com/login")
        assert v1 == v2

    def test_add_vulnerability_same_host_type_url_no_duplicate_node(self):
        """add_vulnerability() dedup does not insert a second node. Req 6.4"""
        kg = make_kg()
        host_id = kg.add_host("10.20.0.2")
        kg.add_vulnerability(host_id, "XSS", url="http://target.com/search")
        kg.add_vulnerability(host_id, "XSS", url="http://target.com/search")
        rows = kg.query(
            "SELECT COUNT(*) AS cnt FROM nodes WHERE type = 'vulnerability' AND label LIKE 'XSS@%'"
        )
        assert rows[0]["cnt"] == 1

    def test_add_vulnerability_same_host_type_url_no_duplicate_edge(self):
        """add_vulnerability() dedup does not insert a second HAS_VULN edge. Req 6.4"""
        kg = make_kg()
        host_id = kg.add_host("10.20.0.3")
        v_id = kg.add_vulnerability(host_id, "RCE", url="http://target.com/exec")
        kg.add_vulnerability(host_id, "RCE", url="http://target.com/exec")
        edges = kg.query(
            "SELECT COUNT(*) AS cnt FROM edges WHERE source_id = ? AND target_id = ? AND edge_type = 'has_vuln'",
            (host_id, v_id),
        )
        assert edges[0]["cnt"] == 1

    def test_add_vulnerability_different_url_creates_new_node(self):
        """add_vulnerability() with different URL creates a distinct node. Req 6.3"""
        kg = make_kg()
        host_id = kg.add_host("10.20.0.4")
        v1 = kg.add_vulnerability(host_id, "SQLi", url="http://target.com/login")
        v2 = kg.add_vulnerability(host_id, "SQLi", url="http://target.com/register")
        assert v1 != v2

    def test_add_vulnerability_different_host_creates_new_node(self):
        """add_vulnerability() with different host_id creates a distinct node. Req 6.3"""
        kg = make_kg()
        h1 = kg.add_host("10.20.0.5")
        h2 = kg.add_host("10.20.0.6")
        v1 = kg.add_vulnerability(h1, "SQLi", url="http://target.com/login")
        v2 = kg.add_vulnerability(h2, "SQLi", url="http://target.com/login")
        assert v1 != v2


class TestAttackPathQueries:
    """Test attack path storage and retrieval. Requirements 6.6, 7.2"""

    def test_get_attack_paths_empty(self):
        """get_attack_paths() returns empty list when no paths exist. Req 7.2"""
        kg = make_kg()
        assert kg.get_attack_paths() == []

    def test_get_attack_paths_returns_all(self):
        """get_attack_paths() returns all stored paths. Req 7.2"""
        kg = make_kg()
        kg.add_attack_path([1, 2], score=5.0, description="path A")
        kg.add_attack_path([3, 4], score=3.0, description="path B")
        paths = kg.get_attack_paths()
        assert len(paths) == 2

    def test_get_attack_paths_sorted_by_score_descending(self):
        """get_attack_paths() returns paths sorted by score descending. Req 7.2"""
        kg = make_kg()
        kg.add_attack_path([1], score=2.0, description="low")
        kg.add_attack_path([2], score=9.0, description="high")
        kg.add_attack_path([3], score=5.5, description="mid")
        paths = kg.get_attack_paths()
        scores = [p["score"] for p in paths]
        assert scores == sorted(scores, reverse=True)

    def test_get_attack_paths_contains_expected_fields(self):
        """get_attack_paths() dicts contain id, path, score, description. Req 7.2"""
        kg = make_kg()
        kg.add_attack_path([10, 20, 30], score=7.5, description="test path")
        paths = kg.get_attack_paths()
        assert len(paths) == 1
        p = paths[0]
        assert "id" in p
        assert p["path"] == [10, 20, 30]
        assert p["score"] == 7.5
        assert p["description"] == "test path"

    def test_add_attack_path_stores_list(self):
        """add_attack_path() correctly serialises and retrieves the path list. Req 6.6"""
        kg = make_kg()
        path_nodes = [1, 5, 9, 12]
        kg.add_attack_path(path_nodes, score=4.0)
        paths = kg.get_attack_paths()
        assert paths[0]["path"] == path_nodes


class TestHighValueTargetRanking:
    """Test high-value target scoring. Requirements 7.1"""

    def test_get_high_value_targets_empty(self):
        """get_high_value_targets() returns empty list when no hosts exist. Req 7.1"""
        kg = make_kg()
        assert kg.get_high_value_targets() == []

    def test_scoring_vulns_weight_2(self):
        """Each vulnerability contributes 2 to the score. Req 7.1"""
        from phantom.db.knowledge_graph import EdgeType
        kg = make_kg()
        host_id = kg.add_host("10.30.0.1")
        kg.add_vulnerability(host_id, "SQLi", url="http://a.com/1")
        kg.add_vulnerability(host_id, "XSS", url="http://a.com/2")
        targets = kg.get_high_value_targets()
        assert len(targets) == 1
        assert targets[0]["score"] == 4  # 2 vulns * 2

    def test_scoring_creds_weight_3(self):
        """Each credential edge contributes 3 to the score. Req 7.1"""
        from phantom.db.knowledge_graph import EdgeType
        kg = make_kg()
        host_id = kg.add_host("10.30.0.2")
        cred1 = kg.add_credential("user1")
        cred2 = kg.add_credential("user2")
        kg.link(host_id, cred1, EdgeType.HAS_CRED)
        kg.link(host_id, cred2, EdgeType.HAS_CRED)
        targets = kg.get_high_value_targets()
        assert targets[0]["score"] == 6  # 2 creds * 3

    def test_scoring_services_weight_1(self):
        """Each service edge contributes 1 to the score. Req 7.1"""
        from phantom.db.knowledge_graph import EdgeType, NodeType
        kg = make_kg()
        host_id = kg.add_host("10.30.0.3")
        # Add service nodes manually
        from phantom.db.knowledge_graph import NodeType
        svc1 = kg._insert_node(NodeType.SERVICE, "http:80", {})
        svc2 = kg._insert_node(NodeType.SERVICE, "ssh:22", {})
        svc3 = kg._insert_node(NodeType.SERVICE, "ftp:21", {})
        kg.link(host_id, svc1, EdgeType.HAS_SERVICE)
        kg.link(host_id, svc2, EdgeType.HAS_SERVICE)
        kg.link(host_id, svc3, EdgeType.HAS_SERVICE)
        targets = kg.get_high_value_targets()
        assert targets[0]["score"] == 3  # 3 services * 1

    def test_scoring_combined(self):
        """Score = vulns*2 + creds*3 + services*1. Req 7.1"""
        from phantom.db.knowledge_graph import EdgeType, NodeType
        kg = make_kg()
        host_id = kg.add_host("10.30.0.4")
        # 1 vuln (score += 2)
        kg.add_vulnerability(host_id, "RCE", url="http://b.com/exec")
        # 1 cred (score += 3)
        cred = kg.add_credential("sysadmin")
        kg.link(host_id, cred, EdgeType.HAS_CRED)
        # 1 service (score += 1)
        svc = kg._insert_node(NodeType.SERVICE, "rdp:3389", {})
        kg.link(host_id, svc, EdgeType.HAS_SERVICE)
        targets = kg.get_high_value_targets()
        assert targets[0]["score"] == 6  # 2 + 3 + 1

    def test_sorted_descending_by_score(self):
        """get_high_value_targets() returns hosts sorted by score descending. Req 7.1"""
        from phantom.db.knowledge_graph import EdgeType
        kg = make_kg()
        # Host A: 0 score
        kg.add_host("10.40.0.1")
        # Host B: 1 vuln → score 2
        h_b = kg.add_host("10.40.0.2")
        kg.add_vulnerability(h_b, "SQLi", url="http://c.com/1")
        # Host C: 2 vulns → score 4
        h_c = kg.add_host("10.40.0.3")
        kg.add_vulnerability(h_c, "SQLi", url="http://d.com/1")
        kg.add_vulnerability(h_c, "XSS", url="http://d.com/2")

        targets = kg.get_high_value_targets()
        scores = [t["score"] for t in targets]
        assert scores == sorted(scores, reverse=True)
        assert scores[0] == 4

    def test_high_value_targets_contain_expected_fields(self):
        """get_high_value_targets() dicts contain required fields. Req 7.1"""
        kg = make_kg()
        kg.add_host("10.50.0.1")
        targets = kg.get_high_value_targets()
        assert len(targets) == 1
        t = targets[0]
        for field in ("id", "label", "properties", "num_vulns", "num_creds", "num_services", "score"):
            assert field in t, f"Missing field: {field}"


class TestAsciiVisualization:
    """Test ASCII visualization output. Requirements 7.4"""

    def test_empty_graph_returns_placeholder(self):
        """visualize_ascii() returns placeholder string for empty graph. Req 7.4"""
        kg = make_kg()
        result = kg.visualize_ascii()
        assert result == "(empty graph)"

    def test_non_empty_graph_returns_non_empty_string(self):
        """visualize_ascii() returns non-empty string for non-empty graph. Req 7.4"""
        kg = make_kg()
        kg.add_host("192.168.10.1")
        result = kg.visualize_ascii()
        assert isinstance(result, str)
        assert len(result) > 0

    def test_host_label_appears_in_output(self):
        """visualize_ascii() includes the host IP in the output. Req 7.4"""
        kg = make_kg()
        kg.add_host("192.168.10.2")
        result = kg.visualize_ascii()
        assert "192.168.10.2" in result

    def test_host_type_tag_in_output(self):
        """visualize_ascii() includes [HOST] tag. Req 7.4"""
        kg = make_kg()
        kg.add_host("192.168.10.3")
        result = kg.visualize_ascii()
        assert "[HOST]" in result

    def test_vulnerability_appears_in_output(self):
        """visualize_ascii() includes [VULN] tag for linked vulnerabilities. Req 7.4"""
        kg = make_kg()
        host_id = kg.add_host("192.168.10.4")
        kg.add_vulnerability(host_id, "SQL Injection", url="http://target.com/login")
        result = kg.visualize_ascii()
        assert "[VULN]" in result

    def test_credential_appears_in_output(self):
        """visualize_ascii() includes [CRED] tag for linked credentials. Req 7.4"""
        from phantom.db.knowledge_graph import EdgeType
        kg = make_kg()
        host_id = kg.add_host("192.168.10.5")
        cred_id = kg.add_credential("operator")
        kg.link(host_id, cred_id, EdgeType.HAS_CRED)
        result = kg.visualize_ascii()
        assert "[CRED]" in result

    def test_service_appears_in_output(self):
        """visualize_ascii() includes [SERVICE] tag for linked services. Req 7.4"""
        from phantom.db.knowledge_graph import EdgeType, NodeType
        kg = make_kg()
        host_id = kg.add_host("192.168.10.6")
        svc_id = kg._insert_node(NodeType.SERVICE, "https:443", {})
        kg.link(host_id, svc_id, EdgeType.HAS_SERVICE)
        result = kg.visualize_ascii()
        assert "[SERVICE]" in result

    def test_multiple_hosts_all_appear(self):
        """visualize_ascii() includes all hosts in the graph. Req 7.4"""
        kg = make_kg()
        kg.add_host("10.0.1.1")
        kg.add_host("10.0.1.2")
        kg.add_host("10.0.1.3")
        result = kg.visualize_ascii()
        assert "10.0.1.1" in result
        assert "10.0.1.2" in result
        assert "10.0.1.3" in result

    def test_tree_connector_present(self):
        """visualize_ascii() uses └─ connector for child nodes. Req 7.4"""
        kg = make_kg()
        host_id = kg.add_host("10.0.2.1")
        kg.add_vulnerability(host_id, "LFI", url="http://target.com/file")
        result = kg.visualize_ascii()
        assert "└─" in result


class TestJsonExport:
    """Test JSON export. Requirements 7.5, 7.6"""

    def test_export_returns_dict(self):
        """export_to_json() returns a dict. Req 7.5"""
        kg = make_kg()
        result = kg.export_to_json()
        assert isinstance(result, dict)

    def test_export_has_required_keys(self):
        """export_to_json() dict contains nodes, edges, attack_paths. Req 7.5"""
        kg = make_kg()
        result = kg.export_to_json()
        assert "nodes" in result
        assert "edges" in result
        assert "attack_paths" in result

    def test_export_empty_graph(self):
        """export_to_json() on empty graph returns empty lists. Req 7.5"""
        kg = make_kg()
        result = kg.export_to_json()
        assert result["nodes"] == []
        assert result["edges"] == []
        assert result["attack_paths"] == []

    def test_export_nodes_present(self):
        """export_to_json() includes all added nodes. Req 7.5"""
        kg = make_kg()
        kg.add_host("10.60.0.1")
        kg.add_host("10.60.0.2")
        result = kg.export_to_json()
        assert len(result["nodes"]) == 2

    def test_export_edges_present(self):
        """export_to_json() includes all edges. Req 7.5"""
        kg = make_kg()
        host_id = kg.add_host("10.60.0.3")
        kg.add_vulnerability(host_id, "SQLi", url="http://e.com/1")
        result = kg.export_to_json()
        # The HAS_VULN edge plus the vuln node should be present
        assert len(result["edges"]) >= 1

    def test_export_attack_paths_present(self):
        """export_to_json() includes all attack paths. Req 7.5"""
        kg = make_kg()
        kg.add_attack_path([1, 2, 3], score=8.0, description="chain")
        result = kg.export_to_json()
        assert len(result["attack_paths"]) == 1

    def test_export_is_json_serializable(self):
        """export_to_json() result can be serialised to JSON without error. Req 7.6"""
        import json
        kg = make_kg()
        host_id = kg.add_host("10.60.0.4", hostname="db-server", os="Ubuntu")
        kg.add_vulnerability(host_id, "SQLi", url="http://f.com/login", severity="critical")
        kg.add_attack_path([host_id], score=9.9, description="direct")
        result = kg.export_to_json()
        # Should not raise
        serialised = json.dumps(result)
        parsed = json.loads(serialised)
        assert parsed["nodes"] == result["nodes"]
        assert parsed["edges"] == result["edges"]
        assert parsed["attack_paths"] == result["attack_paths"]

    def test_export_node_fields(self):
        """export_to_json() node dicts contain id, type, label, properties. Req 7.5"""
        kg = make_kg()
        kg.add_host("10.60.0.5")
        result = kg.export_to_json()
        node = result["nodes"][0]
        for field in ("id", "type", "label", "properties"):
            assert field in node, f"Missing node field: {field}"

    def test_export_edge_fields(self):
        """export_to_json() edge dicts contain id, source_id, target_id, edge_type, properties. Req 7.5"""
        kg = make_kg()
        host_id = kg.add_host("10.60.0.6")
        kg.add_vulnerability(host_id, "RCE", url="http://g.com/exec")
        result = kg.export_to_json()
        edge = result["edges"][0]
        for field in ("id", "source_id", "target_id", "edge_type", "properties"):
            assert field in edge, f"Missing edge field: {field}"

    def test_export_attack_path_fields(self):
        """export_to_json() attack_path dicts contain id, path, score, description. Req 7.5"""
        kg = make_kg()
        kg.add_attack_path([1, 2], score=5.0, description="test")
        result = kg.export_to_json()
        ap = result["attack_paths"][0]
        for field in ("id", "path", "score", "description"):
            assert field in ap, f"Missing attack_path field: {field}"

    def test_export_round_trip_preserves_data(self):
        """export_to_json() preserves all data accurately. Req 7.6"""
        import json
        kg = make_kg()
        host_id = kg.add_host("10.70.0.1", hostname="target", os="Windows")
        vuln_id = kg.add_vulnerability(host_id, "EternalBlue", url="", severity="critical", cve="CVE-2017-0144")
        kg.add_attack_path([host_id, vuln_id], score=10.0, description="ms17-010")

        exported = kg.export_to_json()
        # Re-parse via JSON to confirm round-trip
        reparsed = json.loads(json.dumps(exported))

        host_node = next(n for n in reparsed["nodes"] if n["label"] == "10.70.0.1")
        assert host_node["type"] == "host"
        assert host_node["properties"]["hostname"] == "target"

        ap = reparsed["attack_paths"][0]
        assert ap["score"] == 10.0
        assert ap["description"] == "ms17-010"
