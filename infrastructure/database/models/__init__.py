"""导入所有模型，供 Alembic 发现完整的数据库元数据。"""

from infrastructure.database.models.core import (
    BackgroundTaskModel,
    ConversationModel,
    DocumentChunkModel,
    DocumentModel,
    EvaluationRunModel,
    MessageModel,
    ResearchRunModel,
    UserModel,
)

__all__ = [
    "BackgroundTaskModel",
    "ConversationModel",
    "DocumentChunkModel",
    "DocumentModel",
    "EvaluationRunModel",
    "MessageModel",
    "ResearchRunModel",
    "UserModel",
]
