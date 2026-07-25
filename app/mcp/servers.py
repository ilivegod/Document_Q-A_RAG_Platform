from dataclasses import dataclass

from app.config import settings


@dataclass(frozen=True)
class McpServerConfig:
    key: str
    command: str
    args: tuple[str, ...]
    enabled: bool = True


def get_ddg_server() -> McpServerConfig:
    return McpServerConfig(
        key="duckduckgo",
        command=settings.mcp_ddg_command,
        args=tuple(settings.mcp_ddg_args_list),
        enabled=settings.mcp_web_enabled,
    )


def get_wiki_server() -> McpServerConfig:
    return McpServerConfig(
        key="wikipedia",
        command=settings.mcp_wiki_command,
        args=tuple(settings.mcp_wiki_args_list),
        enabled=settings.mcp_web_enabled,
    )


def get_all_servers() -> list[McpServerConfig]:
    return [get_ddg_server(), get_wiki_server()]
