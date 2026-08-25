"""Shared municipal status / role constants (API + store)."""

from __future__ import annotations

from typing import FrozenSet, Literal

EventStatus = Literal[
    "under_review",
    "confirmed",
    "false_positive",
    "work_order_created",
    "resolved",
    "archived",
]

WorkOrderStatus = Literal[
    "created",
    "assigned",
    "in_progress",
    "resolved",
    "cancelled",
]

EVENT_STATUSES: FrozenSet[str] = frozenset(
    {
        "under_review",
        "confirmed",
        "false_positive",
        "work_order_created",
        "resolved",
        "archived",
    }
)

# Operator-owned statuses that ingest must not overwrite
PROTECTED_EVENT_STATUSES: FrozenSet[str] = frozenset(
    {
        "confirmed",
        "false_positive",
        "work_order_created",
        "resolved",
        "archived",
    }
)

WORK_ORDER_STATUSES: FrozenSet[str] = frozenset(
    {
        "created",
        "assigned",
        "in_progress",
        "resolved",
        "cancelled",
    }
)

USER_ROLES: FrozenSet[str] = frozenset({"viewer", "operator", "admin", "superadmin"})
OPERATOR_ROLES: FrozenSet[str] = frozenset({"operator", "admin", "superadmin"})
ADMIN_ROLES: FrozenSet[str] = frozenset({"admin", "superadmin"})
VIEWER_ROLES: FrozenSet[str] = frozenset({"viewer", "operator", "admin", "superadmin"})
SUPERADMIN_ROLES: FrozenSet[str] = frozenset({"superadmin"})
RESERVED_USERNAMES: FrozenSet[str] = frozenset({"api_key", "anonymous", "system"})
