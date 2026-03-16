from sqlalchemy import select, update, func
from sqlalchemy.ext.asyncio import AsyncSession
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage
import logging

from app.common.settings import settings
from app.models.model import ChatMessage, ChatSummary
from app.prompts.summary_prompt import SUMMARY_PROMPT

logger = logging.getLogger(__name__)

CHUNK_SIZE = 10
_SUMMARY_MODEL = "gemini-2.0-flash-lite"


class SummaryService:

    @staticmethod
    async def get_unsummarized_messages(
        db: AsyncSession, session_id: int, limit: int = CHUNK_SIZE
    ):
        """
        Fetch unsummarized messages for a session.
        Returns messages + their IDs so we can mark only those summarized.
        """

        logger.debug(
            "Fetching unsummarized messages | session_id=%s | limit=%s",
            session_id,
            limit,
        )

        result = await db.execute(
            select(
                ChatMessage.id,
                ChatMessage.role,
                ChatMessage.content,
            )
            .where(
                ChatMessage.session_id == session_id,
                ChatMessage.role.in_(["user", "assistant"]),
                ChatMessage.is_summarized.is_(False),
            )
            .order_by(ChatMessage.created_at.asc())
            .limit(limit)
        )

        rows = result.all()

        messages = []
        message_ids = []

        for msg_id, role, content in rows:
            if not content:
                continue

            message_ids.append(msg_id)

            messages.append(
                {
                    "role": role,
                    "content": content,
                }
            )

        logger.debug(
            "Unsummarized messages fetched | session_id=%s | count=%s",
            session_id,
            len(messages),
        )

        return messages, message_ids

    @staticmethod
    async def update_summary_if_chunk_complete(
        db: AsyncSession, session_id: int
    ) -> None:
        """
        Check if 10+ unsummarized messages exist and update summary.
        """
        
        # Count unsummarized messages
        result = await db.execute(
            select(func.count(ChatMessage.id))
            .where(
                ChatMessage.session_id == session_id,
                ChatMessage.role.in_(["user", "assistant"]),
                ChatMessage.is_summarized.is_(False),
            )
        )
        
        unsummarized_count = result.scalar()
        
        # Not enough messages to summarize yet
        if unsummarized_count < CHUNK_SIZE:
            return

        messages, message_ids = await SummaryService.get_unsummarized_messages(
            db, session_id=session_id, limit=CHUNK_SIZE
        )

        logger.info(
            "Summarization triggered | session_id=%s | messages=%s",
            session_id,
            len(messages),
        )

        conversation_text = "\n".join(
            f"{m['role'].upper()}: {m['content']}"
            for m in messages
            if m.get("content")
        )

        # Load existing summary (lock row for update)
        result = await db.execute(
            select(ChatSummary)
            .where(ChatSummary.session_id == session_id)
            .with_for_update()
        )

        summary_row = result.scalar_one_or_none()
        existing_summary = summary_row.summary if summary_row else "None"

        # Build LLM prompt
        prompt = SUMMARY_PROMPT.format(
            existing_summary=existing_summary,
            conversation=conversation_text,
        )

        # Call Gemini
        llm = ChatGoogleGenerativeAI(
            model=_SUMMARY_MODEL,
            google_api_key=settings.gemini_api_key,
            temperature=0.3,
        )

        response = await llm.ainvoke([HumanMessage(content=prompt)])

        content = response.content

        if isinstance(content, list):
            content = " ".join(
                p.get("text", "") for p in content if isinstance(p, dict)
            )

        updated_summary = str(content).strip().replace("**", "")

        # Save or update summary
        if summary_row:
            summary_row.summary = updated_summary
        else:
            db.add(
                ChatSummary(
                    session_id=session_id,
                    summary=updated_summary,
                )
            )

        # Mark ONLY summarized messages
        await db.execute(
            update(ChatMessage)
            .where(ChatMessage.id.in_(message_ids))
            .values(is_summarized=True)
            .execution_options(synchronize_session=False)
        )

        await db.commit()

        logger.info(
            "Summary updated successfully | session_id=%s | messages=%s",
            session_id,
            len(messages),
        )

    @staticmethod
    async def get_summary(db: AsyncSession, session_id: int) -> str:
        """
        Fetch summary for a session.
        """

        result = await db.execute(
            select(ChatSummary.summary).where(
                ChatSummary.session_id == session_id
            )
        )

        return result.scalar() or ""