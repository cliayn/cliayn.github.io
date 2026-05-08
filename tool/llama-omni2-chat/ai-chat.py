import pyaudio
import webrtcvad
import collections
import wave
import os
import math
import struct
import threading
import time
import atexit
from datetime import datetime
from gradio_client import Client, handle_file
import pygame

# ========== 全局设备配置（可随时修改）==========
# Linux 系统录音设备（默认 hw:3,0）
LINUX_INPUT_DEVICE = "hw:3,0"
# Linux 系统播放设备（默认 hw:3,0）
LINUX_OUTPUT_DEVICE = "hw:3,0"
# Windows 系统录音设备（留空则使用系统默认设备）
WINDOWS_INPUT_DEVICE = ""      # 例如 "麦克风 (Realtek Audio)"
# Windows 系统播放设备（留空则使用系统默认设备）
WINDOWS_OUTPUT_DEVICE = ""     # 例如 "扬声器 (Realtek Audio)"
# ==============================================

class AudioRecorder:
    def __init__(self):
        # --- 基础配置 ---
        self.FORMAT = pyaudio.paInt16
        self.CHANNELS = 1
        self.RATE = 16000
        self.FRAME_DURATION = 30  # ms
        self.CHUNK = int(self.RATE * self.FRAME_DURATION / 1000)
        
        # --- VAD 配置 ---
        self.vad = webrtcvad.Vad(3)
        self.ENERGY_THRESHOLD = 600
        self.MAX_RECORD_SECONDS = 7
        self.PRE_RECORD_SECONDS = 0.5
        self.POST_RECORD_SECONDS = 1.5
        
        self.MAX_FRAMES = int(self.MAX_RECORD_SECONDS * 1000 / self.FRAME_DURATION)
        self.PRE_RECORD_CHUNKS = int(self.PRE_RECORD_SECONDS * 1000 / self.FRAME_DURATION)
        self.POST_RECORD_CHUNKS = int(self.POST_RECORD_SECONDS * 1000 / self.FRAME_DURATION)
        
        self.p = pyaudio.PyAudio()
        
        # --- AI 服务配置 ---
        self.AI_SERVER_URL = "http://192.168.2.123:8888/"
        self.is_processing = False
        
        # --- 提示音文件 ---
        self.STARTUP_SOUND = "hello.wav"
        self.PROMPT_SOUND = "ai-demo.wav"
        
        # --- 音频播放互斥锁 ---
        self.audio_play_lock = threading.Lock()
        
        # --- Gradio客户端（复用）---
        self.ai_client = Client(self.AI_SERVER_URL)
        
        # --- 清理标志 ---
        self._history_cleaned = False
        
        # --- 注册退出清理函数 ---
        atexit.register(self.cleanup)

        # ========== 新增：根据操作系统确定设备 ==========
        self.input_device_index = None   # PyAudio 输入设备索引
        self.output_device_name = None   # Pygame 播放设备名（字符串）

        is_windows = (os.name == 'nt')
        if is_windows:
            # Windows 系统：使用全局配置的设备名，若为空则自动选默认设备
            self._setup_windows_devices()
        else:
            # Linux / macOS 等：使用全局配置的 ALSA 设备名
            self._setup_linux_devices()

    # ---------- 新增：Windows 设备初始化 ----------
    def _setup_windows_devices(self):
        """设置 Windows 录音/播放设备索引"""
        # 录音设备
        if WINDOWS_INPUT_DEVICE:
            self.input_device_index = self._get_device_index(WINDOWS_INPUT_DEVICE, is_input=True)
            if self.input_device_index is None:
                print(f"[警告] 未找到录音设备 '{WINDOWS_INPUT_DEVICE}'，将使用系统默认设备")
        # 播放设备名（传给 pygame）
        self.output_device_name = WINDOWS_OUTPUT_DEVICE if WINDOWS_OUTPUT_DEVICE else None

    # ---------- 新增：Linux 设备初始化 ----------
    def _setup_linux_devices(self):
        """设置 Linux 录音/播放设备索引"""
        # 录音设备
        if LINUX_INPUT_DEVICE:
            self.input_device_index = self._get_device_index(LINUX_INPUT_DEVICE, is_input=True)
            if self.input_device_index is None:
                print(f"[警告] 未找到录音设备 '{LINUX_INPUT_DEVICE}'，将使用系统默认设备")
        # 播放设备名（传给 pygame）
        self.output_device_name = LINUX_OUTPUT_DEVICE if LINUX_OUTPUT_DEVICE else None

    # ---------- 新增：根据设备名查找 PyAudio 设备索引 ----------
    def _get_device_index(self, device_name, is_input=True):
        """
        遍历所有音频设备，返回第一个名称包含 device_name 且满足输入/输出类型的设备索引。
        若未找到则返回 None。
        """
        for i in range(self.p.get_device_count()):
            info = self.p.get_device_info_by_index(i)
            name = info['name']
            # 检查设备名称是否包含目标字符串（不区分大小写）
            if device_name.lower() in name.lower():
                # 确认是输入设备（maxInputChannels>0）或输出设备（maxOutputChannels>0）
                if is_input and info['maxInputChannels'] > 0:
                    return i
                elif not is_input and info['maxOutputChannels'] > 0:
                    return i
        return None

    # ---------- 音频工具函数 ----------
    def get_rms(self, data):
        count = len(data) // 2
        format = "%dh" % count
        shorts = struct.unpack(format, data)
        sum_squares = sum(s**2 for s in shorts)
        rms = math.sqrt(sum_squares / count)
        return rms

    def is_speech(self, data):
        try:
            rms = self.get_rms(data)
            if rms < self.ENERGY_THRESHOLD:
                return False
            return self.vad.is_speech(data, self.RATE)
        except:
            return False

    def save_audio(self, frames):
        if not os.path.exists("recordings"):
            os.makedirs("recordings")
        
        filename = f"recordings/rec_{datetime.now().strftime('%Y%m%d_%H%M%S')}.wav"
        
        wf = wave.open(filename, 'wb')
        wf.setnchannels(self.CHANNELS)
        wf.setsampwidth(self.p.get_sample_size(self.FORMAT))
        wf.setframerate(self.RATE)
        wf.writeframes(b''.join(frames))
        wf.close()
        duration = len(frames) * self.FRAME_DURATION / 1000
        print(f"\n[保存] {filename} (时长: {duration:.2f}s)")
        
        if not self.is_processing:
            threading.Thread(target=self.process_with_ai, args=(filename,), daemon=True).start()
        else:
            print("[跳过] 正在处理上一个请求，本次录音暂不发送")

    # ---------- 统一音频播放方法（带锁）----------
    def _play_audio_file(self, file_path, description="音频"):
        if not os.path.exists(file_path):
            print(f"[提示] 未找到{description}文件 {file_path}，跳过播放")
            return
        with self.audio_play_lock:
            try:
                # 修改：根据系统设备名初始化 pygame mixer
                if self.output_device_name:
                    pygame.mixer.init(devicename=self.output_device_name)
                else:
                    pygame.mixer.init()  # 使用默认设备
                    
                pygame.mixer.music.load(file_path)
                pygame.mixer.music.play()
                while pygame.mixer.music.get_busy():
                    time.sleep(0.1)
            except Exception as e:
                print(f"[{description}播放失败] {e}")
            finally:
                pygame.mixer.quit()
        print(f"[{description}] 播放完成")

    def play_startup_sound(self):
        self._play_audio_file(self.STARTUP_SOUND, "启动提示音")

    def play_prompt_sound(self):
        self._play_audio_file(self.PROMPT_SOUND, "发送前提示")

    def play_ai_response(self, audio_path):
        self._play_audio_file(audio_path, "AI回复")

    # ---------- AI 交互部分 ----------
    def stream_ai_interaction(self, file_path):
        job = self.ai_client.submit(
            audio_input=handle_file(file_path),
            model_selector="LLaMA-Omni2-1.5B-Bilingual",
            temperature=0.7,
            api_name="/inference_fn"
        )

        has_played_audio = False
        last_display = ""

        for chunk in job:
            if len(chunk) < 2:
                continue
            chat_history = chunk[1]
            
            current_display = "\n" + "="*40 + " 对话记录 " + "="*40 + "\n"
            for msg in chat_history:
                role = msg.get('role', '').upper()
                content = msg.get('content', '')
                if isinstance(content, str):
                    current_display += f"[{role}]: {content}\n"
                elif isinstance(content, dict):
                    current_display += f"[{role}]: [语音文件]\n"
            
            if current_display != last_display:
                print(current_display, end="")
                last_display = current_display

            last_msg = chat_history[-1]
            if (not has_played_audio and 
                last_msg.get('role') == 'assistant' and 
                isinstance(last_msg.get('content'), dict)):
                audio_path = last_msg['content'].get('file')
                if audio_path and os.path.exists(audio_path):
                    print("--- 📢 正在播放声音 ---")
                    self.play_ai_response(audio_path)
                    has_played_audio = True
                    return

    def process_with_ai(self, file_path):
        self.is_processing = True
        try:
            print("\n[AI] 准备发送录音，播放提示音...")
            self.play_prompt_sound()
            
            print(f"[AI] 开始处理文件: {os.path.basename(file_path)}")
            self.stream_ai_interaction(file_path)
        except Exception as e:
            print(f"\n[AI错误] {e}")
        finally:
            self.is_processing = False
            print("\n[AI] 处理完成，继续监听...")

    # ---------- 清除对话历史 ----------
    def clear_history(self):
        if self._history_cleaned:
            return
        print("\n[清理] 正在清除对话历史...")
        try:
            result = self.ai_client.predict(api_name="/clear_history")
            print(f"[清理] 服务端响应: {result}")
        except Exception as e:
            print(f"[清理] 失败: {e}")
        finally:
            self._history_cleaned = True

    def cleanup(self):
        self.clear_history()

    # ---------- 主录音循环 ----------
    def start(self):
        print("--- 系统启动: 监听中 ---")
        print(f"配置: 能量阈值={self.ENERGY_THRESHOLD}, 最大时长={self.MAX_RECORD_SECONDS}s")
        print(f"启动提示音: {self.STARTUP_SOUND} (1秒后播放)")
        print(f"发送前提示音: {self.PROMPT_SOUND}")
        # 显示当前使用的录音设备
        if self.input_device_index is not None:
            dev_info = self.p.get_device_info_by_index(self.input_device_index)
            print(f"录音设备: [{self.input_device_index}] {dev_info['name']}")
        else:
            print("录音设备: 系统默认")
        # 显示当前使用的播放设备
        if self.output_device_name:
            print(f"播放设备: {self.output_device_name}")
        else:
            print("播放设备: 系统默认")
        print("录音结束后将自动发送至AI服务器\n")
        
        # 1秒后播放启动提示音（非阻塞）
        timer = threading.Timer(1.0, self.play_startup_sound)
        timer.daemon = True
        timer.start()
        
        # 修改：录音流使用指定的输入设备索引
        stream = self.p.open(format=self.FORMAT,
                             channels=self.CHANNELS,
                             rate=self.RATE,
                             input=True,
                             input_device_index=self.input_device_index,  # 关键修改
                             frames_per_buffer=self.CHUNK)

        ring_buffer = collections.deque(maxlen=self.PRE_RECORD_CHUNKS)
        triggered = False
        voiced_frames = []
        silence_counter = 0

        try:
            while True:
                if self.is_processing:
                    stream.read(self.CHUNK, exception_on_overflow=False)
                    continue

                data = stream.read(self.CHUNK, exception_on_overflow=False)
                active = self.is_speech(data)

                if not triggered:
                    ring_buffer.append(data)
                    if active:
                        print(f"\n[触发] 声音出现 (能量>{self.ENERGY_THRESHOLD})，开始录音...")
                        triggered = True
                        voiced_frames.extend(ring_buffer)
                        voiced_frames.append(data)
                        silence_counter = 0
                else:
                    voiced_frames.append(data)
                    
                    if len(voiced_frames) >= self.MAX_FRAMES:
                        print(f"\n[强制结束] 已达到最大时长 {self.MAX_RECORD_SECONDS}s")
                        self.save_audio(voiced_frames)
                        triggered = False
                        ring_buffer.clear()
                        voiced_frames = []
                        silence_counter = 0
                        print("--- 继续监听 ---")
                        continue

                    if active:
                        silence_counter = 0
                        curr_sec = len(voiced_frames) * self.FRAME_DURATION / 1000
                        print(f"\r录音中: {curr_sec:.1f}s / {self.MAX_RECORD_SECONDS}s", end="")
                    else:
                        silence_counter += 1
                        if silence_counter > self.POST_RECORD_CHUNKS:
                            print(f"\n[结束] 说话停止 (静默{self.POST_RECORD_SECONDS}s)")
                            self.save_audio(voiced_frames)
                            triggered = False
                            ring_buffer.clear()
                            voiced_frames = []
                            silence_counter = 0
                            print("--- 继续监听 ---")

        except KeyboardInterrupt:
            print("\n\n[退出] 用户中断")
        finally:
            stream.stop_stream()
            stream.close()
            self.p.terminate()
            self.clear_history()
            print("--- 程序已退出 ---")

if __name__ == "__main__":
    try:
        import webrtcvad, gradio_client, pygame
    except ImportError as e:
        print(f"缺少依赖库: {e}")
        print("请安装: pip install webrtcvad gradio_client pygame")
        exit(1)
    
    recorder = AudioRecorder()
    recorder.start()