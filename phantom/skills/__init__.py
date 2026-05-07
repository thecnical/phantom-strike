"""
SkillLibrary — YAML-based knowledge base of offensive techniques.

Agents load only frontmatter initially (progressive disclosure) and fetch
full content on demand via load_skill().

Requirements: 11.1–11.7
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

import yaml

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class SkillFrontmatter:
    """
    Lightweight metadata parsed from the YAML front-matter block of a skill
    file.  Full technique content is loaded separately via load_skill().

    Requirements: 11.1
    """

    name: str
    description: str
    phase: str
    mitre_attack: List[str] = field(default_factory=list)
    module: str = ""
    tools: List[str] = field(default_factory=list)
    opsec_level: int = 3
    prerequisites: List[str] = field(default_factory=list)
    file_path: str = ""


# ---------------------------------------------------------------------------
# SkillLibrary
# ---------------------------------------------------------------------------

class SkillLibrary:
    """
    Loads and indexes offensive technique YAML files from a skills directory.

    Each YAML file uses a front-matter block (delimited by ``---``) followed
    by free-form Markdown technique content.  The library parses only the
    front-matter on startup and loads full content on demand.

    Requirements: 11.1–11.7
    """

    def __init__(self, skills_dir: Optional[str] = None) -> None:
        if skills_dir is None:
            # Default: resolve relative to this file's location
            skills_dir = str(Path(__file__).parent)
        self.skills_dir = Path(skills_dir)
        # Lazy cache: name -> SkillFrontmatter
        self._frontmatter_cache: Optional[List[SkillFrontmatter]] = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load_all_frontmatter(self) -> List[SkillFrontmatter]:
        """
        Parse only the YAML front-matter section of every skill file and
        return a list of SkillFrontmatter objects.

        Malformed files are skipped with a warning (Req 11.7).

        Requirements: 11.1
        """
        if self._frontmatter_cache is not None:
            return list(self._frontmatter_cache)

        results: List[SkillFrontmatter] = []
        for yaml_path in sorted(self.skills_dir.rglob("*.yaml")):
            fm = self._parse_frontmatter(yaml_path)
            if fm is not None:
                results.append(fm)

        self._frontmatter_cache = results
        return list(results)

    def load_skill(self, skill_name: str) -> str:
        """
        Return the full raw YAML content of the skill file whose ``name``
        front-matter field matches *skill_name*.

        Returns an empty string if the skill is not found.

        Requirements: 11.2
        """
        for yaml_path in self.skills_dir.rglob("*.yaml"):
            fm = self._parse_frontmatter(yaml_path)
            if fm is not None and fm.name == skill_name:
                try:
                    return yaml_path.read_text(encoding="utf-8")
                except OSError as exc:
                    logger.warning("Could not read skill file %s: %s", yaml_path, exc)
                    return ""
        return ""

    def filter_by_phase(self, phase: str) -> List[SkillFrontmatter]:
        """
        Return SkillFrontmatter objects whose ``phase`` equals *phase*.

        Requirements: 11.3
        """
        return [s for s in self.load_all_frontmatter() if s.phase == phase]

    def filter_by_mitre(self, mitre_id: str) -> List[SkillFrontmatter]:
        """
        Return SkillFrontmatter objects whose ``mitre_attack`` list contains
        *mitre_id*.

        Requirements: 11.4
        """
        return [s for s in self.load_all_frontmatter() if mitre_id in s.mitre_attack]

    def filter_by_opsec(self, max_level: int) -> List[SkillFrontmatter]:
        """
        Return SkillFrontmatter objects whose ``opsec_level`` is less than or
        equal to *max_level*.

        Note: per the task spec the parameter is named ``max_level`` (filter
        skills with opsec_level <= max_level, i.e. at most that noisy).
        The design doc names the parameter ``min_level`` but the task
        description says "filters skills by opsec level (1-5)" with the
        parameter ``max_level: int``.  We implement the task spec.

        Requirements: 11.5
        """
        return [s for s in self.load_all_frontmatter() if s.opsec_level <= max_level]

    def search(self, query: str) -> List[SkillFrontmatter]:
        """
        Return SkillFrontmatter objects whose ``name`` or ``description``
        contains *query* (case-insensitive).

        Requirements: 11.6
        """
        q = query.lower()
        return [
            s for s in self.load_all_frontmatter()
            if q in s.name.lower() or q in s.description.lower()
        ]

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _parse_frontmatter(self, path: Path) -> Optional[SkillFrontmatter]:
        """
        Parse the YAML front-matter block from *path*.

        The front-matter is the content between the first and second ``---``
        delimiters.  If the file is malformed or missing required fields, log
        a warning and return None.

        Requirements: 11.7
        """
        try:
            raw = path.read_text(encoding="utf-8")
        except OSError as exc:
            logger.warning("Cannot read skill file %s: %s", path, exc)
            return None

        # Extract front-matter between first pair of --- delimiters
        parts = raw.split("---")
        if len(parts) < 3:
            # No proper front-matter block
            logger.warning(
                "Skill file %s has no valid front-matter block — skipping", path
            )
            return None

        fm_text = parts[1].strip()
        try:
            data: Dict = yaml.safe_load(fm_text) or {}
        except yaml.YAMLError as exc:
            logger.warning("Malformed YAML front-matter in %s: %s — skipping", path, exc)
            return None

        if not isinstance(data, dict):
            logger.warning("Front-matter in %s is not a mapping — skipping", path)
            return None

        name = data.get("name", "")
        if not name:
            logger.warning("Skill file %s missing required 'name' field — skipping", path)
            return None

        return SkillFrontmatter(
            name=str(name),
            description=str(data.get("description", "")),
            phase=str(data.get("phase", "")),
            mitre_attack=list(data.get("mitre_ids", data.get("mitre_attack", []))),
            module=str(data.get("module", "")),
            tools=list(data.get("tools", [])),
            opsec_level=int(data.get("opsec_level", 3)),
            prerequisites=list(data.get("prerequisites", [])),
            file_path=str(path),
        )


__all__ = ["SkillLibrary", "SkillFrontmatter"]
