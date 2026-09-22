# -*- coding: utf-8 -*-
import arcade_env as _ac  # 凭据集中在 arcade.env（见 arcade.env.example）
"""SSH deployment helper for fnOS NAS (childhood-arcade stage 1)."""
import sys
import time
import paramiko

HOST, PORT = _ac.HOST, 22
USER, PWD = _ac.USER, _ac.PWD
BASE = "/vol1/1000/docker/game-arcade"
COMPOSE_LOCAL = r"D:\MyBlog\GameGo\在线游戏厅\docker-compose.yml"


def main():
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, PORT, USER, PWD, timeout=12, banner_timeout=12, auth_timeout=12)

    def run(cmd, timeout=180, sudo=False, label=None):
        if sudo:
            cmd = "sudo -S -p '' " + cmd
        stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout, get_pty=sudo)
        if sudo:
            stdin.write(PWD + "\n")
            stdin.flush()
        code = stdout.channel.recv_exit_status()
        out = stdout.read().decode("utf-8", "replace")
        err = stderr.read().decode("utf-8", "replace")
        if label is not None:
            print(f"\n===== [{label}] exit={code} =====")
            if out.strip():
                print(out.strip()[-2000:])
            if err.strip() and err.strip() != out.strip():
                print("[stderr]", err.strip()[-1000:])
        return code, out, err

    code, out, _ = run("whoami", label="whoami")
    if _ac.USER not in out:
        print("FATAL: unexpected user"); sys.exit(1)

    run("whoami", sudo=True, label="sudo check (expect root)")

    run(f"mkdir -p {BASE}/arcade-data {BASE}/roms/fbneo {BASE}/roms/nes {BASE}/roms/sfc {BASE}/roms/gb {BASE}/roms/gba {BASE}/roms/md {BASE}/roms/psx && ls -la {BASE}",
        sudo=True, label="create dirs")

    sftp = ssh.open_sftp()
    sftp.put(COMPOSE_LOCAL, "/tmp/game-arcade-compose.yml")
    sftp.close()
    run(f"cp /tmp/game-arcade-compose.yml {BASE}/docker-compose.yml && rm /tmp/game-arcade-compose.yml && head -5 {BASE}/docker-compose.yml",
        sudo=True, label="upload compose")

    run("docker compose version 2>/dev/null || docker-compose version", label="compose availability")

    code, out, err = run(f"bash -c 'cd {BASE} && docker compose up -d'", timeout=900, sudo=True, label="compose up (pull may take minutes)")
    if code != 0:
        print("\n!!! compose up failed, retrying once after 5s ...")
        time.sleep(5)
        code, out, err = run(f"bash -c 'cd {BASE} && docker compose up -d'", timeout=900, sudo=True, label="compose up retry")
        if code != 0:
            print("!!! still failing. Check registry mirror / daemon logs next."); sys.exit(2)

    run("docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'", sudo=True, label="containers")
    time.sleep(6)
    run("curl -s -o /dev/null -w 'local http_code=%{http_code}' http://127.0.0.1:3000/", label="local health check")
    run(f"docker logs childhood-arcade --tail 20 2>&1", sudo=True, label="container logs")

    ssh.close()
    print("\nDEPLOY DONE")


if __name__ == "__main__":
    main()
