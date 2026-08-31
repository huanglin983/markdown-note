# -*- coding: utf-8 -*-
"""
用途：作者登录与会话依赖
分层：业务层
创建：2026-08-21
维护：口令每次从 settings.json 读取，改密无需重启服务
"""

from __future__ import annotations

import secrets

from fastapi import HTTPException, Request

from config import get_admin_credentials


def verify_credentials(username: str, password: str) -> bool:
    admin_user, admin_password = get_admin_credentials()
    if not admin_user or not admin_password:
        return False
    user_ok = secrets.compare_digest(username or "", admin_user)
    pass_ok = secrets.compare_digest(password or "", admin_password)
    return user_ok and pass_ok


def login_session(request: Request, username: str) -> None:
    request.session.clear()
    request.session["user"] = username
    request.session["role"] = "author"


def logout_session(request: Request) -> None:
    request.session.clear()


def current_user(request: Request) -> str | None:
    user = request.session.get("user")
    return user if isinstance(user, str) and user else None


def require_author(request: Request) -> str:
    user = current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="unauthorized")
    return user
