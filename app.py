# -*- coding: utf-8 -*-
"""
用途：墨记开放 Blog FastAPI 接入层
分层：接入层
创建：2026-08-21
维护：路由与静态挂载；业务落 auth/store；文章根目录为仓库外 ../doc/
      v1.2 起无草稿/发布过滤，目录下全部 .md 公开可读
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

import store
from auth import (
    login_session,
    logout_session,
    require_author,
    verify_credentials,
    current_user,
)
from config import SECRET_KEY, SESSION_COOKIE_NAME, SESSION_HTTPS_ONLY, get_posts_dir
from schemas import (
    AuthMeResponse,
    CategoryNode,
    CategoryTreeResponse,
    LoginRequest,
    PostCreate,
    PostDetail,
    PostSummary,
    PostUpdate,
    TagsResponse,
)

ROOT = Path(__file__).resolve().parent
STATIC_DIR = ROOT / "static"


@asynccontextmanager
async def lifespan(_: FastAPI):
    store.ensure_posts_dir()
    yield


app = FastAPI(title="墨记 Markdown Blog", version="1.3.0", lifespan=lifespan)
app.add_middleware(
    SessionMiddleware,
    secret_key=SECRET_KEY,
    session_cookie=SESSION_COOKIE_NAME,
    https_only=SESSION_HTTPS_ONLY,
    same_site="lax",
)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


def _safe_media_file(rel: str) -> Path | None:
    """将 /media 相对路径解析到 posts_dir 内真实文件；防目录穿越。"""
    raw = (rel or "").replace("\\", "/").lstrip("/")
    if not raw:
        return None
    root = store.posts_root().resolve()
    # 禁止路径段中的 ..（含 URL 解码后）
    parts = Path(raw).parts
    if any(p == ".." for p in parts):
        return None
    candidate = (root / raw).resolve()
    try:
        candidate.relative_to(root)
    except ValueError:
        return None
    if not candidate.is_file():
        return None
    return candidate


@app.get("/media/{file_path:path}")
def serve_media(file_path: str) -> FileResponse:
    """提供 md 相对引用的图片/附件（相对 posts_dir）。"""
    path = _safe_media_file(file_path)
    if not path:
        raise HTTPException(status_code=404, detail="media not found")
    return FileResponse(path)


def _to_detail(post: dict) -> PostDetail:
    return PostDetail(
        id=post["id"],
        title=post.get("title") or "",
        content=post.get("content") or "",
        tags=list(post.get("tags") or []),
        category=post.get("category") or "",
        relpath=post.get("relpath") or "",
        createdAt=post.get("createdAt") or 0,
        updatedAt=post.get("updatedAt") or 0,
        filename=post.get("filename"),
    )


def _to_summary(post: dict) -> PostSummary:
    return PostSummary(
        id=post["id"],
        title=post.get("title") or "",
        tags=list(post.get("tags") or []),
        category=post.get("category") or "",
        relpath=post.get("relpath") or "",
        createdAt=post.get("createdAt") or 0,
        updatedAt=post.get("updatedAt") or 0,
        filename=post.get("filename"),
    )


@app.get("/")
def index_page() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/login.html")
def login_page() -> FileResponse:
    return FileResponse(STATIC_DIR / "login.html")


@app.get("/editor.html")
def editor_page() -> FileResponse:
    return FileResponse(STATIC_DIR / "editor.html")


@app.get("/post.html")
def post_page() -> FileResponse:
    return FileResponse(STATIC_DIR / "post.html")


@app.get("/api/health")
def health() -> dict:
    posts = get_posts_dir()
    return {
        "ok": True,
        "postsDir": str(posts),
        "postsExists": posts.exists(),
    }


@app.get("/api/auth/me", response_model=AuthMeResponse)
def auth_me(request: Request) -> AuthMeResponse:
    user = current_user(request)
    return AuthMeResponse(authenticated=bool(user), username=user)


@app.post("/api/auth/login", response_model=AuthMeResponse)
def auth_login(body: LoginRequest, request: Request) -> AuthMeResponse:
    if not verify_credentials(body.username, body.password):
        raise HTTPException(status_code=401, detail="账号或密码错误")
    login_session(request, body.username)
    return AuthMeResponse(authenticated=True, username=body.username)


@app.post("/api/auth/logout", response_model=AuthMeResponse)
def auth_logout(request: Request) -> AuthMeResponse:
    logout_session(request)
    return AuthMeResponse(authenticated=False, username=None)


@app.get("/api/posts", response_model=list[PostSummary])
def list_public_posts(
    q: str | None = None,
    tag: str | None = None,
    category: str | None = None,
) -> list[PostSummary]:
    return [
        _to_summary(p)
        for p in store.list_posts(q=q, tag=tag, category=category)
    ]


@app.get("/api/posts/all", response_model=list[PostSummary])
def list_all_posts(
    q: str | None = None,
    tag: str | None = None,
    category: str | None = None,
    _: str = Depends(require_author),
) -> list[PostSummary]:
    return [
        _to_summary(p)
        for p in store.list_posts(q=q, tag=tag, category=category)
    ]


@app.get("/api/tags", response_model=TagsResponse)
def list_public_tags() -> TagsResponse:
    return TagsResponse(tags=store.list_tags())


@app.get("/api/tags/all", response_model=TagsResponse)
def list_all_tags(_: str = Depends(require_author)) -> TagsResponse:
    return TagsResponse(tags=store.list_tags())


@app.get("/api/categories", response_model=CategoryTreeResponse)
def list_public_categories() -> CategoryTreeResponse:
    return CategoryTreeResponse(
        tree=CategoryNode.model_validate(store.build_category_tree())
    )


@app.get("/api/categories/all", response_model=CategoryTreeResponse)
def list_all_categories(_: str = Depends(require_author)) -> CategoryTreeResponse:
    return CategoryTreeResponse(
        tree=CategoryNode.model_validate(store.build_category_tree())
    )


@app.get("/api/posts/{post_id}", response_model=PostDetail)
def get_post(post_id: str) -> PostDetail:
    post = store.get_post(post_id)
    if not post:
        raise HTTPException(status_code=404, detail="not found")
    return _to_detail(post)


@app.post("/api/posts", response_model=PostDetail, status_code=201)
def create_post(body: PostCreate, _: str = Depends(require_author)) -> PostDetail:
    try:
        post = store.create_post(body.title, body.content, body.tags, body.category)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _to_detail(post)


@app.put("/api/posts/{post_id}", response_model=PostDetail)
def update_post(
    post_id: str, body: PostUpdate, _: str = Depends(require_author)
) -> PostDetail:
    try:
        post = store.update_post(
            post_id,
            body.title,
            body.content,
            body.tags,
            body.category,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not post:
        raise HTTPException(status_code=404, detail="not found")
    return _to_detail(post)


@app.delete("/api/posts/{post_id}", status_code=204)
def delete_post(post_id: str, _: str = Depends(require_author)) -> None:
    if not store.delete_post(post_id):
        raise HTTPException(status_code=404, detail="not found")
