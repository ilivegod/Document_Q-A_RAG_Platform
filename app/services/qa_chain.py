from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser


def format_chunks_into_text(retrievedChunks: list):
    context_parts = []
    for i, chunk in enumerate(retrievedChunks, 1):
        page_info = (
            f" (Page {chunk.page_number})" if hasattr(chunk, "page_number") else ""
        )

        formatted_chunk = f"[{i}]{page_info}: {chunk.content.strip()}"
        context_parts.append(formatted_chunk)
    return "\n\n".join(context_parts)


# def llm_prompt(question: str, retrievedChunks: list):
