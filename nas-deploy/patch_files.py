#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""封面功能一次性部署脚本（在 NAS 上运行）:
1. 给 roms 表加 cover 列
2. patch schema.js / roms.js / Gallery js+css（配合 compose volume 挂载）
3. docker-compose.yml 增加挂载项
4. 建 covers 目录
"""
import sqlite3, sys

BASE = "/vol1/1000/docker/game-arcade"
P = BASE + "/patches"


def patch(path, old, new, must=1):
    s = open(path, encoding="utf-8").read()
    n = s.count(old)
    if n != must:
        print(f"[FAIL] {path}: 模式出现 {n} 次 (期望 {must})")
        sys.exit(1)
    open(path, "w", encoding="utf-8").write(s.replace(old, new))
    print(f"[OK] 已补丁 {path.split('/')[-1]}")


# ---- 1. drizzle schema: roms 表加 cover ----
patch(P + "/schema.js",
      "  versionLabel: text('version_label'),\n",
      "  versionLabel: text('version_label'),\n  cover: text('cover'),\n")

# ---- 2. serialize 返回 cover ----
patch(P + "/roms.js",
      "    title: rom.title,\n",
      "    title: rom.title,\n    cover: rom.cover ?? null,\n")

# ---- 3. Gallery 卡片: 有 cover 渲染 <img>, 否则首字母 ----
patch(P + "/Gallery--nH9P_9t.js",
      't("span",Pt,a(s.title.slice(0,1).toUpperCase()),1),f(d)?',
      's.cover?(o(),i("img",{key:8,class:"tile-cover",src:s.cover,alt:"",loading:"lazy"},null,8,["src"])):'
      't("span",Pt,a(s.title.slice(0,1).toUpperCase()),1),f(d)?')

# ---- 4. Gallery css: 封面图样式 ----
css = P + "/Gallery-dcHxang3.css"
s = open(css, encoding="utf-8").read()
if "tile-cover" not in s:
    with open(css, "a", encoding="utf-8") as f:
        f.write("\n.tile-cover[data-v-a96b52dc]{position:absolute;inset:0;width:100%;height:100%;"
                "object-fit:cover;z-index:0}\n"
                ".tile-cover{position:absolute;inset:0;width:100%;height:100%;object-fit:cover}\n")
    print("[OK] css 已追加 .tile-cover")
else:
    print("[SKIP] css 已有 .tile-cover")

# ---- 5. compose 增加挂载 ----
comp = BASE + "/docker-compose.yml"
s = open(comp, encoding="utf-8").read()
if "patches/schema.js" not in s:
    anchor = None
    for line in s.splitlines():
        if "UploadDialog" in line and "/app/dist/assets" in line:
            anchor = line
            break
    if not anchor:
        print("[FAIL] compose 中未找到 UploadDialog 挂载锚点")
        sys.exit(1)
    add = (
        "      # 封面功能补丁：drizzle schema + serialize + 前端卡片渲染\n"
        "      - ./patches/schema.js:/app/server/db/schema.js:ro\n"
        "      - ./patches/roms.js:/app/server/routes/roms.js:ro\n"
        "      - ./patches/Gallery--nH9P_9t.js:/app/dist/assets/Gallery--nH9P_9t.js:ro\n"
        "      - ./patches/Gallery-dcHxang3.css:/app/dist/assets/Gallery-dcHxang3.css:ro\n"
        "      # 封面图片目录（前端以 /covers/*.png 直接访问）\n"
        "      - ./covers:/app/dist/covers:ro"
    )
    s = s.replace(anchor, anchor + "\n" + add, 1)
    open(comp, "w", encoding="utf-8").write(s)
    print("[OK] compose 已加入 5 个挂载项")
else:
    print("[SKIP] compose 已含封面挂载")

# ---- 6. 建目录 + 数据库加列 ----
import os
os.makedirs(BASE + "/covers", exist_ok=True)
db = sqlite3.connect(BASE + "/arcade-data/app.db")
cols = [r[1] for r in db.execute("PRAGMA table_info(roms)")]
if "cover" not in cols:
    db.execute("ALTER TABLE roms ADD COLUMN cover TEXT")
    db.commit()
    print("[OK] roms 表已加 cover 列")
else:
    print("[SKIP] cover 列已存在")
n = db.execute("SELECT count(*) FROM roms WHERE status=0").fetchone()[0]
print(f"     当前有效 rom 数: {n}")
db.close()
print("PATCH ALL DONE")
