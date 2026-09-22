#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""封面抓取模块 v2
主源: libretro-thumbnails (GitHub raw)
  - 街机: FBNeo_-_Arcade_Games 仓库, 用 FBNeo dat 的 desc 匹配 Named_Boxarts/Snaps/Titles
  - MD:   Sega_-_Mega_Drive_-_Genesis 仓库, 用 ROM 头部标题匹配 (+ 手工映射)
兜底: ScreenScraper CRC 查询 (游客 403 时快速失败)
下载保存到 {BASE}/covers/rom-<id>.png, 数据库 cover 字段写 /covers/rom-<id>.png
"""
import json
import os
import re
import sqlite3
import time
import urllib.parse
import urllib.request
import zipfile
import zlib

BASE = "/vol1/1000/docker/game-arcade"
COVERS = os.path.join(BASE, "covers")
DB_PATH = os.path.join(BASE, "arcade-data", "app.db")
HERE = os.path.dirname(os.path.abspath(__file__))
UA = {"User-Agent": "Mozilla/5.0 childhood-arcade-covers/1.0"}
SS_API = "https://www.screenscraper.fr/api2/jeuInfos.php"
SS_MEDIA_PRIO = ["boxart", "box-3D", "support-2D", "ss", "screenshot"]
RAW = "https://raw.githubusercontent.com/libretro-thumbnails/{repo}/master/"

# 手工映射: zip 原文件名(小写) → 缩略图仓库内的名称(不含 .png)
MANUAL_OVERRIDES = {
    "4101411.zip": {"repo": "Sega_-_Mega_Drive_-_Genesis",
                    "name": "Yu Yu Hakusho - Makyou Toitsusen (Japan)"},
    "双截龙.zip": {"repo": "FBNeo_-_Arcade_Games",
                 "name": "Double Dragon (World set 1)"},
    "7002058.zip": {"repo": "Nintendo_-_Nintendo_Entertainment_System",
                    "name": "Super Mario Bros. (World)"},
}


def _load(p):
    try:
        return json.load(open(p, encoding="utf-8"))
    except Exception:
        return {}


CRCDB = _load(os.path.join(HERE, "fbneo_crc.json"))
SETS = _load(os.path.join(HERE, "fbneo_sets.json"))
FB_THUMBS = _load(os.path.join(HERE, "fbneo_thumbs.json"))
MD_THUMBS = _load(os.path.join(HERE, "md_thumbs.json"))


def norm(s):
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


def http_get(url, timeout=25):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def is_image(data):
    return len(data) > 800 and (data[:8] == b"\x89PNG\r\n\x1a\n" or data[:3] == b"\xff\xd8\xff")


def download(url, dest):
    data = http_get(url)
    if not is_image(data):
        return False
    with open(dest, "wb") as f:
        f.write(data)
    return True


def raw_urls(repo, name):
    """按名称生成 raw.githubusercontent 候选 (Boxart > Snap > Title)"""
    q = urllib.parse.quote
    base = RAW.format(repo=repo)
    return [base + q(d + "/" + name + ".png", safe="/")
            for d in ("Named_Boxarts", "Named_Snaps", "Named_Titles")]


def arcade_candidates(file_name, path):
    """街机: dat desc → 缩略图索引; 找不到再试 setname; 最后 ScreenScraper"""
    setname = stem = os.path.splitext(os.path.basename(file_name))[0].lower()
    if setname not in SETS:
        setname = None
        try:
            z = zipfile.ZipFile(path)
            for i in z.infolist():
                if i.is_dir():
                    continue
                hit = CRCDB.get(f"{i.CRC:08x}")
                if hit:
                    setname = hit[0]
                    break
        except Exception:
            pass
    urls = []
    if setname and FB_THUMBS:
        desc = SETS.get(setname, [None, None])[0]
        for key in (norm(desc), norm(setname)):
            e = FB_THUMBS.get(key)
            if e:
                for d in ("Named_Boxarts", "Named_Snaps", "Named_Titles"):
                    if e.get(d):
                        urls.append(RAW.format(repo="FBNeo_-_Arcade_Games")
                                    + urllib.parse.quote(e[d], safe="/"))
                break  # desc 命中即不再试 setname
    crc = inner_crc(path)
    if crc:
        u = ss_media_url(crc)
        if u:
            urls.append(u)
    return urls


def console_candidates(file_name, path):
    """主机: 手工映射 → 头部标题匹配 → ScreenScraper"""
    urls = []
    ov = MANUAL_OVERRIDES.get(os.path.basename(file_name).lower())
    if ov:
        urls += raw_urls(ov["repo"], ov["name"])
    crc = inner_crc(path)
    if crc:
        u = ss_media_url(crc)
        if u:
            urls.append(u)
    return urls


def inner_crc(path):
    """zip 内单个有效 rom 的 CRC32 (跳过 .url/.txt 等垃圾文件); 裸文件算整体"""
    if path.lower().endswith(".zip"):
        try:
            z = zipfile.ZipFile(path)
            junk = {".url", ".txt", ".nfo", ".htm", ".html", ".png", ".jpg", ".ini"}
            real = [i for i in z.infolist()
                    if not i.is_dir() and os.path.splitext(i.filename)[1].lower() not in junk]
            if len(real) == 1:
                return f"{real[0].CRC:08x}"
        except Exception:
            return None
        return None
    c = 0
    try:
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(1 << 20), b""):
                c = zlib.crc32(chunk, c)
        return f"{c:08x}"
    except Exception:
        return None


def ss_media_url(crc):
    """ScreenScraper 按 CRC 查封面 (游客被拒时快速失败)"""
    q = urllib.parse.urlencode({
        "devid": "guest", "devpassword": "guest",
        "softname": "childhood-arcade", "output": "json", "crc": crc,
    })
    try:
        j = json.loads(http_get(SS_API + "?" + q, timeout=15).decode("utf-8", "replace"))
        medias = (j.get("response", {}).get("jeu", {}) or {}).get("medias") or []
        for t in SS_MEDIA_PRIO:
            for m in medias:
                if m.get("type") == t and m.get("url"):
                    return m["url"]
    except Exception:
        pass
    return None


def apply_db(rom_id, cover):
    db = sqlite3.connect(DB_PATH)
    db.execute("UPDATE roms SET cover=? WHERE id=?", (cover, rom_id))
    db.commit()
    db.close()


def fetch_cover(rom_id, platform, path, file_name):
    """返回 '/covers/rom-<id>.png' 或 None; 成功时同时写库"""
    os.makedirs(COVERS, exist_ok=True)
    dest = os.path.join(COVERS, f"rom-{rom_id}.png")
    ov = MANUAL_OVERRIDES.get(os.path.basename(file_name).lower())
    if ov:
        candidates = raw_urls(ov["repo"], ov["name"])
    elif platform == "arcade":
        candidates = arcade_candidates(file_name, path)
    else:
        candidates = console_candidates(file_name, path)
    for url in candidates:
        try:
            if download(url, dest):
                cover = f"/covers/rom-{rom_id}.png"
                apply_db(rom_id, cover)
                return cover
        except Exception:
            pass
        time.sleep(0.3)
    return None
