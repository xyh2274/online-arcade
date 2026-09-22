# -*- coding: utf-8 -*-
import arcade_env as _ac  # 凭据集中在 arcade.env（见 arcade.env.example）
"""Rebuild CRC db with fixed parser + verify."""
import paramiko

HOST, PORT = _ac.HOST, 22
USER, PWD = _ac.USER, _ac.PWD
IMP = "/vol1/1000/docker/game-arcade/roms-import"
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST, PORT, USER, PWD, timeout=12)

def sudo_run(cmd, timeout=600, label=None):
    stdin, stdout, stderr = ssh.exec_command("sudo -S -p '' " + cmd, timeout=timeout, get_pty=True)
    stdin.write(PWD + "\n")
    stdin.flush()
    code = stdout.channel.recv_exit_status()
    out = stdout.read().decode("utf-8", "replace")
    print(f"===== exit={code} {':: ' + label if label else cmd[:60]}")
    print(out.strip()[-1500:])

sftp = ssh.open_sftp()
sftp.put(r"D:\MyBlog\GameGo\在线游戏厅\nas-deploy\rom_import.py", IMP + "/rom_import.py")
sftp.close()

sudo_run(f"python3 {IMP}/rom_import.py --build-db", timeout=600, label="rebuild CRC db")
sudo_run(f"python3 -c \"import json;db=json.load(open('{IMP}/fbneo_crc.json'));print('条目:',len(db));print('kof2002 示例:',db.get('c69ed68a') or [k for k in list(db)[:3]])\"", label="verify db")
ssh.close()
