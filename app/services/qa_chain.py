from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import PromptTemplate
from pydantic import BaseModel, Field
from app.config import settings
import logging

logger = logging.getLogger(__name__)


class LLMAnswer(BaseModel):
    """Structured output the LLM is forced to produce."""

    has_answer: bool = Field(
        description=(
            "True if you can answer the question from the provided context. "
            "False if the context doesn't contain the information needed, "
            "or if the question is unrelated to the document (greetings, "
            "small talk, off-topic questions)."
        )
    )
    answer: str = Field(
        description=(
            "Your answer to the question, with citations using bracket "
            "numbers like [1] or [2] referencing the context. "
            "If has_answer is False, provide a brief, polite explanation "
            "(e.g. 'The document doesn't contain information about X' or "
            "'I'm here to help with questions about your document')."
        )
    )


def format_chunks_into_text(retrieved_chunks: list) -> str:
    context_parts = []
    for i, chunk in enumerate(retrieved_chunks, 1):
        page_info = f" (Page {chunk.page_num + 1})" if chunk.page_num is not None else ""
        formatted_chunk = f"[{i}]{page_info}: {chunk.content.strip()}"
        context_parts.append(formatted_chunk)
    return "\n\n".join(context_parts)


def llm_prompt(question: str, retrieved_chunks: list) -> LLMAnswer:
    formatted_text = format_chunks_into_text(retrieved_chunks)

    prompt = PromptTemplate.from_template(
        """You are a helpful document assistant. Answer questions based only on the provided context.

Rules:
- If the question can be answered from the context, set has_answer=True and provide the answer with citations like [1], [2] referencing the context numbers.
- If the context doesn't contain enough information, set has_answer=False and briefly explain you don't have that information.
- If the question is casual, off-topic, or unrelated to the document, set has_answer=False and politely redirect.
- Never make up information that isn't in the context.

Context:
{context}

Question: {question}
"""
    )

    model = ChatGoogleGenerativeAI(
        model="gemini-2.5-flash-lite",
        google_api_key=settings.google_api_key,
    ).with_structured_output(LLMAnswer)

    chain = prompt | model

    try:
        result: LLMAnswer = chain.invoke(
            {"context": formatted_text, "question": question}
        )
        return result
    except Exception as e:
        if "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e):
            logger.warning("Gemini rate limit hit")
            return LLMAnswer(
                has_answer=False,
                answer="I'm currently rate limited. Please wait a moment and try again.",
            )
        logger.error(f"LLM call failed: {e}", exc_info=True)
        raise