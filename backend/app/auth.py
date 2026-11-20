"""Very simple role check for development.

The frontend sends two headers: X-User-Role and X-User-Name.
This is NOT real security. Real login (e.g. Azure AD / JWT) can replace this later,
the endpoints only depend on `require_sourcing_manager`.
"""
from dataclasses import dataclass

from fastapi import Depends, Header, HTTPException

SOURCING_MANAGER = "SOURCING_MANAGER"
VALID_ROLES = {"SOURCING_MANAGER", "HIRING_MANAGER", "CONTRACT_MANAGER"}


@dataclass
class User:
    name: str
    role: str


def current_user(
    x_user_role: str = Header(default="HIRING_MANAGER"),
    x_user_name: str = Header(default="anonymous"),
) -> User:
    if x_user_role not in VALID_ROLES:
        raise HTTPException(status_code=401, detail="Unknown user role")
    return User(name=x_user_name, role=x_user_role)


def require_sourcing_manager(user: User = Depends(current_user)) -> User:
    if user.role != SOURCING_MANAGER:
        raise HTTPException(status_code=403, detail="Only a Sourcing Manager can change the role catalogue")
    return user
