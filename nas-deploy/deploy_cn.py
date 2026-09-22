# -*- coding: utf-8 -*-
import arcade_env as _ac  # 凭据集中在 arcade.env（见 arcade.env.example）
"""Deploy CN-name update: script + cn overlay, rebuild db, dry-run tests with real set names."""
import json
import paramiko

HOST, PORT = _ac.HOST, 22
USER, PWD = _ac.USER, _ac.PWD
BASE = "/vol1/1000/docker/game-arcade"
IMP = f"{BASE}/roms-import"
LOCAL = r"D:\MyBlog\GameGo\在线游戏厅\nas-deploy"

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST, PORT, USER, PWD, timeout=12)

def sudo_run(cmd, timeout=600, label=None):
    stdin, stdout, stderr = ssh.exec_command("sudo -S -p '' " + cmd, timeout=timeout, get_pty=True)
    stdin.write(PWD + "\n")
    stdin.flush()
    code = stdout.channel.recv_exit_status()
    out = stdout.read().decode("utf-8", "replace")
    print(f"===== exit={code} {':: ' + label if label else cmd[:70]}")
    print(out.strip()[-2200:])
    return out

sftp = ssh.open_sftp()
sftp.put(LOCAL + r"\rom_import.py", IMP + "/rom_import.py")
with sftp.open(IMP + "/cn_names.json", "w") as f:
    f.write(open(LOCAL + r"\cn_names.json", "r", encoding="utf-8").read())
sftp.close()

sudo_run(f"python3 {IMP}/rom_import.py --build-db", timeout=600, label="rebuild crc + sets db")
sudo_run(f"python3 -c \"import json;s=json.load(open('{IMP}/fbneo_sets.json'));print('setname数:',len(s));print('kov:',s.get('kov'));print('kof2002:',s.get('kof2002'))\"", label="verify sets db")

# 测试: kov.zip / kof2002.zip / 中文命名的 nes
sudo_run(f"python3 -c \"\nimport zipfile, os\nbase='{BASE}/roms/inbox'\nwith zipfile.ZipFile(base+'/kov.zip','w') as z:\n    z.writestr('27c4001.p1', os.urandom(1024))\n    z.writestr('27c4001.s1', os.urandom(512))\nwith zipfile.ZipFile(base+'/kof2002.zip','w') as z:\n    z.writestr('265-p1.bin', os.urandom(1024))\n    z.writestr('265-s1.bin', os.urandom(512))\nopen(base+'/超级玛丽.nes','wb').write(os.urandom(40960))\nprint('cn test files created')\n\"", label="create CN test files")
sudo_run(f"python3 {IMP}/rom_import.py --dry-run", label="CN title dry-run")
ssh.close()
print("CN NAMES READY")
