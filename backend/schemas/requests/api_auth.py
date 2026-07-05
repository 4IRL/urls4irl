from __future__ import annotations

from pydantic import BaseModel, Field

from backend.schemas.requests.splash import LoginRequest


class ApiLoginRequest(LoginRequest):
    """Mobile /api/v1 login body — identical fields/validation to the web
    LoginRequest, but a distinct class so the @api_route kwarg injection name
    (api_login_request) and OpenAPI schema name never collide with the web
    surface."""


class ApiRefreshRequest(BaseModel):
    refresh_token: str = Field(
        min_length=1,
        alias="refreshToken",
        description="The refresh token to rotate for a new token pair",
    )


class ApiLogoutRequest(BaseModel):
    refresh_token: str = Field(
        min_length=1,
        alias="refreshToken",
        description="The refresh token whose device session should be revoked",
    )


class ApiGoogleAuthRequest(BaseModel):
    id_token: str = Field(
        min_length=1,
        alias="idToken",
        description="Google id_token obtained from the native Google Sign-In SDK",
    )
