# -*- coding: utf-8 -*-
import arcade_env as _ac  # 凭据集中在 arcade.env（见 arcade.env.example）
"""部署 CSS 补丁: canvas.portal-canvas 退出 fixed 全屏覆盖, 回归 emu-frame, 顶栏恢复可见"""
import paramiko

cli = paramiko.SSHClient()
cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
cli.connect(_ac.HOST, 22, _ac.USER, _ac.PWD, timeout=10)

def run(cmd, label="", t=180):
    if label: print("="*15, label, "="*15, flush=True)
    _, out, err = cli.exec_command(cmd, timeout=t)
    o, e = out.read().decode("utf-8","replace"), err.read().decode("utf-8","replace")
    if o.strip(): print(o[:3000], flush=True)
    if e.strip(): print("[stderr]", e[:500], flush=True)

B = "/vol1/1000/docker/game-arcade"

# 1. 从容器拷出 CSS
run(f"docker cp childhood-arcade:/app/dist/assets/Player-CYZDJezR.css {B}/patches/Player-CYZDJezR.css && echo COPIED", "拷贝 CSS", t=60)

# 2. 追加补丁规则
run("python3 - <<'EOF'\n"
    "p = '/vol1/1000/docker/game-arcade/patches/Player-CYZDJezR.css'\n"
    "s = open(p).read()\n"
    "if 'canvas.portal-canvas' not in s:\n"
    "    s += ('\\n/* 补丁: RA web 把画布 fixed 全屏覆盖页面(连顶栏一起盖住), 改回容器内布局 */\\n'\n"
    "          'canvas.portal-canvas{position:static !important}\\n')\n"
    "    open(p, 'w').write(s)\n"
    "    print('[OK] CSS 补丁已追加')\n"
    "else:\n"
    "    print('[SKIP] 已存在')\n"
    "EOF", "追加补丁规则", t=30)

# 3. compose 加挂载
run("python3 - <<'EOF'\n"
    "comp = '/vol1/1000/docker/game-arcade/docker-compose.yml'\n"
    "s = open(comp).read()\n"
    "if 'Player-CYZDJezR.css' not in s:\n"
    "    anchor = [l for l in s.splitlines() if 'fbneo-setnames.json' in l and '/app/dist' in l][0]\n"
    "    add = '      - ./patches/Player-CYZDJezR.css:/app/dist/assets/Player-CYZDJezR.css:ro'\n"
    "    s = s.replace(anchor, anchor + '\\n' + add, 1)\n"
    "    open(comp, 'w').write(s)\n"
    "    print('[OK] compose 已加 CSS 挂载')\n"
    "else:\n"
    "    print('[SKIP] 已有挂载')\n"
    "EOF", "compose 加挂载", t=30)

# 4. 重启
run(f"cd {B} && docker compose up -d 2>&1 | tail -3", "compose up", t=180)
run("sleep 3; curl -s http://localhost:3000/assets/Player-CYZDJezR.css | grep -c 'canvas.portal-canvas'", "线上 CSS 补丁生效", t=30)

cli.close()
print("DONE")
