#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
童年游戏厅 · ROM 投喂目录自动识别导入器
把 ROM 拷进 roms/inbox/ → 自动识别平台 → 调官方 API 入库 → 归档
用法:
  python3 rom_import.py             # 处理 inbox 里的文件
  python3 rom_import.py --dry-run   # 只看识别结果, 不上传
  python3 rom_import.py --build-db  # 构建/更新 FBNeo CRC 指纹库
"""
import json
import os
import re
import shutil
import sys
import time
import urllib.request
import uuid
import zipfile

BASE = "/vol1/1000/docker/game-arcade"
ROMS = os.path.join(BASE, "roms")
INBOX = os.path.join(ROMS, "inbox")
IMPORTED = os.path.join(ROMS, "imported")
UNKNOWN = os.path.join(ROMS, "unknown")
HERE = os.path.dirname(os.path.abspath(__file__))
CFG_PATH = os.path.join(HERE, "config.json")
CRCDB_PATH = os.path.join(HERE, "fbneo_crc.json")
SETS_PATH = os.path.join(HERE, "fbneo_sets.json")
CN_PATH = os.path.join(HERE, "cn_names.json")
REPORT_PATH = os.path.join(HERE, "last_report.json")

# ---- 层1: 独占扩展名 ----
EXT_UNIQUE = {
    ".nes": "nes", ".unf": "nes", ".unif": "nes",
    ".fds": "fds",
    ".sfc": "sfc", ".smc": "sfc",
    ".gb": "gb",
    ".gbc": "gbc", ".cgb": "gbc", ".sgb": "gbc",
    ".gba": "gba",
    ".md": "megadrive", ".gen": "megadrive", ".smd": "megadrive",
    ".sms": "sms",
    ".gg": "gamegear",
    ".iso": "psx", ".img": "psx", ".pbp": "psx", ".chd": "psx",
}
# ---- 层2: zip 内部结构 ----
CONSOLE_INNER = {
    ".nes": "nes", ".unf": "nes", ".fds": "fds",
    ".smc": "sfc", ".sfc": "sfc",
    ".gb": "gb", ".gbc": "gbc",
    ".gba": "gba",
    ".md": "megadrive", ".gen": "megadrive", ".smd": "megadrive",
    ".68k": "megadrive", ".sgd": "megadrive", ".bin": "megadrive",
    ".sms": "sms", ".gg": "gamegear",
}
# MD (SMD/GEN/BIN) 头部: 0x100=主机名 0x110=版权 0x120=日文名 0x150=海外名
MD_TITLE_OFFSETS = [(0x150, 0x180), (0x120, 0x150)]
ARCADE_INNER = re.compile(r"^\.[a-z]\d+$")  # p1 c2 v4 b1 e1 ... 街机 rom 命名
ARCADE_EXTRA = {".icl"}

# ---- 层3: FBNeo CRC 指纹 ----
UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) rom-import/1.0"}
DAT_URLS = [
    "https://cdn.jsdelivr.net/gh/libretro/FBNeo@master/dats/FinalBurn%20Neo%20(ClrMame%20Pro%20XML%2C%20Arcade%20only).dat",
    "https://raw.githubusercontent.com/libretro/FBNeo/master/dats/FinalBurn%20Neo%20(ClrMame%20Pro%20XML%2C%20Arcade%20only).dat",
    "https://cdn.jsdelivr.net/gh/finalburnneo/FBNeo@master/dats/FinalBurn%20Neo%20(ClrMame%20Pro%20XML%2C%20Arcade%20only).dat",
]


def load_cfg():
    with open(CFG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def load_crcdb():
    if not os.path.exists(CRCDB_PATH):
        return {}
    with open(CRCDB_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def load_sets():
    if not os.path.exists(SETS_PATH):
        return {}
    with open(SETS_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def load_cn():
    if not os.path.exists(CN_PATH):
        return {}
    with open(CN_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def cn_title(sets, cn, setname):
    """setname → 中文名（有映射用映射, 否则英文名）"""
    if setname in cn:
        return cn[setname]
    return sets.get(setname, [None, None])[0]


def _clean_ascii(s):
    s = "".join(ch if (32 <= ord(ch) < 127 or "\u4e00" <= ch <= "\u9fff") else " " for ch in s)
    return re.sub(r"\s+", " ", s).strip()


def md_title_from_bytes(b):
    """从 MD 的 SMD/GEN/BIN 头部提取游戏名 (优先海外名, 次选日文名)"""
    if not b or len(b) < 0x200:
        return None
    for start, end in MD_TITLE_OFFSETS:
        t = _clean_ascii(b[start:end].decode("latin-1", "replace"))
        if len(t) >= 3:
            return t
    return None


def extract_title(platform, b):
    """各平台 ROM 内置标题提取: MD / GB / GBC / GBA / SFC"""
    if platform == "megadrive":
        return md_title_from_bytes(b)
    if not b or len(b) < 0x200:
        return None
    if platform in ("gb", "gbc"):
        return _clean_ascii(b[0x134:0x143].decode("latin-1", "replace")) or None
    if platform == "gba":
        return _clean_ascii(b[0xA0:0xAC].decode("latin-1", "replace")) or None
    if platform in ("sfc", "snes"):
        data = b
        skip = 512 if len(data) % 1024 == 512 else 0  # smc 拷贝头
        data = data[skip:]
        cands = []
        for off in (0x7FC0, 0xFFC0):  # LoRom / HiRom
            if len(data) >= off + 21:
                t = _clean_ascii(data[off:off + 21].decode("latin-1", "replace"))
                if t:
                    cands.append(t)
        if cands:
            return max(cands, key=len)
    return None


def detect(path):
    """返回 (platform, title_hint, reason)"""
    name = os.path.basename(path)
    ext = os.path.splitext(name)[1].lower()
    if ext in EXT_UNIQUE:
        plat = EXT_UNIQUE[ext]
        hint = None
        if plat in ("megadrive", "gb", "gbc", "gba", "sfc", "snes"):
            try:
                with open(path, "rb") as f:
                    hint = extract_title(plat, f.read())
            except Exception:
                pass
        return plat, hint, "扩展名直判"
    if ext == ".zip":
        sets = load_sets()
        cn = load_cn()
        stem = os.path.splitext(name)[0].lower()
        try:
            z = zipfile.ZipFile(path)
            infos = [i for i in z.infolist() if not i.is_dir()]
        except Exception as e:
            return None, None, f"zip 无法解析: {e}"
        if not infos:
            return None, None, "zip 为空"
        inner = [os.path.splitext(i.filename)[1].lower() for i in infos]
        # 剔除网站快捷方式/说明等垃圾文件后, 再判定"单个主机 ROM"
        junk = {".url", ".txt", ".nfo", ".htm", ".html", ".png", ".jpg", ".ini"}
        real = [(i, e) for i, e in zip(infos, inner) if e not in junk]
        if len(real) == 1 and real[0][1] in CONSOLE_INNER:
            plat = CONSOLE_INNER[real[0][1]]
            hint = None
            if plat in ("megadrive", "gb", "gbc", "gba", "sfc", "snes"):
                try:
                    hint = extract_title(plat, z.read(real[0][0].filename))
                except Exception:
                    pass
            return plat, hint, "zip 内单个主机 ROM"
        # 文件名命中 FBNeo setname → 连标题一起解决（街机/NeoGeo 常用命名如 kov.zip, kof2002.zip）
        if stem in sets and sets[stem]:
            return "arcade", cn_title(sets, cn, stem), "文件名命中 FBNeo setname"
        # CRC 指纹（zip 内 rom 文件的 crc 对应哪个游戏）
        db = load_crcdb()
        for i in infos:
            hit = db.get(f"{i.CRC:08x}")
            if hit:
                return "arcade", cn_title(sets, cn, hit[0]) or hit[1], f"FBNeo CRC 命中 {hit[0]}"
        # 结构推断
        if any(ARCADE_INNER.match(e) for e in inner):
            return "arcade", cn.get(stem), "zip 内部为街机 ROM 结构"
        if inner.count(".bin") >= 2 or any(e in ARCADE_EXTRA for e in inner):
            return "arcade", cn.get(stem), "zip 内部多 bin (街机特征)"
        return None, None, "zip 内容无法判定 (可能非 FBNeo/MAME romset)"
    if ext in (".7z", ".rar", ".ace"):
        return None, None, "暂不支持该压缩格式, 请转 zip"
    return None, None, "未识别的扩展名"


# ---------- FBNeo CRC 库构建 ----------
def fetch(url, timeout=120):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def parse_dat(text):
    """兼容 clrmamepro 行格式与 MAME XML 两种 dat。返回 {crc: [setname, desc]}"""
    db = {}
    # FBNeo dat 是 MAME 风格 XML, 但用 <game> 而非 <machine>
    mach = re.compile(r'<(game|machine)\s[^>]*\bname="([^"]+)"[^>]*>(.*?)</\1>', re.S)
    for m in mach.finditer(text):
        setname, block = m.group(2), m.group(3)
        d = re.search(r"<description>(.*?)</description>", block, re.S)
        desc = d.group(1).strip() if d else ""
        for c in re.finditer(r'crc="([0-9a-fA-F]+)"', block):
            db[c.group(1).lower()] = [setname, desc]
    else:
        gname = re.compile(r"\bname\s+(\S+)")
        gdesc = re.compile(r"description\s+\"([^\"]*)\"")
        rcrc = re.compile(r"crc\s+([0-9a-fA-F]+)")
        cur = None
        for line in text.splitlines():
            s = line.strip()
            if s.startswith("game"):
                cur = None
                m = gname.search(s)
                if m:
                    cur = {"name": m.group(1), "desc": ""}
            elif cur is not None and s.startswith("description"):
                m = gdesc.search(s)
                if m:
                    cur["desc"] = m.group(1)
            elif cur is not None and s.startswith("rom"):
                m = rcrc.search(s)
                if m:
                    db[m.group(1).lower()] = [cur["name"], cur["desc"]]
            elif s.startswith(")"):
                pass
    return db


def build_db():
    text = None
    for url in DAT_URLS:
        print(f"尝试下载: {url[:80]}...")
        try:
            text = fetch(url, timeout=600).decode("utf-8", "replace")
            print(f"  成功 ({len(text) // 1024} KB)")
            break
        except Exception as e:
            print(f"  失败: {e}")
    if not text:
        print("所有数据源失败, CRC 层保持原样")
        return 1
    db = parse_dat(text)
    sets = {}
    for crc, (setname, desc) in db.items():
        if setname not in sets:
            sets[setname] = [desc, setname]
    with open(CRCDB_PATH, "w", encoding="utf-8") as f:
        json.dump(db, f, ensure_ascii=False)
    with open(SETS_PATH, "w", encoding="utf-8") as f:
        json.dump(sets, f, ensure_ascii=False)
    print(f"CRC 指纹库构建完成: {len(db)} 条 / setname {len(sets)} 个 → {CRCDB_PATH}")
    return 0


# ---------- 上传 ----------
def http_req(url, data=None, headers=None, method="GET", timeout=300):
    req = urllib.request.Request(url, data=data, headers=headers or {}, method=method)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.status, r.read(), r.headers


def login(cfg):
    body = json.dumps({"username": cfg["username"], "password": cfg["password"]}).encode()
    st, data, headers = http_req(cfg["api"] + "/api/auth/login", data=body,
                                 headers={"Content-Type": "application/json"}, method="POST")
    if st != 200:
        raise RuntimeError(f"登录失败 HTTP {st}: {data[:200]}")
    setc = headers.get("Set-Cookie", "")
    m = re.search(r"session=([^;]+)", setc)
    if not m:
        raise RuntimeError("登录响应中无会话 Cookie")
    return m.group(1)


def multipart(fields, file_name, file_bytes):
    bnd = "----romimport" + uuid.uuid4().hex
    parts = []
    for k, v in fields.items():
        parts.append(f"--{bnd}\r\nContent-Disposition: form-data; name=\"{k}\"\r\n\r\n{v}\r\n".encode())
    parts.append(
        (f"--{bnd}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"{file_name}\"\r\n"
         f"Content-Type: application/octet-stream\r\n\r\n").encode() + file_bytes + b"\r\n")
    body = b"".join(parts) + f"--{bnd}--\r\n".encode()
    return body, f"multipart/form-data; boundary={bnd}"


def upload(cfg, cookie, path, platform, title):
    with open(path, "rb") as f:
        data = f.read()
    body, ctype = multipart({"platform": platform, "title": title[:128], "isPublic": "true"},
                            os.path.basename(path), data)
    st, resp, _ = http_req(cfg["api"] + "/api/roms/upload", data=body,
                           headers={"Cookie": f"session={cookie}", "Content-Type": ctype}, method="POST")
    out = json.loads(resp.decode("utf-8", "replace"))
    if st != 200:
        raise RuntimeError(f"HTTP {st}: {out}")
    return out


def main():
    dry = "--dry-run" in sys.argv
    if "--build-db" in sys.argv:
        sys.exit(build_db())

    cfg = load_cfg()
    for d in (INBOX, IMPORTED, UNKNOWN):
        os.makedirs(d, exist_ok=True)

    files = sorted(f for f in os.listdir(INBOX) if os.path.isfile(os.path.join(INBOX, f)))
    if not files:
        print("inbox 为空, 没有需要导入的 ROM")
        return

    cookie = None
    results = []
    for fname in files:
        path = os.path.join(INBOX, fname)
        platform, hint, reason = detect(path)
        if platform is None:
            print(f"[跳过] {fname} → {reason}")
            shutil.move(path, os.path.join(UNKNOWN, fname))
            results.append({"file": fname, "ok": False, "reason": reason})
            continue

        stem = os.path.splitext(fname)[0]
        title = hint if hint else stem
        if dry:
            print(f"[识别] {fname} → {platform}  (标题: {title})  [{reason}]")
            results.append({"file": fname, "ok": None, "platform": platform, "title": title, "reason": reason})
            continue

        if cookie is None:
            cookie = login(cfg)
        try:
            row = upload(cfg, cookie, path, platform, title)
            dest = os.path.join(IMPORTED, platform)
            os.makedirs(dest, exist_ok=True)
            shutil.move(path, os.path.join(dest, fname))
            print(f"[入库] {fname} → {platform} «{title}» (id={row.get('id')})")
            # 自动抓封面 (街机走 libretro 缩略图, 其他走 ScreenScraper CRC)
            try:
                import cover_fetch
                cover = cover_fetch.fetch_cover(row.get("id"), platform,
                                                os.path.join(dest, fname), fname)
                print(f"    封面: {cover}" if cover else "    封面: 未找到, 保持文字卡片")
            except Exception as e:
                print(f"    封面抓取失败: {e}")
            results.append({"file": fname, "ok": True, "id": row.get("id"), "platform": platform, "title": title})
        except Exception as e:
            print(f"[失败] {fname}: {e}")
            results.append({"file": fname, "ok": False, "reason": str(e)})

    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        json.dump({"time": time.strftime("%Y-%m-%d %H:%M:%S"), "results": results}, f, ensure_ascii=False, indent=2)
    print(f"完成: {sum(1 for r in results if r['ok'])} 入库 / "
          f"{sum(1 for r in results if r['ok'] is False)} 跳过或失败 → 详见 {REPORT_PATH}")


if __name__ == "__main__":
    main()
