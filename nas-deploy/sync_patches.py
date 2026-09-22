# -*- coding: utf-8 -*-
import arcade_env as _ac  # 凭据集中在 arcade.env（见 arcade.env.example）
"""把容器里「真正在跑的」全部补丁文件拉回本地做镜像。

为什么需要：本地副本一旦落后于线上，任何人拿它整份覆盖上传都会静默抹掉线上功能
（2026-09-14 顶栏修复、UploadDialog 的 zip 自动识别都是这么丢的）。

行为：
  - 从 docker-compose.yml 解析 ./patches/X -> /app/Y 映射
  - 逐个下载容器内实际内容，行尾统一为 LF，写到 nas-deploy/<X>
  - 若本地已有同名且内容不同，先备份为 <X>.pre-sync
  - 打印每个文件的变化情况

用法：
  python sync_patches.py            # 预览（不写文件）
  python sync_patches.py --apply    # 实际写入
"""
import os, re, sys

import paramiko

B = "/vol1/1000/docker/game-arcade"
LOCAL = os.path.dirname(os.path.abspath(__file__))
CONTAINER = "childhood-arcade"


def norm(t):
    return t.replace("\r\n", "\n").replace("\r", "\n")


def main():
    apply_changes = "--apply" in sys.argv
    cli = paramiko.SSHClient()
    cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    cli.connect(_ac.HOST, 22, _ac.USER, _ac.PWD, timeout=10)

    _, out, _ = cli.exec_command("cat %s/docker-compose.yml" % B, timeout=30)
    compose = out.read().decode("utf-8", "replace")
    mounts = re.findall(r"- \./patches/([^:]+):(/app/[^:]+):ro", compose)
    print("待同步补丁: %d 个%s\n" % (len(mounts), "" if apply_changes else "（预览模式，加 --apply 才写盘）"))

    for name, cpath in mounts:
        _, o, _ = cli.exec_command("docker exec %s sh -c 'cat %s'" % (CONTAINER, cpath), timeout=90)
        remote = norm(o.read().decode("utf-8", "replace"))
        local_path = os.path.join(LOCAL, name)

        if not os.path.exists(local_path):
            action = "新增本地副本"
            before = "-"
        else:
            local = norm(open(local_path, encoding="utf-8", errors="replace").read())
            if local == remote:
                print("%-30s 已一致 (%d 字符)" % (name, len(remote)))
                continue
            if len(local) < len(remote):
                action = "!! 本地落后于线上，用线上覆盖（旧版备份为 .pre-sync）"
            else:
                action = "内容不同（本地更新？谨慎：线上覆盖本地）"
            before = len(local)
            if apply_changes:
                with open(local_path + ".pre-sync", "w", encoding="utf-8") as f:
                    f.write(open(local_path, encoding="utf-8", errors="replace").read())

        if apply_changes:
            with open(local_path, "w", encoding="utf-8", newline="\n") as f:
                f.write(remote)
        print("%-30s %s  %s -> %d 字符" % (name, action, before, len(remote)))

    cli.close()
    print("\nDONE")
    return 0


if __name__ == "__main__":
    sys.exit(main())
