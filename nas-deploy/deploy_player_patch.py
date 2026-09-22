# -*- coding: utf-8 -*-
import arcade_env as _ac  # 凭据集中在 arcade.env（见 arcade.env.example）
"""部署播放器补丁 + 验证 7002058 识别"""
import paramiko

cli = paramiko.SSHClient()
cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
cli.connect(_ac.HOST, 22, _ac.USER, _ac.PWD, timeout=10)

def run(cmd, label="", t=180):
    if label: print("="*15, label, "="*15, flush=True)
    _, out, err = cli.exec_command(cmd, timeout=t)
    o, e = out.read().decode("utf-8","replace"), err.read().decode("utf-8","replace")
    if o.strip(): print(o[:5000], flush=True)
    if e.strip(): print("[stderr]", e[:500], flush=True)

B = "/vol1/1000/docker/game-arcade"
R = B + "/roms-import"

# 1. 上传补丁 chunk
sftp = cli.open_sftp()
sftp.put(r"D:\MyBlog\GameGo\在线游戏厅\nas-deploy\Player-BwKb4RpM.js", f"{B}/patches/Player-BwKb4RpM.js")
print("已上传 Player-BwKb4RpM.js 补丁", flush=True)
sftp.close()

# 2. compose 加挂载
run("python3 - <<'EOF'\n"
    "comp = '/vol1/1000/docker/game-arcade/docker-compose.yml'\n"
    "s = open(comp).read()\n"
    "if 'Player-BwKb4RpM.js' not in s:\n"
    "    anchor = [l for l in s.splitlines() if 'Gallery-dcHxang3.css' in l and '/app/dist' in l][0]\n"
    "    add = ('      # 播放器补丁：工具栏「菜单」按钮(F1 呼出 RGUI) + 手柄 Start+Select 呼出菜单\\n'\n"
    "           '      - ./patches/Player-BwKb4RpM.js:/app/dist/assets/Player-BwKb4RpM.js:ro')\n"
    "    s = s.replace(anchor, anchor + '\\n' + add, 1)\n"
    "    open(comp, 'w').write(s)\n"
    "    print('[OK] compose 已加 Player 挂载')\n"
    "else:\n"
    "    print('[SKIP] compose 已有 Player 挂载')\n"
    "EOF", "compose 加挂载", t=30)

# 3. 重启
run(f"cd {B} && docker compose up -d 2>&1 | tail -3", "compose up", t=180)
run("sleep 3; curl -s http://localhost:3000/assets/Player-BwKb4RpM.js | grep -c 模拟器菜单", "线上 chunk 补丁生效", t=30)
run("curl -s -o /dev/null -w 'home=%{http_code}\\n' http://localhost:3000/", "首页状态", t=20)

# 4. 验证导入器对 7002058 的识别 (复制到 /tmp, 不进 inbox 避免 cron 抢跑)
run("cp /vol1/1000/docker/game-arcade/arcade-data/uploads/2/arcade/beb6a627-9097-48f4-9b1f-9a9a1a397bbf.zip /tmp/t7002058.zip && "
    "cd " + R + " && python3 -c \""
    "import sys; sys.path.insert(0,'.');"
    "from rom_import import detect;"
    "print('识别结果:', detect('/tmp/t7002058.zip'));"
    "import os; os.remove('/tmp/t7002058.zip')\"", "导入器识别验证", t=60)

cli.close()
print("DONE")
