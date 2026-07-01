# app.py
import os
import uuid
try:
    import streamlit as st
except ImportError as exc:
    raise RuntimeError('未安装 streamlit。请执行 `pip install streamlit` 后再运行 Web 示例。') from exc

try:
    from .core import create_rag_agent, ensure_knowledge_base, get_knowledge_dir, get_model
except ImportError:
    from core import create_rag_agent, ensure_knowledge_base, get_knowledge_dir, get_model

# 页面配置
st.set_page_config(page_title="RAGAgent UI", page_icon="🤖", layout="wide")

# 初始化 Session State (确保 Agent 只被创建一次)
if "agent" not in st.session_state:
    with st.spinner("🚀 正在初始化知识库和 Agent，请稍候..."):
        ensure_knowledge_base()
        st.session_state.agent = create_rag_agent()
    st.session_state.session_id = str(uuid.uuid4())
    st.session_state.messages = []

# ================= 侧边栏 =================
with st.sidebar:
    st.title("⚙️ 控制面板")
    
    st.markdown("### 📊 运行状态")
    st.info(f"**模型:** `{get_model()}`")
    st.info(f"**知识库:** `{get_knowledge_dir()}`")
    st.caption(f"会话 ID: `{st.session_state.session_id[:8]}...`")
    
    st.markdown("### 🛠️ 操作")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("🔄 重载知识库", use_container_width=True):
            with st.spinner("正在重新加载..."):
                rag = getattr(st.session_state.agent, "_rag", None)
                if rag is not None:
                    rag.reload()
                else:
                    st.session_state.agent = create_rag_agent()
            st.success("加载完成！")
            st.rerun()
    with col2:
        if st.button("🗑️ 清空对话", use_container_width=True):
            st.session_state.messages = []
            st.session_state.session_id = str(uuid.uuid4())
            st.rerun()
            
    st.markdown("### 📚 知识库文件")
    files = [f for f in os.listdir(get_knowledge_dir()) 
             if f.lower().endswith(('.txt', '.md', '.markdown', '.pdf'))]
    if files:
        for f in files:
            st.caption(f"📄 {f}")
    else:
        st.warning("知识库为空")

# ================= 主界面 =================
st.title("🤖 交互式 RAGAgent")
st.caption("基于 AgentKit 的智能知识问答助手 | 支持多轮对话与知识库检索")

# 显示历史消息
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# 输入框
if prompt := st.chat_input("请输入您的问题，例如：AgentKit 是什么？"):
    # 1. 显示用户输入
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)
        
    # 2. 生成助手回复
    with st.chat_message("assistant"):
        with st.status("🤔 正在思考与检索...", expanded=True) as status:
            st.write("🔍 正在检索知识库...")
            # 使用同步模式运行，保证 Streamlit 界面不卡顿且稳定
            result = st.session_state.agent.invoke(
                input=prompt,
                session_id=st.session_state.session_id
            )
            
            if result.success:
                final_output = result.final_output
                st.write("✅ 生成回答完成")
                status.update(label="✅ 回答完成", state="complete", expanded=False)
                
                # 显示最终结果
                st.markdown(final_output)
                
                # 保存到历史
                st.session_state.messages.append({"role": "assistant", "content": final_output})
            else:
                status.update(label="❌ 发生错误", state="error", expanded=True)
                st.error(f"错误信息: {result.error}")
