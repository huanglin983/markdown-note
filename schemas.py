# -*- coding: utf-8 -*-
"""
用途：请求/响应 Pydantic 模型
分层：接入契约
创建：2026-08-21
维护：v1.2 起无 status 字段
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=64)
    password: str = Field(..., min_length=1, max_length=128)


class AuthMeResponse(BaseModel):
    authenticated: bool
    username: str | None = None


class PostCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    content: str = ""
    tags: list[str] = Field(default_factory=list)
    category: str = ""


class PostUpdate(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    content: str = ""
    tags: list[str] = Field(default_factory=list)
    category: str = ""


class PostSummary(BaseModel):
    id: str
    title: str
    tags: list[str] = Field(default_factory=list)
    category: str = ""
    relpath: str = ""
    createdAt: int
    updatedAt: int
    filename: str | None = None


class PostDetail(PostSummary):
    content: str


class TagsResponse(BaseModel):
    tags: list[str]


class CategoryNode(BaseModel):
    name: str
    path: str
    count: int
    directCount: int = 0
    children: list["CategoryNode"] = Field(default_factory=list)


CategoryNode.model_rebuild()


class CategoryTreeResponse(BaseModel):
    tree: CategoryNode
