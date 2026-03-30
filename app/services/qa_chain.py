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
        """Answer the question based only on the following context.
        Cite your sources using the numbers in brackets.
        If the context doesn't contain the answer, say "I don't have enough information to answer this."

        Context:{context}

        Question:{question}
        """
    )

    model = ChatGoogleGenerativeAI(
        model="gemini-2.5-flash-lite", google_api_key=settings.google_api_key
    )

    chain = prompt | model | StrOutputParser()

    result = chain.invoke({"context": formatted_text, "question": question})

    return result
