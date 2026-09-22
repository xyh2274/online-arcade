# 童年游戏厅 · Childhood Arcade

自托管的复古游戏厅：浏览器直接开玩，支持多人联机，局域网/公网都能访问。
基于 `yize8888/childhood-arcade`（Vue 3 + RetroArch/Nostalgist）自建部署，本仓库记录**部署方式、运维手册与周边资料**。

---

## 关于上游

> **本仓库不是 `childhood-arcade` 的官方仓库，也不包含它的源码。**

| | |
|---|---|
| 上游项目 | [`yize8888/childhood-arcade`](https://hub.docker.com/r/yize8888/childhood-arcade)（Docker 镜像，Vue 3 + RetroArch/Nostalgist）|
| 本仓库是什么 | 在该镜像基础上**自建部署**的记录：编排配置、补丁脚本、运维技术笔记 |
| 本仓库不是什么 | 上游源码的分叉或镜像。上游的服务端与前端 chunk 版权归原作者所有，**未收录在此** |

我们做的事是在上游镜像之上打补丁、配键位、调联机，并把过程和教训记下来。
上游源码文件（如服务端路由、前端产物）仅保留在本地用于部署，**已通过 `.gitignore` 排除**。

---

## 目录结构

```
.
├── docker-compose.yml          # 部署编排（凭据走 .env，见下）
├── .env.example                # 环境变量模板 → 复制为 .env 后填写
├── .gitignore
├── nas-deploy/                 # 部署与运维脚本
│   ├── HANDBOOK.md             # 运维手册（架构、调试记录、踩坑）
│   ├── arcade_env.py           # 凭据集中读取（env 文件 > 环境变量）
│   ├── arcade.env.example      # 凭据模板 → 复制为 arcade.env 后填写
│   ├── deploy*.py              # 部署脚本
│   ├── patch*.py               # 补丁生成/应用
│   ├── check_*.py              # 一致性校验
│   └── rebuild_*.py            # 索引重建
└── sango2-guide/
    └── index.html              # 《三国战纪2·群雄争霸》图文攻略（单文件自包含）
```

---

## 快速开始

```bash
cp .env.example .env                              # 填 TUNNEL_TOKEN
cp nas-deploy/arcade.env.example nas-deploy/arcade.env   # 填 SSH 凭据
docker compose up -d
```

访问 `http://<你的NAS地址>:3000`。首次启动默认账号 `admin / admin123`，**登录后立即修改**。

---

## 凭据配置（重要）

本仓库**不含任何密码或 Token**，所有凭据通过本地文件提供，已被 `.gitignore` 排除：

| 文件 | 用途 | 模板 |
|---|---|---|
| `.env` | Cloudflare Tunnel Token | `.env.example` |
| `nas-deploy/arcade.env` | NAS 的 SSH 账号密码 | `nas-deploy/arcade.env.example` |

脚本统一从 `arcade_env.py` 读取，优先级：**环境变量 > `arcade.env` > 占位默认值**。
因此也可以完全不建文件，直接用环境变量覆盖：

```bash
export ARCADE_HOST=192.168.1.100
export ARCADE_USER=your_user
export ARCADE_PWD=your_password
```

> 提交前建议跑一次 `python tools/check_secrets.py`，确认没有凭据被误带进仓库。
> 它只检查 git 待提交的文件（自动尊重 `.gitignore`），不会对已排除的内容报错。

---

## 文档

- **`docs/TECH-NOTES.md`** —— 技术笔记（公开版）。涵盖容器挂载与补丁机制、键位系统的三个大坑、
  多人联机的 WebRTC 架构与已知限制、ROM/romset 的口径问题，以及一份踩坑对照表。
  改键位或打补丁前建议先读。
- `nas-deploy/HANDBOOK.md` —— 完整内部运维手册，**不随仓库公开**（含真实账号、用户数据与内网信息），
  保留在本地供运维使用。

---

## 攻略资料

`sango2-guide/index.html` 是《三国战纪2·群雄争霸》的完整图文攻略：

- 七关全流程 + 关卡地图 + 实机画面
- 全密室进法、全神兵防具收集、全敌将招降、BOSS 打法
- 附带可搜索筛选的道具图鉴

**单文件自包含**（图片已内联为 base64），直接双击打开即可，无需联网、无需解压图片目录。

---

## 联机架构简述

房主把模拟器画布通过 **WebRTC P2P** 推给客机，服务器只负责中继信令（`offer`/`answer`/`ice`），
画面数据不经过服务器。客机侧只做解码与按键回传，负载极低。

> 已知限制：主机窗口必须保持可见——浏览器在页面隐藏时会挂起 `requestAnimationFrame`，
> 导致核心停摆、客机画面冻结。因此推荐配置是**电脑当房主、手机当客机**。

---

## 致谢

- 平台：[childhood-arcade](https://hub.docker.com/r/yize8888/childhood-arcade)
- 攻略资料参考：962 乐游网、GOTVG 三国战纪 wiki
