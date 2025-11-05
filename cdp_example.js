/**
 * Chrome DevTools Protocol (CDP) Example - Node.js
 * Demonstrates interprocess communication with Chrome using CDP
 */

const WebSocket = require('ws');
const { spawn } = require('child_process');

class CDPClient {
    constructor(wsUrl) {
        this.wsUrl = wsUrl;
        this.ws = null;
        this.msgId = 0;
    }

    connect() {
        return new Promise((resolve) => {
            this.ws = new WebSocket(this.wsUrl);
            this.ws.on('open', resolve);
        });
    }

    sendCommand(method, params = {}) {
        return new Promise((resolve) => {
            this.msgId++;
            const message = {
                id: this.msgId,
                method,
                params
            };
            
            this.ws.once('message', (data) => {
                resolve(JSON.parse(data));
            });
            
            this.ws.send(JSON.stringify(message));
        });
    }

    close() {
        if (this.ws) {
            this.ws.close();
        }
    }
}

async function main() {
    // Launch Chrome with remote debugging
    const chromeProcess = spawn('chrome', [
        '--remote-debugging-port=9222',
        '--headless=new',
        '--disable-gpu'
    ]);

    // Wait for Chrome to start
    await new Promise(resolve => setTimeout(resolve, 2000));

    // Connect to CDP
    const client = new CDPClient('ws://localhost:9222/devtools/browser');
    await client.connect();

    // Create a new target (tab)
    let result = await client.sendCommand('Target.createTarget', {
        url: 'https://example.com'
    });
    const targetId = result.result.targetId;
    console.log(`Created target: ${targetId}`);

    // Get target info
    result = await client.sendCommand('Target.getTargetInfo', {
        targetId
    });
    console.log('Target info:', result.result);

    // Activate target
    await client.sendCommand('Target.activateTarget', {
        targetId
    });
    console.log('Target activated');

    // Close connection
    client.close();
    chromeProcess.kill();
}

main();
