"""
Chrome DevTools Protocol (CDP) Example
Demonstrates interprocess communication with Chrome using CDP
"""

import asyncio
import websockets
import json
import subprocess
import time

class CDPClient:
    def __init__(self, ws_url):
        self.ws_url = ws_url
        self.ws = None
        self.msg_id = 0
        
    async def connect(self):
        self.ws = await websockets.connect(self.ws_url)
        
    async def send_command(self, method, params=None):
        self.msg_id += 1
        message = {
            "id": self.msg_id,
            "method": method,
            "params": params or {}
        }
        await self.ws.send(json.dumps(message))
        response = await self.ws.recv()
        return json.loads(response)
    
    async def close(self):
        if self.ws:
            await self.ws.close()

async def main():
    # Launch Chrome with remote debugging
    chrome_process = subprocess.Popen([
        "chrome",
        "--remote-debugging-port=9222",
        "--headless=new",
        "--disable-gpu"
    ])
    
    time.sleep(2)  # Wait for Chrome to start
    
    # Connect to CDP
    client = CDPClient("ws://localhost:9222/devtools/browser")
    await client.connect()
    
    # Create a new target (tab)
    result = await client.send_command("Target.createTarget", {
        "url": "https://example.com"
    })
    target_id = result["result"]["targetId"]
    print(f"Created target: {target_id}")
    
    # Get target info
    result = await client.send_command("Target.getTargetInfo", {
        "targetId": target_id
    })
    print(f"Target info: {result['result']}")
    
    # Navigate to URL
    result = await client.send_command("Target.activateTarget", {
        "targetId": target_id
    })
    print("Target activated")
    
    # Close connection
    await client.close()
    chrome_process.terminate()

if __name__ == "__main__":
    asyncio.run(main())
