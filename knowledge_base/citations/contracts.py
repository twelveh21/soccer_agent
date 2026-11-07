"""最终回答中引用项的统一模型。"""

from __future__ import annotations

from pydantic import BaseModel, HttpUrl


class Citation(BaseModel):
    """表示一个可展示给用户的资料出处。"""

    # locator 是页码、段落或时间戳；没有可靠定位时应为空而不是编造。
    citation_id: str
    title: str
    url: HttpUrl | None = None
    locator: str | None = None
    source_type: str
