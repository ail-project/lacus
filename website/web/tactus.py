#!/usr/bin/env python3

from __future__ import annotations

import asyncio
import html
from functools import lru_cache
from pathlib import Path

from aiohttp import ClientSession, ClientTimeout, UnixConnector, WSMsgType, web
from aiohttp.client_exceptions import ClientConnectionResetError, ClientError, UnixClientConnectorError
from multidict import CIMultiDictProxy

from lacus.default import get_config, get_homedir
from lacus.lacus import Lacus
from lacuscore.helpers import SessionMetadata, SessionStatus


ASSET_DIR = Path(__file__).resolve().parent / 'tactus_assets'
STATIC_ASSET_DIR = ASSET_DIR / 'static'
WRAPPER_TEMPLATE_PATH = ASSET_DIR / 'wrapper.html'
STATIC_URL_PREFIX = '/interactive/assets'

HOP_BY_HOP_HEADERS = {
    'connection',
    'keep-alive',
    'proxy-authenticate',
    'proxy-authorization',
    'te',
    'trailer',
    'transfer-encoding',
    'upgrade',
}


"""Sidecar proxy for interactive xpra sessions.

This process is intentionally separate from the main Flask API application so
that Lacus remains a control-plane service. It proxies HTTP and WebSocket
traffic from a stable public route to the per-session xpra unix sockets managed
by LacusCore.
"""


# Questionable methods

def _filter_request_headers(headers: CIMultiDictProxy[str]) -> dict[str, str]:
    return {
        key: value for key, value in headers.items()
        if key.lower() not in HOP_BY_HOP_HEADERS and key.lower() != 'host'
    }


def _filter_response_headers(headers: CIMultiDictProxy[str]) -> dict[str, str]:
    return {
        key: value for key, value in headers.items()
        if key.lower() not in HOP_BY_HOP_HEADERS and key.lower() != 'content-length'
    }


# End of questionable methods

def _get_session_metadata(capture_uuid: str, lacus: Lacus) -> SessionMetadata | None:
    return lacus.core.get_session_metadata(capture_uuid)


def _get_upstream_target(request: web.Request) -> str:
    lacus: Lacus = request.app['lacus']
    capture_uuid = request.match_info['capture_uuid']
    session_metadata = _get_session_metadata(capture_uuid, lacus)
    if not session_metadata:
        raise web.HTTPNotFound(text=f'No interactive session metadata for capture UUID {capture_uuid}.')

    status_int = int(session_metadata.get('status', int(SessionStatus.UNKNOWN)))
    if session_metadata.get('request_finish') or status_int in (
        int(SessionStatus.STOPPED),
        int(SessionStatus.EXPIRED),
        int(SessionStatus.ERROR),
    ):
        raise web.HTTPNotFound(text='Interactive session view is no longer available.')

    metadata = lacus.core.get_session_backend_metadata(capture_uuid)
    if not metadata:
        raise web.HTTPNotFound(text=f'No interactive session metadata for capture UUID {capture_uuid}.')

    socket_path = metadata.get('socket_path')
    if not socket_path:
        raise web.HTTPNotFound(text=f'No upstream socket path available for capture UUID {capture_uuid}.')

    if not Path(socket_path).exists():
        raise web.HTTPNotFound(text=f'Interactive session transport is unavailable for capture UUID {capture_uuid}.')

    return socket_path


async def _proxy_api_request(request: web.Request, upstream_path: str) -> web.Response:
    timeout = ClientTimeout(total=30)
    payload = await request.read()
    ip = get_config('generic', 'website_listen_ip')
    port = get_config('generic', 'website_listen_port')
    upstream_url = f'http://{ip}:{port}{upstream_path}'

    try:
        async with ClientSession(timeout=timeout) as session:
            async with session.request(
                request.method,
                upstream_url,
                headers=_filter_request_headers(request.headers),
                data=payload if payload else None,
                allow_redirects=False,
            ) as upstream:
                body = await upstream.read()
                response_headers = _filter_response_headers(upstream.headers)
                return web.Response(
                    body=body,
                    status=upstream.status,
                    reason=upstream.reason,
                    headers=response_headers,
                )
    except (asyncio.TimeoutError, TimeoutError):
        raise web.HTTPGatewayTimeout(text='Interactive control-plane request timed out.')
    except ClientError:
        raise web.HTTPBadGateway(text='Interactive control-plane request failed.')


# NOTE: localhost is hardcoded there.
def _build_upstream_url(request: web.Request) -> str:
    tail = request.match_info.get('tail', '')
    path = f'/{tail}' if tail else '/'
    if request.query_string:
        path = f'{path}?{request.query_string}'
    return f'http://localhost{path}'


async def _proxy_http(request: web.Request) -> web.StreamResponse:
    socket_path = _get_upstream_target(request)
    upstream_url = _build_upstream_url(request)
    payload = await request.read()

    connector = UnixConnector(path=socket_path)
    timeout = ClientTimeout(total=300)
    response: web.StreamResponse | None = None
    async with ClientSession(connector=connector, timeout=timeout, auto_decompress=False) as session:
        try:
            async with session.request(
                request.method,
                upstream_url,
                headers=_filter_request_headers(request.headers),
                data=payload if payload else None,
                allow_redirects=False,
            ) as upstream:
                response = web.StreamResponse(
                    status=upstream.status,
                    reason=upstream.reason,
                    headers=_filter_response_headers(upstream.headers),
                )
                await response.prepare(request)
                async for chunk in upstream.content.iter_chunked(64 * 1024):
                    if request.transport is None or request.transport.is_closing():
                        return response
                    await response.write(chunk)
                if request.transport is not None and not request.transport.is_closing():
                    await response.write_eof()
                return response
        except (ClientConnectionResetError, ConnectionResetError):
            # The browser side may disconnect while we are still streaming XPRA assets.
            return response if response is not None else web.Response(status=204)
        except UnixClientConnectorError:
            raise web.HTTPNotFound(text='Interactive session transport is unavailable.')


async def _proxy_websocket(request: web.Request) -> web.WebSocketResponse:
    socket_path = _get_upstream_target(request)
    upstream_url = _build_upstream_url(request)

    client_ws = web.WebSocketResponse(heartbeat=30.0)
    await client_ws.prepare(request)

    connector = UnixConnector(path=socket_path)
    timeout = ClientTimeout(total=300)
    async with ClientSession(connector=connector, timeout=timeout) as session:
        try:
            async with session.ws_connect(upstream_url, headers=_filter_request_headers(request.headers), heartbeat=30.0) as upstream_ws:
                async def client_to_upstream() -> None:
                    try:
                        async for msg in client_ws:
                            if msg.type == WSMsgType.TEXT:
                                await upstream_ws.send_str(msg.data)
                            elif msg.type == WSMsgType.BINARY:
                                await upstream_ws.send_bytes(msg.data)
                            elif msg.type == WSMsgType.PING:
                                await upstream_ws.ping()
                            elif msg.type == WSMsgType.PONG:
                                await upstream_ws.pong()
                            elif msg.type in (WSMsgType.CLOSE, WSMsgType.CLOSING, WSMsgType.CLOSED, WSMsgType.ERROR):
                                break
                    except (ClientConnectionResetError, ConnectionResetError):
                        return

                async def upstream_to_client() -> None:
                    try:
                        async for msg in upstream_ws:
                            if client_ws.closed:
                                break
                            if msg.type == WSMsgType.TEXT:
                                await client_ws.send_str(msg.data)
                            elif msg.type == WSMsgType.BINARY:
                                await client_ws.send_bytes(msg.data)
                            elif msg.type == WSMsgType.PING:
                                await client_ws.ping()
                            elif msg.type == WSMsgType.PONG:
                                await client_ws.pong()
                            elif msg.type in (WSMsgType.CLOSE, WSMsgType.CLOSING, WSMsgType.CLOSED, WSMsgType.ERROR):
                                break
                    except (ClientConnectionResetError, ConnectionResetError):
                        # Finishing the capture intentionally tears down the iframe websocket.
                        return

                client_task = asyncio.create_task(client_to_upstream())
                upstream_task = asyncio.create_task(upstream_to_client())
                done, pending = await asyncio.wait(
                    {client_task, upstream_task},
                    return_when=asyncio.FIRST_COMPLETED,
                )

                for task in pending:
                    task.cancel()
                await asyncio.gather(*pending, return_exceptions=True)
                await asyncio.gather(*done, return_exceptions=True)
        except (ClientConnectionResetError, ConnectionResetError):
            return client_ws
        except UnixClientConnectorError:
            await client_ws.close(message=b'Interactive session transport is unavailable.')
            return client_ws
        finally:
            if not client_ws.closed:
                await client_ws.close()

    return client_ws


async def interactive_view_redirect(request: web.Request) -> web.Response:
    capture_uuid = request.match_info['capture_uuid']
    raise web.HTTPFound(f'/interactive/{capture_uuid}/view/')


async def interactive_view_metadata(request: web.Request) -> web.Response:
    capture_uuid = request.match_info['capture_uuid']
    return await _proxy_api_request(request, f'/interactive/{capture_uuid}')


async def interactive_view_finish(request: web.Request) -> web.Response:
    capture_uuid = request.match_info['capture_uuid']
    return await _proxy_api_request(request, f'/interactive/{capture_uuid}/finish')


def _render_wrapper_html(capture_uuid: str) -> str:
    # The wrapper uses view-local convenience routes that proxy to the canonical API.
    finish_url = f'/interactive/{capture_uuid}/view/finish'
    metadata_url = f'/interactive/{capture_uuid}/view/metadata'
    session_url = f'/interactive/{capture_uuid}/view/session/'
    template = _load_wrapper_template()
    replacements = {
        '__CAPTURE_UUID__': html.escape(capture_uuid, quote=True),
        '__SESSION_URL__': html.escape(session_url, quote=True),
        '__METADATA_URL__': html.escape(metadata_url, quote=True),
        '__FINISH_URL__': html.escape(finish_url, quote=True),
        '__ASSET_BASE__': STATIC_URL_PREFIX,
    }
    for placeholder, value in replacements.items():
        template = template.replace(placeholder, value)
    return template


@lru_cache(maxsize=1)
def _load_wrapper_template() -> str:
    return WRAPPER_TEMPLATE_PATH.read_text(encoding='utf-8')


async def interactive_view_wrapper(request: web.Request) -> web.Response:
    capture_uuid = request.match_info['capture_uuid']
    lacus: Lacus = request.app['lacus']
    metadata = _get_session_metadata(capture_uuid, lacus)
    if not metadata:
        raise web.HTTPNotFound(text=f'No interactive session metadata for capture UUID {capture_uuid}.')

    return web.Response(text=_render_wrapper_html(capture_uuid), content_type='text/html')


async def interactive_view_proxy(request: web.Request) -> web.StreamResponse:
    """Proxy the public interactive view route to the per-session xpra socket."""
    connection = request.headers.get('Connection', '')
    upgrade = request.headers.get('Upgrade', '')
    if 'upgrade' in connection.lower() and upgrade.lower() == 'websocket':
        return await _proxy_websocket(request)
    return await _proxy_http(request)


def make_app() -> web.Application:
    get_homedir()
    app = web.Application()
    app['lacus'] = Lacus()
    app.router.add_static(f'{STATIC_URL_PREFIX}/', STATIC_ASSET_DIR)
    app.router.add_get('/interactive/{capture_uuid}/view', interactive_view_redirect)
    app.router.add_get('/interactive/{capture_uuid}/view/', interactive_view_wrapper)
    app.router.add_get('/interactive/{capture_uuid}/view/metadata', interactive_view_metadata)
    app.router.add_post('/interactive/{capture_uuid}/view/finish', interactive_view_finish)
    app.router.add_route('*', '/interactive/{capture_uuid}/view/session/{tail:.*}', interactive_view_proxy)
    return app
