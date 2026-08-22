"""Minimal deterministic control-plane state machine.

No network calls, secret handling, or production mutations are performed here.
It is intentionally provider-agnostic so execution adapters can be added behind
explicit permission gates.
"""
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class State(str, Enum):
    INBOX = "INBOX"
    PLAN = "PLAN"
    ROUTE = "ROUTE"
    EXECUTE = "EXECUTE"
    QA = "QA"
    VERIFY = "VERIFY"
    EVIDENCE = "EVIDENCE"
    UPDATE = "UPDATE"
    NEXT = "NEXT"
    BLOCKED = "BLOCKED"
    DONE = "DONE"


ALLOWED = {
    State.INBOX: {State.PLAN, State.BLOCKED},
    State.PLAN: {State.ROUTE, State.BLOCKED},
    State.ROUTE: {State.EXECUTE, State.BLOCKED},
    State.EXECUTE: {State.QA, State.BLOCKED},
    State.QA: {State.VERIFY, State.BLOCKED},
    State.VERIFY: {State.EVIDENCE, State.EXECUTE, State.BLOCKED},
    State.EVIDENCE: {State.UPDATE, State.BLOCKED},
    State.UPDATE: {State.NEXT, State.BLOCKED},
    State.NEXT: {State.DONE, State.PLAN, State.BLOCKED},
    State.BLOCKED: {State.PLAN, State.EXECUTE},
    State.DONE: set(),
}


@dataclass
class Task:
    task_id: str
    objective: str
    state: State = State.INBOX
    permission: str = "read_only"
    evidence: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def transition(self, target: State) -> None:
        if target not in ALLOWED[self.state]:
            raise ValueError(f"Invalid transition: {self.state} -> {target}")
        if target == State.DONE and not self.evidence:
            raise ValueError("DONE requires evidence")
        self.state = target

    def add_evidence(self, reference: str) -> None:
        if not reference.strip():
            raise ValueError("Evidence reference cannot be empty")
        self.evidence.append(reference)

    def fail_verification(self, reason: str) -> None:
        self.metadata["verification_failure"] = reason
        self.transition(State.EXECUTE)


def route_language(kind: str) -> str:
    mapping = {
        "web": "typescript",
        "app": "typescript",
        "api": "typescript",
        "integration": "typescript",
        "automation": "python",
        "ai": "python",
        "data": "python",
        "database": "sql",
        "ci": "shell",
        "infrastructure": "shell",
    }
    return mapping.get(kind.lower(), "python")
