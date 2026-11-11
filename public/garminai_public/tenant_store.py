"""Demonstration of fail-closed principal-scoped access. Not wired into MCP.

The absence of real OAuth means no athlete data belongs in this store yet.
"""
from dataclasses import dataclass

@dataclass(frozen=True)
class Principal:
    subject: str

    def __post_init__(self):
        if not self.subject or not self.subject.strip():
            raise ValueError('Verified non-empty subject required')

class IsolatedActivityStore:
    """Illustrative in-memory store; must be replaced with DB row-level controls."""
    def __init__(self):
        self._rows = {}

    def add(self, principal: Principal, activity_id: str, record: dict):
        if not isinstance(principal, Principal):
            raise PermissionError('Verified principal required')
        key = (principal.subject, activity_id)
        self._rows[key] = dict(record)

    def get(self, principal: Principal, activity_id: str):
        if not isinstance(principal, Principal):
            raise PermissionError('Verified principal required')
        row = self._rows.get((principal.subject, activity_id))
        return dict(row) if row is not None else None

    def list(self, principal: Principal):
        if not isinstance(principal, Principal):
            raise PermissionError('Verified principal required')
        return [dict(row) for (subject, _), row in self._rows.items() if subject == principal.subject]
