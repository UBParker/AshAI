"""Multi-Provider API Proxy — runs inside Docker container.

Listens on port 8082 (configurable via PROXY_PORT).
Routes requests by URL prefix, injects the correct API key,
and forwards to the appropriate upstream provider.

Route map
---------
/anthropic/{path}   → https://api.anthropic.com/{path}         x-api-key header
/openai/{path}      → https://api.openai.com/v1/{path}         Bearer token
/gemini/{path}      → https://generativelanguage.googleapis.com/{path}  key query-param
/ollama/{path}      → OLLAMA_BASE_URL/{path}                   no auth
/custom/{name}/{path} → CUSTOM_{NAME}_URL/{path}               optional Bearer

Legacy compat (any path not matching above) → Anthropic upstream (same as before)

Health
------
GET /health → JSON with per-provider status
"""

from __future__ import annotations

import logging
import os
import sys
from typing import NamedTuple

from aiohttp import web, ClientSession, ClientTimeout

logging.basicConfig(level=logging.INFO, stream=sys.stdout)
log = logging.getLogger("multi-proxy")

# ── Configuration from environment ──────────────────────────────────────────

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
ANTHROPIC_BASE_URL = os.environ.get("ANTHROPIC_BASE_URL", "https://api.anthropic.com")

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
OPENAI_BASE_URL = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1")

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_BASE_URL = os.environ.get(
    "GEMINI_BASE_URL", "https://generativelanguage.googleapis.com"
)

OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://host.docker.internal:11434")

LISTEN_PORT = int(os.environ.get("PROXY_PORT", "8082"))

# Long timeout for streaming (LLM responses can be slow)
TIMEOUT = ClientTimeout(total=600, connect=30)

# Hop-by-hop headers that must not be forwarded
_HOP_HEADERS = frozenset(
    {
        "connection",
        "keep-alive",
        "proxy-authenticate",
        "proxy-authorization",
        "te",
        "trailers",
        "transfer-encoding",
        "upgrade",
        # Content-encoding stripped so aiohttp doesn't double-decode
        "content-encoding",
    }
)


# ── Provider definitions ─────────────────────────────────────────────────────

class Provider(NamedTuple):
    name: str
    base_url: str
    api_key: str
    auth_style: str  # "x-api-key" | "bearer" | "gemini-query" | "none"
    default_version_header: str = ""  # e.g. anthropic-version


PROVIDERS: dict[str, Provider] = {
    "anthropic": Provider(
        name="anthropic",
        base_url=ANTHROPIC_BASE_URL,
        api_key=ANTHROPIC_API_KEY,
        auth_style="x-api-key",
        default_version_header="2023-06-01",
    ),
    "openai": Provider(
        name="openai",
        base_url=OPENAI_BASE_URL,
        api_key=OPENAI_API_KEY,
        auth_style="bearer",
    ),
    "gemini": Provider(
        name="gemini",
        base_url=GEMINI_BASE_URL,
        api_key=GEMINI_API_KEY,
        auth_style="gemini-query",
    ),
    "ollama": Provider(
        name="ollama",
        base_url=OLLAMA_BASE_URL,
        api_key="",
        auth_style="none",
    ),
}

# Collect custom providers: CUSTOM_FOO_URL → name "foo"
for _env_key, _env_val in os.environ.items():
    if _env_key.startswith("CUSTOM_") and _env_key.endswith("_URL"):
        _pname = _env_key[7:-4].lower()  # strip CUSTOM_ and _URL, lowercase
        _pkey = os.environ.get(f"CUSTOM_{_pname.upper()}_API_KEY", "")
        PROVIDERS[f"custom_{_pname}"] = Provider(
            name=f"custom_{_pname}",
            base_url=_env_val.rstrip("/"),
            api_key=_pkey,
            auth_style="bearer" if _pkey else "none",
        )


# ── Header helpers ───────────────────────────────────────────────────────────

def _build_upstream_headers(
    original: dict[str, str], provider: Provider
) -> dict[str, str]:
    """Strip hop-by-hop and inject provider auth."""
    headers = {
        k: v
        for k, v in original.items()
        if k.lower() not in _HOP_HEADERS and k.lower() != "host"
    }

    if provider.auth_style == "x-api-key":
        headers.pop("authorization", None)
        headers["x-api-key"] = provider.api_key
        if provider.default_version_header:
            headers.setdefault("anthropic-version", provider.default_version_header)

    elif provider.auth_style == "bearer":
        if provider.api_key:
            headers["authorization"] = f"Bearer {provider.api_key}"

    # gemini-query auth is handled via URL params, not headers
    # "none" style: forward headers as-is

    return headers


def _build_upstream_params(
    original_query: dict[str, str], provider: Provider
) -> dict[str, str]:
    """Add auth query params for Gemini-style auth."""
    params = dict(original_query)
    if provider.auth_style == "gemini-query" and provider.api_key:
        params["key"] = provider.api_key
    return params


# ── Streaming proxy core ─────────────────────────────────────────────────────

async def _proxy(
    request: web.Request,
    provider: Provider,
    upstream_path: str,
) -> web.StreamResponse:
    upstream_url = f"{provider.base_url.rstrip('/')}/{upstream_path.lstrip('/')}"

    headers = _build_upstream_headers(dict(request.headers), provider)
    params = _build_upstream_params(dict(request.rel_url.query), provider)
    body = await request.read()

    session: ClientSession = request.app["session"]

    async with session.request(
        method=request.method,
        url=upstream_url,
        headers=headers,
        params=params,
        data=body,
        timeout=TIMEOUT,
        allow_redirects=True,
    ) as up:
        resp = web.StreamResponse(
            status=up.status,
            headers={
                k: v
                for k, v in up.headers.items()
                if k.lower() not in _HOP_HEADERS
            },
        )
        await resp.prepare(request)
        async for chunk in up.content.iter_any():
            await resp.write(chunk)
        await resp.write_eof()
        return resp


# ── Route handlers ───────────────────────────────────────────────────────────

async def handle_anthropic(request: web.Request) -> web.StreamResponse:
    path = request.match_info.get("path", "")
    return await _proxy(request, PROVIDERS["anthropic"], path)


async def handle_openai(request: web.Request) -> web.StreamResponse:
    path = request.match_info.get("path", "")
    return await _proxy(request, PROVIDERS["openai"], path)


async def handle_gemini(request: web.Request) -> web.StreamResponse:
    path = request.match_info.get("path", "")
    return await _proxy(request, PROVIDERS["gemini"], path)


async def handle_ollama(request: web.Request) -> web.StreamResponse:
    path = request.match_info.get("path", "")
    return await _proxy(request, PROVIDERS["ollama"], path)


async def handle_custom(request: web.Request) -> web.StreamResponse:
    name = request.match_info.get("name", "")
    path = request.match_info.get("path", "")
    provider_key = f"custom_{name}"
    if provider_key not in PROVIDERS:
        raise web.HTTPNotFound(reason=f"Unknown custom provider: {name}")
    return await _proxy(request, PROVIDERS[provider_key], path)


async def handle_legacy(request: web.Request) -> web.StreamResponse:
    """Backwards-compat: anything not matching a prefix → Anthropic."""
    path = request.match_info.get("path", "")
    return await _proxy(request, PROVIDERS["anthropic"], path)


async def handle_health(request: web.Request) -> web.Response:
    statuses = {}
    for name, provider in PROVIDERS.items():
        if provider.auth_style == "none":
            statuses[name] = {"configured": True, "url": provider.base_url}
        else:
            has_key = bool(provider.api_key)
            statuses[name] = {
                "configured": has_key,
                "url": provider.base_url,
                "key_hint": f"...{provider.api_key[-4:]}" if has_key else None,
            }

    overall = "ok" if any(v["configured"] for v in statuses.values()) else "no_providers"
    return web.json_response({"status": overall, "providers": statuses})


# ── App lifecycle ─────────────────────────────────────────────────────────────

async def on_startup(app: web.Application) -> None:
    app["session"] = ClientSession()
    configured = [
        name for name, p in PROVIDERS.items()
        if p.auth_style == "none" or bool(p.api_key)
    ]
    log.info("Multi-provider proxy starting on :%d", LISTEN_PORT)
    log.info("Configured providers: %s", ", ".join(configured) or "(none)")
    if not configured:
        log.warning("No API keys set — all non-Ollama providers will return 401s")


async def on_cleanup(app: web.Application) -> None:
    await app["session"].close()


def main() -> None:
    app = web.Application()
    app.on_startup.append(on_startup)
    app.on_cleanup.append(on_cleanup)

    # Health
    app.router.add_get("/health", handle_health)

    # Provider-prefixed routes (most specific first)
    app.router.add_route("*", "/anthropic/{path:.*}", handle_anthropic)
    app.router.add_route("*", "/openai/{path:.*}", handle_openai)
    app.router.add_route("*", "/gemini/{path:.*}", handle_gemini)
    app.router.add_route("*", "/ollama/{path:.*}", handle_ollama)
    app.router.add_route("*", "/custom/{name}/{path:.*}", handle_custom)

    # Legacy catch-all (keeps existing clients working against port 8082)
    app.router.add_route("*", "/{path:.*}", handle_legacy)

    web.run_app(app, host="0.0.0.0", port=LISTEN_PORT)


if __name__ == "__main__":
    main()
