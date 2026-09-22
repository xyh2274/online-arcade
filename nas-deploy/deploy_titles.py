# -*- coding: utf-8 -*-
import arcade_env as _ac  # 凭据集中在 arcade.env（见 arcade.env.example）
"""Deploy multi-platform title extraction, test with synthetic headers (dry-run)."""
import paramiko

HOST, PORT = _ac.HOST, 22
USER, PWD = _ac.USER, _ac.PWD
BASE = "/vol1/1000/docker/game-arcade"
IMP = f"{BASE}/roms-import"
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST, PORT, USER, PWD, timeout=12)

def sudo_run(cmd, timeout=300, label=None):
    stdin, stdout, stderr = ssh.exec_command("sudo -S -p '' " + cmd, timeout=timeout, get_pty=True)
    stdin.write(PWD + "\n")
    stdin.flush()
    code = stdout.channel.recv_exit_status()
    out = stdout.read().decode("utf-8", "replace")
    print(f"===== exit={code} {':: ' + label if label else cmd[:70]}")
    print(out.strip()[-2500:])

sftp = ssh.open_sftp()
sftp.put(r"D:\MyBlog\GameGo\在线游戏厅\nas-deploy\rom_import.py", IMP + "/rom_import.py")
sftp.close()

# 造带真实头部结构的测试 ROM (dry-run 不会上传, 测完删除)
test = r'''
import os
base = "/vol1/1000/docker/game-arcade/roms/inbox"
def pad(title, width):
    return title.ljust(width)[:width].encode("latin-1")
# GBA: 0xA0 12字节
gba = bytearray(os.urandom(8 * 1024 * 1024))
gba[0xA0:0xAC] = pad("SUPRT MARIO", 12)
open(base + "/gba_test.gba", "wb").write(gba)
# GB: 0x134 15字节
gb = bytearray(os.urandom(256 * 1024))
gb[0x134:0x143] = pad("ZELDA DX", 15)
open(base + "/gb_test.gb", "wb").write(gb)
# SFC LoRom: 0x7FC0 21字节
sfc = bytearray(os.urandom(512 * 1024))
sfc[0x7FC0:0x7FD5] = pad("SUPER DONKEY KONG", 21)
open(base + "/sfc_test.sfc", "wb").write(sfc)
# MD: 头部海外名
md = bytearray(os.urandom(1024 * 1024))
md[0x100:0x110] = pad("SEGA MEGA DRIVE", 16)
md[0x150:0x180] = pad("STREETS OF RAGE", 48)
open(base + "/md_test.gen", "wb").write(md)
print("test roms created")
'''
sftp = ssh.open_sftp()
with sftp.open("/tmp/mktest.py", "w") as f:
    f.write(test)
sftp.close()
sudo_run("python3 /tmp/mktest.py && rm /tmp/mktest.py", label="create synthetic test roms")
sudo_run(f"python3 {IMP}/rom_import.py --dry-run", label="dry-run title extraction")
sudo_run(f"rm -f {BASE}/roms/inbox/gba_test.gba {BASE}/roms/inbox/gb_test.gb {BASE}/roms/inbox/sfc_test.sfc {BASE}/roms/inbox/md_test.gen && ls {BASE}/roms/inbox/ | wc -l", label="cleanup test roms")
ssh.close()
print("MULTI-PLATFORM TITLES READY")
