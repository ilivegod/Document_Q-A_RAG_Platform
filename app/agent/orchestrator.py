import logging
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import StructuredTool
from langchain_google_genai import ChatGoogleGenerativeAI

from app.agent.context import AgentContext
from app.agent.registry import (
    GET_PAGE_CONTENT,
    KEYWORD_SEARCH,
    LIST_USER_DOCUMENTS,
    SEARCH_DOCUMENTS,
    WEB_RESEARCH,
)
from app.agent.trace_utils import public_agent_trace, resolve_follow_up_question
from app.agent.tools.handlers import build_args_schema, build_tool_specs, execute_tool
from app.config import settings
from app.models.user import UserTier
from app.mcp.schemas import WebFinding
from app.services.qa_chain import LLMAnswer

logger = logging.getLogger(__name__)

MAX_TOOL_CALLS = 5

AGENT_SYSTEM = """You are Project Copilot, an assistant that helps freelancers and indie builders
understand project documents — specs, contracts, briefs, and notes in PDF or DOCX format.
You ONLY answer questions grounded in the user's uploaded documents for the current project.

Tool usage:
- search_documents: semantic/conceptual questions about document content (use first for most questions)
- keyword_search: exact terms, dates, names, or phrases in documents
- get_page_content: when the user asks about a specific page number (page_number only in single-document chat)
- list_user_documents: discover what files the user has uploaded for this project
- web_research: ONLY to supplement a topic already found via search_documents (e.g. explain a
  term that appears in the file). Always call search_documents first.
  Never for weather, news, sports, or topics not in the user's files.

Do NOT use tools for identity or meta questions ("who are you", "what can you do", greetings).
Answer those directly: you are Project Copilot and you help users understand their project documents.

Do NOT use any tools for clearly off-topic questions (weather, news, jokes) unrelated to their files.
For document topics (including concepts named in the file), always use search_documents first.

Never call web_research before search_documents.

After gathering context from tools, provide clear answers with citations [D1], [D2] for documents
and [W1], [W2] for internet sources only when web_research supplemented document content.
Never invent facts not supported by tool results.
"""

OFF_TOPIC_DOCUMENT_ONLY = (
    "I only answer questions based on your uploaded project documents. "
    "Ask me something about your files."
)

FINAL_ANSWER_RULES = f"""You are Project Copilot. Follow these response rules strictly.

Identity / capabilities (answer with has_answer=True, no citations needed):
- If asked who you are or what you do, say: "I'm Project Copilot. I help you understand your project documents by searching them and answering with citations."

Forbidden phrasing (never use):
- Do not say you are a generic AI, language model, chatbot, or mention training data / knowledge cutoffs.

Off-topic questions (weather, news, sports, jokes — with NO document context below):
- Set has_answer=False.
- Say exactly: "{OFF_TOPIC_DOCUMENT_ONLY}"

When document context IS provided below:
- The question is about the user's files. Answer from that context with [D1], [D2] citations.
- NEVER use the off-topic decline message when document context exists.
- Set has_answer=True when the context addresses the question.

Document questions without enough context:
- Set has_answer=False.
- Say you could not find that in their documents and suggest rephrasing or checking processing status.

Web context usage:
- Only use internet citations [W1], [W2] when web results supplement something from the user's documents.
- Do not answer general off-topic questions even if web context appears below.
"""


_DOC_TOOLS = {
    SEARCH_DOCUMENTS,
    KEYWORD_SEARCH,
    GET_PAGE_CONTENT,
    LIST_USER_DOCUMENTS,
}


def _sort_tool_calls(tool_calls: list) -> list:
    """Run document tools before web_research when the model batches calls."""

    def priority(tc: dict) -> int:
        name = tc.get("name", "")
        if name in _DOC_TOOLS:
            return 0
        if name == WEB_RESEARCH:
            return 2
        return 1

    return sorted(tool_calls, key=priority)


async def _append_tool_step(
    ctx: AgentContext,
    tier: UserTier,
    allowed_names: set[str],
    agent_trace: list[dict],
    name: str,
    args: dict,
) -> None:
    ctx.last_web_sub_steps = []
    if name not in allowed_names:
        result = f"Tool {name} is not available on your plan."
    else:
        try:
            result = await execute_tool(ctx, name, args)
        except Exception as e:
            logger.error("Tool %s failed: %s", name, e, exc_info=True)
            result = f"Tool error: {e}"

    summary = result[:500] + ("..." if len(result) > 500 else "")
    step: dict = {
        "tool": name,
        "input": args,
        "output_summary": summary,
    }
    if name == WEB_RESEARCH and ctx.last_web_sub_steps:
        step["metadata"] = {"sub_steps": ctx.last_web_sub_steps}
        web_count = len(ctx.collected_web_sources)
        step["output_summary"] = f"{web_count} web source(s): {summary[:400]}"
    agent_trace.append(step)


def _make_langchain_tool(ctx: AgentContext, tier: UserTier, spec) -> StructuredTool:
    name = spec.name
    args_schema = build_args_schema(spec)

    async def _tool_fn(**kwargs) -> str:
        return await execute_tool(ctx, name, kwargs)

    return StructuredTool.from_function(
        coroutine=_tool_fn,
        name=name,
        description=spec.description,
        args_schema=args_schema,
    )


def _dedupe_chunks(chunks: list) -> list:
    seen: set = set()
    out = []
    for c in chunks:
        cid = str(getattr(c, "id", id(c)))
        if cid not in seen:
            seen.add(cid)
            out.append(c)
    return out


def _dedupe_web_findings(findings: list[WebFinding]) -> list[WebFinding]:
    seen: set[tuple[str, str]] = set()
    out: list[WebFinding] = []
    for f in findings:
        key = (f.url or f.title, f.provider)
        if key in seen:
            continue
        seen.add(key)
        out.append(f)
    return out


def _format_document_context(chunks: list) -> str:
    if not chunks:
        return ""
    parts = []
    for i, chunk in enumerate(chunks, 1):
        page_info = f" (Page {(chunk.page_num or 0) + 1})" if chunk.page_num is not None else ""
        parts.append(f"[D{i}]{page_info}: {chunk.content.strip()}")
    return "\n\n".join(parts)


def _format_agent_trace_summary(agent_trace: list[dict]) -> str:
    if not agent_trace:
        return "No tools were called."
    lines = []
    for step in agent_trace:
        tool = step.get("tool", "unknown")
        summary = step.get("output_summary", "")
        lines.append(f"- {tool}: {summary[:200]}")
    return "\n".join(lines)


async def _synthesize_answer(
    question: str,
    doc_context: str,
    web_context: str,
    chat_history: list[dict] | None,
    agent_trace: list[dict],
    project_context: str = "",
) -> LLMAnswer:
    final_model = ChatGoogleGenerativeAI(
        model="gemini-2.5-flash-lite",
        google_api_key=settings.google_api_key,
    ).with_structured_output(LLMAnswer)

    history_text = ""
    if chat_history:
        lines = [f"{m['role'].capitalize()}: {m['content']}" for m in chat_history]
        history_text = "\n".join(lines)

    context_sections = []
    if project_context:
        context_sections.append(f"Project memory:\n{project_context}")
    if doc_context:
        context_sections.append(f"Document context:\n{doc_context}")
    if web_context:
        context_sections.append(f"Internet context:\n{web_context}")
    combined_context = "\n\n".join(context_sections) if context_sections else (
        "No document or internet context was retrieved."
    )

    trace_summary = _format_agent_trace_summary(agent_trace)

    prompt_text = f"""{FINAL_ANSWER_RULES}

{combined_context}

Tool activity:
{trace_summary}

{f"Previous conversation:\n{history_text}\n" if history_text else ""}
Question: {question}
"""
    try:
        return await final_model.ainvoke(prompt_text)
    except Exception as e:
        if "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e):
            return LLMAnswer(
                has_answer=False,
                answer="Rate limited. Please try again shortly.",
            )
        raise


def _format_web_context(findings: list[WebFinding]) -> str:
    if not findings:
        return ""
    parts = []
    for i, finding in enumerate(findings, 1):
        url_info = f" ({finding.url})" if finding.url else ""
        parts.append(
            f"[W{i}] {finding.title}{url_info} [{finding.provider}]: {finding.snippet.strip()}"
        )
    return "\n\n".join(parts)


async def run_agent(
    question: str,
    ctx: AgentContext,
    tier: UserTier,
    chat_history: list[dict] | None = None,
) -> tuple[LLMAnswer, list[dict], list, list[WebFinding]]:
    """Run the agent loop. Returns answer, trace, document chunks, and web findings."""
    specs = build_tool_specs(tier)
    allowed_names = {s.name for s in specs}
    effective_question = resolve_follow_up_question(question, chat_history)

    model = ChatGoogleGenerativeAI(
        model="gemini-2.5-flash-lite",
        google_api_key=settings.google_api_key,
    )

    tools = [_make_langchain_tool(ctx, tier, spec) for spec in specs]
    model_with_tools = model.bind_tools(tools)

    messages: list[Any] = [SystemMessage(content=AGENT_SYSTEM)]
    if chat_history:
        for msg in chat_history:
            if msg["role"] == "user":
                messages.append(HumanMessage(content=msg["content"]))
            else:
                messages.append(AIMessage(content=msg["content"]))
    messages.append(HumanMessage(content=question))

    agent_trace: list[dict] = []
    tool_call_count = 0

    while tool_call_count < MAX_TOOL_CALLS:
        try:
            response = await model_with_tools.ainvoke(messages)
        except Exception as e:
            if "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e):
                return (
                    LLMAnswer(
                        has_answer=False,
                        answer="I'm currently rate limited. Please wait and try again.",
                    ),
                    agent_trace,
                    [],
                    [],
                )
            raise

        messages.append(response)

        if not getattr(response, "tool_calls", None):
            break

        for tc in _sort_tool_calls(response.tool_calls):
            tool_call_count += 1
            name = tc["name"]
            args = tc.get("args") or {}
            await _append_tool_step(ctx, tier, allowed_names, agent_trace, name, args)
            messages.append(
                ToolMessage(
                    content=agent_trace[-1]["output_summary"],
                    tool_call_id=tc["id"],
                )
            )

            if tool_call_count >= MAX_TOOL_CALLS:
                break

    chunks = _dedupe_chunks(ctx.collected_chunks)
    web_findings = _dedupe_web_findings(ctx.collected_web_sources)

    doc_context = _format_document_context(chunks)
    web_context = _format_web_context(web_findings)
    project_context = ""
    if ctx.project_id is not None:
        from app.services.requirements import format_project_requirements_context
        from app.services.technology_stack import format_project_stack_context

        requirements_context = await format_project_requirements_context(
            ctx.db, ctx.project_id
        )
        stack_context = await format_project_stack_context(ctx.db, ctx.project_id)
        project_context = "\n\n".join(
            part for part in [requirements_context, stack_context] if part
        )

    answer = await _synthesize_answer(
        question=effective_question,
        doc_context=doc_context,
        web_context=web_context,
        chat_history=chat_history,
        agent_trace=public_agent_trace(agent_trace),
        project_context=project_context,
    )

    return answer, public_agent_trace(agent_trace), chunks, web_findings
