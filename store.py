# -*- coding: utf-8 -*-
"""
用途：Markdown 文章存储（doc/**/*.md + frontmatter，按目录分类）
分层：数据层
创建：2026-08-21
维护：仅处理磁盘 IO；不感知 HTTP。无草稿/发布状态，扫盘即可见。
"""

from __future__ import annotations

import json
import re
import threading
from datetime import datetime, timezone
from pathlib import Path

from config import MAX_CONTENT_BYTES, get_posts_dir

_lock = threading.Lock()

# 测试可 monkeypatch 为 Path；生产保持 None，每次走 get_posts_dir()
POSTS_DIR: Path | None = None


def posts_root() -> Path:
    return POSTS_DIR if POSTS_DIR is not None else get_posts_dir()


def now_ms() -> int:
    return int(datetime.now(timezone.utc).timestamp() * 1000)


def ensure_posts_dir() -> None:
    posts_root().mkdir(parents=True, exist_ok=True)


def sanitize_filename(title: str) -> str:
    name = (title or "").strip() or "无标题"
    name = re.sub(r'[\\/:*?"<>|\r\n\t]+', "_", name)
    name = re.sub(r"\s+", " ", name).strip(" ._")
    return name[:80] or "无标题"


def sanitize_category(category: str | None) -> str:
    """相对分类路径：允许 a/b；禁止 .. 与绝对路径。"""
    raw = (category or "").strip().replace("\\", "/")
    if not raw or raw in {".", "/"}:
        return ""
    parts: list[str] = []
    for part in raw.split("/"):
        seg = part.strip().strip(".")
        if not seg or seg in {".", ".."}:
            continue
        seg = re.sub(r'[\\:*?"<>|\r\n\t]+', "_", seg)
        if seg and seg not in {".", ".."}:
            parts.append(seg[:64])
    return "/".join(parts)


def normalize_tags(raw: list[str] | str | None) -> list[str]:
    items: list[str] = []
    if raw is None:
        return items
    if isinstance(raw, str):
        parts = re.split(r"[,，;；\s]+", raw)
    else:
        parts = list(raw)
    seen: set[str] = set()
    for part in parts:
        tag = (part or "").strip()
        if not tag or len(tag) > 32:
            continue
        key = tag.lower()
        if key in seen:
            continue
        seen.add(key)
        items.append(tag)
        if len(items) >= 20:
            break
    return items


def dump_frontmatter(meta: dict, content: str) -> str:
    tags = normalize_tags(meta.get("tags"))
    lines = [
        "---",
        f"id: {meta['id']}",
        f"title: {json.dumps(meta.get('title') or '', ensure_ascii=False)}",
        f"tags: {json.dumps(tags, ensure_ascii=False)}",
        f"createdAt: {meta.get('createdAt') or now_ms()}",
        f"updatedAt: {meta.get('updatedAt') or now_ms()}",
        "---",
        "",
        content or "",
    ]
    body = "\n".join(lines)
    if not body.endswith("\n"):
        body += "\n"
    return body


def _rel_parts(path: Path) -> tuple[str, str, str]:
    """返回 (relpath posix, category, filename)。"""
    try:
        rel = path.resolve().relative_to(posts_root().resolve())
    except ValueError:
        return path.name, "", path.name
    rel_posix = rel.as_posix()
    category = rel.parent.as_posix() if rel.parent != Path(".") else ""
    if category == ".":
        category = ""
    return rel_posix, category, path.name


def parse_md_file(path: Path) -> dict | None:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None

    relpath, category, filename = _rel_parts(path)
    meta: dict = {
        "id": path.stem,
        "title": path.stem,
        "content": text,
        "tags": [],
        "createdAt": int(path.stat().st_ctime * 1000),
        "updatedAt": int(path.stat().st_mtime * 1000),
        "filename": filename,
        "category": category,
        "relpath": relpath,
    }

    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end != -1:
            fm = text[3:end].strip()
            body = text[end + 4 :]
            for _ in range(2):
                if body.startswith("\n"):
                    body = body[1:]
                else:
                    break
            for line in fm.splitlines():
                if ":" not in line:
                    continue
                key, val = line.split(":", 1)
                key = key.strip()
                val = val.strip()
                # 历史 status 字段忽略，不再参与可见性
                if key == "status":
                    continue
                if key == "title":
                    try:
                        meta["title"] = json.loads(val)
                    except json.JSONDecodeError:
                        meta["title"] = val.strip("\"'")
                elif key == "id":
                    meta["id"] = val
                elif key == "tags":
                    try:
                        parsed = json.loads(val)
                        meta["tags"] = normalize_tags(
                            parsed if isinstance(parsed, list) else []
                        )
                    except json.JSONDecodeError:
                        meta["tags"] = normalize_tags(val)
                elif key in ("createdAt", "updatedAt"):
                    try:
                        meta[key] = int(val)
                    except ValueError:
                        pass
            meta["content"] = body
            meta["filename"] = filename

    meta["tags"] = normalize_tags(meta.get("tags"))
    meta["category"] = category
    meta["relpath"] = relpath
    return meta


def _iter_post_paths() -> list[Path]:
    ensure_posts_dir()
    paths: list[Path] = []
    root = posts_root()
    for path in root.rglob("*.md"):
        if not path.is_file():
            continue
        if path.name.startswith(".") or path.name.lower() == "readme.md":
            continue
        # 跳过隐藏目录段（如 .git）
        try:
            rel = path.resolve().relative_to(root.resolve())
        except ValueError:
            continue
        if any(part.startswith(".") for part in rel.parts[:-1]):
            continue
        paths.append(path)
    return paths


def _matches_query(post: dict, q: str) -> bool:
    needle = q.strip().lower()
    if not needle:
        return True
    hay = f"{post.get('title') or ''}\n{post.get('content') or ''}".lower()
    return needle in hay


def _matches_tag(post: dict, tag: str) -> bool:
    needle = tag.strip().lower()
    if not needle:
        return True
    tags = [t.lower() for t in (post.get("tags") or [])]
    return needle in tags


def _matches_category(post: dict, category: str) -> bool:
    """category 为空=不过滤；精确匹配或作为前缀（含子目录）。"""
    needle = sanitize_category(category)
    if not needle:
        return True
    cat = post.get("category") or ""
    return cat == needle or cat.startswith(needle + "/")


def list_posts(
    *,
    q: str | None = None,
    tag: str | None = None,
    category: str | None = None,
) -> list[dict]:
    with _lock:
        posts = []
        for path in _iter_post_paths():
            post = parse_md_file(path)
            if not post:
                continue
            if not _matches_query(post, q or ""):
                continue
            if not _matches_tag(post, tag or ""):
                continue
            if not _matches_category(post, category or ""):
                continue
            posts.append(_summary(post))
        posts.sort(key=lambda p: p.get("updatedAt") or 0, reverse=True)
        return posts


def list_tags() -> list[str]:
    with _lock:
        found: set[str] = set()
        for path in _iter_post_paths():
            post = parse_md_file(path)
            if not post:
                continue
            for t in post.get("tags") or []:
                found.add(t)
        return sorted(found, key=lambda s: s.lower())


def build_category_tree() -> dict:
    """
    目录树：{ name, path, count, children: [...] }
    path 为相对 doc 的分类路径；根 path=""。
    凡含 .md 的子目录均出现，无状态过滤。
    """
    with _lock:
        # 收集所有目录节点（含空父路径上的中间目录）
        nodes: set[str] = {""}
        direct: dict[str, int] = {}
        for path in _iter_post_paths():
            post = parse_md_file(path)
            if not post:
                continue
            cat = post.get("category") or ""
            nodes.add(cat)
            if cat:
                parts = cat.split("/")
                for i in range(len(parts)):
                    nodes.add("/".join(parts[: i + 1]))
            direct[cat] = direct.get(cat, 0) + 1

        def subtree(path: str) -> dict:
            name = path.split("/")[-1] if path else "全部"
            children_paths = sorted(
                [
                    n
                    for n in nodes
                    if n
                    and (
                        (path == "" and "/" not in n)
                        or (path != "" and n.startswith(path + "/") and "/" not in n[len(path) + 1 :])
                    )
                ],
                key=lambda s: s.lower(),
            )
            # 含子目录的文章总数
            if path == "":
                total = sum(direct.values())
            else:
                total = sum(
                    c
                    for p, c in direct.items()
                    if p == path or p.startswith(path + "/")
                )
            return {
                "name": name,
                "path": path,
                "count": total,
                "directCount": direct.get(path, 0),
                "children": [subtree(cp) for cp in children_paths],
            }

        return subtree("")


def _summary(post: dict) -> dict:
    return {
        "id": post["id"],
        "title": post.get("title") or "",
        "tags": list(post.get("tags") or []),
        "category": post.get("category") or "",
        "relpath": post.get("relpath") or post.get("filename") or "",
        "createdAt": post.get("createdAt") or 0,
        "updatedAt": post.get("updatedAt") or 0,
        "filename": post.get("filename"),
    }


def find_post_path(post_id: str) -> Path | None:
    for path in _iter_post_paths():
        post = parse_md_file(path)
        if post and post["id"] == post_id:
            return path
    # 兼容根目录 id 文件名
    direct = posts_root() / f"{post_id}.md"
    if direct.exists():
        return direct
    return None


def get_post(post_id: str) -> dict | None:
    with _lock:
        path = find_post_path(post_id)
        if not path:
            return None
        return parse_md_file(path)


def _category_dir(category: str | None) -> Path:
    cat = sanitize_category(category)
    root = posts_root()
    target = root if not cat else root / Path(*cat.split("/"))
    # 防穿越
    resolved = target.resolve()
    root_resolved = root.resolve()
    if root_resolved not in resolved.parents and resolved != root_resolved:
        raise ValueError("invalid category path")
    return resolved


def unique_path(
    title: str,
    post_id: str,
    category: str | None = None,
    exclude: Path | None = None,
) -> Path:
    base = sanitize_filename(title)
    folder = _category_dir(category)
    folder.mkdir(parents=True, exist_ok=True)
    candidate = folder / f"{base}.md"

    if exclude and candidate.resolve() == exclude.resolve():
        return candidate

    if not candidate.exists():
        return candidate

    existing = parse_md_file(candidate)
    if existing and existing["id"] == post_id:
        return candidate

    short = post_id.replace("p_", "")[-8:]
    return folder / f"{base}-{short}.md"


def _validate_content(content: str) -> None:
    raw = (content or "").encode("utf-8")
    if len(raw) > MAX_CONTENT_BYTES:
        raise ValueError(f"content exceeds {MAX_CONTENT_BYTES} bytes")


def create_post(
    title: str,
    content: str,
    tags: list[str] | str | None = None,
    category: str | None = None,
) -> dict:
    title = (title or "").strip()
    if not title:
        raise ValueError("title is required")
    _validate_content(content)
    cat = sanitize_category(category)

    post_id = f"p_{now_ms():x}"
    ts = now_ms()
    post = {
        "id": post_id,
        "title": title,
        "content": content or "",
        "tags": normalize_tags(tags),
        "createdAt": ts,
        "updatedAt": ts,
        "category": cat,
    }
    with _lock:
        ensure_posts_dir()
        path = unique_path(title, post_id, category=cat)
        path.write_text(dump_frontmatter(post, post["content"]), encoding="utf-8")
        loaded = parse_md_file(path)
        return loaded or post


def update_post(
    post_id: str,
    title: str,
    content: str,
    tags: list[str] | str | None = None,
    category: str | None = None,
) -> dict | None:
    title = (title or "").strip()
    if not title:
        raise ValueError("title is required")
    _validate_content(content)

    with _lock:
        old_path = find_post_path(post_id)
        if not old_path:
            return None
        old = parse_md_file(old_path)
        if not old:
            return None
        if category is None:
            cat = old.get("category") or ""
        else:
            cat = sanitize_category(category)
        post = {
            "id": post_id,
            "title": title,
            "content": content or "",
            "tags": normalize_tags(tags if tags is not None else old.get("tags")),
            "createdAt": old.get("createdAt") or now_ms(),
            "updatedAt": now_ms(),
            "category": cat,
        }
        path = unique_path(title, post_id, category=cat, exclude=old_path)
        path.write_text(dump_frontmatter(post, post["content"]), encoding="utf-8")
        if old_path.resolve() != path.resolve() and old_path.exists():
            try:
                old_path.unlink()
            except OSError:
                pass
            # 清理空目录（仅限 doc 内）
            _cleanup_empty_dirs(old_path.parent)
        return parse_md_file(path)


def _cleanup_empty_dirs(folder: Path) -> None:
    root = posts_root().resolve()
    cur = folder.resolve()
    while cur != root and root in cur.parents:
        try:
            if any(cur.iterdir()):
                break
            cur.rmdir()
        except OSError:
            break
        cur = cur.parent


def delete_post(post_id: str) -> bool:
    with _lock:
        path = find_post_path(post_id)
        if not path:
            return False
        parent = path.parent
        path.unlink(missing_ok=True)
        _cleanup_empty_dirs(parent)
        return True
