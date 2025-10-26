from __future__ import annotations

import asyncio
import logging

from .bot import run_bot
from .admin import run_admin


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    try:
        async def _runner() -> None:
            await asyncio.gather(run_bot(), run_admin())

        asyncio.run(_runner())
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":  # pragma: no cover
    main()
