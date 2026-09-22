# -*- coding: utf-8 -*-
"""本机构建 libretro-thumbnails 索引: 标准化名 → 缩略图文件路径"""
import json
import re
import urllib.request

REPOS = {
    "fbneo_thumbs": "FBNeo_-_Arcade_Games",
    "md_thumbs": "Sega_-_Mega_Drive_-_Genesis",
}
DIRS = ["Named_Boxarts", "Named_Snaps", "Named_Titles"]
UA = {"User-Agent": "cover-index-builder/1.0"}


def norm(s):
    return re.sub(r"[^a-z0-9]", "", s.lower())


def fetch_tree(repo):
    url = f"https://api.github.com/repos/libretro-thumbnails/{repo}/git/trees/master?recursive=1"
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.load(r)


for out_name, repo in REPOS.items():
    data = fetch_tree(repo)
    truncated = data.get("truncated", False)
    idx = {}
    for it in data.get("tree", []):
        p = it.get("path", "")
        parts = p.split("/", 1)
        if len(parts) != 2 or parts[0] not in DIRS or not p.endswith(".png"):
            continue
        stem = norm(parts[1][:-4])
        if not stem:
            continue
        e = idx.setdefault(stem, {})
        e[parts[0]] = p
    json.dump(idx, open(out_name + ".json", "w", encoding="utf-8"), ensure_ascii=False)
    print(f"{repo}: 文件树 truncated={truncated}, 索引条目 {len(idx)}")
    # 打几个样例验证
    for probe in ["doubledragon", "doubledragon3therosetastone", "kov", "kof2002", "neobomberman",
                  "yuuyuuhakushomakyoutoitsusenjapan"]:
        if probe in idx:
            print("  样例", probe, "->", idx[probe])
print("BUILD DONE")
