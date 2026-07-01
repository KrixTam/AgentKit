# core.py
import os
from agentkit.utils.env import with_env
from agentkit import SimpleRAGAgent

# ============================================================
# 配置区 —— 根据你的环境修改
# ============================================================
# KNOWLEDGE_DIR = "./knowledge_base"


def _parse_bool(value: str | None, *, default: bool) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


@with_env()
def get_knowledge_dir() -> str:
    return os.getenv("AGENTKIT_RAG_KNOWLEDGE_DIR", "./法律法规")

@with_env()
def get_model() -> str:
    return (
        os.getenv("AGENTKIT_RAG_MODEL")
        or os.getenv("AGENTKIT_MODEL")
        or os.getenv("AGENTKIT_DEFAULT_MODEL")
        or os.getenv("AGENTKIT_STANDARD_MODEL")
        or "qwen/qwen3.6-flash"
    )

TOP_K = 3
CHUNK_SIZE = 500
CHUNK_OVERLAP = 100


@with_env()
def get_enable_memory() -> bool:
    return _parse_bool(os.getenv("AGENTKIT_RAG_ENABLE_MEMORY"), default=True)


@with_env()
def get_storage_path() -> str:
    return os.getenv("AGENTKIT_RAG_STORAGE_PATH", "./.agentkit/rag/index.db")


@with_env()
def ensure_knowledge_base() -> None:
    """确保知识库目录存在，如果为空则创建示例文档"""
    knowledge_dir = get_knowledge_dir()
    os.makedirs(knowledge_dir, exist_ok=True)
    files = [f for f in os.listdir(knowledge_dir)
             if f.lower().endswith(('.txt', '.md', '.markdown', '.pdf'))]
    if not files:
        print(f"⚠️  知识库目录 '{knowledge_dir}' 为空，已自动创建示例文档。")
        sample_path = os.path.join(knowledge_dir, "sample.txt")
        with open(sample_path, "w", encoding="utf-8") as f:
            f.write(
                "AgentKit 是一个 Python 原生 Agent 框架。\n"
                "它支持 Tool（工具）、Skill（技能包）、Memory（记忆）与多模型适配。\n"
                "内置 SimpleRAGAgent 可实现轻量级 RAG（检索增强生成）。\n"
            )


@with_env()
def create_rag_agent():
    """创建 SimpleRAGAgent 并构建可交互的 Agent"""
    knowledge_dir = get_knowledge_dir()
    model = get_model()
    storage_path = get_storage_path()
    enable_memory = get_enable_memory()
    rag = SimpleRAGAgent.from_directory(
        knowledge_dir=knowledge_dir,
        model=model,
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        top_k=TOP_K,
        default_retriever="hybrid",
        storage_path=storage_path,
        enable_memory=enable_memory,
    )

    agent = rag.build_agent(
        name="interactive-rag-assistant",
        instructions=(
            "你是一个智能知识助手，基于本地知识库回答用户问题。\n"
            "规则：\n"
            "1) 优先调用 search_knowledge_base 检索相关文档。\n"
            "2) 回答要结合知识库结果，并注明来源。\n"
            "3) 如果知识库中没有相关信息，请明确说明，不要编造。\n"
            "4) 回答要简洁、准确、使用中文。"
        ),
    )
    setattr(agent, "_rag", rag)
    return agent
