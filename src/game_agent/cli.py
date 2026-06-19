from __future__ import annotations

import json

import typer
from rich.console import Console

from .agent import user_chat
from .memory import memory_manage
from .tools import tool_invoke


cli = typer.Typer(help="AI游玩决策助手")
console = Console()


@cli.command()
def chat(query: str, user_id: str = "demo_user") -> None:
    """Run one chat request."""
    response = user_chat(query, user_id=user_id)
    console.print(response.answer)
    console.print(f"[dim]trace_id={response.trace_id}[/dim]")


@cli.command()
def shell(user_id: str = "demo_user") -> None:
    """Start an interactive console chat."""
    console.print("[bold]AI游玩决策助手[/bold] 输入 exit 退出")
    while True:
        query = console.input("[cyan]你 > [/cyan]").strip()
        if query.lower() in {"exit", "quit"}:
            break
        if not query:
            continue
        response = user_chat(query, user_id=user_id)
        console.print(f"[green]助手 > [/green]{response.answer}")
        console.print(f"[dim]trace_id={response.trace_id}[/dim]")


@cli.command()
def memory(user_id: str, operate_type: str, content: str = "") -> None:
    """Call memory_manage."""
    ok, related = memory_manage(user_id=user_id, content=content, operate_type=operate_type)
    console.print({"operate_result": ok, "related_memory": related})


@cli.command()
def tool(tool_name: str, params_json: str = "{}") -> None:
    """Call tool_invoke with JSON params."""
    console.print(tool_invoke(tool_name, json.loads(params_json)))


if __name__ == "__main__":
    cli()
