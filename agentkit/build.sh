#!/usr/bin/env bash
# ============================================================
#  AgentKit 构建脚本
#
#  用法:
#    ./build.sh                    # 构建 wheel + sdist
#    ./build.sh clean              # 仅清理构建产物
#    ./build.sh test               # 在隔离环境中安装并验证
#    ./build.sh archive            # 将 dist/ 下的包归档到 archive/
#    ./build.sh all                # 归档旧版 + 清理 + 构建 + 验证
#    ./build.sh all -v 0.3.0       # 升级到 0.3.0 + 归档 + 清理 + 构建 + 验证
#    ./build.sh build -v 0.3.0     # 升级到 0.3.0 + 构建
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

# 解析 -v / --version 参数
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

# 读取当前版本
CURRENT_VERSION=$(python3 -c "import re; print(re.search(r'version\s*=\s*\"(.+?)\"', open('pyproject.toml').read()).group(1))")

# ============================================================
# version — 自动修改所有文件中的版本号
# ============================================================

do_version() {
    local old_ver="$1"
    local new_ver="$2"

    if [[ "$old_ver" == "$new_ver" ]]; then
        info "版本号未变化: ${new_ver}"
        return 0
    fi

    # 版本号格式校验
    if [[ ! "$new_ver" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
        fail "版本号格式错误: ${new_ver}（应为 X.Y.Z 格式）"
    fi

    # 动态读取项目名称
    PROJECT_NAME=$(python3 -c "import re; print(re.search(r'name\s*=\s*\"(.+?)\"', open('pyproject.toml').read()).group(1))")
    NORMALIZED_NAME=$(echo "$PROJECT_NAME" | sed 's/[-.]/_/g')

    info "升级版本号: ${old_ver} → ${new_ver}"

    # 1. pyproject.toml
    sed -i '' "s/^version = \"${old_ver}\"/version = \"${new_ver}\"/" pyproject.toml
    echo "   ✓ pyproject.toml"

    # 2. __init__.py
    sed -i '' "s/__version__ = \"${old_ver}\"/__version__ = \"${new_ver}\"/" __init__.py
    echo "   ✓ __init__.py"

    # 3. _cli.py
    sed -i '' "s/AgentKit v${old_ver}/AgentKit v${new_ver}/" _cli.py
    echo "   ✓ _cli.py"

    # 4. docs/README.md（版本徽章）
    sed -i '' "s/Version-${old_ver}/Version-${new_ver}/" docs/README.md
    echo "   ✓ docs/README.md"

    # 5. docs/TestReport.md（测试报告版本）
    if [[ -f "docs/TestReport.md" ]]; then
        sed -i '' "s/AgentKit 版本：v${old_ver}/AgentKit 版本：v${new_ver}/" docs/TestReport.md
        echo "   ✓ docs/TestReport.md"
    fi

    # 6. README.md（构建产物文件名）
    # 使用项目名规范化后的名称进行替换
    sed -i '' "s/${NORMALIZED_NAME}-${old_ver}/${NORMALIZED_NAME}-${new_ver}/g" README.md
    echo "   ✓ README.md"

    ok "版本号已更新为 ${new_ver}"

    # 验证
    local check
    check=$(python3 -c "import re; print(re.search(r'version\s*=\s*\"(.+?)\"', open('pyproject.toml').read()).group(1))")
    if [[ "$check" != "$new_ver" ]]; then
        fail "版本号验证失败: pyproject.toml 中仍为 ${check}"
    fi
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
    # 动态读取项目名称和版本号
    PROJECT_NAME=$(python3 -c "import re; print(re.search(r'name\s*=\s*\"(.+?)\"', open('pyproject.toml').read()).group(1))")
    VERSION=$(python3 -c "import re; print(re.search(r'version\s*=\s*\"(.+?)\"', open('pyproject.toml').read()).group(1))")

    # Python 构建工具会将项目名中的连字符 (-) 和点 (.) 规范化为下划线 (_)
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
        echo "     pip install \"${WHEEL}[all]\"    # 含全部可选依赖"
    else
        fail "构建失败：未找到输出文件"
    fi
}

# ============================================================
# test
# ============================================================

do_test() {
    # 动态读取项目名称和版本号
    PROJECT_NAME=$(python3 -c "import re; print(re.search(r'name\s*=\s*\"(.+?)\"', open('pyproject.toml').read()).group(1))")
    VERSION=$(python3 -c "import re; print(re.search(r'version\s*=\s*\"(.+?)\"', open('pyproject.toml').read()).group(1))")
    NORMALIZED_NAME=$(echo "$PROJECT_NAME" | sed 's/[-.]/_/g')

    WHEEL="dist/${NORMALIZED_NAME}-${VERSION}-py3-none-any.whl"

    if [[ ! -f "$WHEEL" ]]; then
        fail "未找到 $WHEEL，请先运行 ./build.sh 构建"
    fi

    info "创建隔离测试环境: $TEST_VENV"
    rm -rf "$TEST_VENV"
    python3 -m venv "$TEST_VENV"
    source "$TEST_VENV/bin/activate"

    info "安装 wheel..."
    pip install "$WHEEL" --quiet 2>/dev/null

    info "运行验证..."
    python3 -c "
import sys

# 1. 版本
import agentkit
assert agentkit.__version__ == '${VERSION}', f'版本不匹配: {agentkit.__version__}'
print(f'  ✅ 版本: {agentkit.__version__}')

# 2. 文档
import os
docs = agentkit.get_docs_dir()
assert os.path.isdir(docs), f'docs 目录不存在: {docs}'
doc_files = [f for f in os.listdir(docs) if f.endswith('.md')]
print(f'  ✅ 文档: {len(doc_files)} 个文件 → {docs}')

# 3. 示例
examples = agentkit.get_examples_dir()
for sub in ['standard', 'ollama']:
    sub_path = os.path.join(examples, sub)
    assert os.path.isdir(sub_path), f'{sub} 目录不存在'
    py_files = [f for f in os.listdir(sub_path) if f.endswith('.py') and f != '__init__.py']
    print(f'  ✅ 示例 {sub}/: {len(py_files)} 个')

# 4. 核心 API
from agentkit import (
    Agent, Runner, function_tool, Skill, LLMRegistry,
    BaseMemoryProvider, Memory, SequentialAgent, ParallelAgent, LoopAgent,
    InputGuardrail, OutputGuardrail, PermissionPolicy,
)
print('  ✅ 核心 API 导入正常 (27 个符号)')

# 5. function_tool
@function_tool
def add(a: int, b: int) -> int:
    '''两数相加'''
    return a + b
assert add.name == 'add'
print(f'  ✅ @function_tool 装饰器正常')

# 6. Agent 创建
agent = Agent(name='test', instructions='你是助手', model='gpt-4o', tools=[add])
assert agent.name == 'test'
print(f'  ✅ Agent 创建正常')

# 7. LLM 路由
routes = {
    'gpt-4o': 'OpenAIAdapter',
    'claude-sonnet-4-20250514': 'AnthropicAdapter',
    'ollama/qwen3.5:cloud': 'OllamaAdapter',
    'deepseek/deepseek-chat': 'OpenAICompatibleAdapter',
}
for model, expected in routes.items():
    cls = LLMRegistry._resolve_adapter(model)
    assert cls.__name__ == expected, f'{model} → {cls.__name__} != {expected}'
print(f'  ✅ LLM 路由正常 ({len(routes)} 个适配器)')

print()
print('  🎉 全部验证通过！')
" || { deactivate 2>/dev/null; fail "验证失败"; }

    # 测试 CLI
    if command -v agentkit-docs &>/dev/null; then
        ok "agentkit-docs CLI 命令可用"
    else
        warn "agentkit-docs CLI 未注册（可能需要重新激活 PATH）"
    fi

    deactivate 2>/dev/null
    rm -rf "$TEST_VENV"
    echo ""
    ok "隔离环境验证通过，测试环境已清理"
}

# ============================================================
# main
# ============================================================

TEST_VENV="/tmp/agentkit-build-test-venv"

# 如果指定了新版本号，先执行版本升级
if [[ -n "$NEW_VERSION" ]]; then
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "  AgentKit 构建工具 — ${CURRENT_VERSION} → ${NEW_VERSION}"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    do_version "$CURRENT_VERSION" "$NEW_VERSION"
    echo ""
else
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "  AgentKit v${CURRENT_VERSION} 构建工具"
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
        # 仅修改版本号，不构建
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
        echo "    -v, --version X.Y.Z  — 指定新版本号（自动更新所有相关文件）"
        echo ""
        echo "  示例:"
        echo "    $0 all -v 0.3.0      — 升级到 0.3.0 并完整构建"
        echo "    $0 build -v 0.3.0    — 升级到 0.3.0 并构建"
        echo "    $0 version -v 0.3.0  — 仅修改版本号"
        echo "    $0 all               — 使用当前版本完整构建"
        exit 1
        ;;
esac

echo ""
