#!/usr/bin/env bash
# ============================================================
#  AgentHub 构建脚本
#
#  用法:
#    ./build.sh                    # 构建 wheel + sdist
#    ./build.sh clean              # 仅清理构建产物
#    ./build.sh test               # 在隔离环境中安装并验证
#    ./build.sh archive            # 将 dist/ 下的包归档到 archive/
#    ./build.sh all                # 归档旧版 + 清理 + 构建 + 验证
#    ./build.sh all -v 0.1.1       # 升级到 0.1.1 + 归档 + 清理 + 构建 + 验证
#    ./build.sh build -v 0.1.1     # 升级到 0.1.1 + 构建
# ============================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# 颜色
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[0;33m'
CYAN='\033[0;36m'
NC='\033[0m'

info()  { echo -e "${CYAN}▸${NC} $*"; }
ok()    { echo -e "${GREEN}✅${NC} $*"; }
warn()  { echo -e "${YELLOW}⚠️${NC} $*"; }
fail()  { echo -e "${RED}❌${NC} $*"; exit 1; }

# ============================================================
# 解析参数
# ============================================================

ACTION="${1:-build}"
NEW_VERSION=""

shift 2>/dev/null || true
while [[ $# -gt 0 ]]; do
    case "$1" in
        -v|--version)
            NEW_VERSION="$2"
            shift 2
            ;;
        *)
            fail "未知参数: $1"
            ;;
    esac
done

CURRENT_VERSION=$(python3 -c "import re; print(re.search(r'version\s*=\s*\"(.+?)\"', open('pyproject.toml').read()).group(1))")

# ============================================================
# version — 自动修改文件中的版本号（按存在性处理）
# ============================================================

do_version() {
    local old_ver="$1"
    local new_ver="$2"

    if [[ "$old_ver" == "$new_ver" ]]; then
        info "版本号未变化: ${new_ver}"
        return 0
    fi

    if [[ ! "$new_ver" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
        fail "版本号格式错误: ${new_ver}（应为 X.Y.Z 格式）"
    fi

    PROJECT_NAME=$(python3 -c "import re; print(re.search(r'name\s*=\s*\"(.+?)\"', open('pyproject.toml').read()).group(1))")
    NORMALIZED_NAME=$(echo "$PROJECT_NAME" | sed 's/[-.]/_/g')

    info "升级版本号: ${old_ver} → ${new_ver}"

    sed -i '' "s/^version = \"${old_ver}\"/version = \"${new_ver}\"/" pyproject.toml
    echo "   ✓ pyproject.toml"

    # 文档中的版本说明（存在则替换）
    if [[ -f "docs/README.md" ]]; then
        sed -i '' "s/v${old_ver}/v${new_ver}/g" docs/README.md || true
        echo "   ✓ docs/README.md"
    fi
    if [[ -f "docs/QuickStart.md" ]]; then
        sed -i '' "s/agenthub==${old_ver}/agenthub==${new_ver}/g" docs/QuickStart.md || true
        echo "   ✓ docs/QuickStart.md"
    fi
    if [[ -f "docs/TestReport.md" ]]; then
        sed -i '' "s/v${old_ver}/v${new_ver}/g" docs/TestReport.md || true
        echo "   ✓ docs/TestReport.md"
    fi

    # 根 README 构建产物名（存在则替换）
    if [[ -f "README.md" ]]; then
        sed -i '' "s/${NORMALIZED_NAME}-${old_ver}/${NORMALIZED_NAME}-${new_ver}/g" README.md || true
        echo "   ✓ README.md"
    fi

    ok "版本号已更新为 ${new_ver}"
}

# ============================================================
# clean
# ============================================================

do_clean() {
    info "清理构建产物..."
    rm -rf dist/ build/ *.egg-info
    find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
    ok "清理完成"
}

# ============================================================
# archive
# ============================================================

ARCHIVE_DIR="archive"

do_archive() {
    if [[ ! -d "dist" ]] || [[ -z "$(ls -A dist/ 2>/dev/null)" ]]; then
        warn "dist/ 为空，没有可归档的文件"
        return 0
    fi

    mkdir -p "$ARCHIVE_DIR"

    local count=0
    for f in dist/*.whl dist/*.tar.gz; do
        [[ -f "$f" ]] || continue
        local basename
        basename=$(basename "$f")
        if [[ -f "${ARCHIVE_DIR}/${basename}" ]]; then
            warn "归档已存在，跳过: ${basename}"
        else
            cp "$f" "$ARCHIVE_DIR/"
            count=$((count + 1))
        fi
    done

    if [[ $count -gt 0 ]]; then
        ok "已归档 ${count} 个文件到 ${ARCHIVE_DIR}/"
        ls -lh "$ARCHIVE_DIR"/ | tail -n +2 | while read -r line; do
            echo "   $line"
        done
    else
        info "没有新文件需要归档"
    fi
}

# ============================================================
# build
# ============================================================

do_build() {
    PROJECT_NAME=$(python3 -c "import re; print(re.search(r'name\s*=\s*\"(.+?)\"', open('pyproject.toml').read()).group(1))")
    VERSION=$(python3 -c "import re; print(re.search(r'version\s*=\s*\"(.+?)\"', open('pyproject.toml').read()).group(1))")
    NORMALIZED_NAME=$(echo "$PROJECT_NAME" | sed 's/[-.]/_/g')

    WHEEL="dist/${NORMALIZED_NAME}-${VERSION}-py3-none-any.whl"
    SDIST="dist/${NORMALIZED_NAME}-${VERSION}.tar.gz"

    info "检查 build 工具..."
    pip install --quiet build 2>/dev/null || pip install build -q

    info "构建 ${PROJECT_NAME} v${VERSION}..."
    python3 -m build --quiet 2>&1 | grep -v "SetuptoolsDeprecationWarning" | grep -v "^!!" | grep -v "^\*\*\*" | grep -v "Please " | grep -v "By 2027" | grep -v "See https" | grep -v "^$" || true

    if [[ -f "$WHEEL" && -f "$SDIST" ]]; then
        WHEEL_SIZE=$(du -h "$WHEEL" | cut -f1 | xargs)
        SDIST_SIZE=$(du -h "$SDIST" | cut -f1 | xargs)
        FILE_COUNT=$(python3 -m zipfile -l "$WHEEL" 2>/dev/null | wc -l | xargs)

        echo ""
        ok "构建成功！"
        echo ""
        echo "   📦 Wheel:  $WHEEL  ($WHEEL_SIZE, ${FILE_COUNT} 个文件)"
        echo "   📦 Sdist:  $SDIST  ($SDIST_SIZE)"
        echo ""
        echo "   安装命令:"
        echo "     pip install $WHEEL"
    else
        fail "构建失败：未找到输出文件"
    fi
}

# ============================================================
# test
# ============================================================

do_test() {
    PROJECT_NAME=$(python3 -c "import re; print(re.search(r'name\s*=\s*\"(.+?)\"', open('pyproject.toml').read()).group(1))")
    VERSION=$(python3 -c "import re; print(re.search(r'version\s*=\s*\"(.+?)\"', open('pyproject.toml').read()).group(1))")
    NORMALIZED_NAME=$(echo "$PROJECT_NAME" | sed 's/[-.]/_/g')
    IMPORT_NAME=$(python3 - <<'PY'
import re
name = re.search(r'name\s*=\s*"(.+?)"', open('pyproject.toml').read()).group(1)
print(name.split('.')[-1].replace('-', '_'))
PY
)

    WHEEL="dist/${NORMALIZED_NAME}-${VERSION}-py3-none-any.whl"
    if [[ ! -f "$WHEEL" ]]; then
        fail "未找到 $WHEEL，请先运行 ./build.sh 构建"
    fi

    info "创建隔离测试环境: $TEST_VENV"
    rm -rf "$TEST_VENV"
    python3 -m venv "$TEST_VENV"
    source "$TEST_VENV/bin/activate"

    info "安装 wheel..."
    # 严格外部依赖模式：只安装 AgentHub wheel，让 pip 解析并安装依赖（含 agentkit）
    # 不安装本地 ../agentkit，避免将 agentkit 作为 agenthub 打包链路的一部分。
    pip install "$WHEEL" --quiet 2>/dev/null || pip install "$WHEEL" -q

    info "运行验证..."
    (
    cd /tmp
    python3 - <<PY
import importlib
import importlib.metadata as md

dist_name = "${PROJECT_NAME}"
pkg_name = "${IMPORT_NAME}"
ver = md.version(dist_name)
assert ver == "${VERSION}", f"版本不匹配: {ver}"
print(f"  ✅ 版本: {ver}")

pkg = importlib.import_module(pkg_name)
print(f"  ✅ 包导入: {pkg.__name__}")

from ${IMPORT_NAME}.config import HubConfig
from ${IMPORT_NAME}.gateway import create_app
from ${IMPORT_NAME}.models import AgentManifest, SessionStatus
from ${IMPORT_NAME}.stores.memory import InMemoryRegistryStore, InMemorySessionStore
from ${IMPORT_NAME}.stores.sqlite import SQLiteRegistryStore, SQLiteSessionStore
print("  ✅ 核心 API 导入正常")

cfg = HubConfig()
assert cfg.port == 8008
app = create_app(cfg)
assert app.title == "AgentHub"
print("  ✅ FastAPI 应用创建正常")

m = AgentManifest(
    name="demo",
    version="1.0.0",
    entry="mod:create",
    schema={"type": "object"},
    runner_config={},
    tags=[],
)
assert m.entry == "mod:create"
assert SessionStatus.RUNNING.value == "running"
print("  ✅ 模型与状态机正常")

print()
print("  🎉 全部验证通过！")
PY
    ) || { deactivate 2>/dev/null; fail "验证失败"; }

    if command -v agenthub &>/dev/null; then
        ok "agenthub CLI 命令可用"
    else
        warn "agenthub CLI 未注册（可能需要重新激活 PATH）"
    fi

    deactivate 2>/dev/null
    rm -rf "$TEST_VENV"
    echo ""
    ok "隔离环境验证通过，测试环境已清理"
}

# ============================================================
# main
# ============================================================

TEST_VENV="/tmp/agenthub-build-test-venv"

if [[ -n "$NEW_VERSION" ]]; then
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "  AgentHub 构建工具 — ${CURRENT_VERSION} → ${NEW_VERSION}"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    do_version "$CURRENT_VERSION" "$NEW_VERSION"
    echo ""
else
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "  AgentHub v${CURRENT_VERSION} 构建工具"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
fi

case "$ACTION" in
    clean)
        do_clean
        ;;
    build)
        do_build
        ;;
    test)
        do_test
        ;;
    archive)
        do_archive
        ;;
    all)
        do_archive
        do_clean
        do_build
        echo ""
        do_test
        ;;
    version)
        if [[ -z "$NEW_VERSION" ]]; then
            echo "当前版本: ${CURRENT_VERSION}"
            echo "用法: $0 version -v X.Y.Z"
        fi
        ;;
    *)
        echo "用法: $0 {clean|build|test|archive|all|version} [-v X.Y.Z]"
        echo ""
        echo "  命令:"
        echo "    clean    — 清理 dist/、build/、__pycache__"
        echo "    build    — 构建 wheel + sdist（默认）"
        echo "    test     — 在隔离 venv 中安装并验证"
        echo "    archive  — 将 dist/ 下的包归档到 archive/"
        echo "    all      — 归档 + 清理 + 构建 + 验证（推荐）"
        echo "    version  — 仅修改版本号，不构建"
        echo ""
        echo "  选项:"
        echo "    -v, --version X.Y.Z  — 指定新版本号（自动更新相关文件）"
        echo ""
        echo "  示例:"
        echo "    $0 all -v 0.1.1      — 升级到 0.1.1 并完整构建"
        echo "    $0 build -v 0.1.1    — 升级到 0.1.1 并构建"
        echo "    $0 version -v 0.1.1  — 仅修改版本号"
        echo "    $0 all               — 使用当前版本完整构建"
        exit 1
        ;;
esac

echo ""
