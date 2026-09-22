#!/bin/sh
# 在线游戏厅 · NAS 一键部署脚本（在飞牛 SSH 里执行）
set -e

BASE=/vol1/1000/docker/game-arcade

echo "==> 1/4 创建目录结构"
mkdir -p "$BASE/arcade-data"
mkdir -p "$BASE/roms/fbneo" "$BASE/roms/nes" "$BASE/roms/sfc" "$BASE/roms/gb" "$BASE/roms/gba" "$BASE/roms/md" "$BASE/roms/psx"

echo "==> 2/4 复制 docker-compose.yml"
cp "$(dirname "$0")/docker-compose.yml" "$BASE/docker-compose.yml"

echo "==> 3/4 启动童年游戏厅容器"
cd "$BASE"
docker compose up -d

echo "==> 4/4 等待服务就绪"
sleep 5
if curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:3000/ | grep -q "200\|302"; then
  echo "✔ 部署成功：http://192.168.1.100:3000 （默认账号 admin / admin123，请立即修改）"
else
  echo "⚠ 容器已启动但首页未就绪，查看日志：docker logs childhood-arcade"
fi
