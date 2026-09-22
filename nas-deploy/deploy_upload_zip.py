# -*- coding: utf-8 -*-
import arcade_env as _ac  # 凭据集中在 arcade.env（见 arcade.env.example）
"""部署: 上传补丁 UploadDialog + NAS 生成 setnames 资产 + compose 挂载 + 重启验证"""
import paramiko

cli = paramiko.SSHClient()
cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
cli.connect(_ac.HOST, 22, _ac.USER, _ac.PWD, timeout=10)

def run(cmd, label="", t=180):
    if label: print("="*15, label, "="*15, flush=True)
    _, out, err = cli.exec_command(cmd, timeout=t)
    o, e = out.read().decode("utf-8","replace"), err.read().decode("utf-8","replace")
    if o.strip(): print(o[:4000], flush=True)
    if e.strip(): print("[stderr]", e[:500], flush=True)

B = "/vol1/1000/docker/game-arcade"
R = B + "/roms-import"

# 1. 上传补丁后的 UploadDialog
sftp = cli.open_sftp()
sftp.put(r"D:\MyBlog\GameGo\在线游戏厅\nas-deploy\UploadDialog_patched.js", f"{B}/patches/UploadDialog-kZO6Kb_z.js")
print("已上传 UploadDialog-kZO6Kb_z.js (遮罩补丁+zip识别)", flush=True)
sftp.close()

# 2. NAS 生成 setnames 资产
run("cd " + R + " && python3 -c \""
    "import json;"
    "sets=json.load(open('fbneo_sets.json'));"
    "json.dump(sorted(sets.keys()), open('" + B + "/patches/fbneo-setnames.json','w'));"
    "print('setnames 条目:', len(sets))\"", "生成 fbneo-setnames.json", t=60)

# 3. compose 加挂载
run("python3 - <<'EOF'\n"
    "comp = '/vol1/1000/docker/game-arcade/docker-compose.yml'\n"
    "s = open(comp).read()\n"
    "if 'fbneo-setnames.json' not in s:\n"
    "    anchor = [l for l in s.splitlines() if 'Player-BwKb4RpM.js' in l and '/app/dist' in l][0]\n"
    "    add = '      - ./patches/fbneo-setnames.json:/app/dist/assets/fbneo-setnames.json:ro'\n"
    "    s = s.replace(anchor, anchor + '\\n' + add, 1)\n"
    "    open(comp, 'w').write(s)\n"
    "    print('[OK] compose 已加 setnames 挂载')\n"
    "else:\n"
    "    print('[SKIP] compose 已有挂载')\n"
    "EOF", "compose 加挂载", t=30)

# 4. 重启 + 验证
run(f"cd {B} && docker compose up -d 2>&1 | tail -3", "compose up", t=180)
run("sleep 3; curl -s http://localhost:3000/assets/UploadDialog-kZO6Kb_z.js | grep -c 'fbneo-setnames'", "线上 chunk 补丁生效", t=30)
run("curl -s -o /dev/null -w 'setnames.json -> %{http_code} %{size_download}B\\n' http://localhost:3000/assets/fbneo-setnames.json", "setnames 资产可访问", t=20)
run("curl -s http://localhost:3000/assets/UploadDialog-kZO6Kb_z.js | grep -c '\\[\"self\\]' || true; curl -s -o /dev/null -w 'home=%{http_code}\\n' http://localhost:3000/", "遮罩补丁仍在+首页", t=20)

cli.close()
print("DONE")
