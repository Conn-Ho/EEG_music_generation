#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
EEG音乐系统服务启动管理器
Service Startup Manager for EEG Music System

使用方法:
python start_services.py
"""

import subprocess
import time
import signal
import sys
import threading
import os

class ServiceManager:
    def __init__(self):
        self.audio_process = None
        self.brain_process = None
        self.running = True
        
    def start_audio_service(self):
        """启动音频生成服务"""
        print("🎵 启动音频生成服务...")
        try:
            self.audio_process = subprocess.Popen(
                [sys.executable, "audio_service.py"],
                cwd=os.path.dirname(os.path.abspath(__file__))
            )
            print("✅ 音频生成服务已启动 (PID: {})".format(self.audio_process.pid))
        except Exception as e:
            print(f"❌ 启动音频服务失败: {e}")
            return False
        return True
    
    def start_brain_processor(self):
        """启动脑波数据处理服务"""
        print("🧠 启动脑波数据处理服务...")
        try:
            self.brain_process = subprocess.Popen(
                [sys.executable, "brain_processor.py"],
                cwd=os.path.dirname(os.path.abspath(__file__))
            )
            print("✅ 脑波数据处理服务已启动 (PID: {})".format(self.brain_process.pid))
        except Exception as e:
            print(f"❌ 启动脑波处理服务失败: {e}")
            return False
        return True
    
    def wait_for_audio_service(self, max_wait=30):
        """等待音频服务启动完成"""
        print("⏳ 等待音频服务完全启动...")
        import requests
        
        for i in range(max_wait):
            try:
                response = requests.get("http://localhost:8080/health", timeout=1)
                if response.status_code == 200:
                    print("✅ 音频服务已就绪")
                    return True
            except requests.exceptions.RequestException:
                pass
            
            time.sleep(1)
            if i % 5 == 0:
                print(f"⏳ 继续等待音频服务启动... ({i}/{max_wait})")
        
        print("❌ 音频服务启动超时")
        return False
    
    def stop_services(self):
        """停止所有服务"""
        print("\n🛑 正在停止所有服务...")
        self.running = False
        
        if self.brain_process:
            print("🧠 停止脑波数据处理服务...")
            self.brain_process.terminate()
            try:
                self.brain_process.wait(timeout=5)
                print("✅ 脑波数据处理服务已停止")
            except subprocess.TimeoutExpired:
                print("⚠️  强制终止脑波数据处理服务")
                self.brain_process.kill()
        
        if self.audio_process:
            print("🎵 停止音频生成服务...")
            self.audio_process.terminate()
            try:
                self.audio_process.wait(timeout=5)
                print("✅ 音频生成服务已停止")
            except subprocess.TimeoutExpired:
                print("⚠️  强制终止音频生成服务")
                self.audio_process.kill()
    
    def signal_handler(self, signum, frame):
        """处理中断信号"""
        print(f"\n📡 接收到信号 {signum}")
        self.stop_services()
        sys.exit(0)
    
    def monitor_services(self):
        """监控服务状态"""
        while self.running:
            time.sleep(5)
            
            # 检查音频服务
            if self.audio_process and self.audio_process.poll() is not None:
                print("❌ 音频服务意外停止")
                self.running = False
                break
            
            # 检查脑波处理服务
            if self.brain_process and self.brain_process.poll() is not None:
                print("❌ 脑波处理服务意外停止")
                self.running = False
                break
    
    def run(self):
        """启动整个系统"""
        # 设置信号处理
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)
        
        print("🚀 EEG音乐生成系统启动中...")
        print("=" * 50)
        
        # 1. 启动音频服务
        if not self.start_audio_service():
            return
        
        # 2. 等待音频服务就绪
        if not self.wait_for_audio_service():
            self.stop_services()
            return
        
        # 3. 启动脑波处理服务
        if not self.start_brain_processor():
            self.stop_services()
            return
        
        print("\n🎯 所有服务已成功启动!")
        print("📊 系统状态监控中...")
        print("🎧 请戴上你的Emotiv EEG设备")
        print("🎵 音乐将根据你的情绪实时变化")
        print("⏱️  情绪数据每5秒更新一次")
        print("\n按 Ctrl+C 停止系统")
        print("=" * 50)
        
        # 4. 监控服务状态
        monitor_thread = threading.Thread(target=self.monitor_services)
        monitor_thread.daemon = True
        monitor_thread.start()
        
        # 5. 等待用户中断或服务异常
        try:
            while self.running:
                time.sleep(1)
        except KeyboardInterrupt:
            pass
        finally:
            self.stop_services()

def main():
    """主程序入口"""
    # 检查依赖
    try:
        import requests
        import fastapi
        import uvicorn
    except ImportError as e:
        print(f"❌ 缺少依赖包: {e}")
        print("请运行: pip install -r requirements.txt")
        return
    
    # 检查文件存在性
    if not os.path.exists("audio_service.py"):
        print("❌ 找不到 audio_service.py")
        return
    
    if not os.path.exists("brain_processor.py"):
        print("❌ 找不到 brain_processor.py")
        return
    
    # 启动服务管理器
    manager = ServiceManager()
    manager.run()

if __name__ == "__main__":
    main() 