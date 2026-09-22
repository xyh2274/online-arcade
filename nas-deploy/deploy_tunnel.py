# -*- coding: utf-8 -*-
import arcade_env as _ac  # 凭据集中在 arcade.env（见 arcade.env.example）
"""Deploy cloudflared with tunnel token, verify connector registers."""
import time
import paramiko

HOST, PORT = _ac.HOST, 22
USER, PWD = _ac.USER, _ac.PWD
BASE = "/vol1/1000/docker/game-arcade"
LOCAL = r"D:\MyBlog\GameGo\在线游戏厅\docker-compose.yml"

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
    print(out.strip()[-2500:])
    return out

sftp = ssh.open_sftp()
sftp.put(LOCAL, "/tmp/game-compose.yml")
sftp.close()
sudo_run(f"cp /tmp/game-compose.yml {BASE}/docker-compose.yml && rm /tmp/game-compose.yml", label="upload compose")

# 若用户已在飞牛应用中心装了同名应用容器, 先检查避免双实例
sudo_run("docker ps --format '{{.Names}}' | grep -i cloud", label="existing cloudflare containers")

sudo_run(f"bash -c 'cd {BASE} && docker compose up -d'", timeout=600, label="compose up (pull cloudflared)")
time.sleep(8)
sudo_run("docker logs cloudflared --tail 15 2>&1", label="cloudflared logs")
sudo_run("docker ps --format '{{.Names}} {{.Status}}' | grep -E 'cloudflared|arcade'", label="containers")
ssh.close()
print("CLOUDFLARED DEPLOYED")
