# -*- coding: utf-8 -*-
"""集中读取 NAS 部署凭据 —— 避免把账号密码写进每一个脚本。

读取优先级：环境变量 > 同目录 arcade.env > 占位默认值

真实凭据请写在 nas-deploy/arcade.env（已被 .gitignore 排除，绝不会提交）。
仓库里只有 arcade.env.example 模板。
"""
import os

_DIR = os.path.dirname(os.path.abspath(__file__))
_ENV_FILE = os.path.join(_DIR, "arcade.env")


def _load_env_file(path):
    """把 arcade.env 里的键值对注入环境变量（不覆盖已存在的环境变量）。"""
    if not os.path.exists(path):
        return
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())
    except OSError:
        pass


_load_env_file(_ENV_FILE)

HOST = os.environ.get("ARCADE_HOST", "192.168.1.100")
PORT = int(os.environ.get("ARCADE_PORT", "22"))
USER = os.environ.get("ARCADE_USER", "")
PWD = os.environ.get("ARCADE_PWD", "")
BASE = os.environ.get("ARCADE_BASE", "/vol1/1000/docker/game-arcade")

__all__ = ["HOST", "PORT", "USER", "PWD", "BASE"]
