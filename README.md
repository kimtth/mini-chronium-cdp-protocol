# Chromium IPC Demonstrations

Practical examples of **Mojo IPC** (Chromium's inter-process communication) and **Chrome DevTools Protocol (CDP)**.

## Overview

### Mojo IPC

Chromium's type-safe IPC system using message pipes and .mojom IDL files.

**Key benefits:** Type safety, zero-copy messaging, process isolation, cross-language support.

**When to use:** Multi-process architecture, performance-critical IPC, sandboxed processes.

**Mojo IDL syntax:**
```mojom
interface UserService {
  GetUser(int32 id) => (User user, Status status);
  LogEvent(string event);  // One-way
};
```

**Common types:** `bool`, `int32`/`uint32`, `int64`/`uint64`, `float`, `double`, `string`, `array<T>`, `map<K,V>`, `T?`

**Real Chromium IPC:**
- Renderer ↔ Browser: DOM, navigation, resources
- Browser ↔ GPU: Graphics commands
- Browser ↔ Network Service: HTTP, cookies
- Browser ↔ Storage: IndexedDB, Cache API

### Chrome DevTools Protocol (CDP)

WebSocket-based debugging protocol for browser automation and inspection.

**Features:** JSON-RPC messages, remote debugging, tab management, network/DOM inspection.

**Use cases:** Puppeteer, Playwright, performance monitoring, screenshot generation.

## Examples

| File | Purpose | Usage |
|------|---------|-------|
| `cdp_example.py` | Chrome DevTools Protocol (Python) | `pip install websockets && python cdp_example.py` |
| `cdp_example.js` | Chrome DevTools Protocol (Node.js) | `npm install ws && node cdp_example.js` |
| `mojo_ipc_simulation.py` | Mojo IPC simulation using multiprocessing | `python mojo_ipc_simulation.py` |
| `mojom_loader.py` | Parse & load real .mojom files, generate Python bindings | `python mojom_loader.py` |
| `browser_service.mojom` | Sample Mojo interface definition | Reference for .mojom syntax |

## Architecture

**Mojo Code Generation Flow:**
```
.mojom file → Build System → Generate C++ bindings → Server (Receiver) + Client (Remote)
```

**Mojo IPC Communication:**
```
Renderer Process                    Browser Process
    |                                    |
    |-------[Message Pipe]-------|
    |→ CreateTab("http://...")  →|→ Execute CreateTab()
    |←      {tab_id}           ←|← Return tab_id
```

**CDP Communication:**
```
Client → WebSocket → Chrome Browser
  ↓ {Target.createTarget}
  ← {targetId, success}
```

**Chromium Multi-Process with Mojo:**
```
Browser Process (privileged)
├─ BrowserService impl
└─ Receiver<BrowserService>
   ↕ [Mojo Message Pipes]
┌─ Renderer Process (sandboxed)    ┬─ GPU Process    ┬─ Network Service
├─ Remote<BrowserService>          ├─ GPUService     ├─ URLLoader
└─ Blink Engine                    └─ Graphics       └─ CookieManager
```

## Comparison

| Feature | Mojo IPC | CDP |
|---------|----------|-----|
| Purpose | Internal Chromium IPC | External debugging/automation |
| Protocol | Binary message pipes | JSON over WebSocket |
| Type Safety | Strongly typed | JSON schema |
| Performance | Optimized | Human-readable |
| Access | Requires build | Works with any Chrome |
| Language | C++/Java/JS | Any language with WebSocket |

## Requirements

- Python 3.7+, Node.js 14+
- `websockets` (Python) / `ws` (Node.js)
- Chrome/Chromium browser
- No Chromium build required for examples

## Key Resources

- [Chrome DevTools Protocol](https://chromedevtools.github.io/devtools-protocol/)
- [Mojo Documentation](https://chromium.googlesource.com/chromium/src/+/main/mojo/README.md)
- [Chromium Multi-Process Architecture](https://www.chromium.org/developers/design-documents/multi-process-architecture/)

## License

MIT
