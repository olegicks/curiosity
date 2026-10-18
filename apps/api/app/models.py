"""Import every model module so Base.metadata is complete (Alembic, tests)."""

from app.auth import models as auth_models
from app.users import models as users_models

__all__ = ["auth_models", "users_models"]
