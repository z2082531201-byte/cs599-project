from __future__ import annotations

import typer
import uvicorn


def main(host: str = "127.0.0.1", port: int = 8765) -> None:
    uvicorn.run("src.game_agent.api:app", host=host, port=port, reload=False)


if __name__ == "__main__":
    typer.run(main)
