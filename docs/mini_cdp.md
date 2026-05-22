# mini_cdp

This is a compact protocol note for the subset of Chrome DevTools Protocol (CDP) used by this project. It follows the official CDP model: browser discovery over HTTP, then JSON command and event messages over WebSocket.

## Transport

Start Chrome or Edge with a remote debugging port:

```bash
chrome --remote-debugging-port=9222 --user-data-dir=%TEMP%\cdp-profile
```

Discovery endpoints are served on the same port:

| Endpoint | Purpose |
|----------|---------|
| `GET /json/version` | Browser metadata and the browser-level `webSocketDebuggerUrl`. |
| `GET /json` or `GET /json/list` | Page targets and their WebSocket URLs. |
| `GET /json/protocol` | The protocol schema supported by that browser build. |

This project connects to the browser-level WebSocket from `/json/version`, then creates and attaches to a page target through the `Target` domain.

## Message Envelope

Commands are JSON objects with an integer `id`, a domain-qualified `method`, and optional `params`.

```json
{
	"id": 1,
	"method": "Target.createTarget",
	"params": {
		"url": "about:blank"
	}
}
```

Responses reuse the same `id` and contain either `result` or `error`.

```json
{
	"id": 1,
	"result": {
		"targetId": "E1EB6C6E0EDC51EF2ED9ABA291A42BBF"
	}
}
```

```json
{
	"id": 1,
	"error": {
		"code": -32602,
		"message": "Invalid parameters"
	}
}
```

Events do not have an `id`. They contain a `method` and optional `params`.

```json
{
	"method": "Network.requestWillBeSent",
	"params": {
		"requestId": "1234.1",
		"request": {
			"url": "data:text/html;charset=utf-8,..."
		}
	}
}
```

When using flattened target sessions, commands and events include a `sessionId` so traffic can be routed to the attached page target.

```json
{
	"id": 4,
	"sessionId": "A1B2C3",
	"method": "Runtime.evaluate",
	"params": {
		"expression": "document.title",
		"returnByValue": true
	}
}
```

## Minimal Domains

The current app uses a small domain subset:

| Domain | Commands or events used | Role |
|--------|-------------------------|------|
| `Target` | `createTarget`, `attachToTarget`, `closeTarget` | Create a page target and attach a session. |
| `Runtime` | `enable`, `evaluate` | Evaluate JavaScript in the renderer. |
| `Page` | `enable`, `navigate`, `setLifecycleEventsEnabled`, `captureScreenshot`, `lifecycleEvent` | Navigate and capture browser-rendered output. |
| `Network` | `enable`, `requestWillBeSent` | Observe real network activity. |

## Command Flow

The project's default run follows this sequence:

```text
HTTP GET /json/version
WebSocket connect to webSocketDebuggerUrl
Target.createTarget({ url: "about:blank" })
Target.attachToTarget({ targetId, flatten: true })
Runtime.enable(sessionId)
Page.enable(sessionId)
Network.enable(sessionId)
Page.setLifecycleEventsEnabled({ enabled: true }, sessionId)
Page.navigate({ url }, sessionId)
Runtime.evaluate({ expression: "document.title", returnByValue: true }, sessionId)
Runtime.evaluate({ expression: "location.href", returnByValue: true }, sessionId)
Page.captureScreenshot({ format: "png" }, sessionId)
Target.closeTarget({ targetId })
```

## Mini Client Responsibilities

A minimal CDP client needs only a few moving parts:

1. Maintain a monotonically increasing command `id`.
2. Store pending command futures by `id`.
3. Decode incoming JSON messages.
4. Resolve responses by matching `id`.
5. Dispatch events by `method`.
6. Include `sessionId` for page-target commands after `Target.attachToTarget`.
7. Treat CDP `error` payloads as command failures.

In this repo, [cdp_example.py](../cdp_example.py) implements those pieces in the `CDPClient` class.

## Relationship To The Official Protocol

The official CDP protocol is much larger and changes by browser version. Chrome exposes its exact supported schema at `GET /json/protocol` when remote debugging is enabled. This `mini_cdp` document is intentionally a small, runnable subset for the workflow in this project.
