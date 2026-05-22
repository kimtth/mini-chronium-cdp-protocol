# Real Chrome DevTools Protocol With uv

This project contains one realistic browser IPC example: a Python client that talks to a real Chrome or Microsoft Edge process through the Chrome DevTools Protocol (CDP). It does not simulate Mojo or fake browser state.

The client launches or attaches to a browser, creates a page target, navigates it, evaluates JavaScript in the renderer, observes network events, and writes a screenshot captured by the browser.

## Run

```bash
uv sync
uv run python cdp_example.py
```

The default run writes `cdp-screenshot.png`, which is ignored by git.

If Chrome or Edge is not in a standard location:

```bash
uv run python cdp_example.py --browser-executable "C:\\Path\\To\\chrome.exe"
```

To attach to an already-running browser:

```bash
chrome --remote-debugging-port=9222 --user-data-dir=%TEMP%\cdp-profile
curl http://127.0.0.1:9222/json/version
uv run python cdp_example.py --browser-ws-url <webSocketDebuggerUrl from /json/version>
```

## Files

| File | Purpose |
|------|---------|
| [cdp_example.py](cdp_example.py) | Real CDP client. |
| [pyproject.toml](pyproject.toml) | uv project metadata and Python dependencies. |
| [docs/sample.md](docs/sample.md) | Sample commands and output. |
| [docs/mini_cdp.md](docs/mini_cdp.md) | Minimal CDP protocol notes for this project. |

## Requirements

- `uv`
- Python 3.13 or newer, managed by uv
- Chrome or Microsoft Edge

## Why CDP, Not Mojo

True Mojo IPC is Chromium-internal. A real Mojo service needs Chromium's C++ generated bindings, GN/Ninja build integration, platform handle passing, task runners, sandbox-aware process setup, and `.mojom` code generation.

For a standalone tool that controls or inspects a real browser, CDP is the realistic external protocol.

## Resources

- [Chrome DevTools Protocol](https://chromedevtools.github.io/devtools-protocol/)
- [Mojo Documentation](https://chromium.googlesource.com/chromium/src/+/main/mojo/README.md)
