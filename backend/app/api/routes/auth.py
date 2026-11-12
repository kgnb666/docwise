"""账号登录、会话查询和登出。"""

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field

from app.config import get_settings
from app.core.rate_limit import RateLimiter
from app.storage.accounts import (
    Account,
    authenticate,
    create_session,
    normalize_username,
    revoke_session,
    session_account,
)

SESSION_COOKIE = "docwise_session"
_ACCOUNT_HEADER = "X-DocWise-Account"
_NO_STORE = {"Cache-Control": "no-store"}
_login_by_account = RateLimiter(capacity=6, refill_per_sec=0.05)
_login_total = RateLimiter(capacity=12, refill_per_sec=1.0)
router = APIRouter()


class Credentials(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=128)


def _check_origin(request: Request) -> None:
    origin = request.headers.get("origin")
    host = request.headers.get("host")
    if origin is not None and (not host or origin not in (f"http://{host}", f"https://{host}")):
        raise HTTPException(status_code=403, detail="请求来源不受信任", headers=_NO_STORE)


def _unauthorized(message: str) -> HTTPException:
    return HTTPException(status_code=401, detail=message, headers=_NO_STORE)


def require_account(request: Request, response: Response) -> Account:
    if request.method not in {"GET", "HEAD", "OPTIONS"}:
        _check_origin(request)
    token = request.cookies.get(SESSION_COOKIE)
    account = session_account(token) if token else None
    expected = request.headers.get(_ACCOUNT_HEADER)
    if account is None or (expected is not None and expected != account.id):
        raise _unauthorized("请重新登录")
    response.headers.update(_NO_STORE)
    return account


@router.post("/login")
def login(credentials: Credentials, request: Request, response: Response) -> Account:
    _check_origin(request)
    username = normalize_username(credentials.username)
    if not _login_by_account.allow(username) or not _login_total.allow("login"):
        raise HTTPException(status_code=429, detail="登录请求过多，请稍后重试", headers=_NO_STORE)
    account = authenticate(username, credentials.password)
    if account is None:
        raise _unauthorized("账号或密码不正确")
    token = create_session(account, request.cookies.get(SESSION_COOKIE))
    settings = get_settings()
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=settings.auth_session_seconds,
        path="/api",
        secure=settings.auth_cookie_secure,
        httponly=True,
        samesite="strict",
    )
    response.headers.update(_NO_STORE)
    return account


@router.get("/me")
def me(account: Account = Depends(require_account)) -> Account:
    return account


@router.post("/logout", status_code=204, dependencies=[Depends(require_account)])
def logout(request: Request) -> Response:
    revoke_session(request.cookies[SESSION_COOKIE])
    response = Response(status_code=204, headers=_NO_STORE)
    response.delete_cookie(
        SESSION_COOKIE,
        path="/api",
        secure=get_settings().auth_cookie_secure,
        httponly=True,
        samesite="strict",
    )
    return response
