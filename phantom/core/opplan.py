"""
PhantomStrike OPPLAN (Operational Plan) System
Single source of truth for all engagement objectives.
Manages the full lifecycle from AI-generated plan through execution with dependency resolution.
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

import yaml

logger = logging.getLogger("phantom.opplan")


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------

class ObjPhase(str):
    """Attack phase enumeration."""
    RECON = "recon"
    SCAN = "scan"
    EXPLOIT = "exploit"
    POST_EXPLOIT = "post_exploit"
    LATERAL_MOVE = "lateral_move"
    EXFIL = "exfil"
    CLEANUP = "cleanup"
    REPORT = "report"

    # Make it behave like an enum for comparison purposes
    _values = (
        "recon", "scan", "exploit", "post_exploit",
        "lateral_move", "exfil", "cleanup", "report",
    )

    def __new__(cls, value: str):
        if value not in cls._values:
            raise ValueError(f"Invalid ObjPhase: {value!r}. Must be one of {cls._values}")
        obj = str.__new__(cls, value)
        return obj

    def __repr__(self) -> str:
        return f"ObjPhase({str(self)!r})"

    @classmethod
    def values(cls) -> tuple:
        return cls._values


# Re-expose as module-level constants for convenience
ObjPhase.RECON = ObjPhase("recon")
ObjPhase.SCAN = ObjPhase("scan")
ObjPhase.EXPLOIT = ObjPhase("exploit")
ObjPhase.POST_EXPLOIT = ObjPhase("post_exploit")
ObjPhase.LATERAL_MOVE = ObjPhase("lateral_move")
ObjPhase.EXFIL = ObjPhase("exfil")
ObjPhase.CLEANUP = ObjPhase("cleanup")
ObjPhase.REPORT = ObjPhase("report")


class ObjStatus(str):
    """Objective lifecycle state enumeration."""
    PENDING = "pending"
    READY = "ready"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"

    _values = ("pending", "ready", "in_progress", "completed", "failed", "skipped")

    def __new__(cls, value: str):
        if value not in cls._values:
            raise ValueError(f"Invalid ObjStatus: {value!r}. Must be one of {cls._values}")
        obj = str.__new__(cls, value)
        return obj

    def __repr__(self) -> str:
        return f"ObjStatus({str(self)!r})"

    @classmethod
    def values(cls) -> tuple:
        return cls._values


# Re-expose as module-level constants
ObjStatus.PENDING = ObjStatus("pending")
ObjStatus.READY = ObjStatus("ready")
ObjStatus.IN_PROGRESS = ObjStatus("in_progress")
ObjStatus.COMPLETED = ObjStatus("completed")
ObjStatus.FAILED = ObjStatus("failed")
ObjStatus.SKIPPED = ObjStatus("skipped")


# ---------------------------------------------------------------------------
# Objective dataclass
# ---------------------------------------------------------------------------

@dataclass
class Objective:
    """A single unit of work within an OPPLAN."""
    id: str
    title: str
    description: str = ""
    phase: str = ObjPhase.RECON          # accepts ObjPhase or plain str
    status: str = ObjStatus.PENDING      # accepts ObjStatus or plain str
    assigned_agent: str = ""
    dependencies: List[str] = field(default_factory=list)   # list of objective IDs
    result: Dict[str, Any] = field(default_factory=dict)    # populated after completion
    created_at: datetime = field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to a plain dict suitable for YAML output."""
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "phase": str(self.phase),
            "status": str(self.status),
            "assigned_agent": self.assigned_agent,
            "dependencies": list(self.dependencies),
            "result": dict(self.result),
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Objective":
        """Deserialize from a plain dict."""
        created_at = data.get("created_at")
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at)
        elif created_at is None:
            created_at = datetime.now()

        completed_at = data.get("completed_at")
        if isinstance(completed_at, str):
            completed_at = datetime.fromisoformat(completed_at)

        return cls(
            id=data["id"],
            title=data.get("title", ""),
            description=data.get("description", ""),
            phase=data.get("phase", ObjPhase.RECON),
            status=data.get("status", ObjStatus.PENDING),
            assigned_agent=data.get("assigned_agent", ""),
            dependencies=list(data.get("dependencies", [])),
            result=dict(data.get("result", {})),
            created_at=created_at,
            completed_at=completed_at,
        )


# ---------------------------------------------------------------------------
# OPPLAN dataclass
# ---------------------------------------------------------------------------

@dataclass
class OPPLAN:
    """
    Operational Plan — ordered, dependency-aware list of engagement objectives.
    Objectives are stored in a dict keyed by objective ID for O(1) lookup.
    """
    engagement_id: str
    target: str
    objectives: Dict[str, Objective] = field(default_factory=dict)

    # -----------------------------------------------------------------------
    # Internal helpers
    # -----------------------------------------------------------------------

    def _has_cycle(self, new_obj: Objective) -> bool:
        """
        DFS cycle detection.
        Returns True if adding *new_obj* to the current objectives dict would
        create a cycle.  The new objective is treated as already present for
        the purpose of the check (but has NOT been inserted yet).
        """
        # Build a temporary adjacency map that includes the new node
        adj: Dict[str, List[str]] = {
            oid: list(obj.dependencies)
            for oid, obj in self.objectives.items()
        }
        adj[new_obj.id] = list(new_obj.dependencies)

        # Standard DFS with three-colour marking
        WHITE, GRAY, BLACK = 0, 1, 2
        colour: Dict[str, int] = {oid: WHITE for oid in adj}

        def dfs(node: str) -> bool:
            colour[node] = GRAY
            for neighbour in adj.get(node, []):
                if neighbour not in colour:
                    # Dependency references a node not in the graph — not a cycle
                    continue
                if colour[neighbour] == GRAY:
                    return True   # back-edge → cycle
                if colour[neighbour] == WHITE and dfs(neighbour):
                    return True
            colour[node] = BLACK
            return False

        for node in list(colour.keys()):
            if colour[node] == WHITE:
                if dfs(node):
                    return True
        return False

    # -----------------------------------------------------------------------
    # Public API
    # -----------------------------------------------------------------------

    def add_objective(self, obj: Objective) -> None:
        """
        Add an objective to the OPPLAN.

        Raises ValueError if:
        - obj.id already exists in the OPPLAN
        - adding obj would create a dependency cycle

        The OPPLAN remains in its prior valid state if ValueError is raised.
        """
        if obj.id in self.objectives:
            raise ValueError(
                f"Objective with id {obj.id!r} already exists in the OPPLAN."
            )

        if self._has_cycle(obj):
            raise ValueError(
                f"Adding objective {obj.id!r} would create a circular dependency cycle."
            )

        self.objectives[obj.id] = obj

    def get_objective(self, obj_id: str) -> Optional[Objective]:
        """Return the Objective with the given ID, or None if not found."""
        return self.objectives.get(obj_id)

    def list_objectives(self) -> List[Objective]:
        """Return all objectives as a list."""
        return list(self.objectives.values())

    def update_objective(self, obj_id: str, **kwargs: Any) -> None:
        """Update fields on an existing objective."""
        obj = self.objectives.get(obj_id)
        if obj is None:
            raise KeyError(f"Objective {obj_id!r} not found in OPPLAN.")
        for key, value in kwargs.items():
            if hasattr(obj, key):
                setattr(obj, key, value)
            else:
                raise AttributeError(f"Objective has no field {key!r}.")

    def get_ready_objectives(self) -> List[Objective]:
        """
        Return objectives that are ready to execute.

        An objective is ready when:
        - Its status is PENDING
        - ALL of its dependency IDs reference objectives with status COMPLETED

        This method never mutates any objective's status.
        """
        completed_ids = {
            oid
            for oid, obj in self.objectives.items()
            if str(obj.status) == ObjStatus.COMPLETED
        }

        ready: List[Objective] = []
        for obj in self.objectives.values():
            if str(obj.status) != ObjStatus.PENDING:
                continue
            if all(dep_id in completed_ids for dep_id in obj.dependencies):
                ready.append(obj)
        return ready

    def expand_objective(self, obj_id: str, sub_objectives: List[Objective]) -> None:
        """
        Add sub-objectives that depend on the parent objective.
        Each sub-objective automatically gets the parent's ID added to its
        dependencies (if not already present).
        """
        if obj_id not in self.objectives:
            raise KeyError(f"Parent objective {obj_id!r} not found in OPPLAN.")

        for sub_obj in sub_objectives:
            if obj_id not in sub_obj.dependencies:
                sub_obj.dependencies = list(sub_obj.dependencies) + [obj_id]
            self.add_objective(sub_obj)

    def mark_complete(self, obj_id: str, result: Dict[str, Any] = None) -> None:
        """Mark an objective as COMPLETED, recording the result and timestamp."""
        obj = self.objectives.get(obj_id)
        if obj is None:
            raise KeyError(f"Objective {obj_id!r} not found in OPPLAN.")
        obj.status = ObjStatus.COMPLETED
        obj.completed_at = datetime.now()
        obj.result = dict(result) if result is not None else {}

    def mark_failed(self, obj_id: str, error: str = "") -> None:
        """Mark an objective as FAILED, storing the error message in result."""
        obj = self.objectives.get(obj_id)
        if obj is None:
            raise KeyError(f"Objective {obj_id!r} not found in OPPLAN.")
        obj.status = ObjStatus.FAILED
        obj.result = {"error": error}

    # -----------------------------------------------------------------------
    # Serialization
    # -----------------------------------------------------------------------

    def to_yaml(self) -> str:
        """Serialize the OPPLAN to a YAML string."""
        data: Dict[str, Any] = {
            "engagement_id": self.engagement_id,
            "target": self.target,
            "objectives": [obj.to_dict() for obj in self.objectives.values()],
        }
        return yaml.dump(data, default_flow_style=False, allow_unicode=True, sort_keys=False)

    @classmethod
    def from_yaml(cls, yaml_str: str) -> "OPPLAN":
        """Deserialize an OPPLAN from a YAML string produced by to_yaml()."""
        data = yaml.safe_load(yaml_str)
        opplan = cls(
            engagement_id=data["engagement_id"],
            target=data["target"],
        )
        for obj_data in data.get("objectives", []):
            obj = Objective.from_dict(obj_data)
            # Bypass cycle detection for deserialization — trust the stored data
            opplan.objectives[obj.id] = obj
        return opplan

    def save(self, base_dir: str = "~/.phantom-strike/oplans") -> str:
        """
        Write the OPPLAN YAML to {base_dir}/{engagement_id}.yaml.
        Returns the absolute file path.
        """
        expanded = os.path.expanduser(base_dir)
        os.makedirs(expanded, exist_ok=True)
        path = os.path.join(expanded, f"{self.engagement_id}.yaml")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(self.to_yaml())
        logger.info(f"[OPPLAN] Saved to {path}")
        return path

    @classmethod
    def load(cls, path: str) -> "OPPLAN":
        """Load an OPPLAN from a YAML file path."""
        expanded = os.path.expanduser(path)
        with open(expanded, "r", encoding="utf-8") as fh:
            yaml_str = fh.read()
        return cls.from_yaml(yaml_str)


# ---------------------------------------------------------------------------
# OPPLANMiddleware
# ---------------------------------------------------------------------------

class OPPLANMiddleware:
    """
    Injects OPPLAN state into AI calls and provides CRUD tool definitions
    for AI function-calling (OpenAI-compatible format).
    """

    def __init__(self, opplan: OPPLAN):
        self.opplan = opplan

    def get_context_for_agent(self, agent_name: str) -> Dict[str, Any]:
        """
        Return a context dict containing objectives relevant to the given agent.
        Includes all objectives assigned to the agent plus all completed objectives
        (for dependency context).
        """
        all_objs = self.opplan.list_objectives()
        assigned = [
            obj.to_dict()
            for obj in all_objs
            if obj.assigned_agent == agent_name
        ]
        completed = [
            obj.to_dict()
            for obj in all_objs
            if str(obj.status) == ObjStatus.COMPLETED
        ]
        pending = [
            obj.to_dict()
            for obj in all_objs
            if str(obj.status) == ObjStatus.PENDING
        ]
        return {
            "engagement_id": self.opplan.engagement_id,
            "target": self.opplan.target,
            "assigned_objectives": assigned,
            "completed_objectives": completed,
            "pending_objectives": pending,
            "ready_objectives": [o.to_dict() for o in self.opplan.get_ready_objectives()],
        }

    def get_ai_tools(self) -> List[Dict[str, Any]]:
        """
        Return a list of tool definitions in OpenAI function-calling format.
        These allow an AI agent to interact with the OPPLAN programmatically.
        """
        return [
            {
                "type": "function",
                "function": {
                    "name": "opplan_add_objective",
                    "description": "Add a new objective to the OPPLAN.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "id": {"type": "string", "description": "Unique objective ID"},
                            "title": {"type": "string", "description": "Short title"},
                            "description": {"type": "string", "description": "Detailed description"},
                            "phase": {
                                "type": "string",
                                "enum": list(ObjPhase.values()),
                                "description": "Attack phase",
                            },
                            "dependencies": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "List of objective IDs this depends on",
                            },
                        },
                        "required": ["id", "title", "phase"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "opplan_mark_complete",
                    "description": "Mark an objective as completed with optional result data.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "obj_id": {"type": "string", "description": "Objective ID to complete"},
                            "result": {
                                "type": "object",
                                "description": "Result data from the completed objective",
                            },
                        },
                        "required": ["obj_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "opplan_mark_failed",
                    "description": "Mark an objective as failed with an error message.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "obj_id": {"type": "string", "description": "Objective ID to fail"},
                            "error": {"type": "string", "description": "Error message"},
                        },
                        "required": ["obj_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "opplan_get_ready_objectives",
                    "description": "Get all objectives that are ready to execute (PENDING with all deps COMPLETED).",
                    "parameters": {
                        "type": "object",
                        "properties": {},
                        "required": [],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "opplan_list_objectives",
                    "description": "List all objectives in the OPPLAN.",
                    "parameters": {
                        "type": "object",
                        "properties": {},
                        "required": [],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "opplan_update_objective",
                    "description": "Update fields on an existing objective.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "obj_id": {"type": "string", "description": "Objective ID to update"},
                            "status": {"type": "string", "description": "New status value"},
                            "assigned_agent": {"type": "string", "description": "Agent name to assign"},
                            "description": {"type": "string", "description": "Updated description"},
                        },
                        "required": ["obj_id"],
                    },
                },
            },
        ]
