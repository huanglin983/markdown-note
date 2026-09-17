# -*- coding: utf-8 -*-
"""
用途：墨记 Blog 配置（优先 settings.json，便于改密）
分层：配置层
创建：2026-08-21
维护：账号密码放 settings.json；文章默认在仓库外 ../doc/
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
# 默认数据目录：上一级的 doc/（与本仓库并列，避免被版本管理）
# markdown-note -> (parent) / doc
DEFAULT_DOC_DIR = (ROOT.parent / "doc").resolve()
SETTINGS_FILE = Path(os.getenv("MOJI_SETTINGS", str(ROOT / "settings.json")))
SESSION_COOKIE_NAME = "moji_blog_session"

_DEFAULTS: dict[str, Any] = {
    "secret_key": "dev-only-change-me",
    "admin_user": "admin",
    "admin_password": "admin123",
    "posts_dir": "",
    "session_https_only": False,
    "max_content_bytes": 2 * 1024 * 1024,
}


def _coerce_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.lower() in {"1", "true", "yes"}
    return bool(value)


def load_settings() -> dict[str, Any]:
    """每次调用重新读盘，方便定期改密后立即生效。"""
    data = dict(_DEFAULTS)
    if SETTINGS_FILE.exists():
        try:
            raw = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
            if not isinstance(raw, dict):
                raise ValueError("settings.json root must be an object")
            data.update(raw)
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            raise RuntimeError(f"failed to load settings: {SETTINGS_FILE}: {exc}") from exc

    env_map = {
        "SECRET_KEY": "secret_key",
        "ADMIN_USER": "admin_user",
        "ADMIN_PASSWORD": "admin_password",
        "POSTS_DIR": "posts_dir",
        "SESSION_HTTPS_ONLY": "session_https_only",
        "MAX_CONTENT_BYTES": "max_content_bytes",
    }
    for env_key, conf_key in env_map.items():
        val = os.getenv(env_key)
        if val is not None and val != "":
            data[conf_key] = val

    data["session_https_only"] = _coerce_bool(data.get("session_https_only"))
    try:
        data["max_content_bytes"] = int(data.get("max_content_bytes") or _DEFAULTS["max_content_bytes"])
    except (TypeError, ValueError) as exc:
        raise RuntimeError("max_content_bytes must be an integer") from exc

    posts = (data.get("posts_dir") or "").strip()
    if posts:
        p = Path(posts)
        # 相对路径相对仓库根目录解析，避免受启动 cwd 影响
        data["posts_dir_path"] = (p if p.is_absolute() else (ROOT / p)).resolve()
    else:
        data["posts_dir_path"] = DEFAULT_DOC_DIR
    data["admin_user"] = str(data.get("admin_user") or "")
    data["admin_password"] = str(data.get("admin_password") or "")
    data["secret_key"] = str(data.get("secret_key") or _DEFAULTS["secret_key"])
    return data


def get_admin_credentials() -> tuple[str, str]:
    cfg = load_settings()
    return cfg["admin_user"], cfg["admin_password"]


_boot = load_settings()
SECRET_KEY = _boot["secret_key"]
POSTS_DIR = _boot["posts_dir_path"]
SESSION_HTTPS_ONLY = _boot["session_https_only"]
MAX_CONTENT_BYTES = _boot["max_content_bytes"]
ADMIN_USER = _boot["admin_user"]
ADMIN_PASSWORD = _boot["admin_password"]


def get_posts_dir() -> Path:
    """每次从 settings 读取 posts_dir，改配置后无需重启即可生效。"""
    return load_settings()["posts_dir_path"]
