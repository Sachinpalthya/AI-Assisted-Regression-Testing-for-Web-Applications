"""
sample_project/user_manager.py

A user management module demonstrating business logic patterns
including validation, CRUD operations, and role-based access control.
"""

import hashlib
import re
from datetime import datetime
from typing import Optional


class UserValidationError(Exception):
    """Raised when user data fails validation."""
    pass


class UserNotFoundError(Exception):
    """Raised when a requested user does not exist."""
    pass


class User:
    """Represents a single user in the system."""

    ROLES = {"admin", "editor", "viewer"}

    def __init__(
        self,
        user_id: int,
        username: str,
        email: str,
        role: str = "viewer",
    ):
        self.user_id   = user_id
        self.username  = username
        self.email     = email
        self.role      = role
        self.created_at = datetime.utcnow()
        self.is_active  = True

    def __repr__(self) -> str:
        return f"User(id={self.user_id}, username={self.username!r}, role={self.role!r})"

    def has_permission(self, action: str) -> bool:
        """
        Check if the user has permission for a given action.

        Permissions:
            admin  → all actions
            editor → read, write, delete_own
            viewer → read only

        Args:
            action: One of "read", "write", "delete_own", "delete_any", "admin"

        Returns:
            True if the user has permission
        """
        permissions = {
            "admin":  {"read", "write", "delete_own", "delete_any", "admin"},
            "editor": {"read", "write", "delete_own"},
            "viewer": {"read"},
        }
        return action in permissions.get(self.role, set())

    def deactivate(self) -> None:
        """Mark the user as inactive."""
        self.is_active = False


class UserManager:
    """
    In-memory user store with CRUD operations and validation.
    """

    def __init__(self):
        self._users: dict[int, User] = {}
        self._next_id = 1

    def create_user(self, username: str, email: str, role: str = "viewer") -> User:
        """
        Create and store a new user after validating inputs.

        Args:
            username: 3–50 chars, alphanumeric + underscores only
            email:    Valid email format
            role:     One of User.ROLES

        Returns:
            The created User object

        Raises:
            UserValidationError: On invalid input or duplicate username/email
        """
        self._validate_username(username)
        self._validate_email(email)
        self._validate_role(role)

        # Check for duplicates
        for user in self._users.values():
            if user.username.lower() == username.lower():
                raise UserValidationError(f"Username '{username}' is already taken")
            if user.email.lower() == email.lower():
                raise UserValidationError(f"Email '{email}' is already registered")

        user = User(
            user_id=self._next_id,
            username=username,
            email=email,
            role=role,
        )
        self._users[self._next_id] = user
        self._next_id += 1
        return user

    def get_user(self, user_id: int) -> User:
        """
        Retrieve a user by ID.

        Raises:
            UserNotFoundError: If no user with that ID exists
        """
        if user_id not in self._users:
            raise UserNotFoundError(f"No user with ID {user_id}")
        return self._users[user_id]

    def update_email(self, user_id: int, new_email: str) -> User:
        """
        Update a user's email address.

        Raises:
            UserNotFoundError: If the user doesn't exist
            UserValidationError: If the new email is invalid or already used
        """
        user = self.get_user(user_id)
        self._validate_email(new_email)

        for uid, u in self._users.items():
            if uid != user_id and u.email.lower() == new_email.lower():
                raise UserValidationError(f"Email '{new_email}' is already registered")

        user.email = new_email
        return user

    def delete_user(self, user_id: int) -> None:
        """
        Remove a user from the store.

        Raises:
            UserNotFoundError: If the user doesn't exist
        """
        if user_id not in self._users:
            raise UserNotFoundError(f"No user with ID {user_id}")
        del self._users[user_id]

    def list_users(self, active_only: bool = True) -> list[User]:
        """Return all users, optionally filtering to active users only."""
        users = list(self._users.values())
        if active_only:
            users = [u for u in users if u.is_active]
        return users

    def search_by_role(self, role: str) -> list[User]:
        """Return all active users with the given role."""
        return [u for u in self._users.values() if u.role == role and u.is_active]

    # ── Private Validators ────────────────────────────────────────────────────

    @staticmethod
    def _validate_username(username: str) -> None:
        if not isinstance(username, str):
            raise UserValidationError("Username must be a string")
        if not 3 <= len(username) <= 50:
            raise UserValidationError("Username must be 3–50 characters long")
        if not re.match(r"^[a-zA-Z0-9_]+$", username):
            raise UserValidationError("Username may only contain letters, digits, and underscores")

    @staticmethod
    def _validate_email(email: str) -> None:
        if not isinstance(email, str):
            raise UserValidationError("Email must be a string")
        pattern = r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$"
        if not re.match(pattern, email):
            raise UserValidationError(f"Invalid email format: '{email}'")

    @staticmethod
    def _validate_role(role: str) -> None:
        if role not in User.ROLES:
            raise UserValidationError(f"Invalid role '{role}'. Must be one of {User.ROLES}")


def hash_password(password: str, salt: Optional[str] = None) -> tuple[str, str]:
    """
    Hash a password with an optional salt using SHA-256.

    Args:
        password: Plain-text password
        salt:     Optional salt string (generated if not provided)

    Returns:
        Tuple of (hashed_password, salt) — both as hex strings

    Raises:
        ValueError: If password is empty
    """
    if not password:
        raise ValueError("Password cannot be empty")

    if salt is None:
        import secrets
        salt = secrets.token_hex(16)

    combined = f"{salt}{password}"
    hashed   = hashlib.sha256(combined.encode()).hexdigest()
    return hashed, salt


def verify_password(password: str, hashed: str, salt: str) -> bool:
    """
    Verify a plain-text password against a stored hash + salt.

    Args:
        password: Plain-text password to verify
        hashed:   Previously stored hash (hex string)
        salt:     Salt used during hashing

    Returns:
        True if the password matches
    """
    computed, _ = hash_password(password, salt)
    return computed == hashed
