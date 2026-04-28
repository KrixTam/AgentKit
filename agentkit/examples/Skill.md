---
name: "skill_name"
version: "1.0.0"
description: "一句话说明技能用途"
author: "your_name"
license: "MIT"
triggers:
  - "触发词1"
  - "触发词2"
dependencies:
  - package1>=1.0
  - package2
tools:
  - name: "tool_name"
    description: "工具功能简述"
    entry: "tools/tool_module.py:tool_function"
    parameters:
      param1: { type: string, description: "参数说明" }
      param2: { type: integer, default: 10, description: "可选参数" }
metadata:
  additional_tools:
    - "extra_tool_name"
  sandbox_required: true
  timeout: 30
---

# 🛠️ 技能名称

## 🎯 能力边界
- ✅ 支持：...
- ❌ 不支持：...
- ⚠️ 限制：...

## 💡 调用示例
**用户**: "请执行 XX 操作"
**Agent**:
```json
{
  "tool": "tool_name",
  "arguments": { "param1": "value", "param2": 5 }
}