# -*- coding: utf-8 -*-
"""补丁结构体检（防止「新补丁被吞进上一个 IIFE」这类静默事故）。

背景（2026-09-14 真实踩到）：
  Player-BwKb4RpM.js 里 `/*[patch]gp-port-assign*/;(function(){...` 的 IIFE **没有就地闭合**，
  它的收尾 `})();` 被一路推到了文件最末尾。后果是：之后追加的 `[patch] kb-focus`、`[patch] router`
  全都变成了那个 IIFE 的**内部语句**，落在 `if(globalThis.__gpStatusInstalled)return;` 之后。
  语法检查（node --check）照样通过，页面也照样能跑 —— 属于最难发现的一类。

判据（简单且准确）：
  真正追加在文件尾部的补丁块，必须自己括号自平衡。取「最后一个 [patch] 标记 → EOF」这段，
  丢给 node --check：能过 = 该块自洽；不能过 = 它把括号泄漏给了下一个块（或有别的结构错误）。

用法：
  python check_patch_structure.py                # 检查 Player-BwKb4RpM.js
  python check_patch_structure.py <文件>          # 检查任意 JS 补丁
"""
import os
import re
import subprocess
import sys

NODE = r"C:/Users/a2274/.workbuddy/binaries/node/versions/22.22.2-3/node.exe"
HERE = os.path.dirname(os.path.abspath(__file__))
MARKER = re.compile(r"/\* ?\[patch\]\s*([A-Za-z0-9_\-]+)")


def check_node(blk, tmp):
    with open(tmp, "w", encoding="utf-8", newline="") as f:
        f.write(blk)
    r = subprocess.run([NODE, "--check", tmp], capture_output=True, text=True)
    return r.returncode == 0, (r.stderr or "").strip()


def iife_start_before(text, pos):
    """标记往往写在它所标注的 IIFE 内部，所以也要试着从最近的顶层 `\\n(function` 起切。"""
    a = text.rfind("\n(function", 0, pos)
    return a + 1 if a >= 0 else None


def probe(text, pos, tmp):
    """判定「这个补丁块是否自洽」：标记处起的切片，或最近顶层 `(function` 起的切片，
    任意一个能通过 node --check 就算自洽。两者都不过 → 很可能是括号泄漏给了下一个块。"""
    ok1, err1 = check_node(text[pos:], tmp)
    alt = iife_start_before(text, pos)
    ok2, err2 = (False, "")
    if alt is not None:
        ok2, err2 = check_node(text[alt:], tmp)
    return (ok1, err1, ok2, err2)


def main():
    name = sys.argv[1] if len(sys.argv) > 1 else "Player-BwKb4RpM.js"
    path = os.path.join(HERE, name)
    text = open(path, encoding="utf-8", newline="").read()
    tmp = os.path.join(HERE, "_structure_probe.js")

    ok_whole, err_whole = check_node(text, tmp)
    print("整文件 node --check : %s" % ("PASS" if ok_whole else "FAIL"))
    if not ok_whole:
        print("   " + " | ".join(err_whole.split("\n")[:4]))

    hits = list(MARKER.finditer(text))
    print("发现 %d 个 [patch] 标记" % len(hits))
    last_ok = None
    for m in hits:
        tag = m.group(1)
        pos = m.start()
        ok1, err1, ok2, err2 = probe(text, pos, tmp)
        ok = ok1 or ok2
        line = text.count("\n", 0, pos) + 1
        how = "标记起" if ok1 else ("顶层IIFE起" if ok2 else "都不平衡")
        print("   %-16s @%-7d (line %-4d) 自洽=%-2s [%s]" % (
            tag, pos, line, "是" if ok else "否", how))
        if not ok:
            e = (err1 or err2)
            if e:
                print("        " + " | ".join(e.split("\n")[:3]))
        last_ok = (tag, ok)

    if os.path.exists(tmp):
        os.remove(tmp)

    # 只对「文件最末尾那个追加块」做强断言：它必须自洽。
    print("-" * 60)
    if last_ok is None:
        print("没有 [patch] 标记，跳过结构断言")
        return 0
    tag, ok = last_ok
    if ok:
        print("PASS：末尾补丁块 [patch] %s 自洽，括号没有泄漏给下一个块。" % tag)
        return 0
    print("FAIL：末尾补丁块 [patch] %s 括号不平衡 —— " % tag)
    print("      多半是上一个补丁的 IIFE 没就地闭合，后面的代码被吞进去了。")
    print("      修法：找到上一个块开 `(function(){` 的位置，在它自己的收尾处就地补 `})();`，")
    print("            并从文件末尾删掉那个多出来的 `})();`。改完再跑一遍本脚本。")
    return 1


if __name__ == "__main__":
    sys.exit(main())
