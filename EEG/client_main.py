#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Client Service Manager for Social EEG Music System
社交EEG音乐系统客户端服务管理器

使用方法:
python client_main.py

客户端负责：
1. 连接主设备的社交音频服务
2. 处理本地EEG设备数据
3. 将情绪数据发送到主设备
4. 不生成音乐，仅作为情绪数据源
"""

import subprocess
import time
import signal
import sys
import os
import socket

class ClientServiceManager:
    def __init__(self):
        self.client_brain_process = None
        self.running = True
        
    def display_client_info(self):
        """显示客户端信息"""
        hostname = socket.gethostname()
        try:
            local_ip = socket.gethostbyname(hostname)
        except Exception:
            local_ip = "Unknown"
        
        print("=" * 60)
        print("📱 EEG音乐社交系统 - 客户端")
        print("=" * 60)
        print(f"🖥️  设备名称: {hostname}")
        print(f"🌐 本机IP: {local_ip}")
        print()
        print("📋 使用说明:")
        print("1. 确保主设备已启动社交音频服务")
        print("2. 准备好Emotiv EEG设备")
        print("3. 输入主设备的IP地址")
        print("4. 戴上EEG设备开始情绪检测")
        print()
        print("💡 你的情绪数据将与其他用户融合生成音乐")
        print("=" * 60)
    
    def start_client_brain_processor(self):
        """启动客户端脑波数据处理服务"""
        print("🧠 启动客户端脑波数据处理服务...")
        try:
            self.client_brain_process = subprocess.Popen(
                [sys.executable, "client_brain_processor.py"],
                cwd=os.path.dirname(os.path.abspath(__file__))
            )
            print("✅ 客户端脑波数据处理服务已启动 (PID: {})".format(self.client_brain_process.pid))
        except Exception as e:
            print(f"❌ 启动客户端脑波处理服务失败: {e}")
            return False
        return True
    
    def stop_services(self):
        """停止所有服务"""
        print("\n🛑 正在停止客户端服务...")
        self.running = False
        
        if self.client_brain_process:
            print("🧠 停止客户端脑波数据处理服务...")
            self.client_brain_process.terminate()
            try:
                self.client_brain_process.wait(timeout=5)
                print("✅ 客户端脑波数据处理服务已停止")
            except subprocess.TimeoutExpired:
                print("⚠️  强制终止客户端脑波数据处理服务")
                self.client_brain_process.kill()
    
    def signal_handler(self, signum, frame):
        """处理中断信号"""
        print(f"\n📡 接收到信号 {signum}")
        self.stop_services()
        sys.exit(0)
    
    def monitor_services(self):
        """监控服务状态"""
        while self.running:
            time.sleep(5)
            
            # 检查客户端脑波处理服务
            if self.client_brain_process and self.client_brain_process.poll() is not None:
                print("❌ 客户端脑波处理服务意外停止")
                self.running = False
                break
    
    def run(self):
        """启动客户端系统"""
        # 设置信号处理
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)
        
        # 显示客户端信息
        self.display_client_info()
        
        print("🚀 客户端EEG音乐系统启动中...")
        print("=" * 50)
        
        # 启动客户端脑波处理服务
        if not self.start_client_brain_processor():
            return
        
        print("\n🎯 客户端服务已成功启动!")
        print("📊 连接到主设备中...")
        print("🎧 请戴上你的Emotiv EEG设备")
        print("🎵 你的情绪将与其他用户融合生成音乐")
        print("⏱️  情绪数据每5秒发送一次")
        print("\n按 Ctrl+C 停止客户端")
        print("=" * 50)
        
        # 监控服务状态（非阻塞）
        import threading
        monitor_thread = threading.Thread(target=self.monitor_services)
        monitor_thread.daemon = True
        monitor_thread.start()
        
        # 等待用户中断或服务异常
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
    except ImportError as e:
        print(f"❌ 缺少依赖包: {e}")
        print("请运行: pip install -r requirements.txt")
        return
    
    # 检查文件存在性
    if not os.path.exists("client_brain_processor.py"):
        print("❌ 找不到 client_brain_processor.py")
        print("请确保在正确的目录中运行此脚本")
        return
    
    if not os.path.exists("cortex.py"):
        print("❌ 找不到 cortex.py")
        print("请确保Cortex SDK已正确安装")
        return
    
    # 启动客户端服务管理器
    manager = ClientServiceManager()
    manager.run()

if __name__ == "__main__":
    main() 