# 墨记 Blog 部署手册（FastAPI + Uvicorn）

> 适用：开放 Blog MVP；应用进程用 Uvicorn，公网建议 Nginx 反代 + HTTPS。  
> 项目目录约定：仓库根目录，入口 `app:app`。

---

## 1. 部署架构

```text
用户浏览器
    │
    ▼
Nginx :80/:443  ──静态/HTTPS/反代──►  Uvicorn(FastAPI) :8000
                                          │
                                          ▼
                                    文章目录 posts/*.md
```

| 层级 | 职责 |
|------|------|
| Nginx | HTTPS、域名、限流、静态资源缓存 |
| Uvicorn | 跑 FastAPI：登录、CRUD、API、静态页 |
| 数据 | 仓库外 `../doc/**/*.md`（可配置）；需持久化与备份 |

---

## 2. 环境要求

| 项 | 建议 |
|----|------|
| OS | Ubuntu 22.04+ / Debian 12+（生产） |
| Python | 3.11+ |
| 进程 | 非 root（如用户 `blog`） |
| 网络 | 开放 80/443；**不要**把 8000 直接暴露公网 |

---

## 3. 本地 / 内网快速跑通

```bash
cd markdown-note   # 或本仓库克隆目录
python3 -m venv .venv
source .venv/bin/activate   # Windows: .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

# 可选：复制环境变量
cp .env.example .env        # Windows: copy .env.example .env

# 开发
uvicorn app:app --reload --host 127.0.0.1 --port 8000

# 接近生产（文件存储建议 1 worker）
uvicorn app:app --host 127.0.0.1 --port 8000 --workers 1
```

浏览器：`http://127.0.0.1:8000`  
默认作者账号见 `.env.example`（上线必须修改）。

---

## 4. 生产：systemd 托管 Uvicorn

### 4.1 目录约定

```text
/opt/moji-blog/
  .venv/
  app.py
  static/
  posts/
  .env                 # 权限 600，勿提交 Git
```

### 4.2 配置文件 `settings.json`（推荐改密方式）

从模板复制：

```bash
cp settings.example.json settings.json
```

```json
{
  "secret_key": "请换成长随机串",
  "admin_user": "admin",
  "admin_password": "请换成强密码",
  "posts_dir": "",
  "session_https_only": true
}
```

- `posts_dir` 留空：默认使用仓库外的 `../doc/`（相对仓库根，递归扫描 `.md`）
- 也可写成绝对路径，如 `"/data/moji-doc"` 或 Windows `E:/doc`

定期改密：只改 `admin_password` 保存即可，**下次登录生效，无需重启 Uvicorn**。  
`settings.json` 权限建议 `600`，且不要提交到 Git。

环境变量（`SECRET_KEY` / `ADMIN_*` / `POSTS_DIR` 等）仍可覆盖配置文件，便于容器部署。

### 4.3 systemd 单元 `/etc/systemd/system/moji-blog.service`

```ini
[Unit]
Description=Moji Markdown Blog (FastAPI)
After=network.target

[Service]
Type=simple
User=blog
Group=blog
WorkingDirectory=/opt/moji-blog
EnvironmentFile=/opt/moji-blog/.env
ExecStart=/opt/moji-blog/.venv/bin/uvicorn app:app \
  --host 127.0.0.1 \
  --port 8000 \
  --workers 1 \
  --proxy-headers \
  --forwarded-allow-ips=127.0.0.1
Restart=always
RestartSec=3
NoNewPrivileges=true
PrivateTmp=true

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now moji-blog
sudo systemctl status moji-blog
journalctl -u moji-blog -f
```

---

## 5. Nginx 反代

`/etc/nginx/sites-available/moji-blog`：

```nginx
server {
    listen 80;
    server_name blog.example.com;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 60s;
        client_max_body_size 4m;
    }
}
```

```bash
sudo ln -s /etc/nginx/sites-available/moji-blog /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d blog.example.com
```

---

## 6. Windows 本机（仅开发）

```powershell
cd e:\markdown-note
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app:app --host 127.0.0.1 --port 8000
```

局域网调试可用 `--host 0.0.0.0`，勿在无防护环境下裸奔公网。

---

## 7. 发布与回滚

```bash
cd /opt/moji-blog
git pull
source .venv/bin/activate
pip install -r requirements.txt
sudo systemctl restart moji-blog
curl -fsS http://127.0.0.1:8000/api/health

# 回滚
git checkout <上一版本>
sudo systemctl restart moji-blog
```

---

## 8. 数据备份

```bash
# cron 示例：每日 03:00
0 3 * * * rsync -a /opt/moji-blog/posts/ /backup/moji-blog/posts/
```

恢复：停服务 → 还原 `posts/` → 启服务。`.env` 单独备份。

---

## 9. 安全清单

- [ ] Uvicorn 仅监听 `127.0.0.1`
- [ ] 强 `SECRET_KEY`、强管理员密码；关闭调试
- [ ] HTTPS；会话 Cookie `Secure` / `HttpOnly`
- [ ] Nginx `client_max_body_size` 有上限
- [ ] 防火墙仅 SSH + 80/443

---

## 10. 常见问题

| 现象 | 排查 |
|------|------|
| 502 | `systemctl status moji-blog`；journalctl |
| Cookie 丢失 | `X-Forwarded-Proto`、HTTPS、`SESSION_HTTPS_ONLY` |
| 写文件失败 | `chown -R blog:blog posts` |
| 多 worker 写乱 | MVP 保持 `--workers 1` |

---

## 11. 验收

- [ ] 访客可读已发布文章
- [ ] 未登录无法写删
- [ ] 重启/开机后服务自动起来
