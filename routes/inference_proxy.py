"""Inference proxy routes — /inference/v1/models, /inference/v1/chat/completions, /inference/v1/completions.

Mounts only when INFERENCE_SERVER_MODE=server. Forwards requests to a local
Ollama instance (or any OpenAI-compatible backend) without exposing its port
directly. Callers must present a Bearer token matching INFERENCE_SERVER_KEY.
"""

import logging
import os
import secrets

import httpx
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

logger = logging.getLogger(__name__)

INFERENCE_SERVER_KEY = os.getenv("INFERENCE_SERVER_KEY", "")
INFERENCE_OLLAMA_HOST = os.getenv("INFERENCE_OLLAMA_HOST", "localhost")
INFERENCE_OLLAMA_PORT = int(os.getenv("INFERENCE_OLLAMA_PORT", "11434"))

_PROXIED_PATHS = {
    "/inference/v1/models",
    "/inference/v1/chat/completions",
    "/inference/v1/completions",
}

_OLLAMA_BASE = f"http://{INFERENCE_OLLAMA_HOST}:{INFERENCE_OLLAMA_PORT}"

# Hop-by-hop headers must not be forwarded to upstream or back to the client.
_HOP_BY_HOP = frozenset([
    "connection", "keep-alive", "proxy-authenticate", "proxy-authorization",
    "te", "trailers", "transfer-encoding", "upgrade",
])


def _check_bearer(request: Request) -> None:
    if not INFERENCE_SERVER_KEY:
        raise HTTPException(500, "INFERENCE_SERVER_KEY not configured on this server")
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(401, "Missing Bearer token")
    provided = auth[len("Bearer "):]
    if not secrets.compare_digest(provided.encode(), INFERENCE_SERVER_KEY.encode()):
        raise HTTPException(401, "Invalid Bearer token")


def _upstream_url(request: Request) -> str:
    # /inference/v1/... -> /v1/...
    path = request.url.path.removeprefix("/inference")
    qs = request.url.query
    return f"{_OLLAMA_BASE}{path}{'?' + qs if qs else ''}"


def setup_inference_proxy_routes() -> APIRouter:
    router = APIRouter(tags=["inference-proxy"])

    @router.api_route(
        "/inference/v1/{path:path}",
        methods=["GET", "POST", "DELETE", "OPTIONS"],
    )
    async def proxy_inference(request: Request, path: str):
        _check_bearer(request)

        method = request.method
        upstream = _upstream_url(request)
        body = await request.body()

        # Forward a filtered subset of request headers.
        fwd_headers = {
            k: v for k, v in request.headers.items()
            if k.lower() not in _HOP_BY_HOP and k.lower() != "host"
        }

        is_stream = b'"stream":true' in body or b'"stream": true' in body

        if is_stream:
            async def _stream():
                try:
                    async with httpx.AsyncClient(timeout=120) as sc:
                        async with sc.stream(method, upstream, headers=fwd_headers, content=body) as r:
                            async for chunk in r.aiter_bytes():
                                yield chunk
                except httpx.ConnectError:
                    logger.error("Cannot reach Ollama at %s", _OLLAMA_BASE)

            return StreamingResponse(
                _stream(),
                status_code=200,
                media_type="text/event-stream",
            )

        async with httpx.AsyncClient(timeout=120) as client:
            try:
                upstream_resp = await client.request(
                    method,
                    upstream,
                    headers=fwd_headers,
                    content=body,
                )
            except httpx.ConnectError:
                logger.error("Cannot reach Ollama at %s", _OLLAMA_BASE)
                raise HTTPException(502, f"Cannot reach local inference backend at {_OLLAMA_BASE}")
            except httpx.TimeoutException:
                raise HTTPException(504, "Inference backend timed out")

        resp_headers = {
            k: v for k, v in upstream_resp.headers.items()
            if k.lower() not in _HOP_BY_HOP
        }
        return StreamingResponse(
            iter([upstream_resp.content]),
            status_code=upstream_resp.status_code,
            headers=resp_headers,
            media_type=upstream_resp.headers.get("content-type", "application/json"),
        )

    return router
