"""Reverse proxy for Anthropic API — runs inside Docker container.

Listens on port 8082, injects ANTHROPIC_API_KEY from environment,
and forwards all requests to https://api.anthropic.com.
Streams responses back verbatim (critical for SSE).
"""

import os
import sys

from aiohttp import web, ClientSession, ClientTimeout

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
UPSTREAM = "https://api.anthropic.com"
LISTEN_PORT = int(os.environ.get("PROXY_PORT", "8082"))

# Long timeout for streaming responses
TIMEOUT = ClientTimeout(total=600, connect=30)


async def health(request: web.Request) -> web.Response:
    has_key = bool(ANTHROPIC_API_KEY)
    status = 200 if has_key else 503
    return web.json_response(
        {"status": "ok" if has_key else "no_api_key", "has_key": has_key},
        status=status,
    )


async def proxy(request: web.Request) -> web.StreamResponse:
    """Forward any request to the Anthropic API, injecting auth headers."""
    path = request.path
    upstream_url = f"{UPSTREAM}{path}"

    # Build headers — copy originals, inject/override auth
    headers = dict(request.headers)
    headers.pop("Host", None)
    headers["x-api-key"] = ANTHROPIC_API_KEY
    headers.setdefault("anthropic-version", "2023-06-01")

    body = await request.read()

    session: ClientSession = request.app["client_session"]
    async with session.request(
        method=request.method,
        url=upstream_url,
        headers=headers,
        data=body,
        params=request.query,
        timeout=TIMEOUT,
    ) as upstream_resp:
        # Start streaming response back
        resp = web.StreamResponse(
            status=upstream_resp.status,
            headers={
                k: v
                for k, v in upstream_resp.headers.items()
                if k.lower()
                not in ("transfer-encoding", "content-encoding", "connection")
            },
        )
        await resp.prepare(request)

        async for chunk in upstream_resp.content.iter_any():
            await resp.write(chunk)

        await resp.write_eof()
        return resp


async def on_startup(app: web.Application) -> None:
    app["client_session"] = ClientSession()
    if not ANTHROPIC_API_KEY:
        print("WARNING: ANTHROPIC_API_KEY not set — proxy will return 401s", file=sys.stderr)
    else:
        print(f"Anthropic proxy ready on :{LISTEN_PORT} (key: ...{ANTHROPIC_API_KEY[-4:]})")


async def on_cleanup(app: web.Application) -> None:
    await app["client_session"].close()


def main() -> None:
    app = web.Application()
    app.on_startup.append(on_startup)
    app.on_cleanup.append(on_cleanup)
    app.router.add_get("/health", health)
    # Catch-all proxy route
    app.router.add_route("*", "/{path:.*}", proxy)
    web.run_app(app, host="0.0.0.0", port=LISTEN_PORT)


if __name__ == "__main__":
    main()
