from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser
from app.config import settings


def format_chunks_into_text(retrievedChunks: list):
    context_parts = []
    for i, chunk in enumerate(retrievedChunks, 1):
        page_info = f" (Page {chunk.page_num})" if chunk.page_num else ""

        formatted_chunk = f"[{i}]{page_info}: {chunk.content.strip()}"
        context_parts.append(formatted_chunk)
    return "\n\n".join(context_parts)


def llm_prompt(question: str, retrievedChunks: list):
    formatted_text = format_chunks_into_text(retrievedChunks)
    prompt = PromptTemplate.from_template(
        """You are a helpful document assistant. Your job is to answer questions based only on the provided context.

    Rules:
    - If the question is about the document, answer it and cite your sources using the numbers in brackets.
    - If the question is casual, off-topic, or not related to the document (like greetings, small talk, or general questions), respond with exactly: "I'm here to help you with your document! Ask me anything about its content and I'll find the answer with citations."
    - Never make up information that isn't in the context.

    Context:{context}

    Question:{question}
    """
    )

    model = ChatGoogleGenerativeAI(
        model="gemini-2.5-flash-lite", google_api_key=settings.google_api_key
    )

    chain = prompt | model | StrOutputParser()

    try:
        result = chain.invoke({"context": formatted_text, "question": question})
        return result
    except Exception as e:
        if "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e):
            return "I'm currently rate limited. Please wait a moment and try again."
        raise
