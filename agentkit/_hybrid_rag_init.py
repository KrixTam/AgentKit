"""HybridRAGAgent 交互式初始化向导。"""

from __future__ import annotations

import argparse
import importlib.util
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from textwrap import dedent


MODEL_ENV_KEYS = (
    "AGENTKIT_HYBRID_RAG_MODEL",
    "AGENTKIT_MODEL",
    "AGENTKIT_DEFAULT_MODEL",
    "AGENTKIT_STANDARD_MODEL",
)

DEFAULT_FINAL_MODEL = "gpt-4o-mini"
DEFAULT_EMBEDDING_MODEL = "ollama/qllama/bge-small-zh-v1.5:f16"
DEFAULT_RERANKER_MODEL = "ollama/qllama/bce-reranker-base_v1:f16"
DEFAULT_RERANKER_BASE_URL = "http://127.0.0.1:11535"


@dataclass(slots=True)
class HybridRAGWorkspaceConfig:
    target_dir: Path
    knowledge_dir: str
    vector_store_dir: str
    memory_db_path: str
    model: str
    embedding_model: str
    reranker_model: str
    embedding_base_url: str | None
    reranker_base_url: str | None
    chunk_size_tokens: int
    chunk_overlap_tokens: int
    recall_top_k: int
    final_top_k: int
    max_context_tokens: int | None
    enable_memory: bool
    agent_name: str
    create_sample_doc: bool
    force: bool = False


def resolve_default_model() -> str:
    for key in MODEL_ENV_KEYS:
        value = os.getenv(key)
        if value:
            return value
    return DEFAULT_FINAL_MODEL


def _normalize_relative_path(raw: str) -> str:
    value = raw.strip().replace("\\", "/")
    if not value:
        return "."

    path = Path(value).expanduser()
    if path.is_absolute():
        return str(path)

    normalized = value.strip("/")
    return normalized or "."


def _prompt_text(prompt: str, default: str | None = None) -> str:
    while True:
        suffix = f" [{default}]" if default is not None else ""
        value = input(f"{prompt}{suffix}: ").strip()
        if value:
            return value
        if default is not None:
            return default
        print("请输入有效内容。")


def _prompt_bool(prompt: str, default: bool = True) -> bool:
    suffix = "Y/n" if default else "y/N"
    while True:
        value = input(f"{prompt} [{suffix}]: ").strip().lower()
        if not value:
            return default
        if value in {"y", "yes"}:
            return True
        if value in {"n", "no"}:
            return False
        print("请输入 y 或 n。")


def _prompt_int(prompt: str, default: int) -> int:
    while True:
        value = input(f"{prompt} [{default}]: ").strip()
        if not value:
            return default
        try:
            return int(value)
        except ValueError:
            print("请输入整数。")


def _prompt_optional_int(prompt: str, default: int | None = None) -> int | None:
    suffix = f" [{default}]" if default is not None else " [留空表示不限制]"
    while True:
        value = input(f"{prompt}{suffix}: ").strip()
        if not value:
            return default
        try:
            return int(value)
        except ValueError:
            print("请输入整数，或直接回车。")


def _prompt_optional_text(prompt: str, default: str | None = None) -> str | None:
    suffix = f" [{default}]" if default else " [留空表示使用默认]"
    value = input(f"{prompt}{suffix}: ").strip()
    if value:
        return value
    return default


def _default_workspace_dir() -> Path:
    return Path.cwd() / "hybrid-rag-workspace"


def _build_config_from_wizard(force: bool = False) -> HybridRAGWorkspaceConfig:
    print("=" * 68)
    print("AgentKit HybridRAGAgent 初始化向导")
    print("=" * 68)
    print("这个向导会逐步收集配置，并生成一个可直接运行的 Hybrid RAG 工作目录。")
    print()

    target_dir = Path(_prompt_text("1/8 工作目录", str(_default_workspace_dir()))).expanduser()
    knowledge_dir = _normalize_relative_path(_prompt_text("2/8 知识库目录", "knowledge_base"))
    model = _prompt_text("3/8 最终回答模型", resolve_default_model())

    use_default_providers = _prompt_bool("4/8 是否使用默认的 embedding / reranker 模型", True)
    embedding_model = DEFAULT_EMBEDDING_MODEL
    reranker_model = DEFAULT_RERANKER_MODEL
    embedding_base_url: str | None = None
    reranker_base_url: str | None = None
    if not use_default_providers:
        embedding_model = _prompt_text("   Embedding 模型", DEFAULT_EMBEDDING_MODEL)
        reranker_model = _prompt_text("   Reranker 模型", DEFAULT_RERANKER_MODEL)
        embedding_base_url = _prompt_optional_text("   Embedding 服务地址")
        reranker_base_url = _prompt_optional_text("   Reranker 服务地址")

    enable_memory = _prompt_bool("5/8 是否启用默认 SQLite 记忆", True)

    use_advanced = _prompt_bool("6/8 是否配置高级检索参数", False)
    vector_store_dir = ".agentkit/rag_v2/chroma"
    memory_db_path = ".agentkit/rag_v2/memory.db"
    chunk_size_tokens = 350
    chunk_overlap_tokens = 50
    recall_top_k = 20
    final_top_k = 3
    max_context_tokens: int | None = None
    if use_advanced:
        vector_store_dir = _normalize_relative_path(_prompt_text("   向量库存储目录", vector_store_dir))
        memory_db_path = _normalize_relative_path(_prompt_text("   记忆数据库路径", memory_db_path))
        chunk_size_tokens = _prompt_int("   Chunk 大小（tokens）", chunk_size_tokens)
        chunk_overlap_tokens = _prompt_int("   Chunk 重叠（tokens）", chunk_overlap_tokens)
        recall_top_k = _prompt_int("   召回候选数 recall_top_k", recall_top_k)
        final_top_k = _prompt_int("   最终注入文档数 final_top_k", final_top_k)
        max_context_tokens = _prompt_optional_int("   最终上下文预算 max_context_tokens", None)

    create_sample_doc = _prompt_bool("7/8 是否写入一份示例知识库文档", True)
    agent_name = _prompt_text("8/8 生成的 Agent 名称", "hybrid-rag-assistant")

    print()
    print("配置摘要：")
    print(f"- 工作目录: {target_dir}")
    print(f"- 知识库目录: {knowledge_dir}")
    print(f"- 回答模型: {model}")
    print(f"- Embedding 模型: {embedding_model}")
    print(f"- Reranker 模型: {reranker_model}")
    print(f"- 启用记忆: {'是' if enable_memory else '否'}")
    print(f"- 写入示例文档: {'是' if create_sample_doc else '否'}")
    print()
    if not _prompt_bool("确认开始生成工作目录", True):
        raise SystemExit("已取消。")

    return HybridRAGWorkspaceConfig(
        target_dir=target_dir,
        knowledge_dir=knowledge_dir,
        vector_store_dir=vector_store_dir,
        memory_db_path=memory_db_path,
        model=model,
        embedding_model=embedding_model,
        reranker_model=reranker_model,
        embedding_base_url=embedding_base_url,
        reranker_base_url=reranker_base_url,
        chunk_size_tokens=chunk_size_tokens,
        chunk_overlap_tokens=chunk_overlap_tokens,
        recall_top_k=recall_top_k,
        final_top_k=final_top_k,
        max_context_tokens=max_context_tokens,
        enable_memory=enable_memory,
        agent_name=agent_name,
        create_sample_doc=create_sample_doc,
        force=force,
    )


def _resolve_existing_conflicts(config: HybridRAGWorkspaceConfig) -> None:
    paths = [
        config.target_dir / ".env",
        config.target_dir / ".env.example",
        config.target_dir / "README.md",
        config.target_dir / "create_agent.py",
        config.target_dir / "chat.py",
        config.target_dir / "start_rerank_server.py",
    ]
    if config.create_sample_doc:
        paths.append(config.target_dir / config.knowledge_dir / "welcome.md")
    conflicts = [path for path in paths if path.exists()]
    if conflicts and not config.force:
        joined = "\n".join(f"  - {path}" for path in conflicts)
        raise FileExistsError(
            "目标目录中已存在将要写入的文件，请更换目录或使用 --force 覆盖：\n"
            f"{joined}"
        )


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _env_value(value: str | int | None) -> str:
    if value is None:
        return ""
    return str(value)


def _create_env_file(config: HybridRAGWorkspaceConfig) -> str:
    return dedent(
        f"""\
        # HybridRAGAgent 工作目录配置
        # 最终回答模型遵循 AgentKit 模型标识规则；也可删除本行，改由外部环境变量提供
        AGENTKIT_HYBRID_RAG_MODEL={config.model}
        AGENTKIT_HYBRID_RAG_AGENT_NAME={config.agent_name}
        AGENTKIT_HYBRID_RAG_KNOWLEDGE_DIR={config.knowledge_dir}
        AGENTKIT_HYBRID_RAG_VECTOR_STORE_DIR={config.vector_store_dir}
        AGENTKIT_HYBRID_RAG_MEMORY_DB_PATH={config.memory_db_path}
        AGENTKIT_HYBRID_RAG_ENABLE_MEMORY={'true' if config.enable_memory else 'false'}
        AGENTKIT_HYBRID_RAG_EMBEDDING_MODEL={config.embedding_model}
        AGENTKIT_HYBRID_RAG_RERANKER_MODEL={config.reranker_model}
        AGENTKIT_HYBRID_RAG_CHUNK_SIZE_TOKENS={config.chunk_size_tokens}
        AGENTKIT_HYBRID_RAG_CHUNK_OVERLAP_TOKENS={config.chunk_overlap_tokens}
        AGENTKIT_HYBRID_RAG_RECALL_TOP_K={config.recall_top_k}
        AGENTKIT_HYBRID_RAG_FINAL_TOP_K={config.final_top_k}
        AGENTKIT_HYBRID_RAG_MAX_CONTEXT_TOKENS={_env_value(config.max_context_tokens)}
        AGENTKIT_HYBRID_RAG_EMBEDDING_BASE_URL={_env_value(config.embedding_base_url)}
        AGENTKIT_HYBRID_RAG_RERANKER_BASE_URL={_env_value(config.reranker_base_url or DEFAULT_RERANKER_BASE_URL)}

        # 如果你使用 OpenAI / DeepSeek / 通义等兼容服务，请在外部补充对应 API Key。
        # 如果你使用 Ollama 作为最终回答模型，请改成如：AGENTKIT_HYBRID_RAG_MODEL=ollama/qwen3.5:cloud
        """
    )


def _create_agent_module(config: HybridRAGWorkspaceConfig) -> str:
    return dedent(
        """\
        from __future__ import annotations

        import os
        from pathlib import Path

        from agentkit import HybridRAGAgent
        ROOT_DIR = Path(__file__).resolve().parent
        MODEL_ENV_KEYS = (
            "AGENTKIT_HYBRID_RAG_MODEL",
            "AGENTKIT_MODEL",
            "AGENTKIT_DEFAULT_MODEL",
            "AGENTKIT_STANDARD_MODEL",
        )


        def _load_env_file(path: Path) -> None:
            if not path.exists():
                return
            for raw_line in path.read_text(encoding="utf-8").splitlines():
                line = raw_line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                os.environ[key.strip()] = value.strip()


        def _resolve_bool(name: str, default: bool) -> bool:
            raw = os.getenv(name)
            if raw is None or raw == "":
                return default
            return raw.strip().lower() in {"1", "true", "yes", "on"}


        def _resolve_int(name: str, default: int) -> int:
            raw = os.getenv(name)
            if raw is None or raw == "":
                return default
            return int(raw)


        def _resolve_optional_int(name: str) -> int | None:
            raw = os.getenv(name)
            if raw is None or raw.strip() == "":
                return None
            return int(raw)


        def _resolve_model(default: str) -> str:
            for key in MODEL_ENV_KEYS:
                value = os.getenv(key)
                if value:
                    return value
            return default


        def _resolve_path(raw: str) -> str:
            expanded = os.path.expandvars(os.path.expanduser((raw or "").strip()))
            path = Path(expanded)
            if path.is_absolute():
                return str(path.resolve())

            # 容错处理：macOS 用户有时会把 "/Users/..." 误写成 "Users/..."。
            # 如果补上根目录后能命中现有路径，则优先按绝对路径解析。
            slash_prefixed = Path("/") / expanded.lstrip("/")
            if expanded and not expanded.startswith((".", "..")) and slash_prefixed.exists():
                return str(slash_prefixed.resolve())

            return str((ROOT_DIR / path).resolve())

        def resolve_knowledge_dir() -> str:
            _load_env_file(ROOT_DIR / ".env")
            return _resolve_path(os.getenv("AGENTKIT_HYBRID_RAG_KNOWLEDGE_DIR", "knowledge_base"))

        def create_rag_agent() -> HybridRAGAgent:
            _load_env_file(ROOT_DIR / ".env")
            return HybridRAGAgent.from_directory(
                knowledge_dir=resolve_knowledge_dir(),
                model=_resolve_model("gpt-4o-mini"),
                vector_store_dir=_resolve_path(
                    os.getenv("AGENTKIT_HYBRID_RAG_VECTOR_STORE_DIR", ".agentkit/rag_v2/chroma")
                ),
                memory_db_path=_resolve_path(
                    os.getenv("AGENTKIT_HYBRID_RAG_MEMORY_DB_PATH", ".agentkit/rag_v2/memory.db")
                ),
                embedding_model=os.getenv(
                    "AGENTKIT_HYBRID_RAG_EMBEDDING_MODEL",
                    "ollama/qllama/bge-small-zh-v1.5:f16",
                ),
                reranker_model=os.getenv(
                    "AGENTKIT_HYBRID_RAG_RERANKER_MODEL",
                    "ollama/qllama/bce-reranker-base_v1:f16",
                ),
                chunk_size_tokens=_resolve_int("AGENTKIT_HYBRID_RAG_CHUNK_SIZE_TOKENS", 350),
                chunk_overlap_tokens=_resolve_int("AGENTKIT_HYBRID_RAG_CHUNK_OVERLAP_TOKENS", 50),
                recall_top_k=_resolve_int("AGENTKIT_HYBRID_RAG_RECALL_TOP_K", 20),
                final_top_k=_resolve_int("AGENTKIT_HYBRID_RAG_FINAL_TOP_K", 3),
                max_context_tokens=_resolve_optional_int("AGENTKIT_HYBRID_RAG_MAX_CONTEXT_TOKENS"),
                enable_memory=_resolve_bool("AGENTKIT_HYBRID_RAG_ENABLE_MEMORY", True),
                embedding_base_url=os.getenv("AGENTKIT_HYBRID_RAG_EMBEDDING_BASE_URL") or None,
                reranker_base_url=(
                    os.getenv("AGENTKIT_HYBRID_RAG_RERANKER_BASE_URL")
                    or "http://127.0.0.1:11535"
                ),
            )


        def create_agent():
            rag = create_rag_agent()
            return rag.build_agent(
                name=os.getenv("AGENTKIT_HYBRID_RAG_AGENT_NAME", "hybrid-rag-assistant"),
            )
        """
    )


def _create_chat_module() -> str:
    return dedent(
        """\
        from __future__ import annotations

        import os
        import uuid

        from create_agent import create_agent, create_rag_agent, resolve_knowledge_dir


        def main() -> None:
            knowledge_dir = resolve_knowledge_dir()
            rag = create_rag_agent()
            agent = rag.build_agent()
            session_id = str(uuid.uuid4())
            files = rag.list_knowledge_files()

            print("=" * 68)
            print("HybridRAGAgent 工作目录已就绪")
            print("=" * 68)
            print("命令: /files 查看知识库 | /reload 重建索引 | /quit 退出")
            print(f"当前会话: {session_id}")
            print(f"知识库目录: {knowledge_dir}")
            if not files:
                print(f"当前知识库为空，请先向 {knowledge_dir} 目录放入文档。")
            else:
                print(f"当前已加载 {len(files)} 个知识库文件。")
                if files == ["welcome.md"]:
                    print("当前仅加载初始化示例文档 welcome.md，它只用于演示工作目录结构，不包含真实业务知识。")

            while True:
                try:
                    user_input = input("\\n请输入问题: ").strip()
                except (EOFError, KeyboardInterrupt):
                    print("\\n已退出。")
                    break

                if not user_input:
                    continue
                if user_input.lower() in {"/quit", "/exit"}:
                    print("已退出。")
                    break
                if user_input.lower() == "/files":
                    files = rag.list_knowledge_files()
                    if not files:
                        print(f"知识库为空，请先向 {knowledge_dir} 目录放入文档。")
                    else:
                        print("当前知识库文件：")
                        for item in files:
                            print(f"  - {item}")
                    continue
                if user_input.lower() == "/reload":
                    count = rag.reload()
                    agent = rag.build_agent(
                        name=os.getenv("AGENTKIT_HYBRID_RAG_AGENT_NAME", "hybrid-rag-assistant"),
                    )
                    print(f"重建完成，共索引 {count} 个文档块。")
                    continue

                result = agent.invoke(input=user_input, session_id=session_id)
                if result.success:
                    print(f"\\n{result.final_output}")
                else:
                    print(f"\\n执行失败: {result.error}")


        if __name__ == "__main__":
            main()
        """
    )


def _create_rerank_server_module() -> str:
    return dedent(
        """\
        from __future__ import annotations

        import os
        from pathlib import Path
        from urllib.parse import urlparse

        from agentkit.rag.rerank_server import main as rerank_server_main

        ROOT_DIR = Path(__file__).resolve().parent


        def _load_env_file(path: Path) -> None:
            if not path.exists():
                return
            for raw_line in path.read_text(encoding="utf-8").splitlines():
                line = raw_line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                os.environ[key.strip()] = value.strip()


        def _parse_server_host_and_port(base_url: str) -> tuple[str, int]:
            parsed = urlparse(base_url)
            host = parsed.hostname or "127.0.0.1"
            port = parsed.port or 11535
            return host, port


        def main() -> int:
            _load_env_file(ROOT_DIR / ".env")

            base_url = os.getenv("AGENTKIT_HYBRID_RAG_RERANKER_BASE_URL", "http://127.0.0.1:11535")
            host, port = _parse_server_host_and_port(base_url)
            model = os.getenv("AGENTKIT_HYBRID_RAG_RERANKER_MODEL", "ollama/qllama/bce-reranker-base_v1:f16")
            fallback_model = os.getenv(
                "AGENTKIT_HYBRID_RAG_EMBEDDING_MODEL",
                "ollama/qllama/bge-small-zh-v1.5:f16",
            )
            ollama_base_url = os.getenv("AGENTKIT_HYBRID_RAG_EMBEDDING_BASE_URL", "http://localhost:11434")

            print("=" * 68)
            print("启动 AgentKit 本地 rerank sidecar")
            print("=" * 68)
            print(f"监听地址: http://{host}:{port}")
            print(f"Reranker 模型: {model}")
            print(f"Fallback 模型: {fallback_model}")
            print(f"Ollama 地址: {ollama_base_url}")

            return rerank_server_main([
                "--host", host,
                "--port", str(port),
                "--model", model,
                "--fallback-model", fallback_model,
                "--ollama-base-url", ollama_base_url,
            ])


        if __name__ == "__main__":
            raise SystemExit(main())
        """
    )


def _create_workspace_readme(config: HybridRAGWorkspaceConfig) -> str:
    memory_line = (
        "- 默认记忆: 已启用，数据会写入 `"
        f"{config.memory_db_path}"
        "`\n"
    ) if config.enable_memory else "- 默认记忆: 已关闭\n"
    return dedent(
        f"""\
        # HybridRAGAgent 工作目录

        这个目录由 `agentkit-hybrid-rag-init` 自动生成，可直接用于体验 AgentKit 的 `HybridRAGAgent`。

        ## 目录结构

        - `knowledge_base/`: 放置知识库文档（支持 `txt/md/markdown/pdf`）
        - `create_agent.py`: 创建 `HybridRAGAgent` / Agent 的工厂文件
        - `start_rerank_server.py`: 启动本地 rerank sidecar 的辅助脚本
        - `chat.py`: 交互式对话入口
        - `.env`: 当前工作目录配置

        ## 当前配置

        - Agent 名称: `{config.agent_name}`
        - 回答模型: `{config.model}`
        - Embedding 模型: `{config.embedding_model}`
        - Reranker 模型: `{config.reranker_model}`
        - Reranker 服务地址: `{config.reranker_base_url or DEFAULT_RERANKER_BASE_URL}`
        - 向量库存储: `{config.vector_store_dir}`
        {memory_line}- Chunk 配置: `{config.chunk_size_tokens}` / overlap `{config.chunk_overlap_tokens}`
        - Recall / Final Top K: `{config.recall_top_k}` / `{config.final_top_k}`

        ## 使用步骤

        1. 按需编辑 `.env`，补充模型与服务地址配置。
        2. 如果需要本地 embedding / reranker，请先准备对应服务：

           ```bash
           ollama serve
           ollama pull qllama/bge-small-zh-v1.5:f16
           ollama pull qllama/bce-reranker-base_v1:f16
           pip install "ni.agentkit[rerank]"
           python start_rerank_server.py
           ```

           如果当前 Ollama 版本无法让 `qllama/bce-reranker-base_v1:f16` 通过 `/api/embed`
           提供向量，`agentkit-rerank-server` 会自动回退到
           `qllama/bge-small-zh-v1.5:f16` 继续完成排序。

        3. 把你的文档放到 `{config.knowledge_dir}` 目录。
        4. 启动交互式体验：

           ```bash
           python chat.py
           ```

        ## 常用命令

        - `/files`: 查看已加载的知识库文件
        - `/reload`: 重建索引
        - `/quit`: 退出对话

        ## 依赖提醒

        运行 `HybridRAGAgent` 需要 `chromadb`；如果你希望启用本地 rerank sidecar，还需要安装 rerank extra。推荐执行：

        ```bash
        pip install "ni.agentkit[rag,rerank]"
        ```
        """
    )


def _create_sample_doc() -> str:
    return dedent(
        """\
        # 欢迎使用 HybridRAGAgent

        这是初始化向导自动生成的示例知识库文档。
        它只用于帮助你确认工作目录已经创建成功，并不代表真实业务知识库内容。

        AgentKit 是一个 Python 原生的 Agent 开发框架，提供 Agent、Tool、Skill、Memory 与多模型适配能力。
        `HybridRAGAgent` 是 AgentKit 内置的增强版 RAG 方案，默认采用：

        - BM25 关键字召回
        - Chroma 向量检索
        - RRF 融合排序
        - Reranker 精排

        如果你向它询问具体行业知识、产品资料、法规条文或交易策略，通常不会命中。

        建议你把自己的业务文档放进这个目录，然后执行 `/files` 确认文件已被发现，
        再执行 `/reload` 重建索引，最后运行 `python chat.py` 开始体验检索增强问答。
        """
    )


def generate_workspace(config: HybridRAGWorkspaceConfig) -> list[Path]:
    _resolve_existing_conflicts(config)
    config.target_dir.mkdir(parents=True, exist_ok=True)

    written: list[Path] = []
    env_content = _create_env_file(config)
    for name in (".env", ".env.example"):
        path = config.target_dir / name
        _write_text(path, env_content)
        written.append(path)

    files = {
        "create_agent.py": _create_agent_module(config),
        "start_rerank_server.py": _create_rerank_server_module(),
        "chat.py": _create_chat_module(),
        "README.md": _create_workspace_readme(config),
    }
    for name, content in files.items():
        path = config.target_dir / name
        _write_text(path, content)
        written.append(path)

    knowledge_dir = config.target_dir / config.knowledge_dir
    knowledge_dir.mkdir(parents=True, exist_ok=True)
    if config.create_sample_doc:
        sample_path = knowledge_dir / "welcome.md"
        _write_text(sample_path, _create_sample_doc())
        written.append(sample_path)

    vector_store_parent = config.target_dir / Path(config.vector_store_dir).parent
    vector_store_parent.mkdir(parents=True, exist_ok=True)

    if config.enable_memory:
        memory_parent = config.target_dir / Path(config.memory_db_path).parent
        memory_parent.mkdir(parents=True, exist_ok=True)

    return written


def check_runtime_dependencies() -> list[tuple[str, bool, str]]:
    checks: list[tuple[str, bool, str]] = []
    chromadb_installed = importlib.util.find_spec("chromadb") is not None
    checks.append(
        (
            "chromadb",
            chromadb_installed,
            '缺少 chromadb，请执行: pip install "ni.agentkit[rag]"',
        )
    )
    return checks


def print_dependency_report() -> None:
    print()
    print("环境自检：")
    for name, ok, message in check_runtime_dependencies():
        status = "OK" if ok else "MISSING"
        print(f"- {name}: {status}")
        if not ok:
            print(f"  {message}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="agentkit-hybrid-rag-init",
        description="交互式创建 HybridRAGAgent 工作目录。",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="如果目标目录已有同名文件，则覆盖写入。",
    )
    parser.add_argument(
        "--skip-self-check",
        action="store_true",
        help="跳过 chromadb 依赖自检。",
    )
    args = parser.parse_args(argv)

    try:
        config = _build_config_from_wizard(force=args.force)
        written = generate_workspace(config)
    except FileExistsError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\n已取消。", file=sys.stderr)
        return 130

    print()
    print("已生成以下文件：")
    for path in written:
        print(f"- {path}")

    if not args.skip_self_check:
        print_dependency_report()

    print()
    print("下一步：")
    print(f"1. 进入目录: cd {config.target_dir}")
    print("2. 按需编辑 .env")
    print(f"3. 向 {config.knowledge_dir} 放入文档")
    print("4. 启动 rerank 服务: python start_rerank_server.py")
    print("5. 运行: python chat.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
