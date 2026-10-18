"""Import every model module so Base.metadata is complete (Alembic, tests)."""

from app.auth import models as auth_models
from app.content import models as content_models
from app.users import models as users_models

__all__ = ["auth_models", "content_models", "users_models"]
