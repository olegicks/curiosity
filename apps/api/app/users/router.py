"""/v1/me and /v1/me/preferences (docs/spec/05 §5.3)."""

from datetime import datetime

from fastapi import APIRouter, Depends, Request, Response, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth.deps import get_current_user, get_now, rate_limit
from app.auth.models import User
from app.auth.schemas import UserOut
from app.core.db import get_db
from app.core.ratelimit import RateRule
from app.users import export, service
from app.users.schemas import DeleteMeIn, MePatchIn, PreferencesOut, PreferencesPatchIn

router = APIRouter(prefix="/me", tags=["me"])

EXPORT_PER_USER = RateRule("export_user", 3, 24 * 3600)


class MeOut(BaseModel):
    user: UserOut
    preferences: PreferencesOut


class UserResponse(BaseModel):
    user: UserOut


@router.get("", response_model=MeOut)
def get_me(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> MeOut:
    prefs = service.get_preferences(db, user.id)
    return MeOut(user=UserOut.model_validate(user), preferences=service.preferences_out(db, prefs))


@router.patch("", response_model=UserResponse)
def patch_me(
    body: MePatchIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> UserResponse:
    updated = service.update_display_name(db, user, body.display_name)
    return UserResponse(user=UserOut.model_validate(updated))


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
def delete_me(
    body: DeleteMeIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    now: datetime = Depends(get_now),
) -> Response:
    service.delete_account(db, user, password=body.password, confirm=body.confirm, now=now)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/preferences", response_model=PreferencesOut)
def get_preferences(
    user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> PreferencesOut:
    return service.preferences_out(db, service.get_preferences(db, user.id))


@router.patch("/preferences", response_model=PreferencesOut)
def patch_preferences(
    body: PreferencesPatchIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    now: datetime = Depends(get_now),
) -> PreferencesOut:
    prefs = service.update_preferences(db, user.id, body, now)
    return service.preferences_out(db, prefs)


@router.get(
    "/export",
    response_class=JSONResponse,
    responses={200: {"description": "All personal data as a JSON attachment"}},
)
def export_my_data(
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    now: datetime = Depends(get_now),
) -> JSONResponse:
    rate_limit(request, EXPORT_PER_USER, str(user.id), now)
    filename = f"curiosity-export-{now.date().isoformat()}.json"
    return JSONResponse(
        content=export.build_export(db, user, now),
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
