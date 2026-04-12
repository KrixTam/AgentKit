"""
AgentKit CLI 工具。

安装后提供以下命令：
  agentkit-docs       — 显示文档目录位置，或在浏览器中打开
"""
import os
import sys


def _get_docs_dir() -> str:
    """返回 docs 目录的绝对路径"""
    return os.path.join(os.path.dirname(__file__), "docs")


def _get_examples_dir() -> str:
    """返回 examples 目录的绝对路径"""
    return os.path.join(os.path.dirname(__file__), "examples")


def show_docs():
    """agentkit-docs 命令入口"""
    docs_dir = _get_docs_dir()
    examples_dir = _get_examples_dir()

    print("=" * 60)
    print("  AgentKit v0.3.0 — 文档与示例")
    print("=" * 60)
    print()

    # 文档
    print("📚 文档目录:")
    print(f"   {docs_dir}")
    print()

    if os.path.isdir(docs_dir):
        print("   文件列表:")
        for f in sorted(os.listdir(docs_dir)):
            fpath = os.path.join(docs_dir, f)
            size = os.path.getsize(fpath) / 1024
            print(f"     • {f:30s} ({size:.1f} KB)")
    else:
        print("   ⚠️  文档目录不存在（包可能未正确安装）")

    print()

    # 示例
    print("💡 示例目录:")
    print(f"   {examples_dir}")
    print()

    if os.path.isdir(examples_dir):
        for subdir in ["standard", "ollama"]:
            sub_path = os.path.join(examples_dir, subdir)
            if os.path.isdir(sub_path):
                files = [f for f in sorted(os.listdir(sub_path)) if f.endswith(".py") and f != "__init__.py"]
                print(f"   📁 {subdir}/ ({len(files)} 个示例)")
                for f in files:
                    print(f"     • {f}")
                print()

    print("-" * 60)
    print("快速开始:")
    print("  1. 查看文档:  cat $(agentkit-docs-path)/README.md")
    print("  2. 运行示例:  python -m agentkit.examples.ollama.01_basic_chat")
    print("  3. Python 中获取路径:")
    print("     >>> import agentkit; print(agentkit.get_docs_dir())")
    print("     >>> import agentkit; print(agentkit.get_examples_dir())")
    print()


if __name__ == "__main__":
    show_docs()
