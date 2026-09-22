# -*- coding: utf-8 -*-
import arcade_env as _ac  # 凭据集中在 arcade.env（见 arcade.env.example）
"""补丁文件安全部署器（带回归闸门）。

它解决的问题：
  这些补丁文件是「整份覆盖」上传的。如果某一轮改动只落在 NAS 上、本地副本没同步，
  下一次上传就会把之前的功能静默抹掉（2026-09-14 顶栏 position:static 修复就是这样丢的）。

闸门逻辑（上传前执行）：
  1. 把容器里当前的同名文件拉下来。
  2. 提取其中所有 `[patch] 说明` 标记块。
  3. 若某个标记在新（本地）内容里不存在 → 判定为「会丢功能」→ 中止，除非 --force。
  4. 再按 KNOWN_MARKERS 做一次关键特性存在性核对。

用法：
  python deploy_patch.py Player-CYZDJezR.css
  python deploy_patch.py Player-CYZDJezR.css --force
"""
import os, re, sys

import paramiko

B = "/vol1/1000/docker/game-arcade"
LOCAL = os.path.dirname(os.path.abspath(__file__))
CONTAINER = "childhood-arcade"

# 容器内路径映射（补丁文件名 -> 容器内绝对路径）
CONTAINER_PATH = {
    "Player-CYZDJezR.css": "/app/dist/assets/Player-CYZDJezR.css",
    "Player-BwKb4RpM.js": "/app/dist/assets/Player-BwKb4RpM.js",
    "Gallery-dcHxang3.css": "/app/dist/assets/Gallery-dcHxang3.css",
    "Gallery--nH9P_9t.js": "/app/dist/assets/Gallery--nH9P_9t.js",
    "UploadDialog-kZO6Kb_z.js": "/app/dist/assets/UploadDialog-kZO6Kb_z.js",
    "fbneo-setnames.json": "/app/dist/assets/fbneo-setnames.json",
    "auth.js": "/app/auth.js",
    "roms.js": "/app/roms.js",
    "schema.js": "/app/server/db/schema.js",
    "db-index.js": "/app/server/db/index.js",
    "server-index.js": "/app/server/index.js",
    "input-mapping.js": "/app/server/routes/input-mapping.js",
    # 平台按键表：由 docker-compose 挂到 dist/assets 下（挂载已存在，改内容即时生效）
    "platforms-remote.js": "/app/dist/assets/platforms-B-OfxkWt.js",
}

# 关键特性白名单：远端有、新内容也必须有的串（防止 marker 之外的功能被吞）
KNOWN_MARKERS = {
    "Player-CYZDJezR.css": ["position:static", "gp-status-line", "pa-panel", "pa-opt", "pa-hide",
                            # 街机式席位提示条（[patch] seat-hud）
                            "arcade-seat-hud", "arcadeSeatPop"],
    "Player-BwKb4RpM.js": ["__gpStatusInstalled", "k[0]!==m", "menu_toggle_gamepad_combo",
                           "_joypad_index", "gp-port-assign",
                           "kbPlayer",
                           "__arcadePorts", "portOrder",
                           "__arcadePadBridgeOff", "padNativeOnly", "isTrusted", "showFix",
                           # 街机式动态占位（[patch] router / [patch] kb-focus）
                           "__arcadeSlots", "__arcadeSeatClaim", "__arcadeSeatPlan",
                           "__arcadeRouterOn", "arcade-seat-hud",
                           # 连发（[patch] turbo）：NES 的 4 个动作键 = RetroPad a/b/x/y，
                           # X=连发A、Y=连发B（libretro-fceumm turbomap）。
                           # ⛔ 这里曾经是 "turboA" / "turboB" —— 那两个是我编的逻辑键，
                           #    RetroArch 不认，已废弃；现在靠核心选项 + 平台表暴露 x/y。
                           "arcade-turbo", "fceumm_turbo_enable", "fceumm_turbo_delay",
                           "__arcadeCoreOptions", "__arcadeAnalogDpadCfg",
                           "retroarchCoreConfig",
                           # 键位按平台分维度（2026-09-14）：站点默认 + 玩家只存 diff + 自动去重
                           "__arcadeEffKb", "__arcadeEffGm", "__arcadeKeyPack",
                           "__arcadeSetKeyPlatform", "__arcadeKeyAdminUI",
                           "kb-dedupe", "HARD_KB", "HARD_GM",
                           # 重复键清理（WASD 的 W 被 r 抢走）
                           "__arcadeDedupe", "kb-conflict", "KORDER",
                           # 手柄自定义必须下发（改 ABXY 没效果）
                           "pad-map",
                           # 平台必须在核心启动前就位（否则站点默认键位从未下发核心，2026-09-15）
                           "key-platform-sync", "__arcadeApplyPlatformNow", "applyMerged",
                           # 「应用并重启」按钮（改完键立刻生效）
                           "keys-live", "__arcadeApplyKeysLive", "__arcadePortalRemount",
                           # 重置/暂停浮动按钮
                           "__arcadeEmuInst", "emu-buttons",
                           # 手柄按钮号→标准名显示
                           "__arcadePadNames",
                           # 摇杆轴绑定（面板能拨摇杆绑上/下/左/右，下发 input_playerN_*_axis）
                           "axis-bind", "__arcadeAxisName", "__arcadeAxisTok",
                           # 本机已保存的键位不能被 applyMerged 重置掉（游客/401 时「改完键又变回去」）
                           "local-keep",
                           # 底部按钮区外观统一（面板底部原来会把三个动作按钮挤成竖排字）
                           "foot-css", "foot-ui", "__arcadeFootCssMod", "ka-grid", "ka-btn"],
    "platforms-remote.js": ["[patch] turbo", '"a","b","x","y"', "X-连发A", "Y-连发B"],
    # 键位按平台分维度（2026-09-14）：站点默认 input_defaults + 玩家键位 (user_id, platform)
    "schema.js": ["inputDefaults", "inputMappings", "GLOBAL_PLATFORM", "primaryKey"],
    "db-index.js": ["ensureInputSchema", "input_defaults", "PRAGMA table_info",
                    "diffAgainstDefault", "PT_DEFAULT", "import.meta.url"],
    "input-mapping.js": ["normalizePlatform", "GLOBAL_PLATFORM", "/defaults",
                         "inputDefaults", "PLATFORM_RE"],
}

# 本轮明确移除的旧 UI（2026-09-14）：工具栏「玩家分配」按钮 + 键盘=1P..4P 选择器
# 它们从本地消失是预期内的，但远端可能还在 —— 登记为「被取代」，避免闸门误报。
SUPERSEDED_MARKER_STRINGS = {
    "Player-BwKb4RpM.js": {
        "bar-btn-players": "旧工具栏「玩家分配」按钮（已被动态席位 HUD 取代）",
        "is-players": "旧「键盘=1P..4P」选择器（已被 START 入座取代）",
        "is-kbtip": "旧键盘归属提示",
        '"players"': "旧 players 事件（已随按钮移除）",
    },
}


def markers_of(text):
    """提取 [patch] 标签（稳定短标签，如 '[patch] ports' / '[patch]pa-panel'）。
    旧版正则贪婪吃掉 80 字符，导致只改一行日志就被判成"丢功能"，这里改为只取标签本身。"""
    return set(m.strip() for m in re.findall(r"\[patch\][A-Za-z0-9_\-]+(?:\s[A-Za-z0-9_\-]+)*", text))


# 明确"已被新补丁取代"的旧标签：它们从远端消失是预期内的，不算回归
SUPERSEDED = {
    "Player-BwKb4RpM.js": {
        "[patch] gamepad ports",   # 旧的手柄端口分配 IIFE，已被 [patch] ports 统一取代
    },
    # 2026-09-14：旧玩家分配 UI 整体下线（工具栏按钮 + 键盘=1P..4P 选择器 + 其样式）
    # 取代者：街机式动态席位（按 START 入座）+ 常驻席位 HUD
    "Player-CYZDJezR.css": {
        "[patch]kb-owner",
    },
}


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    force = "--force" in sys.argv
    if not args:
        print("用法: python deploy_patch.py <补丁文件名> [--force]")
        return 2
    name = args[0]
    local_path = os.path.join(LOCAL, name)
    if not os.path.exists(local_path):
        print("!! 本地文件不存在:", local_path)
        return 2
    local_text = open(local_path, encoding="utf-8", errors="replace").read()

    cli = paramiko.SSHClient()
    cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    cli.connect(_ac.HOST, 22, _ac.USER, _ac.PWD, timeout=10)

    cpath = CONTAINER_PATH.get(name)
    remote_text = ""
    if cpath:
        cmd = "docker exec %s sh -c 'cat %s'" % (CONTAINER, cpath)
        _, out, _ = cli.exec_command(cmd, timeout=60)
        remote_text = out.read().decode("utf-8", "replace")
        print("远端当前大小: %d 字符" % len(remote_text))

    # --pull：把容器内「真实在跑的」内容存成参考副本，作为手工修改的基线
    # （不覆盖本地文件，避免丢掉还没部署的改动）
    if "--pull" in sys.argv:
        if not remote_text:
            print("!! 无法获取远端内容（无路径映射或容器读取失败）")
            cli.close()
            return 1
        ref = local_path + ".remote"
        # ⚠ newline="" 必须写：Windows 默认文本模式会把 LF 改写成 CRLF，
        #   于是参考副本与本地比出 690 处「假差异」（2026-09-15 踩过）。
        open(ref, "w", encoding="utf-8", newline="").write(remote_text)
        print("已保存参考副本:", ref, "(%d 字符)" % len(remote_text))
        print("其中的补丁块:", sorted(m.strip() for m in markers_of(remote_text)) or "（无 [patch] 标记）")
        cli.close()
        return 0

    # ---- 闸门 1：远端已有的 [patch] 标记必须保留（已登记为"被取代"的除外）----
    sup = SUPERSEDED.get(name, set())
    lost = sorted(m for m in markers_of(remote_text)
                  if m not in local_text and m not in sup)
    if sup & markers_of(remote_text):
        print("已登记被取代的旧标签（预期消失）:", sorted(sup & markers_of(remote_text)))
    # ---- 闸门 2：关键特性白名单必须在新内容里存在（不看远端，避免"两边都没有"被静默放过）----
    miss = [mk for mk in KNOWN_MARKERS.get(name, []) if mk not in local_text]

    if lost or miss:
        print("\n!!! 回归闸门拦截 !!!")
        for m in lost:
            print("  将丢失补丁块:", m.strip())
        for m in miss:
            print("  将丢失关键特性:", m)
        print("远端已有的功能会消失。若确认是有意删除，加 --force 重跑。")
        cli.close()
        return 1
    print("回归闸门: PASS（远端已有功能均被保留）")

    # ---- 上传 ----
    sftp = cli.open_sftp()
    sftp.put(local_path, B + "/patches/" + name)
    st = sftp.stat(B + "/patches/" + name)
    sftp.close()
    print("已上传 -> %s/patches/%s (%d bytes)" % (B, name, st.st_size))

    # ---- 校验：容器内 + HTTP 服务端内容一致 ----
    if cpath:
        _, out, _ = cli.exec_command("docker exec %s sh -c 'wc -c %s'" % (CONTAINER, cpath), timeout=40)
        print("容器内:", out.read().decode("utf-8", "replace").strip())
        checks = []
        for mk in ["position:static", "gp-status-line"] if name.endswith(".css") else []:
            checks.append("echo -n '%s='; curl -s http://localhost:3000/assets/%s | grep -c '%s';"
                          % (mk, name, mk))
        if checks:
            _, out, _ = cli.exec_command(" ".join(checks), timeout=40)
            print(out.read().decode("utf-8", "replace").strip())

    _, out, _ = cli.exec_command("curl -s -o /dev/null -w 'home=%{http_code}\\n' http://localhost:3000/", timeout=20)
    print(out.read().decode("utf-8", "replace").strip())

    cli.close()
    print("DONE")
    return 0


if __name__ == "__main__":
    sys.exit(main())
