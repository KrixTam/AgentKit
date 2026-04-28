"""示例工具：由 SKILL.md tools.entry 动态发现并注册。"""


def weather_lookup(city: str) -> str:
    data = {
        "北京": "晴，25°C",
        "上海": "多云，22°C",
        "深圳": "阵雨，28°C",
        "广州": "晴，31°C",
        "成都": "阴，18°C",
    }
    return data.get(city, f"{city}：暂无数据")
