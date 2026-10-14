#!/usr/bin/env bash
# 在 Mac 上起一个 HTTP 服务，把插件暴露给同一 Wi-Fi 下的 iPhone。
# 用法: ./start-server.sh [端口]   默认 8000
set -euo pipefail

PORT="${1:-8000}"
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# 挑一个真实的局域网地址（跳过回环和 utun 隧道网段）
LAN_IP=""
for iface in en0 en1 en2; do
  ip="$(ipconfig getifaddr "$iface" 2>/dev/null || true)"
  if [ -n "$ip" ]; then LAN_IP="$ip"; break; fi
done
[ -z "$LAN_IP" ] && LAN_IP="127.0.0.1"

echo "服务目录: $DIR"
echo "插件地址: http://${LAN_IP}:${PORT}/ximalaya-adblock.plugin"
echo "把这个地址粘进 Loon → 插件 → + → 从 URL 添加"
echo "Ctrl-C 停止"
echo

cd "$DIR"
exec python3 -m http.server "$PORT" --bind 0.0.0.0
