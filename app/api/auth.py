"""
/v1/auth — login endpoint that issues a JWT bearer token for AUTH_USERS entries.
"""
from fastapi import APIRouter, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from typing import Annotated

from fastapi import Depends

from app.auth import CurrentUser, TokenResponse, authenticate, create_access_token

router = APIRouter(prefix="/v1/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
async def login(form: Annotated[OAuth2PasswordRequestForm, Depends()]) -> TokenResponse:
    """
    Username/password login. `form.username` is treated as the email address.
    Returns a bearer access token on success.
    """
    user = authenticate(form.username, form.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return create_access_token(user.email)


@router.get("/me")
async def me(user: CurrentUser) -> dict[str, str]:
    """Returns the currently-authenticated principal."""
    return {"email": user.email}
