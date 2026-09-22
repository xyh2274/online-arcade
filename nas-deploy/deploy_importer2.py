# -*- coding: utf-8 -*-
import arcade_env as _ac  # 凭据集中在 arcade.env（见 arcade.env.example）
"""Redeploy updated importer, build CRC db, zip-structure detection tests, cron via crontab."""
import json
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

sftp = ssh.open_sftp()
sftp.put(LOCAL + r"\rom_import.py", IMP + "/rom_import.py")
sftp.close()

# 1. CRC db build
sudo_run(f"python3 {IMP}/rom_import.py --build-db", timeout=600, label="build FBNeo CRC db")

# 2. zip 结构识别测试: 造街机结构 zip 和 内嵌 nes 的 zip, 加上未知 zip
sudo_run(f"python3 -c \"\nimport zipfile, os\nbase='{BASE}/roms/inbox'\nwith zipfile.ZipFile(base+'/Kov Arcade.zip','w') as z:\n    z.writestr('27c4001.p1', os.urandom(1024))\n    z.writestr('27c4001.s1', os.urandom(512))\n    z.writestr('27c4001.m1', os.urandom(512))\nwith zipfile.ZipFile(base+'/Some SFC game.zip','w') as z:\n    z.writestr('game.sfc', os.urandom(2048))\nwith zipfile.ZipFile(base+'/Mystery.zip','w') as z:\n    z.writestr('data1.dat', os.urandom(512))\n    z.writestr('data2.dat', os.urandom(512))\nprint('test zips created')\n\"", label="create test zips")
sudo_run(f"python3 {IMP}/rom_import.py --dry-run", label="detection dry-run")

# 3. cron via root crontab (fnOS 保护 /etc/cron.d)
cronline = f"*/5 * * * * flock -n /tmp/rom-import.lock {IMP}/run.sh >> {IMP}/import.log 2>&1"
cron_cmd = f"(crontab -l 2>/dev/null | grep -v rom_import | grep -v rom-import; echo '{cronline}') | crontab - && crontab -l | tail -3"
sudo_run(cron_cmd, label="install cron via crontab")
ssh.close()
print("IMPORTER UPDATED")
