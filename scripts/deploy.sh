#!/usr/bin/env bash
#
# Production deploy for the H5 frontend.
#
# 默认目标：阿里云 nginx 静态目录 /www/wwwroot/ai.trendpower.cc/chat/
# （H5 部署在 ai.trendpower.cc/chat/ 子路径，由外层 nginx 转发到该目录）
#
# 用法：
#   bash scripts/deploy.sh                       # 默认部署到生产
#   bash scripts/deploy.sh /path/to/webroot/chat # 自定义部署目标
#
# 前置条件（只需一次）：
#   1. 服务器已运行 Dify 后端（端口 8012）
#   2. nginx 已配好把 ai.trendpower.cc/chat/ 静态文件指向 $DEPLOY_DIR
#   3. 服务器上 frontend/.env 已设好 VITE_BASE_PATH 和 VITE_API_BASE
#
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DEPLOY_DIR="${1:-/www/wwwroot/ai.trendpower.cc/chat}"
TIMESTAMP="$(date +%Y%m%d_%H%M%S)"

echo "[1/5] Build frontend..."
cd "$REPO_ROOT/frontend"
npm ci --silent
npm run build

echo "[2/5] Backup current deployed bundle (if exists)..."
if [ -d "$DEPLOY_DIR" ]; then
  BACKUP="$DEPLOY_DIR.bak.$TIMESTAMP"
  cp -a "$DEPLOY_DIR" "$BACKUP"
  echo "    -> $BACKUP"
  # 只保留最近 5 个备份，清理更早的
  ls -dt "$DEPLOY_DIR".bak.* 2>/dev/null | tail -n +6 | xargs -r rm -rf
fi

echo "[3/5] Ensure deploy dir exists..."
mkdir -p "$DEPLOY_DIR/assets"

echo "[4/5] Sync new bundle to $DEPLOY_DIR..."
rm -f "$DEPLOY_DIR/assets/"*.js "$DEPLOY_DIR/assets/"*.css
cp dist/assets/* "$DEPLOY_DIR/assets/"
cp dist/index.html "$DEPLOY_DIR/index.html"
# 同步 vite.svg（favicon），首次部署才需要
[ -f dist/vite.svg ] && cp dist/vite.svg "$DEPLOY_DIR/vite.svg"

echo "[5/5] Verify..."
BUNDLE_FILE=$(ls "$DEPLOY_DIR/assets/"*.js | head -1)
MEDIA_HITS=$(grep -c mediaBubble "$BUNDLE_FILE" || true)
BASE_HITS=$(grep -oE 'base:"/[^"]*"' "$BUNDLE_FILE" 2>/dev/null | head -1 || echo 'check vite.config.ts')

if [ "$MEDIA_HITS" -ge 1 ]; then
  echo "[deploy ok] $BUNDLE_FILE (mediaBubble=$MEDIA_HITS, $BASE_HITS)"
else
  echo "[deploy FAILED] mediaBubble=0 — bundle 缺少图片渲染代码，回滚！"
  if [ -n "${BACKUP:-}" ] && [ -d "$BACKUP" ]; then
    rm -rf "$DEPLOY_DIR"
    mv "$BACKUP" "$DEPLOY_DIR"
    echo "    -> 已回滚到 $BACKUP"
  fi
  exit 1
fi

echo ""
echo "Next steps:"
echo "  1. 浏览器硬刷新 (Ctrl+Shift+R / Cmd+Shift+R)"
echo "  2. 验证 API:  curl http://ai.trendpower.cc/chat/api/health"
echo "  3. 验证图片:  问一个知识库相关问题，看气泡是否嵌入图"
