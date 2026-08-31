# 墨记 · 开放 Markdown Blog

公开阅读、登录写作的轻量 Markdown 博客（FastAPI + Uvicorn）。

## 快速启动

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Linux / macOS（推荐）
chmod +x start.sh
./start.sh              # 启动
./start.sh restart      # 重启
./start.sh stop         # 停止
./start.sh status       # 状态

# 或手动
uvicorn app:app --reload --host 127.0.0.1 --port 8000
```

默认脚本监听 `0.0.0.0:8000`，可用 `http://<IP>:8000` 访问。  
改端口/地址：`MOJI_HOST=127.0.0.1 MOJI_PORT=8000 ./start.sh`

打开 http://127.0.0.1:8000  

默认作者：见 `settings.json` 中 `admin_user` / `admin_password`（模板：`settings.example.json`）。

改密：直接编辑 `settings.json` 的 `admin_password`，**无需重启**，下次登录即生效。

## 数据目录（与代码 / Git 分离）

默认文章根目录为**上一级**的 `doc/`（与本仓库并列，不被 Git 管理）：

```text
E:/
  doc/                 # Markdown 数据（仓库外）
    数仓/ODS/xxx.md
  markdown-note/       # 本 Git 仓库（代码）
```

相对代码路径：`../doc`（`settings.json` 中 `posts_dir` 留空即用此默认）。

- 递归读取 `doc/**/*.md`
- 按相对路径构建目录树分类（首页左侧）
- 正文相对路径图片/附件经 `/media/{文章目录}/...` 访问
- 自定义路径：`settings.json` → `posts_dir`（可用相对或绝对路径）

## 搜索与标签

- 首页：关键字搜索 + 标签下拉 + **目录树**筛选（目录下全部 `.md`）
- 工作台：侧栏同样支持；可填「目录」与「标签」
- API：`GET /api/posts?q=&tag=&category=`，`GET /api/categories`，`GET /api/tags`


| 文档 | 说明 |
|------|------|
| [PRD](docs/PRD-markdown-blog-v1.md) | 产品需求 |
| [架构](docs/ARCH-markdown-blog-v1.md) | 分层与 API |
| [部署](docs/DEPLOY-fastapi-uvicorn.md) | Uvicorn + Nginx |
| [自测报告](docs/TEST-markdown-blog-v1.md) | 测试结果 |

## 测试

```bash
pytest -q
```
