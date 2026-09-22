#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""重建 FBNeo 指纹库（修正「父集被克隆集覆盖而消失」的 bug）。

## 原实现的 bug（2026-09-17 发现）

rom_import.py 的 parse_dat():
    for c in ...: db[crc] = [setname, desc]      # ← 后写覆盖
    ...
    for crc,(setname,desc) in db.items():
        if setname not in sets: sets[setname] = [desc, setname]

父集（如 `kof98`）的 ROM 与它的克隆/变体集（`kof98a`/`kof98h`/`kof98mix`…）**共享同一批 CRC**，
而覆盖是「后来的赢」——变体按字母序排在父集后面 ⇒ 父集的所有 CRC 都被改写成变体名
⇒ **`kof98` 这个父集在 sets.json 里彻底消失**。

后果（实测）：
  · `kof98.zip` 文件名层匹配不上 → 落到 CRC 层 → 被判成 `kof98mix`(Unlimited Hack)
  · 结果是**中文名和封面都会取错**（标题变成「拳皇98 Unlimited」、封面取到 hack 版）
  · 同样受害的还有 `kof2002`（→ 被判成 kf2k2plc / kof2002t）

## 修法

1. **CRCDB 改「首次命中优先」**：dat 是按 name 排序的，父集总在变体之前 ⇒
   首次命中大概率就是父集，符合「想知道这个 zip 是哪个游戏」的用途。
2. **SETS 独立构建**：直接遍历 dat 里**每一个** `<game>/<machine>` 节点，
   不再从 CRC 倒排表反推 ⇒ 父集不会再消失。
3. **`parents.json`（新增）**：记录「父集 → 全部子集」，供将来做别名/回退时用。

用法（在 NAS 上跑，dat 已在 /tmp/fbneo.dat）：
    python3 rebuild_fbneo_db.py [dat路径]
输出：fbneo_crc.json / fbneo_sets.json（先备份为 .bak-<时间戳>）
"""
import json
import os
import re
import shutil
import sys
import time

HERE = "/vol1/1000/docker/game-arcade/roms-import"
DEFAULT_DAT = "/tmp/fbneo.dat"
CRCDB = os.path.join(HERE, "fbneo_crc.json")
SETS = os.path.join(HERE, "fbneo_sets.json")
PARENTS = os.path.join(HERE, "fbneo_parents.json")
MACH = re.compile(r'<(game|machine)\s([^>]*)>(.*?)</\1>', re.S)
ATTR = re.compile(r'(\w+)="([^"]*)"')


def main():
    dat = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_DAT
    if not os.path.exists(dat):
        print("找不到 dat:", dat)
        return 1
    text = open(dat, encoding="utf-8", errors="replace").read()
    print("dat: %s  (%.1f MB)" % (dat, len(text) / 1e6))

    games = []           # [(name, desc, romof, cloneof)]
    crc_sets = {}        # crc -> [setname, desc]（候选，稍后按「父集优先」裁决）
    sets = {}            # setname -> [desc, romof]
    is_clone = {}        # setname -> bool
    for m in MACH.finditer(text):
        attrs = dict(ATTR.findall(m.group(2)))       # ★ 属性都在开标签里
        name, block = attrs.get("name"), m.group(3)
        if not name or name in sets:
            continue
        d = re.search(r"<description>(.*?)</description>", block, re.S)
        desc = d.group(1).strip() if d else ""
        # ⚠️ NeoGeo/街机里 romof 指的是 BIOS（neogeo/pgm…），父集用 cloneof 表示
        romof = attrs.get("romof")
        cloneof = attrs.get("cloneof")
        games.append((name, desc, romof, cloneof))
        sets[name] = [desc, romof]
        is_clone[name] = bool(cloneof)
        for c in re.finditer(r'crc="([0-9a-fA-F]+)"', block):
            key = c.group(1).lower()
            cur = crc_sets.get(key)
            # ★ 裁决规则：**非克隆集（父集）优先**；同为克隆或同为父集时保留首次出现
            if cur is None or (is_clone.get(cur[0], True) and not cloneof):
                crc_sets[key] = [name, desc]
    crc_db = crc_sets

    # 父集 → 子集（用 cloneof；romof 是 BIOS 依赖，不是父子）
    parents = {}
    for name, desc, romof, cloneof in games:
        if cloneof and cloneof in sets:
            parents.setdefault(cloneof, []).append(name)

    for f in (CRCDB, SETS):
        if os.path.exists(f):
            bak = f + ".bak-" + time.strftime("%Y%m%d-%H%M%S")
            shutil.copyfile(f, bak)
            print("  备份 ->", os.path.basename(bak))

    with open(CRCDB, "w", encoding="utf-8") as f:
        json.dump(crc_db, f, ensure_ascii=False)
    with open(SETS, "w", encoding="utf-8") as f:
        json.dump(sets, f, ensure_ascii=False)
    with open(PARENTS, "w", encoding="utf-8") as f:
        json.dump(parents, f, ensure_ascii=False)

    print("完成：setname %d 个 / CRC %d 条 / 有子集的父集 %d 个"
          % (len(sets), len(crc_db), len(parents)))

    print("\n--- 关键校验 ---")
    for st in ("kof97", "kof98", "kof2002", "kf2k2pla", "kov2", "neobombe", "dino"):
        print("  SETS[%-9s] = %s" % (st, sets.get(st, ["(缺失)"])[0]))
    print("  CRC 反查（应指向父集）:")
    for crc, want in (("8893df89", "kof98"), ("7db81ad9", "kof97"),
                      ("9ede7323", "kof2002"), ("6a3a02f3", "kf2k2pla")):
        got = crc_db.get(crc)
        ok = "OK" if got and got[0] == want else "!!"
        print("    %s -> %-12s (期望 %-9s) %s" % (crc, got[0] if got else "(无)", want, ok))
    print("  kof98 的子集: %s" % json.dumps(parents.get("kof98", [])[:10], ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
