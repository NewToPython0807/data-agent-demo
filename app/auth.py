"""登录认证核心逻辑（T07）。

- bcrypt 密码哈希 / 校验（决策 D5）
- 签名 Cookie 会话令牌的生成与校验（决策 D3，有效期 7 天，可配置）
签名使用标准库 hmac + hashlib + base64 完成，不额外引入依赖。
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import time

import bcrypt
from fastapi import HTTPException, Request

from app.config import settings


def hash_password(plain: str) -> str:
    """生成明文密码的 bcrypt 哈希。"""
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    """校验明文密码与 bcrypt 哈希是否匹配。"""
    if not plain or not hashed:
        return False
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except (ValueError, TypeError):
        return False


def _sign(payload: bytes) -> str:
    return hmac.new(settings.secret_key.encode("utf-8"), payload, hashlib.sha256).hexdigest()


def create_session_token(username: str) -> str:
    """生成签名会话令牌（内含用户名与过期时间）。"""
    exp = int(time.time()) + settings.session_max_age_seconds
    payload = f"{username}|{exp}".encode("utf-8")
    b64 = base64.urlsafe_b64encode(payload).decode("utf-8").rstrip("=")
    return f"{b64}.{_sign(payload)}"


def verify_session_token(token: str) -> str | None:
    """校验会话令牌：签名正确且未过期则返回用户名，否则返回 None。"""
    if not token:
        return None
    try:
        b64, sig = token.split(".", 1)
        pad = "=" * (-len(b64) % 4)
        payload = base64.urlsafe_b64decode(b64 + pad)
        if not hmac.compare_digest(_sign(payload), sig):
            return None
        username, exp_str = payload.decode("utf-8").split("|", 1)
        if int(exp_str) < int(time.time()):
            return None
        return username
    except Exception:
        return None


def get_current_user(request: Request) -> str:
    """FastAPI 鉴权依赖：校验会话 Cookie。

    未登录或会话过期/无效时抛 401；否则返回当前用户名。
    后续业务接口（T09 历史、T14/T15 生成 SQL、T17 执行等）统一用
    `Depends(get_current_user)` 保护。
    """
    token = request.cookies.get(settings.session_cookie_name, "")
    username = verify_session_token(token)
    if not username:
        raise HTTPException(status_code=401, detail="未登录或会话已过期")
    return username
