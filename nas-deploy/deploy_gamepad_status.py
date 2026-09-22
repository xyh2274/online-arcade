# -*- coding: utf-8 -*-
import arcade_env as _ac  # 凭据集中在 arcade.env（见 arcade.env.example）
"""部署手柄补丁（放宽手柄序号 + 对话框手柄状态提示）并验证线上生效。"""
import paramiko

B = "/vol1/1000/docker/game-arcade"
LOCAL = r"D:\MyBlog\GameGo\在线游戏厅\nas-deploy"

cli = paramiko.SSHClient()
cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
cli.connect(_ac.HOST, 22, _ac.USER, _ac.PWD, timeout=10)


def run(cmd, label="", t=120):
    if label:
        print("=" * 12, label, "=" * 12, flush=True)
    _, out, err = cli.exec_command(cmd, timeout=t)
    o = out.read().decode("utf-8", "replace")
    e = err.read().decode("utf-8", "replace")
    if o.strip():
        print(o[:3000], flush=True)
    if e.strip():
        print("[stderr]", e[:600], flush=True)


# 0. 确认 compose 里两个补丁挂载都在
run("grep -nE 'Player-BwKb4RpM\\.js|Player-CYZDJezR\\.css' " + B + "/docker-compose.yml", "compose 挂载检查", t=20)

# 1. 上传两个补丁文件（sftp.put 为原地截断写入，bind-mount inode 不变）
sftp = cli.open_sftp()
sftp.put(LOCAL + r"\Player-BwKb4RpM.js", B + "/patches/Player-BwKb4RpM.js")
print("uploaded Player-BwKb4RpM.js", flush=True)
sftp.put(LOCAL + r"\Player-CYZDJezR.css", B + "/patches/Player-CYZDJezR.css")
print("uploaded Player-CYZDJezR.css", flush=True)
st1 = sftp.stat(B + "/patches/Player-BwKb4RpM.js")
st2 = sftp.stat(B + "/patches/Player-CYZDJezR.css")
print("remote sizes:", st1.st_size, st2.st_size, flush=True)
sftp.close()

# 2. 容器内看到的文件大小（验证 mount 生效、inode 一致）
run("docker exec childhood-arcade sh -c 'wc -c /app/dist/assets/Player-BwKb4RpM.js /app/dist/assets/Player-CYZDJezR.css'",
    "container 内文件大小", t=40)

# 3. 线上 HTTP 内容验证
run("echo -n 'gpStatusInstalled='; curl -s http://localhost:3000/assets/Player-BwKb4RpM.js | grep -c __gpStatusInstalled; "
    "echo -n 'statusText='; curl -s http://localhost:3000/assets/Player-BwKb4RpM.js | grep -c '已检测到手柄'; "
    "echo -n 'oldIndexFilter(expect 0)='; curl -s http://localhost:3000/assets/Player-BwKb4RpM.js | grep -c 'm.index!==0'; "
    "echo -n 'newIndexFilter(expect 1)='; curl -s http://localhost:3000/assets/Player-BwKb4RpM.js | grep -c 'k\\[0\\]!==m'; "
    "echo -n 'cssRules(expect 3)='; curl -s http://localhost:3000/assets/Player-CYZDJezR.css | grep -c 'gp-status-line'",
    "HTTP 内容验证", t=40)

run("curl -s -o /dev/null -w 'home=%{http_code} api=%{http_code}\\n' http://localhost:3000/", "健康检查", t=20)

cli.close()
print("DONE")
