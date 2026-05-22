"""
Real Chrome DevTools Protocol client for uv.

This script talks to an actual Chrome/Edge process over CDP. It creates a real
page target, navigates it, evaluates JavaScript in the renderer, observes
network events, and writes a screenshot captured by the browser.
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import contextlib
import json
import os
import shutil
import socket
import subprocess
import tempfile
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

import websockets


DEFAULT_HTML = """<!doctype html>
<html>
  <head>
    <meta charset="utf-8">
    <title>Real CDP Target</title>
    <style>
      body { font-family: system-ui, sans-serif; margin: 40px; }
      main { max-width: 720px; }
      code { background: #f1f5f9; padding: 2px 5px; border-radius: 4px; }
    </style>
  </head>
  <body>
    <main>
      <h1>Chrome DevTools Protocol</h1>
      <p>This page was loaded in a real browser target and inspected over <code>CDP</code>.</p>
    </main>
  </body>
</html>"""


class CDPError(RuntimeError):
    pass


class CDPClient:
    def __init__(self, websocket_url: str):
        self.websocket_url = websocket_url
        self.websocket: Any = None
        self.next_id = 1
        self.pending: dict[int, asyncio.Future[dict[str, Any]]] = {}
        self.event_waiters: list[
            tuple[str, Callable[[dict[str, Any]], bool], asyncio.Future[dict[str, Any]]]
        ] = []
        self.event_handlers: dict[str, list[Callable[[dict[str, Any]], None]]] = {}
        self.reader_task: asyncio.Task[None] | None = None

    async def connect(self) -> None:
        self.websocket = await websockets.connect(self.websocket_url)
        self.reader_task = asyncio.create_task(self._read_loop())

    async def send(
        self,
        method: str,
        params: dict[str, Any] | None = None,
        session_id: str | None = None,
    ) -> dict[str, Any]:
        if self.websocket is None:
            raise CDPError("CDP socket is not connected")

        request_id = self.next_id
        self.next_id += 1
        message: dict[str, Any] = {"id": request_id, "method": method, "params": params or {}}
        if session_id:
            message["sessionId"] = session_id

        future: asyncio.Future[dict[str, Any]] = asyncio.get_running_loop().create_future()
        self.pending[request_id] = future
        await self.websocket.send(json.dumps(message))
        return await future

    def on(self, method: str, handler: Callable[[dict[str, Any]], None]) -> None:
        self.event_handlers.setdefault(method, []).append(handler)

    async def wait_for_event(
        self,
        method: str,
        predicate: Callable[[dict[str, Any]], bool],
        timeout: float,
    ) -> dict[str, Any]:
        future: asyncio.Future[dict[str, Any]] = asyncio.get_running_loop().create_future()
        self.event_waiters.append((method, predicate, future))
        try:
            return await asyncio.wait_for(future, timeout)
        finally:
            self.event_waiters = [waiter for waiter in self.event_waiters if waiter[2] is not future]

    async def close(self) -> None:
        if self.websocket:
            await self.websocket.close()
        if self.reader_task:
            with contextlib.suppress(asyncio.CancelledError):
                await self.reader_task

    async def _read_loop(self) -> None:
        try:
            async for raw_message in self.websocket:
                message = json.loads(raw_message)
                request_id = message.get("id")
                if request_id is not None:
                    self._resolve_response(request_id, message)
                    continue
                self._dispatch_event(message)
        except Exception as exc:  # propagate socket failure to pending CDP calls
            for future in self.pending.values():
                if not future.done():
                    future.set_exception(exc)
            self.pending.clear()

    def _resolve_response(self, request_id: int, message: dict[str, Any]) -> None:
        future = self.pending.pop(request_id, None)
        if future is None or future.done():
            return

        if "error" in message:
            error = message["error"]
            future.set_exception(CDPError(f"{error['code']}: {error['message']}"))
            return

        future.set_result(message.get("result", {}))

    def _dispatch_event(self, message: dict[str, Any]) -> None:
        method = message.get("method")
        for handler in self.event_handlers.get(method, []):
            handler(message)

        for waiter_method, predicate, future in list(self.event_waiters):
            if future.done() or waiter_method != method or not predicate(message):
                continue
            future.set_result(message)


@dataclass
class BrowserConnection:
    client: CDPClient
    product: str
    process: subprocess.Popen[bytes] | None = None
    user_data_dir: Path | None = None

    async def close(self) -> None:
        await self.client.close()
        if self.process:
            await stop_process(self.process)
        if self.user_data_dir:
            await remove_dir(self.user_data_dir)


async def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    browser = await connect_browser(args)

    try:
        client = browser.client
        target = await client.send("Target.createTarget", {"url": "about:blank"})
        attached = await client.send(
            "Target.attachToTarget",
            {"targetId": target["targetId"], "flatten": True},
        )
        session_id = attached["sessionId"]

        network_requests: list[str] = []
        client.on(
            "Network.requestWillBeSent",
            lambda event: network_requests.append(event["params"]["request"]["url"])
            if event.get("sessionId") == session_id
            else None,
        )

        await client.send("Runtime.enable", session_id=session_id)
        await client.send("Page.enable", session_id=session_id)
        await client.send("Network.enable", session_id=session_id)
        await navigate_and_wait(client, session_id, args.url)

        title = await client.send(
            "Runtime.evaluate",
            {"expression": "document.title", "returnByValue": True},
            session_id=session_id,
        )
        location = await client.send(
            "Runtime.evaluate",
            {"expression": "location.href", "returnByValue": True},
            session_id=session_id,
        )
        screenshot = await client.send(
            "Page.captureScreenshot",
            {"format": "png", "captureBeyondViewport": False},
            session_id=session_id,
        )

        screenshot_path = Path(args.screenshot).resolve()
        screenshot_path.write_bytes(base64.b64decode(screenshot["data"]))

        print(f"Connected to real browser: {browser.product}")
        print(f"Created target: {target['targetId']}")
        print(f"Page title: {title['result']['value']}")
        print(f"Page URL: {location['result']['value']}")
        print(f"Observed network requests: {len(network_requests)}")
        print(f"Screenshot: {screenshot_path}")

        await client.send("Target.closeTarget", {"targetId": target["targetId"]})
    finally:
        await browser.close()


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    default_url = "data:text/html;charset=utf-8," + urllib.parse.quote(DEFAULT_HTML)
    parser = argparse.ArgumentParser(description="Run a real Chrome/Edge CDP workflow.")
    parser.add_argument("--headed", action="store_true", help="Run browser with a visible window")
    parser.add_argument("--url", default=default_url, help="Navigate to this URL")
    parser.add_argument("--screenshot", default="cdp-screenshot.png", help="Write a PNG screenshot")
    parser.add_argument("--browser-executable", help="Chrome/Edge executable to launch")
    parser.add_argument("--browser-ws-url", help="Attach to an existing browser WebSocket")
    return parser.parse_args(argv)


async def connect_browser(args: argparse.Namespace) -> BrowserConnection:
    browser_ws_url = args.browser_ws_url or os.getenv("CDP_BROWSER_WS_URL")
    if browser_ws_url:
        client = CDPClient(browser_ws_url)
        await client.connect()
        return BrowserConnection(client=client, product="existing browser")

    port = get_free_port()
    user_data_dir = Path(tempfile.mkdtemp(prefix="real-cdp-"))
    executable = args.browser_executable or find_browser_executable()
    launch_args = [
        executable,
        f"--remote-debugging-port={port}",
        f"--user-data-dir={user_data_dir}",
        "--no-first-run",
        "--no-default-browser-check",
        "--disable-background-networking",
        "about:blank",
    ]

    if not args.headed:
        launch_args.extend(["--headless=new", "--disable-gpu"])

    process = subprocess.Popen(launch_args, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    version = await wait_for_browser_version(port, process)

    client = CDPClient(version["webSocketDebuggerUrl"])
    await client.connect()
    return BrowserConnection(
        client=client,
        product=version["Browser"],
        process=process,
        user_data_dir=user_data_dir,
    )


async def navigate_and_wait(client: CDPClient, session_id: str, url: str) -> None:
    lifecycle_task = asyncio.create_task(
        client.wait_for_event(
            "Page.lifecycleEvent",
            lambda event: event.get("sessionId") == session_id
            and event["params"]["name"] == "networkIdle",
            timeout=10,
        )
    )
    await client.send("Page.setLifecycleEventsEnabled", {"enabled": True}, session_id=session_id)
    await client.send("Page.navigate", {"url": url}, session_id=session_id)

    with contextlib.suppress(asyncio.TimeoutError):
        await lifecycle_task


async def wait_for_browser_version(
    port: int,
    process: subprocess.Popen[bytes],
    timeout: float = 10,
) -> dict[str, Any]:
    deadline = asyncio.get_running_loop().time() + timeout
    url = f"http://127.0.0.1:{port}/json/version"

    while True:
        if process.poll() is not None:
            stderr = process.stderr.read().decode(errors="replace") if process.stderr else ""
            raise CDPError(f"Browser exited early. {stderr.strip()}")

        try:
            with urllib.request.urlopen(url, timeout=1) as response:
                return json.loads(response.read().decode("utf-8"))
        except OSError:
            if asyncio.get_running_loop().time() >= deadline:
                raise CDPError(f"Timed out waiting for {url}") from None
            await asyncio.sleep(0.1)


def find_browser_executable() -> str:
    explicit = [os.getenv("CHROME_PATH"), os.getenv("EDGE_PATH")]
    windows_candidates = [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    ]
    mac_candidates = [
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
        "/Applications/Chromium.app/Contents/MacOS/Chromium",
    ]

    for candidate in [*explicit, *windows_candidates, *mac_candidates]:
        if candidate and Path(candidate).exists():
            return candidate

    if os.name != "nt":
        return "google-chrome"

    raise CDPError(
        "Could not find Chrome or Edge. Pass --browser-executable, set CHROME_PATH/EDGE_PATH, "
        "or attach with --browser-ws-url."
    )


def get_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


async def stop_process(process: subprocess.Popen[bytes]) -> None:
    if process.poll() is not None:
        return

    process.terminate()
    try:
        await asyncio.wait_for(asyncio.to_thread(process.wait), timeout=3)
    except asyncio.TimeoutError:
        process.kill()
        await asyncio.to_thread(process.wait)


async def remove_dir(directory: Path) -> None:
    for attempt in range(5):
        try:
            await asyncio.to_thread(shutil.rmtree, directory, ignore_errors=False)
            return
        except OSError as exc:
            if attempt == 4:
                print(f"Warning: could not remove temporary browser profile {directory}: {exc}")
                return
            await asyncio.sleep(0.2)


def cli() -> None:
    asyncio.run(main())


if __name__ == "__main__":
    cli()
