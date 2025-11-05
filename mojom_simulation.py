"""
Mojo Interface Definition Language (.mojom) Conceptual Demo

Demonstrates how .mojom interfaces work by simulating the code generation
and interface binding process without building Chromium.

In real Chromium, .mojom files are compiled to generate C++ binding code.
This demo shows the concept using Python classes.
"""

from dataclasses import dataclass
from typing import Callable, Optional
from enum import Enum

# Simulated .mojom interface definition:
"""
// browser_service.mojom
module browser.mojom;

enum TabState {
  LOADING,
  LOADED,
  CRASHED
};

interface BrowserService {
  CreateTab(string url) => (int32 tab_id, TabState state);
  CloseTab(int32 tab_id) => (bool success);
  NavigateTab(int32 tab_id, string url) => (TabState state);
  GetTabInfo(int32 tab_id) => (string title, string url, TabState state);
};
"""

class TabState(Enum):
    LOADING = 0
    LOADED = 1
    CRASHED = 2

@dataclass
class TabInfo:
    title: str
    url: str
    state: TabState

# Generated interface (proxy side - renderer process)
class BrowserServiceProxy:
    """Client-side proxy generated from .mojom"""
    
    def __init__(self, message_sender: Callable):
        self.message_sender = message_sender
        self.request_id = 0
        self.pending_callbacks = {}
    
    def create_tab(self, url: str, callback: Callable):
        self.request_id += 1
        request = {
            "id": self.request_id,
            "method": "CreateTab",
            "params": {"url": url}
        }
        self.pending_callbacks[self.request_id] = callback
        self.message_sender(request)
    
    def close_tab(self, tab_id: int, callback: Callable):
        self.request_id += 1
        request = {
            "id": self.request_id,
            "method": "CloseTab",
            "params": {"tab_id": tab_id}
        }
        self.pending_callbacks[self.request_id] = callback
        self.message_sender(request)
    
    def navigate_tab(self, tab_id: int, url: str, callback: Callable):
        self.request_id += 1
        request = {
            "id": self.request_id,
            "method": "NavigateTab",
            "params": {"tab_id": tab_id, "url": url}
        }
        self.pending_callbacks[self.request_id] = callback
        self.message_sender(request)
    
    def get_tab_info(self, tab_id: int, callback: Callable):
        self.request_id += 1
        request = {
            "id": self.request_id,
            "method": "GetTabInfo",
            "params": {"tab_id": tab_id}
        }
        self.pending_callbacks[self.request_id] = callback
        self.message_sender(request)
    
    def handle_response(self, response: dict):
        request_id = response["id"]
        if request_id in self.pending_callbacks:
            callback = self.pending_callbacks.pop(request_id)
            callback(response["result"])

# Generated implementation stub (service side - browser process)
class BrowserServiceImpl:
    """Server-side implementation stub generated from .mojom"""
    
    def __init__(self):
        self.tabs = {}
        self.next_tab_id = 1
    
    def create_tab(self, url: str) -> tuple[int, TabState]:
        tab_id = self.next_tab_id
        self.next_tab_id += 1
        self.tabs[tab_id] = TabInfo(
            title=f"Tab {tab_id}",
            url=url,
            state=TabState.LOADED
        )
        return tab_id, TabState.LOADED
    
    def close_tab(self, tab_id: int) -> bool:
        if tab_id in self.tabs:
            del self.tabs[tab_id]
            return True
        return False
    
    def navigate_tab(self, tab_id: int, url: str) -> Optional[TabState]:
        if tab_id in self.tabs:
            self.tabs[tab_id].url = url
            self.tabs[tab_id].state = TabState.LOADING
            return TabState.LOADING
        return None
    
    def get_tab_info(self, tab_id: int) -> Optional[tuple[str, str, TabState]]:
        if tab_id in self.tabs:
            info = self.tabs[tab_id]
            return info.title, info.url, info.state
        return None

class BrowserServiceStub:
    """Handles incoming messages and dispatches to implementation"""
    
    def __init__(self, impl: BrowserServiceImpl, response_sender: Callable):
        self.impl = impl
        self.response_sender = response_sender
    
    def handle_request(self, request: dict):
        method = request["method"]
        params = request["params"]
        request_id = request["id"]
        
        if method == "CreateTab":
            tab_id, state = self.impl.create_tab(params["url"])
            response = {
                "id": request_id,
                "result": {"tab_id": tab_id, "state": state.name}
            }
        elif method == "CloseTab":
            success = self.impl.close_tab(params["tab_id"])
            response = {
                "id": request_id,
                "result": {"success": success}
            }
        elif method == "NavigateTab":
            state = self.impl.navigate_tab(params["tab_id"], params["url"])
            response = {
                "id": request_id,
                "result": {"state": state.name if state else None}
            }
        elif method == "GetTabInfo":
            info = self.impl.get_tab_info(params["tab_id"])
            if info:
                response = {
                    "id": request_id,
                    "result": {
                        "title": info[0],
                        "url": info[1],
                        "state": info[2].name
                    }
                }
            else:
                response = {
                    "id": request_id,
                    "result": None
                }
        
        self.response_sender(response)

# Simulated message channel
class MessageChannel:
    def __init__(self):
        self.client_to_service = []
        self.service_to_client = []

def main():
    print("🔗 Mojo Interface Definition Language (.mojom) Demo\n")
    
    # Create message channel
    channel = MessageChannel()
    
    # Browser process side
    impl = BrowserServiceImpl()
    stub = BrowserServiceStub(
        impl,
        lambda msg: channel.service_to_client.append(msg)
    )
    
    # Renderer process side
    proxy = BrowserServiceProxy(
        lambda msg: channel.client_to_service.append(msg)
    )
    
    print("📝 Interface: BrowserService")
    print("   Methods: CreateTab, CloseTab, NavigateTab, GetTabInfo\n")
    
    # Example 1: Create tab
    print("1️⃣ Creating tab...")
    proxy.create_tab("https://example.com", lambda result: 
        print(f"   ✅ Created tab {result['tab_id']} - State: {result['state']}")
    )
    
    # Process messages
    if channel.client_to_service:
        request = channel.client_to_service.pop(0)
        stub.handle_request(request)
    
    if channel.service_to_client:
        response = channel.service_to_client.pop(0)
        proxy.handle_response(response)
    
    tab_id = 1  # From response
    
    # Example 2: Get tab info
    print("\n2️⃣ Getting tab info...")
    proxy.get_tab_info(tab_id, lambda result:
        print(f"   📄 Title: {result['title']}")
        or print(f"   🌐 URL: {result['url']}")
        or print(f"   📊 State: {result['state']}")
    )
    
    if channel.client_to_service:
        request = channel.client_to_service.pop(0)
        stub.handle_request(request)
    
    if channel.service_to_client:
        response = channel.service_to_client.pop(0)
        proxy.handle_response(response)
    
    # Example 3: Navigate tab
    print("\n3️⃣ Navigating tab...")
    proxy.navigate_tab(tab_id, "https://google.com", lambda result:
        print(f"   🔄 Navigation started - State: {result['state']}")
    )
    
    if channel.client_to_service:
        request = channel.client_to_service.pop(0)
        stub.handle_request(request)
    
    if channel.service_to_client:
        response = channel.service_to_client.pop(0)
        proxy.handle_response(response)
    
    # Example 4: Close tab
    print("\n4️⃣ Closing tab...")
    proxy.close_tab(tab_id, lambda result:
        print(f"   ❌ Closed successfully: {result['success']}")
    )
    
    if channel.client_to_service:
        request = channel.client_to_service.pop(0)
        stub.handle_request(request)
    
    if channel.service_to_client:
        response = channel.service_to_client.pop(0)
        proxy.handle_response(response)
    
    print("\n✨ Demo completed!")
    print("\n💡 Key Concepts:")
    print("   • Proxy: Client-side stub for making calls")
    print("   • Stub: Server-side dispatcher to implementation")
    print("   • Type-safe: Interfaces defined in .mojom IDL")
    print("   • Async: All calls are asynchronous with callbacks")

if __name__ == "__main__":
    main()
