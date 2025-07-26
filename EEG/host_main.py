#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Host Device Service Manager for Social EEG Music System
社交EEG音乐系统主设备服务管理器

使用方法:
python host_main.py

主设备负责：
1. 运行社交音频生成服务（接收多个用户的情绪数据）
2. 运行本地脑波数据处理服务（如果有本地EEG设备）
3. 融合多用户情绪数据并生成音乐
4. 提供网络API供客户端连接
"""

import subprocess
import time
import signal
import sys
import threading
import os
import socket
import requests
import json

class SocialServiceManager:
    def __init__(self):
        self.social_audio_process = None
        self.local_brain_process = None
        self.running = True
        self.local_user_id = None
        
    def get_local_ip(self):
        """获取本机IP地址"""
        try:
            # 连接到一个远程地址来获取本机IP
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            try:
                # 备用方法
                hostname = socket.gethostname()
                return socket.gethostbyname(hostname)
            except Exception:
                return "127.0.0.1"
    
    def display_host_info(self):
        """显示主设备信息"""
        local_ip = self.get_local_ip()
        print("=" * 60)
        print("🏠 EEG音乐社交系统 - 主设备")
        print("=" * 60)
        print(f"📡 服务地址: http://{local_ip}:8080")
        print(f"🌐 局域网IP: {local_ip}")
        print(f"🔗 客户端连接地址: {local_ip}")
        print()
        print("📋 给客户端用户的连接信息:")
        print(f"   IP地址: {local_ip}")
        print(f"   端口: 8080")
        print()
        print("💡 客户端用户需要在启动时输入上述IP地址")
        print("=" * 60)
    
    def start_social_audio_service(self):
        """启动社交音频生成服务"""
        print("🎵 启动社交音频生成服务...")
        try:
            self.social_audio_process = subprocess.Popen(
                [sys.executable, "social_audio_service.py"],
                cwd=os.path.dirname(os.path.abspath(__file__))
            )
            print("✅ 社交音频生成服务已启动 (PID: {})".format(self.social_audio_process.pid))
        except Exception as e:
            print(f"❌ 启动社交音频服务失败: {e}")
            return False
        return True
    
    def start_local_brain_processor(self):
        """启动本地脑波数据处理服务（可选）"""
        use_local_eeg = input("是否使用本地EEG设备？ (y/n): ").strip().lower()
        
        if use_local_eeg in ['y', 'yes', '是']:
            print("🧠 启动本地脑波数据处理服务...")
            try:
                self.local_brain_process = subprocess.Popen(
                    [sys.executable, "brain_processor.py"],
                    cwd=os.path.dirname(os.path.abspath(__file__))
                )
                print("✅ 本地脑波数据处理服务已启动 (PID: {})".format(self.local_brain_process.pid))
                
                # 生成本地用户ID
                import uuid
                hostname = socket.gethostname()
                self.local_user_id = f"host_{hostname}_{str(uuid.uuid4())[:8]}"
                
                return True
            except Exception as e:
                print(f"❌ 启动本地脑波处理服务失败: {e}")
                return False
        else:
            print("⏭️  跳过本地EEG设备，仅作为音频服务器运行")
            return True
    
    def wait_for_social_audio_service(self, max_wait=30):
        """等待社交音频服务启动完成"""
        print("⏳ 等待社交音频服务完全启动...")
        
        for i in range(max_wait):
            try:
                response = requests.get("http://localhost:8080/health", timeout=1)
                if response.status_code == 200:
                    data = response.json()
                    if data.get('status') == 'healthy':
                        print("✅ 社交音频服务已就绪")
                        return True
            except requests.exceptions.RequestException:
                pass
            
            time.sleep(1)
            if i % 5 == 0:
                print(f"⏳ 继续等待社交音频服务启动... ({i}/{max_wait})")
        
        print("❌ 社交音频服务启动超时")
        return False
    
    def join_local_session(self):
        """将本地用户加入会话"""
        if not self.local_user_id:
            return True
        
        try:
            device_info = f"Host_{socket.gethostname()}"
            response = requests.post(
                "http://localhost:8080/join_session",
                params={
                    "user_id": self.local_user_id,
                    "device_info": device_info
                },
                timeout=5
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get('status') == 'success':
                    print(f"✅ 本地用户已加入会话: {self.local_user_id}")
                    return True
            
            print(f"⚠️  本地用户加入会话失败: {response.text}")
            return False
            
        except Exception as e:
            print(f"⚠️  本地用户加入会话失败: {e}")
            return False
    
    def get_service_status(self):
        """获取服务状态"""
        try:
            response = requests.get("http://localhost:8080/status", timeout=3)
            if response.status_code == 200:
                return response.json()
            return None
        except Exception:
            return None
    
    def display_status_info(self):
        """显示状态信息"""
        status = self.get_service_status()
        if status:
            print(f"\n📊 系统状态:")
            print(f"   🎵 音乐生成: {'✅ 运行中' if status.get('is_playing') else '❌ 停止'}")
            print(f"   👥 连接用户: {status.get('user_count', 0)} 人")
            print(f"   💪 活跃用户: {status.get('active_user_count', 0)} 人")
            print(f"   🌐 WebSocket连接: {status.get('websocket_connections', 0)}")
            print(f"   🎼 当前风格: {status.get('current_prompt', 'N/A')}")
            print(f"   🔊 当前强度: {status.get('current_intensity', 0):.2f}")
            
            if status.get('current_fused_emotion'):
                fused = status['current_fused_emotion']
                print(f"   😊 融合情绪: {fused.get('primary_emotion')} ({fused.get('fusion_intensity', 0):.2f})")
                print(f"   🔀 融合方法: {fused.get('fusion_method')}")
            
            if status.get('users'):
                print(f"   👤 用户列表:")
                for user in status['users']:
                    active_symbol = "🟢" if user.get('is_active') else "🔴"
                    emotion = user.get('last_emotion', 'N/A')
                    intensity = user.get('last_intensity')
                    if intensity is not None:
                        print(f"      {active_symbol} {user['user_id']}: {emotion} ({intensity:.2f})")
                    else:
                        print(f"      {active_symbol} {user['user_id']}: {emotion} (--)")
        else:
            print("\n❌ 无法获取服务状态")
    
    def stop_services(self):
        """停止所有服务"""
        print("\n🛑 正在停止所有服务...")
        self.running = False
        
        # 本地用户离开会话
        if self.local_user_id:
            try:
                requests.post(
                    "http://localhost:8080/leave_session",
                    params={"user_id": self.local_user_id},
                    timeout=3
                )
                print("✅ 本地用户已离开会话")
            except Exception:
                pass
        
        # 停止本地脑波处理服务
        if self.local_brain_process:
            print("🧠 停止本地脑波数据处理服务...")
            self.local_brain_process.terminate()
            try:
                self.local_brain_process.wait(timeout=5)
                print("✅ 本地脑波数据处理服务已停止")
            except subprocess.TimeoutExpired:
                print("⚠️  强制终止本地脑波数据处理服务")
                self.local_brain_process.kill()
        
        # 停止社交音频服务
        if self.social_audio_process:
            print("🎵 停止社交音频生成服务...")
            self.social_audio_process.terminate()
            try:
                self.social_audio_process.wait(timeout=5)
                print("✅ 社交音频生成服务已停止")
            except subprocess.TimeoutExpired:
                print("⚠️  强制终止社交音频生成服务")
                self.social_audio_process.kill()
    
    def signal_handler(self, signum, frame):
        """处理中断信号"""
        print(f"\n📡 接收到信号 {signum}")
        self.stop_services()
        sys.exit(0)
    
    def monitor_services(self):
        """监控服务状态"""
        last_status_time = time.time()
        status_interval = 60.0  # 60秒显示一次详细状态
        
        while self.running:
            time.sleep(5)
            
            # 检查社交音频服务
            if self.social_audio_process and self.social_audio_process.poll() is not None:
                print("❌ 社交音频服务意外停止")
                self.running = False
                break
            
            # 检查本地脑波处理服务
            if self.local_brain_process and self.local_brain_process.poll() is not None:
                print("❌ 本地脑波处理服务意外停止")
                # 本地脑波服务停止不影响整个系统运行
                self.local_brain_process = None
            
            # 定期显示状态信息
            current_time = time.time()
            if current_time - last_status_time >= status_interval:
                self.display_status_info()
                last_status_time = current_time
    
    def run(self):
        """启动整个系统"""
        # 设置信号处理
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)
        
        # 显示主设备信息
        self.display_host_info()
        
        print("🚀 社交EEG音乐生成系统启动中...")
        print("=" * 50)
        
        # 1. 启动社交音频服务
        if not self.start_social_audio_service():
            return
        
        # 2. 等待社交音频服务就绪
        if not self.wait_for_social_audio_service():
            self.stop_services()
            return
        
        # 3. 启动本地脑波处理服务（可选）
        if not self.start_local_brain_processor():
            print("⚠️  本地脑波处理服务启动失败，但不影响远程用户连接")
        
        # 4. 本地用户加入会话（如果有本地EEG）
        self.join_local_session()
        
        print("\n🎯 社交音频服务已成功启动!")
        print("📊 系统状态监控中...")
        print("🔗 等待客户端用户连接...")
        if self.local_user_id:
            print("🎧 请戴上你的Emotiv EEG设备（本地用户）")
        print("🎵 音乐将根据所有用户的情绪实时变化")
        print("⏱️  情绪数据每5秒更新一次")
        print("\n按 Ctrl+C 停止系统")
        print("=" * 50)
        
        # 显示初始状态
        time.sleep(2)  # 等待服务完全启动
        self.display_status_info()
        
        # 5. 监控服务状态
        monitor_thread = threading.Thread(target=self.monitor_services)
        monitor_thread.daemon = True
        monitor_thread.start()
        
        # 6. 等待用户中断或服务异常
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
        import numpy as np
    except ImportError as e:
        print(f"❌ 缺少依赖包: {e}")
        print("请运行: pip install -r requirements.txt")
        return
    
    # 检查文件存在性
    if not os.path.exists("social_audio_service.py"):
        print("❌ 找不到 social_audio_service.py")
        print("请确保在正确的目录中运行此脚本")
        return
    
    # 启动服务管理器
    manager = SocialServiceManager()
    manager.run()

if __name__ == "__main__":
    main() 