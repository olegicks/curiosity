"""Auth-specific error codes (docs/spec/05 §5.2)."""

from app.core.errors import ConflictError, ForbiddenError, UnauthenticatedError, ValidationError


class EmailTakenError(ConflictError):
    code = "EMAIL_TAKEN"
    message = "An account with this email already exists."


class AlreadyFullAccountError(ConflictError):
    code = "ALREADY_FULL_ACCOUNT"
    message = "This account already has credentials."


class WeakPasswordError(ValidationError):
    code = "WEAK_PASSWORD"
    message = "Choose a stronger password."

    def __init__(self, reason: str, field: str = "password") -> None:
        super().__init__(details=[{"field": field, "issue": reason}])


class InvalidCredentialsError(UnauthenticatedError):
    code = "INVALID_CREDENTIALS"
    message = "Email or password is incorrect."


class InvalidRefreshTokenError(UnauthenticatedError):
    code = "INVALID_REFRESH_TOKEN"
    message = "Session expired. Please sign in again."


class RefreshTokenReusedError(UnauthenticatedError):
    code = "REFRESH_TOKEN_REUSED"
    message = "Session expired. Please sign in again."


class FullAccountRequiredError(ForbiddenError):
    code = "FULL_ACCOUNT_REQUIRED"
    message = "Create an account to use this feature."
