from typing import Annotated, Any, cast

from authlib.integrations.starlette_client import OAuth, OAuthError  # type: ignore[import-untyped]
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.security import Principal, create_access_token, get_current_principal
from app.db.session import get_db
from app.schemas.auth import LoginRequest, RegisterRequest, TokenResponse
from app.services import auth_service

router = APIRouter(prefix="/auth", tags=["authentication"])
oauth = OAuth()
_registered_client_id: str | None = None


def _configure_oidc(settings: Settings) -> Any:
    global _registered_client_id
    if not settings.oidc_client_id or not settings.oidc_client_secret:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="OIDC SSO is not configured",
        )
    if _registered_client_id != settings.oidc_client_id:
        oauth.register(
            name="oidc",
            client_id=settings.oidc_client_id,
            client_secret=settings.oidc_client_secret,
            server_metadata_url=settings.oidc_discovery_url,
            client_kwargs={"scope": "openid email profile"},
            overwrite=True,
        )
        _registered_client_id = settings.oidc_client_id
    return oauth.create_client("oidc")


def _token(user: Any, settings: Settings) -> TokenResponse:
    access_token = create_access_token(auth_service.as_principal(user), settings)
    return TokenResponse(
        access_token=access_token,
        expires_in=settings.access_token_expire_minutes * 60,
    )


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def register(
    payload: RegisterRequest,
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> TokenResponse:
    return _token(auth_service.register(db, payload), settings)


@router.post("/login", response_model=TokenResponse)
def login(
    payload: LoginRequest,
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> TokenResponse:
    return _token(auth_service.authenticate(db, payload.email, payload.password), settings)


@router.get("/me", response_model=Principal)
def me(principal: Annotated[Principal, Depends(get_current_principal)]) -> Principal:
    return principal


@router.get("/oidc/start")
async def oidc_start(
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
) -> Response:
    client = _configure_oidc(settings)
    return cast(Response, await client.authorize_redirect(request, settings.oidc_redirect_uri))


@router.get("/oidc/callback", response_model=TokenResponse)
async def oidc_callback(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> TokenResponse:
    client = _configure_oidc(settings)
    try:
        token = await client.authorize_access_token(request)
    except OAuthError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="SSO failed") from exc
    userinfo = token.get("userinfo")
    if not isinstance(userinfo, dict):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing OIDC profile")
    subject = userinfo.get("sub")
    email = userinfo.get("email")
    display_name = userinfo.get("name") or email
    if not isinstance(subject, str) or not isinstance(email, str):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid OIDC profile")
    user = auth_service.upsert_oidc_user(
        db,
        provider="oidc",
        subject=subject,
        email=email,
        display_name=str(display_name),
    )
    return _token(user, settings)
