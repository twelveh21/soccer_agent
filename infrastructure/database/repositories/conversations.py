"""conversations 与 messages 表的数据访问实现。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from infrastructure.database.models.core import ConversationModel, MessageModel


MessageRole = Literal["user", "assistant"]


@dataclass(frozen=True)
class StoredMessage:
    """从数据库返回给 API 的一条安全消息快照。"""

    message_id: str
    role: MessageRole
    content: str


class ConversationRepository:
    """封装匿名会话的创建、消息追加与历史读取。"""

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        """保存创建短生命周期数据库 Session 的工厂。

        参数：
        - session_factory：创建 SQLAlchemy Session 的工厂函数。

        实现逻辑：每个仓储方法独立开关事务，避免不同网页请求共享同一个数据库连接。
        """
        self._session_factory = session_factory

    def get_or_create(self, client_session_id: str, title: str) -> str:
        """按浏览器会话 ID 获取或创建数据库对话，并返回 conversation_id。

        参数：
        - client_session_id：前端为每个新对话生成的稳定 ID。
        - title：首次创建时使用的问题摘要；已有对话不会覆盖旧标题。

        实现逻辑：先按唯一 client_session_id 查询；没有记录才插入，避免同一对话重复创建。
        """
        with self._session_factory.begin() as session:
            conversation = session.scalar(
                select(ConversationModel).where(ConversationModel.client_session_id == client_session_id)
            )
            if conversation is None:
                conversation = ConversationModel(
                    client_session_id=client_session_id,
                    title=title[:200] or "新对话",
                )
                session.add(conversation)
                session.flush()
            return conversation.id

    def append_message(self, conversation_id: str, role: MessageRole, content: str) -> str:
        """向指定对话追加一条用户消息或 Agent 回复。

        参数：
        - conversation_id：数据库中的对话 ID。
        - role：消息角色，只允许 user 或 assistant。
        - content：需要保存的消息正文。

        实现逻辑：先确认对话存在，再插入消息；使用外键保证不会出现“孤儿消息”。
        """
        with self._session_factory.begin() as session:
            if session.get(ConversationModel, conversation_id) is None:
                raise LookupError(f"对话不存在：{conversation_id}")
            message = MessageModel(conversation_id=conversation_id, role=role, content=content)
            session.add(message)
            session.flush()
            return message.id

    def list_messages(self, client_session_id: str) -> list[StoredMessage]:
        """按浏览器会话 ID 读取完整消息历史。

        参数：
        - client_session_id：前端保存的对话 session_id。

        实现逻辑：先定位对话，再按消息创建顺序返回；查不到对话时返回空列表，便于前端处理新对话。
        """
        with self._session_factory() as session:
            conversation = session.scalar(
                select(ConversationModel).where(ConversationModel.client_session_id == client_session_id)
            )
            if conversation is None:
                return []
            messages = session.scalars(
                select(MessageModel)
                .where(MessageModel.conversation_id == conversation.id)
                .order_by(MessageModel.created_at.asc())
            ).all()
            return [
                StoredMessage(message_id=item.id, role=item.role, content=item.content)
                for item in messages
            ]
