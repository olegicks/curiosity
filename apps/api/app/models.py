"""Import every model module so Base.metadata is complete (Alembic, tests)."""

from app.ai import models as ai_models
from app.auth import models as auth_models
from app.content import models as content_models
from app.gamification import models as gamification_models
from app.learning import models as learning_models
from app.reviews import models as reviews_models
from app.users import models as users_models

__all__ = [
    "ai_models",
    "auth_models",
    "content_models",
    "gamification_models",
    "learning_models",
    "reviews_models",
    "users_models",
]
