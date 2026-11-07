"""重建项目自带的本地战术基础知识索引。"""

from __future__ import annotations

import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from knowledge_base.ingestion.foundation_ingestion import build_and_write_foundation_index


def main() -> None:
    """从人工维护的战术条目生成可供检索器加载的切块索引。"""
    # 输出路径让维护者确认构建完成，不打印知识正文以保持命令行输出简洁。
    index_path = build_and_write_foundation_index()
    print(f"本地战术知识索引已生成：{index_path}")


if __name__ == "__main__":
    main()
