# -*- coding: utf-8 -*-
"""
用途：墨记 Blog 接口与存储单元测试
分层：测试
创建：2026-08-21
维护：v1.2 无状态管理，全部 md 公开可见
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

TEST_ROOT = Path(__file__).resolve().parent / "_tmp_posts"
TEST_SETTINGS = Path(__file__).resolve().parent / "_tmp_settings.json"
TEST_ROOT.mkdir(parents=True, exist_ok=True)
TEST_SETTINGS.write_text(
    json.dumps(
        {
            "secret_key": "test-secret-key",
            "admin_user": "admin",
            "admin_password": "secret",
            "posts_dir": str(TEST_ROOT),
            "session_https_only": False,
        },
        ensure_ascii=False,
        indent=2,
    ),
    encoding="utf-8",
)
os.environ["MOJI_SETTINGS"] = str(TEST_SETTINGS)

import config  # noqa: E402
import store  # noqa: E402
from app import app  # noqa: E402


@pytest.fixture(autouse=True)
def clean_posts(tmp_path, monkeypatch):
    posts_dir = tmp_path / "posts"
    posts_dir.mkdir()
    monkeypatch.setattr(config, "POSTS_DIR", posts_dir)
    monkeypatch.setattr(store, "POSTS_DIR", posts_dir)
    # 每个用例重置 settings 口令，避免改密用例污染
    TEST_SETTINGS.write_text(
        json.dumps(
            {
                "secret_key": "test-secret-key",
                "admin_user": "admin",
                "admin_password": "secret",
                "posts_dir": str(posts_dir),
                "session_https_only": False,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(config, "SETTINGS_FILE", TEST_SETTINGS)
    yield


@pytest.fixture
def client():
    return TestClient(app)


def login(client: TestClient, password: str = "secret") -> None:
    r = client.post("/api/auth/login", json={"username": "admin", "password": password})
    assert r.status_code == 200
    assert r.json()["authenticated"] is True


def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["ok"] is True


def test_login_fail(client):
    r = client.post("/api/auth/login", json={"username": "admin", "password": "wrong"})
    assert r.status_code == 401


def test_password_reload_from_settings(client):
    """改 settings.json 后无需重启即可用新密码登录。"""
    login(client, "secret")
    client.post("/api/auth/logout")

    data = json.loads(TEST_SETTINGS.read_text(encoding="utf-8"))
    data["admin_password"] = "new-pass-456"
    TEST_SETTINGS.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    assert (
        client.post("/api/auth/login", json={"username": "admin", "password": "secret"}).status_code
        == 401
    )
    login(client, "new-pass-456")


def test_public_list_shows_all_md(client):
    """无状态管理：API 新建与无 frontmatter 的纯 md 均对访客可见。"""
    login(client)
    a = client.post(
        "/api/posts",
        json={"title": "文章甲", "content": "x"},
    )
    assert a.status_code == 201
    b = client.post(
        "/api/posts",
        json={"title": "文章乙", "content": "hello", "category": "技术"},
    )
    assert b.status_code == 201
    id_a = a.json()["id"]
    id_b = b.json()["id"]

    # 直接落盘无 frontmatter 的 md
    plain = store.POSTS_DIR / "生活" / "纯文本笔记.md"
    plain.parent.mkdir(parents=True, exist_ok=True)
    plain.write_text("# 纯文本\n内容", encoding="utf-8")

    client.post("/api/auth/logout")
    listed = client.get("/api/posts")
    assert listed.status_code == 200
    titles = {x["title"] for x in listed.json()}
    assert "文章甲" in titles
    assert "文章乙" in titles
    assert "纯文本笔记" in titles

    assert client.get(f"/api/posts/{id_a}").status_code == 200
    assert client.get(f"/api/posts/{id_b}").status_code == 200

    tree = client.get("/api/categories")
    assert tree.status_code == 200
    names = {c["name"] for c in tree.json()["tree"]["children"]}
    assert "技术" in names
    assert "生活" in names


def test_unauthorized_write(client):
    assert client.post("/api/posts", json={"title": "a", "content": ""}).status_code == 401
    assert client.get("/api/posts/all").status_code == 401


def test_crud_flow(client):
    login(client)
    created = client.post(
        "/api/posts",
        json={"title": "第一篇", "content": "# hi"},
    )
    assert created.status_code == 201
    pid = created.json()["id"]
    assert "status" not in created.json()

    updated = client.put(
        f"/api/posts/{pid}",
        json={"title": "第一篇改", "content": "# hello", "tags": ["t1"]},
    )
    assert updated.status_code == 200
    assert updated.json()["title"] == "第一篇改"
    assert updated.json()["tags"] == ["t1"]

    all_posts = client.get("/api/posts/all")
    assert any(x["id"] == pid for x in all_posts.json())

    deleted = client.delete(f"/api/posts/{pid}")
    assert deleted.status_code == 204
    assert client.get(f"/api/posts/{pid}").status_code == 404


def test_empty_title_rejected(client):
    login(client)
    r = client.post("/api/posts", json={"title": "  ", "content": ""})
    assert r.status_code == 400
    r2 = client.post("/api/posts", json={"title": "", "content": ""})
    assert r2.status_code == 422


def test_store_sanitize_and_parse():
    post = store.create_post("a/b:c", "body", tags=["test", "blog"])
    assert post["tags"] == ["test", "blog"]
    assert "status" not in post
    loaded = store.get_post(post["id"])
    assert loaded is not None
    assert loaded["content"].startswith("body")
    assert "/" not in (loaded.get("filename") or "")
    # 新写入 frontmatter 不含 status
    path = store.find_post_path(post["id"])
    assert path is not None
    text = path.read_text(encoding="utf-8")
    assert "status:" not in text


def test_legacy_status_ignored(client):
    """历史 status: draft 的文件仍公开可见。"""
    path = store.POSTS_DIR / "legacy.md"
    path.write_text(
        "---\n"
        'id: p_legacy\n'
        'title: "旧草稿"\n'
        "status: draft\n"
        "tags: []\n"
        "createdAt: 1\n"
        "updatedAt: 2\n"
        "---\n\n"
        "旧正文\n",
        encoding="utf-8",
    )
    listed = client.get("/api/posts")
    titles = [x["title"] for x in listed.json()]
    assert "旧草稿" in titles
    detail = client.get("/api/posts/p_legacy")
    assert detail.status_code == 200
    assert detail.json()["content"].strip().startswith("旧正文")


def test_search_and_tag_filter(client):
    login(client)
    client.post(
        "/api/posts",
        json={
            "title": "Python 入门",
            "content": "学习变量与函数",
            "tags": ["python", "教程"],
        },
    )
    client.post(
        "/api/posts",
        json={
            "title": "Java 笔记",
            "content": "JVM 原理",
            "tags": ["java"],
        },
    )
    client.post(
        "/api/posts",
        json={
            "title": "另一篇 Python",
            "content": "also python",
            "tags": ["python"],
        },
    )
    client.post("/api/auth/logout")

    by_q = client.get("/api/posts", params={"q": "变量"})
    assert len(by_q.json()) == 1
    assert by_q.json()[0]["title"] == "Python 入门"

    by_tag = client.get("/api/posts", params={"tag": "java"})
    assert len(by_tag.json()) == 1
    assert by_tag.json()[0]["title"] == "Java 笔记"

    tags = client.get("/api/tags")
    assert set(tags.json()["tags"]) == {"java", "python", "教程"}

    login(client)
    all_tags = client.get("/api/tags/all")
    assert "python" in all_tags.json()["tags"]


def test_category_tree_and_filter(client):
    login(client)
    client.post(
        "/api/posts",
        json={
            "title": "ODS 明细",
            "content": "ods layer",
            "tags": ["数仓"],
            "category": "数仓/ODS",
        },
    )
    client.post(
        "/api/posts",
        json={
            "title": "DWD 清洗",
            "content": "dwd layer",
            "category": "数仓/DWD",
        },
    )
    client.post(
        "/api/posts",
        json={
            "title": "根目录文",
            "content": "root",
            "category": "",
        },
    )
    client.post("/api/auth/logout")

    tree = client.get("/api/categories")
    assert tree.status_code == 200
    root = tree.json()["tree"]
    assert root["path"] == ""
    assert root["count"] == 3
    names = {c["name"] for c in root["children"]}
    assert "数仓" in names

    by_cat = client.get("/api/posts", params={"category": "数仓"})
    titles = {x["title"] for x in by_cat.json()}
    assert titles == {"ODS 明细", "DWD 清洗"}

    by_ods = client.get("/api/posts", params={"category": "数仓/ODS"})
    assert len(by_ods.json()) == 1
    assert by_ods.json()[0]["category"] == "数仓/ODS"
    assert by_ods.json()[0]["relpath"].startswith("数仓/ODS/")


def test_media_relative_assets(client):
    """相对路径附件经 /media/{文章目录}/... 可读；防穿越。"""
    cat = store.POSTS_DIR / "微信公众号文章" / "附件资源" / "示例文"
    cat.mkdir(parents=True)
    img = cat / "img_1.png"
    # 最小合法 PNG
    img.write_bytes(
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
        b"\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00"
        b"\x0cIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00\x05\x18\xd8N"
        b"\x00\x00\x00\x00IEND\xaeB`\x82"
    )
    md = store.POSTS_DIR / "微信公众号文章" / "示例文.md"
    md.write_text(
        "---\n"
        'id: p_media_demo\n'
        'title: "带图文"\n'
        "tags: []\n"
        "createdAt: 1\n"
        "updatedAt: 2\n"
        "---\n\n"
        "![图片 1](附件资源/示例文/img_1.png)\n",
        encoding="utf-8",
    )

    post = client.get("/api/posts/p_media_demo")
    assert post.status_code == 200
    assert post.json()["category"] == "微信公众号文章"

    media_url = "/media/" + "/".join(
        [
            "微信公众号文章",
            "附件资源",
            "示例文",
            "img_1.png",
        ]
    )
    r = client.get(media_url)
    assert r.status_code == 200
    assert r.content[:8] == b"\x89PNG\r\n\x1a\n"

    assert client.get("/media/../settings.json").status_code == 404


def test_edit_entry_pages_served(client):
    """阅读页与工作台提供编辑深链入口（前端契约）。"""
    post_page = client.get("/post.html")
    assert post_page.status_code == 200
    assert b'id="btnEdit"' in post_page.content

    index_page = client.get("/")
    assert index_page.status_code == 200
    assert b'id="btnFloatEdit"' in index_page.content

    editor_page = client.get("/editor.html")
    assert editor_page.status_code == 200
    assert b"editor.js" in editor_page.content

    login(client)
    me = client.get("/api/auth/me")
    assert me.status_code == 200
    assert me.json()["authenticated"] is True
