from app.mcp.schemas import WebFinding
from app.schemas.query import Source


def _web_findings_to_sources(findings: list[WebFinding]) -> list[Source]:
    return [
        Source(
            source_type="web",
            content=finding.snippet,
            url=finding.url or None,
            title=finding.title,
            provider=finding.provider,
        )
        for finding in findings
    ]


def _build_sources(chunks: list, web_findings: list[WebFinding]) -> list[Source]:
    doc_sources = [
        Source(
            source_type="document",
            chunk_id=str(chunk.id),
            content=chunk.content,
            page=(chunk.page_num or 0) + 1,
            bboxes=chunk.bboxes,
            page_width=chunk.page_width,
            page_height=chunk.page_height,
        )
        for chunk in chunks
    ]
    return doc_sources + _web_findings_to_sources(web_findings)


def test_web_finding_to_source_mapping():
    finding = WebFinding(
        title="Python (programming language)",
        url="https://en.wikipedia.org/wiki/Python_(programming_language)",
        snippet="Python is a high-level programming language.",
        provider="wikipedia",
    )
    sources = _web_findings_to_sources([finding])
    assert len(sources) == 1
    src = sources[0]
    assert src.source_type == "web"
    assert src.title == finding.title
    assert src.url == finding.url
    assert src.provider == "wikipedia"
    assert src.chunk_id is None
    assert src.page is None


def test_mixed_sources_order():
    class FakeChunk:
        id = "chunk-1"
        content = "Doc text"
        page_num = 0
        bboxes = None
        page_width = 100
        page_height = 200

    web = WebFinding(
        title="News",
        url="https://example.com",
        snippet="Web snippet",
        provider="duckduckgo",
    )
    sources = _build_sources([FakeChunk()], [web])
    assert len(sources) == 2
    assert sources[0].source_type == "document"
    assert sources[1].source_type == "web"
    assert sources[1].provider == "duckduckgo"
