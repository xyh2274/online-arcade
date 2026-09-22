# -*- coding: utf-8 -*-
import arcade_env as _ac  # 凭据集中在 arcade.env（见 arcade.env.example）
"""补丁文件「本地副本 vs 线上实况」全量对账。

用途：本地 nas-deploy/ 里的补丁副本可能和容器里真正在跑的内容不一致。
     只要有人（比如我）拿本地副本整份覆盖上传，就会静默抹掉线上已有功能
     （2026-09-14 顶栏 position:static 修复就是这样丢的）。

做法：从 NAS 的 docker-compose.yml 解析出所有 ./patches/X -> /app/Y 映射，
      逐个把容器内实际内容拉下来，和本地同名文件比对，并报告
      「线上有、本地没有」的关键串 —— 这些就是一旦部署就会丢失的功能。
"""
import os, re, sys

import paramiko

B = "/vol1/1000/docker/game-arcade"
LOCAL = os.path.dirname(os.path.abspath(__file__))
CONTAINER = "childhood-arcade"

# 线上有、本地必须也有的关键特性串（按文件名）。
# 这些是「功能身份证」，一旦本地缺失，说明本地副本落后于线上。
KEY_MARKERS = {
    "Player-CYZDJezR.css": ["position:static", "gp-status-line"],
    "Player-BwKb4RpM.js": ["k[0]!==m", "__gpStatusInstalled", "menu_toggle_gamepad_combo"],
    "UploadDialog-kZO6Kb_z.js": ["fbneo-setnames", "zip"],
    "Gallery-dcHxang3.css": ["tile-cover"],
    "Gallery--nH9P_9t.js": ["tile-cover"],
}


def main():
    cli = paramiko.SSHClient()
    cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    cli.connect(_ac.HOST, 22, _ac.USER, _ac.PWD, timeout=10)

    _, out, _ = cli.exec_command("cat %s/docker-compose.yml" % B, timeout=30)
    compose = out.read().decode("utf-8", "replace")

    mounts = re.findall(r"- \./patches/([^:]+):(/app/[^:]+):ro", compose)
    print("compose 中的补丁挂载: %d 个\n" % len(mounts))

    problems = 0
    print("%-30s %9s %9s  %s" % ("文件", "本地", "线上", "结论"))
    print("-" * 88)
    for name, cpath in mounts:
        local_path = os.path.join(LOCAL, name)
        _, o, _ = cli.exec_command("docker exec %s sh -c 'cat %s'" % (CONTAINER, cpath), timeout=60)
        remote = o.read().decode("utf-8", "replace")
        rlen = len(remote)

        if not os.path.exists(local_path):
            print("%-30s %9s %9d  !! 本地缺失（无法覆盖，但也没有可编辑的基线）" % (name, "-", rlen))
            problems += 1
            continue

        local = open(local_path, encoding="utf-8", errors="replace").read()
        llen = len(local)
        lost = [m for m in KEY_MARKERS.get(name, []) if m in remote and m not in local]

        # 行尾符无关紧要：比对前统一为 LF，避免 CRLF 造成假报警
        same = (local.replace("\r\n", "\n") == remote.replace("\r\n", "\n"))

        if lost:
            verdict = "!! 危险：本地缺 %s —— 覆盖会丢功能" % ", ".join(lost)
            problems += 1
        elif same:
            verdict = "一致"
        else:
            verdict = "有差异（本地缺的功能串: 无）"
        print("%-30s %9d %9d  %s" % (name, llen, rlen, verdict))

    print("-" * 88)
    if problems:
        print("\n发现 %d 处问题：部署前先用 deploy_patch.py --pull 拉取线上基线。" % problems)
    else:
        print("\n全部补丁的本地副本均未落后于线上。")
    cli.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
