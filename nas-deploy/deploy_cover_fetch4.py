# -*- coding: utf-8 -*-
import arcade_env as _ac  # 凭据集中在 arcade.env（见 arcade.env.example）
"""检查回填状态, 必要时重启, 轮询结果"""
import paramiko, time

cli = paramiko.SSHClient()
cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
cli.connect(_ac.HOST, 22, _ac.USER, _ac.PWD, timeout=10)

def run(cmd, label="", t=60):
    if label: print("="*15, label, "="*15, flush=True)
    _, out, err = cli.exec_command(cmd, timeout=t)
    o, e = out.read().decode("utf-8","replace"), err.read().decode("utf-8","replace")
    if o.strip(): print(o[:6000], flush=True)
    if e.strip(): print("[stderr]", e[:600], flush=True)

R = "/vol1/1000/docker/game-arcade/roms-import"
_, out, _ = cli.exec_command("pgrep -f cover_backfill >/dev/null && echo RUNNING || echo NOT_RUNNING", timeout=15)
st = out.read().decode().strip()
print("当前状态:", st, flush=True)

if st == "NOT_RUNNING":
    run("cd " + R + " && nohup python3 -u cover_backfill.py > cover_backfill.log 2>&1 < /dev/null & sleep 1; pgrep -f cover_backfill >/dev/null && echo STARTED || echo FAILED", "启动回填", t=20)

for i in range(5):
    time.sleep(35)
    _, out, _ = cli.exec_command("cat " + R + "/cover_backfill.log", timeout=20)
    print(f"----- 第{i+1}次查看 -----", flush=True)
    print(out.read().decode("utf-8", "replace")[:4000], flush=True)
    _, out2, _ = cli.exec_command("pgrep -f cover_backfill >/dev/null && echo RUNNING || echo FINISHED", timeout=15)
    st = out2.read().decode().strip()
    print("状态:", st, flush=True)
    if st == "FINISHED":
        break

run("ls -la /vol1/1000/docker/game-arcade/covers/ 2>/dev/null | head -20", "covers 目录", t=20)
cli.close()
print("DONE")
