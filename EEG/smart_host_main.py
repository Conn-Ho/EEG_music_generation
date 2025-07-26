#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Smart Host Device Service Manager for Social EEG Music System
智能社交EEG音乐系统主设备服务管理器

支持VPN环境下的智能网络配置和多种连接方案

使用方法:
python smart_host_main.py
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
from network_utils import NetworkDetector, VPNConfigHelper, NetworkScanner

class SmartSocialServiceManager:
    def __init__(self):
        self.social_audio_process = None
        self.local_brain_process = None
        self.running = True
        self.local_user_id = None
        self.network_config = None
        
        # 初始化网络工具
        self.network_detector = NetworkDetector()
        self.vpn_helper = VPNConfigHelper()
        self.network_scanner = NetworkScanner()
        
    def setup_network_configuration(self):
        """配置网络连接"""
        print("🌐 智能网络配置中...")
        print("=" * 60)
        
        # 检测网络状态
        vpn_status = self.vpn_helper.detect_vpn_status()
        all_ips = self.network_detector.get_all_local_ips()
        
        print(f"检测到 {len(all_ips)} 个网络接口")
        if vpn_status['has_vpn']:
            print(f"🔒 VPN状态: 已连接 ({vpn_status['vpn_count']} 个)")
        else:
            print("✅ VPN状态: 未检测到")
        
        # 显示详细网络信息
        self.network_detector.display_network_info()
        
        # 获取连接建议
        if vpn_status['has_vpn']:
            print("\n🔧 VPN环境连接方案:")
            recommendations = self.vpn_helper.get_connection_recommendations()
            
            print("可选方案:")
            for i, rec in enumerate(recommendations, 1):
                print(f"{i}. {rec['title']}")
                if rec.get('ips') and rec['ips'][0] != '需要配置云服务器':
                    print(f"   可用IP: {', '.join(rec['ips'])}")
            
            # 让用户选择
            while True:
                try:
                    choice = input(f"\n选择方案 (1-{len(recommendations)}, 回车使用推荐): ").strip()
                    
                    if not choice:
                        # 使用第一个推荐方案
                        self.network_config = recommendations[0]
                        break
                    
                    choice_num = int(choice)
                    if 1 <= choice_num <= len(recommendations):
                        self.network_config = recommendations[choice_num - 1]
                        break
                    else:
                        print("❌ 无效选择，请重新输入")
                except ValueError:
                    print("❌ 请输入数字")
        else:
            # 无VPN环境，使用标准配置
            recommended_ip = self.network_detector.get_recommended_ip()
            self.network_config = {
                'method': 'standard_lan',
                'title': '🏠 标准局域网连接',
                'ips': [recommended_ip],
                'description': '标准局域网直连'
            }
        
        print(f"\n✅ 已选择: {self.network_config['title']}")
        
        # 获取服务IP
        if self.network_config.get('ips'):
            service_ip = self.network_config['ips'][0]
        else:
            service_ip = self.network_detector.get_recommended_ip()
        
        return service_ip
    
    def display_connection_info(self, service_ip: str):
        """显示连接信息"""
        print("\n" + "=" * 60)
        print("🏠 EEG音乐社交系统 - 智能主设备")
        print("=" * 60)
        print(f"📡 服务地址: http://{service_ip}:8080")
        print(f"🔗 连接方案: {self.network_config['title']}")
        print(f"🌐 服务IP: {service_ip}")
        
        # 显示客户端连接指导
        print("\n📋 客户端连接信息:")
        print(f"   主设备IP: {service_ip}")
        print(f"   服务端口: 8080")
        print(f"   完整地址: http://{service_ip}:8080")
        
        # 根据连接方案给出特殊说明
        if self.network_config['method'] == 'local_lan':
            print("\n💡 VPN环境说明:")
            print("   - 使用局域网IP绕过VPN")
            print("   - 客户端也需选择同样的局域网连接方案")
            print("   - 确保两台设备在同一WiFi网络下")
        elif self.network_config['method'] == 'vpn_network':
            print("\n💡 VPN连接说明:")
            print("   - 使用VPN虚拟网络")
            print("   - 客户端需连接到相同VPN服务器")
            print("   - 检查VPN是否允许P2P通信")
        elif self.network_config['method'] == 'hotspot':
            print("\n💡 热点连接说明:")
            print("   - 请开启手机热点")
            print("   - 客户端连接到同一热点")
        
        print("=" * 60)
    
    def scan_for_conflicts(self, port: int = 8080) -> bool:
        """检查端口冲突"""
        print(f"🔍 检查端口 {port} 是否可用...")
        
        try:
            # 检查本地端口
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            result = sock.connect_ex(('127.0.0.1', port))
            sock.close()
            
            if result == 0:
                print(f"⚠️  端口 {port} 已被占用")
                
                # 尝试连接看是否是我们的服务
                try:
                    response = requests.get(f"http://127.0.0.1:{port}/health", timeout=2)
                    if response.status_code == 200:
                        data = response.json()
                        if 'Social EEG' in data.get('service', ''):
                            print("✅ 检测到已运行的社交音频服务")
                            return False  # 服务已运行，不需要重新启动
                except Exception:
                    pass
                
                print("❌ 端口被其他服务占用，请关闭相关服务或更换端口")
                return False
            else:
                print(f"✅ 端口 {port} 可用")
                return True
                
        except Exception as e:
            print(f"⚠️  端口检查失败: {e}")
            return True  # 假设可用
    
    def start_social_audio_service(self):
        """启动社交音频生成服务"""
        print("🎵 启动社交音频生成服务...")
        
        # 检查端口可用性
        if not self.scan_for_conflicts():
            response = input("发现端口冲突，是否强制继续？(y/n): ").strip().lower()
            if response not in ['y', 'yes', '是']:
                return False
        
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
        print("\n🧠 本地EEG设备配置:")
        use_local_eeg = input("是否在主设备上也使用EEG设备？ (y/n): ").strip().lower()
        
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
            device_info = f"SmartHost_{socket.gethostname()}"
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
    
    def display_detailed_status(self):
        """显示详细状态信息"""
        status = self.get_service_status()
        if status:
            print(f"\n📊 系统详细状态:")
            print(f"   🎵 音乐生成: {'✅ 运行中' if status.get('is_playing') else '❌ 停止'}")
            print(f"   👥 总用户数: {status.get('user_count', 0)} 人")
            print(f"   💪 活跃用户: {status.get('active_user_count', 0)} 人")
            print(f"   🌐 WebSocket连接: {status.get('websocket_connections', 0)}")
            print(f"   🎼 当前风格: {status.get('current_prompt', 'N/A')}")
            print(f"   🔊 当前强度: {status.get('current_intensity', 0):.2f}")
            
            if status.get('current_fused_emotion'):
                fused = status['current_fused_emotion']
                print(f"   😊 融合情绪: {fused.get('primary_emotion')} ({fused.get('fusion_intensity', 0):.2f})")
                print(f"   🔀 融合方法: {fused.get('fusion_method')}")
                
                if fused.get('secondary_emotion'):
                    print(f"   🎭 次要情绪: {fused.get('secondary_emotion')}")
            
            if status.get('users'):
                print(f"   👤 用户列表:")
                for user in status['users']:
                    active_symbol = "🟢" if user.get('is_active') else "🔴"
                    emotion = user.get('last_emotion', 'N/A')
                    intensity = user.get('last_intensity', 0) if user.get('last_intensity') else 0
                    print(f"      {active_symbol} {user['user_id']}: {emotion} ({intensity:.2f})")
        else:
            print("\n❌ 无法获取服务状态")
    
    def scan_for_clients(self):
        """扫描网络中的潜在客户端"""
        if self.network_config and self.network_config['method'] in ['local_lan', 'standard_lan']:
            print("\n🔍 扫描网络中的设备...")
            
            # 这里可以添加更复杂的客户端发现逻辑
            # 比如mDNS广播、UDP广播等
            
            found_devices = self.network_scanner.scan_local_services(port=22)  # SSH端口作为设备检测
            if found_devices:
                print(f"🖥️  发现 {len(found_devices)} 台设备在网络中")
                print("💡 客户端可能运行在这些设备上")
    
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
        status_interval = 90.0  # 90秒显示一次详细状态
        simple_check_interval = 15.0  # 15秒检查一次连接
        last_simple_check = time.time()
        
        while self.running:
            time.sleep(5)
            current_time = time.time()
            
            # 检查社交音频服务
            if self.social_audio_process and self.social_audio_process.poll() is not None:
                print("❌ 社交音频服务意外停止")
                self.running = False
                break
            
            # 检查本地脑波处理服务
            if self.local_brain_process and self.local_brain_process.poll() is not None:
                print("❌ 本地脑波处理服务意外停止")
                self.local_brain_process = None
            
            # 简单连接检查
            if current_time - last_simple_check >= simple_check_interval:
                status = self.get_service_status()
                if status:
                    active_users = status.get('active_user_count', 0)
                    if active_users > 0:
                        print(f"💓 系统运行正常 - {active_users} 个活跃用户")
                last_simple_check = current_time
            
            # 详细状态显示
            if current_time - last_status_time >= status_interval:
                self.display_detailed_status()
                last_status_time = current_time
    
    def run(self):
        """启动整个系统"""
        # 设置信号处理
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)
        
        print("🚀 智能社交EEG音乐生成系统启动中...")
        
        # 1. 网络配置
        service_ip = self.setup_network_configuration()
        if not service_ip:
            print("❌ 网络配置失败")
            return
        
        # 2. 显示连接信息
        self.display_connection_info(service_ip)
        
        print("\n🚀 服务启动序列...")
        print("=" * 50)
        
        # 3. 启动社交音频服务
        if not self.start_social_audio_service():
            return
        
        # 4. 等待社交音频服务就绪
        if not self.wait_for_social_audio_service():
            self.stop_services()
            return
        
        # 5. 启动本地脑波处理服务（可选）
        if not self.start_local_brain_processor():
            print("⚠️  本地脑波处理服务启动失败，但不影响远程用户连接")
        
        # 6. 本地用户加入会话（如果有本地EEG）
        self.join_local_session()
        
        # 7. 扫描潜在客户端
        self.scan_for_clients()
        
        print("\n🎯 智能社交音频服务已成功启动!")
        print("📊 系统状态监控中...")
        print("🔗 等待客户端用户连接...")
        if self.local_user_id:
            print("🎧 请戴上你的Emotiv EEG设备（本地用户）")
        print("🎵 音乐将根据所有用户的情绪实时变化")
        print("⏱️  情绪数据每5秒更新一次")
        print("\n按 Ctrl+C 停止系统")
        print("=" * 50)
        
        # 显示初始状态
        time.sleep(3)  # 等待服务完全启动
        self.display_detailed_status()
        
        # 8. 监控服务状态
        monitor_thread = threading.Thread(target=self.monitor_services)
        monitor_thread.daemon = True
        monitor_thread.start()
        
        # 9. 等待用户中断或服务异常
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
        import netifaces
    except ImportError as e:
        print(f"❌ 缺少依赖包: {e}")
        print("请运行: pip install -r requirements.txt")
        return
    
    # 检查文件存在性
    required_files = ["social_audio_service.py", "network_utils.py"]
    missing_files = []
    
    for file in required_files:
        if not os.path.exists(file):
            missing_files.append(file)
    
    if missing_files:
        print(f"❌ 缺少文件: {', '.join(missing_files)}")
        print("请确保在正确的目录中运行此脚本")
        return
    
    # 启动智能服务管理器
    manager = SmartSocialServiceManager()
    manager.run()

if __name__ == "__main__":
    main() 