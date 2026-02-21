"""Entry point: python -m helperai"""

from __future__ import annotations

import uvicorn

from helperai.config import get_settings


def main() -> None:
    settings = get_settings()
    uvicorn.run(
        "helperai.api.app:create_app",
        factory=True,
        host=settings.host,
        port=settings.port,
        log_level=settings.log_level,
        reload=False,
    )


if __name__ == "__main__":
    main()
