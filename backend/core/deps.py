"""
deps.py — FastAPI dependency shim.
All auth logic lives in auth_service.py; this file just re-exports
so existing `from backend.core.deps import ...` statements keep working.
"""
from backend.core.auth_service import (
    SECRET_KEY,
    ALGORITHM,
    oauth2_scheme,
    get_current_user,
    require_role,
)

__all__ = [
    "SECRET_KEY",
    "ALGORITHM",
    "oauth2_scheme",
    "get_current_user",
    "require_role",
]
