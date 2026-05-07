"""
PhantomStrike v3.0 — SkillLibrary Tests
Run with: pytest tests/test_v3_skills.py -v

Includes:
  - Unit tests for SkillLibrary (task 1.16)

Requirements: 11.1–11.7
"""

import logging
import pytest
from pathlib import Path
from tempfile import TemporaryDirectory

from phantom.skills import SkillLibrary, SkillFrontmatter


# ─── Fixtures ─────────────────────────────────────────────────────────────────


@pytest.fixture
def temp_skills_dir():
    """Create a temporary directory with test skill YAML files."""
    with TemporaryDirectory() as tmpdir:
        skills_path = Path(tmpdir)
        
        # Create subdirectories
        (skills_path / "recon").mkdir()
        (skills_path / "exploit").mkdir()
        (skills_path / "post").mkdir()
        
        # Valid skill 1: recon phase
        (skills_path / "recon" / "test-recon-1.yaml").write_text(
            """---
name: test-recon-1
description: Test reconnaissance skill for subdomain enumeration
phase: recon
mitre_ids: [T1595.003, T1590.001]
opsec_level: 2
module: phantom-osint
tools: [subfinder, amass]
prerequisites: []
---
# Test Recon Skill 1

This is the full content of the test recon skill.
It includes technique details and commands.
"""
        )
        
        # Valid skill 2: recon phase, different opsec
        (skills_path / "recon" / "test-recon-2.yaml").write_text(
            """---
name: test-recon-2
description: Test passive OSINT gathering
phase: recon
mitre_ids: [T1590.001]
opsec_level: 4
module: phantom-osint
tools: [shodan, censys]
prerequisites: []
---
# Test Recon Skill 2

Passive reconnaissance content.
"""
        )
        
        # Valid skill 3: exploit phase
        (skills_path / "exploit" / "test-exploit-1.yaml").write_text(
            """---
name: test-exploit-1
description: Test SQL injection exploitation
phase: exploit
mitre_ids: [T1190, T1059.004]
opsec_level: 2
module: phantom-web
tools: [sqlmap]
prerequisites: [web_application_url]
---
# Test Exploit Skill 1

SQL injection technique content.
"""
        )
        
        # Valid skill 4: post phase
        (skills_path / "post" / "test-post-1.yaml").write_text(
            """---
name: test-post-1
description: Test post-exploitation credential dumping
phase: post
mitre_ids: [T1003.001]
opsec_level: 3
module: phantom-post
tools: [mimikatz, procdump]
prerequisites: [admin_access]
---
# Test Post Skill 1

Post-exploitation content.
"""
        )
        
        # Malformed skill 1: no frontmatter delimiters
        (skills_path / "recon" / "malformed-1.yaml").write_text(
            """name: malformed-1
description: This has no frontmatter delimiters
phase: recon
"""
        )
        
        # Malformed skill 2: invalid YAML in frontmatter
        (skills_path / "exploit" / "malformed-2.yaml").write_text(
            """---
name: malformed-2
description: "Unclosed quote
phase: exploit
---
Content here
"""
        )
        
        # Malformed skill 3: missing required 'name' field
        (skills_path / "post" / "malformed-3.yaml").write_text(
            """---
description: This skill has no name field
phase: post
---
Content here
"""
        )
        
        yield skills_path


@pytest.fixture
def skill_library(temp_skills_dir):
    """Return a SkillLibrary instance pointing to the temp skills directory."""
    return SkillLibrary(skills_dir=str(temp_skills_dir))


# ─── Unit Tests ───────────────────────────────────────────────────────────────


class TestLoadAllFrontmatter:
    """
    Req 11.1 — load_all_frontmatter() returns list of SkillFrontmatter objects.
    """
    
    def test_returns_list_of_skill_frontmatter(self, skill_library):
        """load_all_frontmatter() returns a list of SkillFrontmatter objects."""
        result = skill_library.load_all_frontmatter()
        assert isinstance(result, list)
        assert len(result) > 0
        for item in result:
            assert isinstance(item, SkillFrontmatter)
    
    def test_loads_all_valid_skills(self, skill_library):
        """load_all_frontmatter() loads all valid skill files."""
        result = skill_library.load_all_frontmatter()
        # We have 4 valid skills in the fixture
        assert len(result) == 4
        
        names = {s.name for s in result}
        assert names == {"test-recon-1", "test-recon-2", "test-exploit-1", "test-post-1"}
    
    def test_frontmatter_fields_populated(self, skill_library):
        """SkillFrontmatter objects have all required fields populated."""
        result = skill_library.load_all_frontmatter()
        skill = next(s for s in result if s.name == "test-recon-1")
        
        assert skill.name == "test-recon-1"
        assert skill.description == "Test reconnaissance skill for subdomain enumeration"
        assert skill.phase == "recon"
        assert skill.mitre_attack == ["T1595.003", "T1590.001"]
        assert skill.opsec_level == 2
        assert skill.module == "phantom-osint"
        assert skill.tools == ["subfinder", "amass"]
        assert skill.prerequisites == []
        assert skill.file_path != ""
    
    def test_caching_returns_same_list(self, skill_library):
        """Subsequent calls return cached results."""
        result1 = skill_library.load_all_frontmatter()
        result2 = skill_library.load_all_frontmatter()
        # Should return the same list object (cached)
        assert result1 == result2


class TestLoadSkill:
    """
    Req 11.2 — load_skill() returns full YAML content of a skill file.
    """
    
    def test_returns_full_yaml_content(self, skill_library):
        """load_skill() returns the complete YAML file content as a string."""
        content = skill_library.load_skill("test-recon-1")
        assert isinstance(content, str)
        assert len(content) > 0
        
        # Should contain frontmatter
        assert "name: test-recon-1" in content
        assert "phase: recon" in content
        
        # Should contain full content after frontmatter
        assert "# Test Recon Skill 1" in content
        assert "This is the full content of the test recon skill." in content
    
    def test_returns_empty_string_for_nonexistent_skill(self, skill_library):
        """load_skill() returns empty string when skill name not found."""
        content = skill_library.load_skill("nonexistent-skill")
        assert content == ""
    
    def test_loads_different_skills(self, skill_library):
        """load_skill() can load different skills by name."""
        content1 = skill_library.load_skill("test-recon-1")
        content2 = skill_library.load_skill("test-exploit-1")
        
        assert content1 != content2
        assert "test-recon-1" in content1
        assert "test-exploit-1" in content2


class TestFilterByPhase:
    """
    Req 11.3 — filter_by_phase() returns only skills with matching phase.
    """
    
    def test_returns_only_matching_phase(self, skill_library):
        """filter_by_phase() returns only skills with the specified phase."""
        recon_skills = skill_library.filter_by_phase("recon")
        assert len(recon_skills) == 2
        for skill in recon_skills:
            assert skill.phase == "recon"
    
    def test_returns_empty_list_for_nonexistent_phase(self, skill_library):
        """filter_by_phase() returns empty list when no skills match."""
        result = skill_library.filter_by_phase("nonexistent")
        assert result == []
    
    def test_filters_exploit_phase(self, skill_library):
        """filter_by_phase() correctly filters exploit phase."""
        exploit_skills = skill_library.filter_by_phase("exploit")
        assert len(exploit_skills) == 1
        assert exploit_skills[0].name == "test-exploit-1"
    
    def test_filters_post_phase(self, skill_library):
        """filter_by_phase() correctly filters post phase."""
        post_skills = skill_library.filter_by_phase("post")
        assert len(post_skills) == 1
        assert post_skills[0].name == "test-post-1"


class TestFilterByMitre:
    """
    Req 11.4 — filter_by_mitre() returns skills containing the MITRE ID.
    """
    
    def test_returns_skills_with_mitre_id(self, skill_library):
        """filter_by_mitre() returns skills whose mitre_attack list contains the ID."""
        result = skill_library.filter_by_mitre("T1590.001")
        assert len(result) == 2
        
        names = {s.name for s in result}
        assert names == {"test-recon-1", "test-recon-2"}
    
    def test_returns_empty_list_for_nonexistent_mitre_id(self, skill_library):
        """filter_by_mitre() returns empty list when no skills match."""
        result = skill_library.filter_by_mitre("T9999.999")
        assert result == []
    
    def test_filters_single_skill_by_unique_mitre_id(self, skill_library):
        """filter_by_mitre() returns single skill with unique MITRE ID."""
        result = skill_library.filter_by_mitre("T1003.001")
        assert len(result) == 1
        assert result[0].name == "test-post-1"
    
    def test_filters_by_mitre_id_in_multiple_ids(self, skill_library):
        """filter_by_mitre() finds skills where ID is one of multiple."""
        result = skill_library.filter_by_mitre("T1595.003")
        assert len(result) == 1
        assert result[0].name == "test-recon-1"


class TestFilterByOpsec:
    """
    Req 11.5 — filter_by_opsec() returns skills with opsec_level <= max_level.
    """
    
    def test_returns_skills_at_or_below_max_level(self, skill_library):
        """filter_by_opsec() returns skills with opsec_level <= max_level."""
        result = skill_library.filter_by_opsec(2)
        assert len(result) == 2
        
        names = {s.name for s in result}
        assert names == {"test-recon-1", "test-exploit-1"}
        
        for skill in result:
            assert skill.opsec_level <= 2
    
    def test_returns_all_skills_with_high_max_level(self, skill_library):
        """filter_by_opsec() returns all skills when max_level is high."""
        result = skill_library.filter_by_opsec(10)
        assert len(result) == 4
    
    def test_returns_empty_list_with_zero_max_level(self, skill_library):
        """filter_by_opsec() returns empty list when max_level is 0."""
        result = skill_library.filter_by_opsec(0)
        assert result == []
    
    def test_boundary_at_exact_opsec_level(self, skill_library):
        """filter_by_opsec() includes skills at exactly max_level."""
        result = skill_library.filter_by_opsec(3)
        assert len(result) == 3
        
        names = {s.name for s in result}
        assert names == {"test-recon-1", "test-exploit-1", "test-post-1"}
    
    def test_excludes_skills_above_max_level(self, skill_library):
        """filter_by_opsec() excludes skills with opsec_level > max_level."""
        result = skill_library.filter_by_opsec(3)
        
        # test-recon-2 has opsec_level=4, should be excluded
        names = {s.name for s in result}
        assert "test-recon-2" not in names


class TestSearch:
    """
    Req 11.6 — search() returns skills with query in name or description.
    """
    
    def test_search_by_name(self, skill_library):
        """search() finds skills by name substring (case-insensitive)."""
        result = skill_library.search("recon-1")
        assert len(result) == 1
        assert result[0].name == "test-recon-1"
    
    def test_search_by_description(self, skill_library):
        """search() finds skills by description substring (case-insensitive)."""
        result = skill_library.search("SQL injection")
        assert len(result) == 1
        assert result[0].name == "test-exploit-1"
    
    def test_search_case_insensitive(self, skill_library):
        """search() is case-insensitive."""
        result1 = skill_library.search("RECON")
        result2 = skill_library.search("recon")
        result3 = skill_library.search("Recon")
        
        assert len(result1) == len(result2) == len(result3) == 2
    
    def test_search_returns_empty_list_for_no_match(self, skill_library):
        """search() returns empty list when no skills match."""
        result = skill_library.search("nonexistent-query-xyz")
        assert result == []
    
    def test_search_matches_multiple_skills(self, skill_library):
        """search() returns all skills matching the query."""
        result = skill_library.search("test")
        # All 4 valid skills have "test" in their name
        assert len(result) == 4
    
    def test_search_by_partial_word(self, skill_library):
        """search() matches partial words in name or description."""
        result = skill_library.search("cred")
        assert len(result) == 1
        assert result[0].name == "test-post-1"


class TestMalformedFileHandling:
    """
    Req 11.7 — Malformed YAML files are skipped with warning, no exception.
    """
    
    def test_malformed_files_skipped(self, skill_library, caplog):
        """Malformed YAML files are skipped without raising exceptions."""
        with caplog.at_level(logging.WARNING):
            result = skill_library.load_all_frontmatter()
        
        # Only 4 valid skills should be loaded
        assert len(result) == 4
        
        # Should have logged warnings for malformed files
        assert len(caplog.records) >= 3
    
    def test_no_exception_raised_for_malformed_files(self, skill_library):
        """load_all_frontmatter() does not raise exceptions for malformed files."""
        # Should not raise any exception
        result = skill_library.load_all_frontmatter()
        assert isinstance(result, list)
    
    def test_malformed_file_without_delimiters_skipped(self, skill_library, caplog):
        """Files without frontmatter delimiters are skipped with warning."""
        with caplog.at_level(logging.WARNING):
            result = skill_library.load_all_frontmatter()
        
        # Check that a warning was logged about missing frontmatter
        warning_messages = [r.message for r in caplog.records if r.levelname == "WARNING"]
        assert any("no valid front-matter block" in msg for msg in warning_messages)
    
    def test_malformed_yaml_syntax_skipped(self, skill_library, caplog):
        """Files with invalid YAML syntax are skipped with warning."""
        with caplog.at_level(logging.WARNING):
            result = skill_library.load_all_frontmatter()
        
        # Check that a warning was logged about malformed YAML
        warning_messages = [r.message for r in caplog.records if r.levelname == "WARNING"]
        assert any("Malformed YAML" in msg for msg in warning_messages)
    
    def test_missing_required_field_skipped(self, skill_library, caplog):
        """Files missing required 'name' field are skipped with warning."""
        with caplog.at_level(logging.WARNING):
            result = skill_library.load_all_frontmatter()
        
        # Check that a warning was logged about missing name field
        warning_messages = [r.message for r in caplog.records if r.levelname == "WARNING"]
        assert any("missing required 'name' field" in msg for msg in warning_messages)


class TestEmptySkillsDirectory:
    """Test behavior with an empty skills directory."""
    
    def test_empty_directory_returns_empty_list(self):
        """load_all_frontmatter() returns empty list for empty directory."""
        with TemporaryDirectory() as tmpdir:
            lib = SkillLibrary(skills_dir=tmpdir)
            result = lib.load_all_frontmatter()
            assert result == []
    
    def test_load_skill_returns_empty_string_in_empty_directory(self):
        """load_skill() returns empty string when directory is empty."""
        with TemporaryDirectory() as tmpdir:
            lib = SkillLibrary(skills_dir=tmpdir)
            content = lib.load_skill("any-skill")
            assert content == ""


class TestDefaultSkillsDirectory:
    """Test that SkillLibrary uses default directory when none specified."""
    
    def test_default_directory_is_skills_module_location(self):
        """SkillLibrary() with no args uses phantom/skills/ directory."""
        lib = SkillLibrary()
        # Should point to the phantom/skills directory
        assert lib.skills_dir.name == "skills"
        assert lib.skills_dir.parent.name == "phantom"
    
    def test_loads_real_skills_from_default_directory(self):
        """SkillLibrary() loads real skills from phantom/skills/."""
        lib = SkillLibrary()
        result = lib.load_all_frontmatter()
        # Should load the actual skills from the codebase
        assert len(result) > 0
        assert all(isinstance(s, SkillFrontmatter) for s in result)
