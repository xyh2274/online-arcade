# -*- coding: utf-8 -*-
import arcade_env as _ac  # 凭据集中在 arcade.env（见 arcade.env.example）
"""Grant admin role - script placed inside /app so node_modules resolves."""
import paramiko

HOST, PORT = _ac.HOST, 22
USER, PWD = _ac.USER, _ac.PWD

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST, PORT, USER, PWD, timeout=12)

JS = (
    "const db=require('better-sqlite3')('/data/app.db');"
    "db.prepare(\"update users set role='admin' where username=_ac.USER\").run();"
    "console.log('USERS=' + JSON.stringify(db.prepare('select id,username,role from users').all()));"
)
sftp = ssh.open_sftp()
with sftp.open("/tmp/g.js", "w") as f:
    f.write(JS)
sftp.close()

def sudo_run(cmd, timeout=60):
    stdin, stdout, stderr = ssh.exec_command("sudo -S -p '' " + cmd, timeout=timeout, get_pty=True)
    stdin.write(PWD + "\n")
    stdin.flush()
    code = stdout.channel.recv_exit_status()
    out = stdout.read().decode("utf-8", "replace")
    print(f"exit={code} :: {cmd[:70]}")
    print(out.strip()[-1200:])
    return code

sudo_run("docker cp /tmp/g.js childhood-arcade:/app/g.cjs")
sudo_run("docker exec -w /app childhood-arcade node /app/g.cjs")
sudo_run("docker exec childhood-arcade rm -f /app/g.cjs")
sudo_run("rm -f /tmp/g.js")
ssh.close()
