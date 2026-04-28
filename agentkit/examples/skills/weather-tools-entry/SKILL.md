---
name: weather-tools-entry
description: 通过 SKILL.md 的 tools.entry 动态注册天气查询工具
triggers:
  - 天气
  - 穿衣建议
dependencies:
  - requests
tools:
  - name: weather_lookup
    description: 查询城市天气并给出简要信息
    entry: tools/weather_tools.py:weather_lookup
    parameters:
      city: { type: string, description: "城市名称，如北京/上海/深圳" }
---

## 天气助手执行步骤

1. 当用户询问天气或穿衣建议时，先调用 `weather_lookup` 获取天气信息。
2. 根据温度和天气状况给出简短建议：
   - 温度 >= 30：短袖 + 防晒
   - 温度 20-29：薄外套
   - 温度 < 20：保暖外套
3. 如果天气包含“雨”，提醒携带雨具。
4. 使用简洁中文回复。
