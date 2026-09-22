# -*- coding: utf-8 -*-
import arcade_env as _ac  # 凭据集中在 arcade.env（见 arcade.env.example）
"""等回填完成 → 上传最终版 cover_fetch 再补漏 → 全面验证"""
import paramiko, time, json

cli = paramiko.SSHClient()
cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
cli.connect(_ac.HOST, 22, _ac.USER, _ac.PWD, timeout=10)

def run(cmd, label="", t=60):
    if label: print("="*15, label, "="*15, flush=True)
    _, out, err = cli.exec_command(cmd, timeout=t)
    o, e = out.read().decode("utf-8","replace"), err.read().decode("utf-8","replace")
    if o.strip(): print(o[:7000], flush=True)
    if e.strip(): print("[stderr]", e[:600], flush=True)

R = "/vol1/1000/docker/game-arcade/roms-import"

# 1. 等待当前回填结束
for i in range(8):
    _, out, _ = cli.exec_command("pgrep -f cover_backfill >/dev/null && echo RUNNING || echo FINISHED", timeout=15)
    st = out.read().decode().strip()
    print(f"[轮询{i+1}] {st}", flush=True)
    if st == "FINISHED":
        break
    time.sleep(40)
run("cat " + R + "/cover_backfill.log", "第一轮回填日志", t=20)

# 2. 上传带手工映射的最终版, 对未命中的再补一轮
sftp = cli.open_sftp()
sftp.put(r"D:\MyBlog\GameGo\在线游戏厅\nas-deploy\cover_fetch.py", f"{R}/cover_fetch.py")
sftp.close()
print("已上传最终版 cover_fetch.py", flush=True)
run("cd " + R + " && python3 -u cover_backfill.py 2>&1 | tail -20", "第二轮补漏(前台)", t=500)

# 3. 数据库覆盖情况
run("python3 -c \""
    "import sqlite3;"
    "db=sqlite3.connect('/vol1/1000/docker/game-arcade/arcade-data/app.db');"
    "[print(r) for r in db.execute('SELECT id,title,cover FROM roms WHERE status=1 ORDER BY id')]"
    "\"", "数据库 cover 字段", t=30)

# 4. 静态访问验证
run("curl -s -o /dev/null -w 'rom-5.png -> %{http_code} %{content_type} %{size_download}B\\n' http://localhost:3000/covers/rom-5.png", "封面静态访问", t=20)

# 5. API 验证 (登录取 cookie, 查 /api/roms/public)
cmd = ("python3 -c \""
       "import json,urllib.request;"
       "cfg=json.load(open('$PWD/config.json'));"
       "req=urllib.request.Request(cfg['api']+'/api/auth/login',"
       "data=json.dumps({'username':cfg['username'],'password':cfg['password']}).encode(),"
       "headers={'Content-Type':'application/json'});"
       "r=urllib.request.urlopen(req,timeout=15);"
       "ck=r.headers.get('Set-Cookie').split(';')[0];"
       "req2=urllib.request.Request(cfg['api']+'/api/roms/public',headers={'Cookie':ck});"
       "d=json.load(urllib.request.urlopen(req2,timeout=15));"
       "[print(x['id'],x['title'],'cover=',x.get('cover')) for x in d['roms'][:20]]"
       "\"")
run("cd " + R + " && " + cmd, "API 返回 cover 验证", t=40)

cli.close()
print("DONE")
