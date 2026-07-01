# cli.py
import uuid
try:
    from .core import create_rag_agent, ensure_knowledge_base, get_knowledge_dir, get_model
except ImportError:
    from core import create_rag_agent, ensure_knowledge_base, get_knowledge_dir, get_model

def chat_sync(agent, user_input: str, session_id: str):
    print(f"\n🧑 用户: {user_input}")
    print("🤖 助手: 思考中...", flush=True)

    result = agent.invoke(input=user_input, session_id=session_id)
    if result.success:
        output = result.final_output
        print(f"\n{output}")
        return output
    else:
        print(f"\n❌ 错误: {result.error}")
        return None

def print_banner():
    print("""
╔══════════════════════════════════════════════════════════════╗
║           🤖 交互式 RAGAgent - CLI 模式                     ║
╠══════════════════════════════════════════════════════════════╣
║  命令: /files (查看文件) | /reload (重载) | /quit (退出)     ║
╚══════════════════════════════════════════════════════════════╝
""")

def main():
    ensure_knowledge_base()
    agent = create_rag_agent()
    session_id = str(uuid.uuid4())

    print_banner()
    print(f"📌 模型: {get_model()} | 会话 ID: {session_id[:8]}...")
    print("─" * 60)

    while True:
        try:
            user_input = input("\n🧑 请输入: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n👋 再见！")
            break

        if not user_input:
            continue
        if user_input.lower() in ("/quit", "/exit"):
            print("👋 再见！")
            break
        elif user_input.lower() == "/reload":
            print("🔄 正在重新加载知识库...")
            rag = getattr(agent, "_rag", None)
            if rag is not None:
                count = rag.reload()
                print(f"✅ 重载完成（共 {count} 个文档块）")
            else:
                agent = create_rag_agent()
                print("✅ 重载完成")
            continue
        elif user_input.lower() == "/files":
            import os
            print("\n📚 知识库文件：")
            for f in os.listdir(get_knowledge_dir()):
                if f.lower().endswith(('.txt', '.md', '.markdown', '.pdf')):
                    print(f"  📄 {f}")
            continue

        chat_sync(agent, user_input, session_id)

if __name__ == "__main__":
    main()
