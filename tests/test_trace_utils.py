from app.agent.trace_utils import public_agent_trace, resolve_follow_up_question


def test_resolve_follow_up_yes():
    history = [
        {"role": "user", "content": "What are the payment terms in the contract?"},
        {"role": "assistant", "content": "Should I search the documents for that?"},
    ]
    assert (
        resolve_follow_up_question("yes", history)
        == "What are the payment terms in the contract?"
    )


def test_public_agent_trace_strips_internal_fields():
    trace = [{"tool": "search_documents", "output_summary": "ok", "_full_output": "secret"}]
    public = public_agent_trace(trace)
    assert public[0] == {"tool": "search_documents", "output_summary": "ok"}
