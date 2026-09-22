# -*- coding: utf-8 -*-
import arcade_env as _ac  # 凭据集中在 arcade.env（见 arcade.env.example）
"""后台上传+执行封面回填, 避免前台超时"""
import paramiko, time

cli = paramiko.SSHClient()
cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
cli.connect(_ac.HOST, 22, _ac.USER, _ac.PWD, timeout=10)

R = "/vol1/1000/docker/game-arcade/roms-import"
sftp = cli.open_sftp()
for f in ("cover_fetch.py", "cover_backfill.py", "rom_import.py"):
    sftp.put(rf"D:\MyBlog\GameGo\在线游戏厅\nas-deploy\{f}", f"{R}/{f}")
    print(f"已上传 {f}", flush=True)
sftp.close()

# 后台执行, 日志落盘
cli.exec_command(f"cd {R} && nohup python3 -u cover_backfill.py > cover_backfill.log 2>&1 &")
print("已在 NAS 后台启动回填, 日志: roms-import/cover_backfill.log", flush=True)

# 轮询 3 次, 每次等 45 秒
for i in range(3):
    time.sleep(45)
    _, out, _ = cli.exec_command(f"cat {R}/cover_backfill.log", timeout=20)
    print(f"----- 第{i+1}次查看 -----", flush=True)
    print(out.read().decode("utf-8", "replace")[:4000], flush=True)
    _, out2, _ = cli.exec_command(f"pgrep -f cover_backfill >/dev/null && echo RUNNING || echo FINISHED", timeout=15)
    st = out2.read().decode().strip()
    print("状态:", st, flush=True)
    if st == "FINISHED":
        break
cli.close()
print("DONE", flush=True)
