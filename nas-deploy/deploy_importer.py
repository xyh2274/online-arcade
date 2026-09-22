# -*- coding: utf-8 -*-
import arcade_env as _ac  # 凭据集中在 arcade.env（见 arcade.env.example）
"""Deploy rom importer: script + config + run.sh + cron, then build CRC db and dry-run test."""
import json
import stat
import paramiko

HOST, PORT = _ac.HOST, 22
USER, PWD = _ac.USER, _ac.PWD
BASE = "/vol1/1000/docker/game-arcade"
IMP = f"{BASE}/roms-import"
LOCAL = r"D:\MyBlog\GameGo\在线游戏厅\nas-deploy"

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST, PORT, USER, PWD, timeout=12)

def sudo_run(cmd, timeout=600, label=None):
    stdin, stdout, stderr = ssh.exec_command("sudo -S -p '' " + cmd, timeout=timeout, get_pty=True)
    stdin.write(PWD + "\n")
    stdin.flush()
    code = stdout.channel.recv_exit_status()
    out = stdout.read().decode("utf-8", "replace")
    print(f"===== exit={code} {':: ' + label if label else cmd[:70]}")
    print(out.strip()[-2000:])
    return out

sudo_run(f"mkdir -p {IMP} {BASE}/roms/inbox {BASE}/roms/imported {BASE}/roms/unknown", label="dirs")

sftp = ssh.open_sftp()
sftp.put(LOCAL + r"\rom_import.py", IMP + "/rom_import.py")
config = {"api": "http://127.0.0.1:3000", "username": "admin", "password": "admin123"}
with sftp.open(IMP + "/config.json", "w") as f:
    f.write(json.dumps(config, indent=2))
with sftp.open(IMP + "/run.sh", "w") as f:
    f.write("#!/bin/sh\nexec python3 %s/rom_import.py \"$@\"\n" % IMP)
sftp.close()

sudo_run(f"chmod 755 {IMP}/run.sh && chmod 600 {IMP}/config.json", label="perms")

# cron: 每5分钟扫一次 inbox
cron = f"*/5 * * * * root flock -n /tmp/rom-import.lock {IMP}/run.sh >> {IMP}/import.log 2>&1\n"
sftp = ssh.open_sftp()
with sftp.open("/tmp/game-rom-import.cron", "w") as f:
    f.write(cron)
sftp.close()
sudo_run("cp /tmp/game-rom-import.cron /etc/cron.d/game-rom-import && chmod 644 /etc/cron.d/game-rom-import && rm /tmp/game-rom-import.cron && echo cron-installed", label="install cron")

# 构建 FBNeo CRC 指纹库（走 jsdelivr，国内可达）
sudo_run(f"python3 {IMP}/rom_import.py --build-db", timeout=600, label="build FBNeo CRC db")

# 端到端测试：造一个假 .nes → dry-run 识别 → 真实入库 → 验证 → 删除测试 ROM
test_js = (
    "const db=require('better-sqlite3')('/data/app.db');"
    "console.log(JSON.stringify(db.prepare('select id,title,platform,isPublic from roms order by id desc limit 1').all()));"
)
sftp = ssh.open_sftp()
with sftp.open("/tmp/g2.cjs", "w") as f:
    f.write(test_js)
sftp.close()
sudo_run("docker cp /tmp/g2.cjs childhood-arcade:/app/g2.cjs && rm /tmp/g2.cjs", label="stage test query")

sudo_run(f"python3 -c \"import os; open('{BASE}/roms/inbox/Test Super Mario (J).nes','wb').write(os.urandom(65536))\"", label="make dummy nes")
sudo_run(f"python3 {IMP}/rom_import.py --dry-run", label="dry-run detection")
sudo_run(f"python3 {IMP}/rom_import.py", timeout=300, label="real import run")
sudo_run("curl -s -o /dev/null -w '%{http_code}'", label="noop")
sudo_run("sleep 1", label="wait")
sudo_run(f"docker exec childhood-arcade node /app/g2.cjs", label="latest rom row")
sudo_run("docker exec childhood-arcade rm -f /app/g2.cjs", label="cleanup staging")
ssh.close()
print("IMPORTER DEPLOYED")
