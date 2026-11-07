"""供应商无关的模型调用成本估算，价格由环境变量而非代码常量控制。"""

from __future__ import annotations

import os


def estimate_cost_usd(input_tokens: int, output_tokens: int) -> float | None:
    """按每百万 Token 单价估算本次调用成本；未配置价格时返回 None。"""
    # 不猜测供应商价格，避免把过期价格写进运行报表造成错误决策。
    try:
        input_price = float(os.getenv("SOCCER_INPUT_USD_PER_M_TOKEN", ""))
        output_price = float(os.getenv("SOCCER_OUTPUT_USD_PER_M_TOKEN", ""))
    except ValueError:
        return None
    return round(input_tokens * input_price / 1_000_000 + output_tokens * output_price / 1_000_000, 8)
