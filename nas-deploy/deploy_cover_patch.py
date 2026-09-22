# -*- coding: utf-8 -*-
import arcade_env as _ac  # 凭据集中在 arcade.env（见 arcade.env.example）
"""部署封面补丁：拷贝容器文件 → 上传并执行 patch_files.py → 重启容器 → 验证"""
import paramiko

cli = paramiko.SSHClient()
cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
cli.connect(_ac.HOST, 22, _ac.USER, _ac.PWD, timeout=10)

def run(cmd, label="", t=60):
    if label: print("="*15, label, "="*15)
    _, out, err = cli.exec_command(cmd, timeout=t)
    o, e = out.read().decode("utf-8","replace"), err.read().decode("utf-8","replace")
    if o.strip(): print(o[:4000])
    if e.strip(): print("[stderr]", e[:600])
    return o

B = "/vol1/1000/docker/game-arcade"
# 1. 从容器拷出待补丁文件
run(f"mkdir -p {B}/covers && "
    f"docker cp childhood-arcade:/app/server/db/schema.js {B}/patches/schema.js && "
    f"docker cp childhood-arcade:/app/server/routes/roms.js {B}/patches/roms.js && "
    f"docker cp childhood-arcade:/app/dist/assets/Gallery--nH9P_9t.js {B}/patches/Gallery--nH9P_9t.js && "
    f"docker cp childhood-arcade:/app/dist/assets/Gallery-dcHxang3.css {B}/patches/Gallery-dcHxang3.css && echo COPIED",
    "拷贝容器文件到 patches/")

# 2. 上传补丁脚本并执行
sftp = cli.open_sftp()
sftp.put(r"D:\MyBlog\GameGo\在线游戏厅\nas-deploy\patch_files.py", "/tmp/patch_files.py")
sftp.close()
run("python3 /tmp/patch_files.py", "执行补丁", t=120)

# 3. 重启容器（重建以应用新挂载）
run(f"cd {B} && docker compose up -d 2>&1 | tail -5", "compose up -d", t=180)
run("sleep 4; docker ps --filter name=childhood-arcade --format '{{.Names}} {{.Status}}'", "容器状态")

# 4. 验证
run("curl -s -o /dev/null -w 'home=%{http_code}\\n' http://localhost:3000/", "首页状态")
run("docker exec childhood-arcade grep -c 'tile-cover' /app/dist/assets/Gallery--nH9P_9t.js", "容器内前端补丁生效")
run("docker exec childhood-arcade grep -c 'cover' /app/server/db/schema.js", "容器内 schema 补丁生效")
run("docker logs childhood-arcade 2>&1 | tail -5", "容器日志尾部")

cli.close()
print("DONE")
