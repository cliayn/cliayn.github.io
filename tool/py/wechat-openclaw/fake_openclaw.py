# fake_openclaw.py
# 放在宿主机 (Windows) 上运行
# 模拟易受攻击的 OpenClaw 本地网关

import asyncio
import websockets
import json
import threading
from flask import Flask, request, render_template_string

HTTP_PORT = 18788
WS_PORT = 18789
AI_WS_PORT = 8001
STORED_TOKEN = "REAL_OPENCLAW_TOKEN_12345"

app = Flask(__name__)

INDEX_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>OpenClaw 控制面板 (模拟)</title>
</head>
<body>
    <h1>OpenClaw 本地控制面板</h1>
    <p>你的令牌: <strong>{{ token }}</strong> (实际存储在LocalStorage中)</p>
    <hr>
    <button id="sendBtn">向AI发送消息</button>
    <div id="log"></div>

    <script>
        const urlParams = new URLSearchParams(window.location.search);
        // 优先使用 URL 参数中的 gatewayUrl，否则使用默认的 ws://127.0.0.1:8001
        let gatewayUrl = urlParams.get('gatewayUrl') || "ws://127.0.0.1:8001";
        console.log(`[OpenClaw] 使用的WebSocket地址: ${gatewayUrl}`);

        let ws = null;
        let timer = null;

        function appendLog(msg) {
            const div = document.getElementById('log');
            div.innerHTML += `<p>${new Date().toLocaleTimeString()}: ${msg}</p>`;
        }

        // 如果 URL 中有 gatewayUrl 参数，立即建立连接并发送一次令牌（模拟漏洞自动泄露）
        if (urlParams.get('gatewayUrl')) {
            console.log("[OpenClaw] 检测到gatewayUrl参数，自动发送令牌...");
            ws = new WebSocket(gatewayUrl);
            ws.onopen = () => {
                const msg = `#sym:{{ token }}`;
                ws.send(msg);
                appendLog(`[自动] 发送令牌: ${msg}`);
            };
            ws.onmessage = (event) => {
                appendLog(`[自动] 收到: ${event.data}`);
            };
            ws.onclose = () => appendLog("[自动] WebSocket关闭");
            ws.onerror = (err) => appendLog("[自动] WebSocket错误");
        }

        // 手动按钮：持续发送（每秒一次）
        document.getElementById('sendBtn').onclick = () => {
            if (ws && ws.readyState === WebSocket.OPEN) {
                appendLog("WebSocket已连接，开始持续发送消息...");
                if (timer) clearInterval(timer);
                timer = setInterval(() => {
                    if (ws.readyState === WebSocket.OPEN) {
                        const msg = `#sym:{{ token }}`;
                        ws.send(msg);
                        appendLog(`发送: ${msg}`);
                    } else {
                        appendLog("WebSocket未连接，停止发送");
                        clearInterval(timer);
                        timer = null;
                    }
                }, 1000);
            } else {
                appendLog("WebSocket未连接，正在建立连接...");
                ws = new WebSocket(gatewayUrl);
                ws.onopen = () => {
                    appendLog("WebSocket连接已建立，开始发送消息");
                    if (timer) clearInterval(timer);
                    timer = setInterval(() => {
                        if (ws.readyState === WebSocket.OPEN) {
                            const msg = `#sym:{{ token }}`;
                            ws.send(msg);
                            appendLog(`发送: ${msg}`);
                        } else {
                            appendLog("WebSocket已断开，停止发送");
                            clearInterval(timer);
                            timer = null;
                        }
                    }, 1000);
                };
                ws.onmessage = (event) => {
                    appendLog(`收到: ${event.data}`);
                };
                ws.onclose = () => {
                    appendLog("WebSocket连接关闭");
                    if (timer) clearInterval(timer);
                    timer = null;
                };
                ws.onerror = (err) => appendLog(`WebSocket错误: ${err}`);
            }
        };
    </script>
</body>
</html>
"""

@app.route('/chat')
def chat():
    return render_template_string(INDEX_HTML, token=STORED_TOKEN)

@app.route('/')
def index():
    return '<a href="/chat">进入控制面板</a>'

def run_http():
    app.run(host='0.0.0.0', port=HTTP_PORT, debug=False, use_reloader=False)

# --- WebSocket服务1：命令执行入口（端口18789）---
async def ws_handler(websocket):
    print(f"[本地网关] 新的WebSocket连接")
    try:
        message = await websocket.recv()
        data = json.loads(message)
        if data.get('method') == 'connect':
            token = data.get('params', {}).get('auth', {}).get('token')
            if token == STORED_TOKEN:
                await websocket.send(json.dumps({"type": "res", "id": data['id'], "ok": True}))
                print("[本地网关] 认证成功，等待命令...")
                async for cmd_msg in websocket:
                    cmd_data = json.loads(cmd_msg)
                    if cmd_data.get('type') == 'exec':
                        command = cmd_data.get('command', 'unknown')
                        result = f"模拟执行结果：命令 '{command}' 已运行，输出为：Hello from fake OpenClaw"
                        await websocket.send(json.dumps({"type": "exec_result", "result": result}))
                        print(f"[本地网关] 执行命令: {command}，已返回结果")
                    else:
                        await websocket.send(json.dumps({"type": "error", "message": "未知命令类型"}))
            else:
                await websocket.send(json.dumps({"type": "res", "id": data['id'], "ok": False, "error": "无效令牌"}))
                await websocket.close()
        else:
            await websocket.close()
    except Exception as e:
        print(f"[本地网关] 错误: {e}")
        await websocket.close()

async def run_ws():
    async with websockets.serve(ws_handler, "0.0.0.0", WS_PORT):
        print(f"[本地网关] WebSocket服务启动成功: ws://localhost:{WS_PORT}")
        await asyncio.Future()

# --- WebSocket服务2：AI回复模拟（端口8001）---
async def ai_handler(websocket):
    print("[AI服务] 新的连接")
    try:
        async for message in websocket:
            print(f"[AI服务] 收到消息: {message}")
            await websocket.send("ai回复消息成功")
    except websockets.ConnectionClosed:
        print("[AI服务] 连接关闭")

async def run_ai_ws():
    async with websockets.serve(ai_handler, "0.0.0.0", AI_WS_PORT):
        print(f"[AI服务] WebSocket服务启动成功: ws://localhost:{AI_WS_PORT}")
        await asyncio.Future()

if __name__ == "__main__":
    print("="*50)
    print("   模拟 OpenClaw 本地网关启动")
    print("="*50)
    print(f"HTTP 控制面板: http://localhost:{HTTP_PORT}/chat")
    print(f"WebSocket 网关(命令): ws://localhost:{WS_PORT}")
    print(f"WebSocket AI服务: ws://localhost:{AI_WS_PORT}")
    print(f"预设令牌: {STORED_TOKEN}")
    print("="*50)

    http_thread = threading.Thread(target=run_http, daemon=True)
    http_thread.start()

    loop = asyncio.new_event_loop()
    def run_ws_in_thread():
        asyncio.set_event_loop(loop)
        loop.run_until_complete(asyncio.gather(run_ws(), run_ai_ws()))
    ws_thread = threading.Thread(target=run_ws_in_thread, daemon=True)
    ws_thread.start()

    try:
        while True:
            import time
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n关闭服务...")