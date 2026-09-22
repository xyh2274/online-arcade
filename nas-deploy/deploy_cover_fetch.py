# -*- coding: utf-8 -*-
import arcade_env as _ac  # 凭据集中在 arcade.env（见 arcade.env.example）
"""上传 cover_fetch.py / cover_backfill.py / rom_import.py 到 NAS 并执行存量回填"""
import paramiko

cli = paramiko.SSHClient()
cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
cli.connect(_ac.HOST, 22, _ac.USER, _ac.PWD, timeout=10)

def run(cmd, label="", t=300):
    if label: print("="*15, label, "="*15)
    _, out, err = cli.exec_command(cmd, timeout=t)
    o, e = out.read().decode("utf-8","replace"), err.read().decode("utf-8","replace")
    if o.strip(): print(o[:6000])
    if e.strip(): print("[stderr]", e[:600])

R = "/vol1/1000/docker/game-arcade/roms-import"
sftp = cli.open_sftp()
for f in ("cover_fetch.py", "cover_backfill.py", "rom_import.py"):
    sftp.put(rf"D:\MyBlog\GameGo\在线游戏厅\nas-deploy\{f}", f"{R}/{f}")
    print(f"已上传 {f}")
sftp.close()

run("python3 " + R + "/cover_backfill.py", "存量封面回填", t=600)
cli.close()
print("DONE")
