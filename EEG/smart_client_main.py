#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Smart Client Service Manager for Social EEG Music System
智能社交EEG音乐系统客户端服务管理器

支持VPN环境下的智能网络配置和自动主设备发现

使用方法:
python smart_client_main.py
"""

import subprocess
import time
import signal
import sys
import os
import socket
import requests
from network_utils import NetworkDetector, VPNConfigHelper, NetworkScanner

class SmartClientServiceManager:
    def __init__(self):
        self.client_brain_process = None
        self.running = True
        self.network_config = None
        self.host_ip = None
        
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
                    print(f"   本机IP: {', '.join(rec['ips'])}")
            
            # 让用户选择
            while True:
                try:
                    choice = input(f"\n选择连接方案 (1-{len(recommendations)}, 回车使用推荐): ").strip()
                    
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
            self.network_config = {
                'method': 'standard_lan',
                'title': '🏠 标准局域网连接',
                'description': '标准局域网直连'
            }
        
        print(f"\n✅ 已选择: {self.network_config['title']}")
        return True
    
    def discover_host_services(self) -> list:
        """发现主设备服务"""
        print("\n🔍 正在扫描网络中的主设备服务...")
        
        # 根据网络配置选择扫描策略
        if self.network_config['method'] in ['local_lan', 'standard_lan']:
            # 扫描局域网
            found_services = self.network_scanner.scan_local_services(port=8080, timeout=2.0)
            
            if found_services:
                print(f"✅ 发现 {len(found_services)} 个可能的主设备服务:")
                
                # 验证服务
                valid_services = []
                for service_ip in found_services:
                    if self._verify_social_audio_service(service_ip):
                        valid_services.append(service_ip)
                        print(f"  ✅ {service_ip}:8080 - 社交音频服务")
                    else:
                        print(f"  ❌ {service_ip}:8080 - 非目标服务")
                
                return valid_services
            else:
                print("❌ 未发现运行中的服务")
                return []
        
        elif self.network_config['method'] == 'vpn_network':
            print("💡 VPN网络模式：请手动输入主设备的VPN IP地址")
            return []
        
        else:
            print("💡 其他连接模式：请手动输入主设备IP地址")
            return []
    
    def _verify_social_audio_service(self, ip: str) -> bool:
        """验证是否为社交音频服务"""
        try:
            response = requests.get(f"http://{ip}:8080/health", timeout=3)
            if response.status_code == 200:
                data = response.json()
                service_name = data.get('service', '')
                return 'Social EEG' in service_name or 'EEG Audio' in service_name
            return False
        except Exception:
            return False
    
    def get_host_ip_from_user(self, discovered_services: list) -> str:
        """从用户获取主设备IP"""
        if discovered_services:
            print(f"\n🎯 发现的主设备服务:")
            for i, service_ip in enumerate(discovered_services, 1):
                print(f"  {i}. {service_ip}")
            
            print(f"  {len(discovered_services) + 1}. 手动输入其他IP地址")
            
            while True:
                try:
                    choice = input(f"\n选择主设备 (1-{len(discovered_services) + 1}): ").strip()
                    
                    if choice.isdigit():
                        choice_num = int(choice)
                        if 1 <= choice_num <= len(discovered_services):
                            return discovered_services[choice_num - 1]
                        elif choice_num == len(discovered_services) + 1:
                            # 手动输入
                            break
                        else:
                            print("❌ 无效选择，请重新输入")
                    else:
                        print("❌ 请输入数字")
                except ValueError:
                    print("❌ 请输入数字")
        
        # 手动输入IP地址
        print("\n📝 手动输入主设备IP地址:")
        
        if self.network_config['method'] == 'local_lan':
            print("💡 使用局域网IP（通常是192.168.x.x格式）")
        elif self.network_config['method'] == 'vpn_network':
            print("💡 使用VPN分配的IP地址")
            if self.network_config.get('ips'):
                print(f"   参考本机VPN IP: {', '.join(self.network_config['ips'])}")
        
        while True:
            user_input = input("主设备IP地址: ").strip()
            
            if not user_input:
                print("❌ IP地址不能为空")
                continue
            
            # 简单验证IP地址格式
            parts = user_input.split('.')
            if len(parts) == 4 and all(part.isdigit() and 0 <= int(part) <= 255 for part in parts):
                # 测试连接
                print(f"🔍 测试连接到 {user_input}...")
                if self._verify_social_audio_service(user_input):
                    print("✅ 连接测试成功！")
                    return user_input
                else:
                    retry = input("❌ 无法连接到服务，是否重试？(y/n): ").strip().lower()
                    if retry not in ['y', 'yes', '是']:
                        return user_input  # 用户坚持使用这个IP
            else:
                print("❌ 无效的IP地址格式，请重新输入")
    
    def display_client_info(self):
        """显示客户端信息"""
        hostname = socket.gethostname()
        client_ip = self.network_detector.get_recommended_ip()
        
        print("\n" + "=" * 60)
        print("📱 EEG音乐社交系统 - 智能客户端")
        print("=" * 60)
        print(f"🖥️  设备名称: {hostname}")
        print(f"🌐 本机IP: {client_ip}")
        print(f"🔗 连接方案: {self.network_config['title']}")
        if self.host_ip:
            print(f"🎯 目标主设备: {self.host_ip}:8080")
        
        # 根据连接方案给出说明
        if self.network_config['method'] == 'local_lan':
            print("\n💡 局域网连接说明:")
            print("   - 绕过VPN使用局域网直连")
            print("   - 确保与主设备在同一WiFi网络")
        elif self.network_config['method'] == 'vpn_network':
            print("\n💡 VPN连接说明:")
            print("   - 通过VPN虚拟网络连接")
            print("   - 确保连接到相同VPN服务器")
        
        print("=" * 60)
    
    def start_client_brain_processor(self):
        """启动客户端脑波数据处理服务"""
        print("🧠 启动智能客户端脑波数据处理服务...")
        
        if not self.host_ip:
            print("❌ 未指定主设备IP地址")
            return False
        
        try:
            # 设置环境变量传递主设备IP
            env = os.environ.copy()
            env['HOST_DEVICE_IP'] = self.host_ip
            env['NETWORK_METHOD'] = self.network_config['method']
            
            self.client_brain_process = subprocess.Popen(
                [sys.executable, "client_brain_processor.py"],
                cwd=os.path.dirname(os.path.abspath(__file__)),
                env=env
            )
            print("✅ 智能客户端脑波数据处理服务已启动 (PID: {})".format(self.client_brain_process.pid))
        except Exception as e:
            print(f"❌ 启动客户端脑波处理服务失败: {e}")
            return False
        return True
    
    def monitor_connection(self):
        """监控连接状态"""
        if not self.host_ip:
            return
        
        last_check = time.time()
        check_interval = 30.0  # 30秒检查一次
        
        while self.running:
            time.sleep(5)
            current_time = time.time()
            
            # 检查客户端脑波处理服务
            if self.client_brain_process and self.client_brain_process.poll() is not None:
                print("❌ 客户端脑波处理服务意外停止")
                self.running = False
                break
            
            # 定期检查与主设备的连接
            if current_time - last_check >= check_interval:
                if self._verify_social_audio_service(self.host_ip):
                    print(f"💓 与主设备连接正常 ({self.host_ip})")
                else:
                    print(f"⚠️  与主设备连接异常 ({self.host_ip})")
                last_check = current_time
    
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
    
    def run(self):
        """启动客户端系统"""
        # 设置信号处理
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)
        
        print("🚀 智能客户端EEG音乐系统启动中...")
        
        # 1. 网络配置
        if not self.setup_network_configuration():
            print("❌ 网络配置失败")
            return
        
        # 2. 发现主设备服务
        discovered_services = self.discover_host_services()
        
        # 3. 获取主设备IP
        self.host_ip = self.get_host_ip_from_user(discovered_services)
        if not self.host_ip:
            print("❌ 未指定主设备IP")
            return
        
        # 4. 显示客户端信息
        self.display_client_info()
        
        print("\n🚀 客户端启动序列...")
        print("=" * 50)
        
        # 5. 启动客户端脑波处理服务
        if not self.start_client_brain_processor():
            return
        
        print("\n🎯 智能客户端服务已成功启动!")
        print("📊 连接到主设备中...")
        print("🎧 请戴上你的Emotiv EEG设备")
        print("🎵 你的情绪将与其他用户融合生成音乐")
        print("⏱️  情绪数据每5秒发送一次")
        print("\n按 Ctrl+C 停止客户端")
        print("=" * 50)
        
        # 6. 监控连接状态
        import threading
        monitor_thread = threading.Thread(target=self.monitor_connection)
        monitor_thread.daemon = True
        monitor_thread.start()
        
        # 7. 等待用户中断或服务异常
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
        import netifaces
    except ImportError as e:
        print(f"❌ 缺少依赖包: {e}")
        print("请运行: pip install -r requirements.txt")
        return
    
    # 检查文件存在性
    required_files = ["client_brain_processor.py", "network_utils.py", "cortex.py"]
    missing_files = []
    
    for file in required_files:
        if not os.path.exists(file):
            missing_files.append(file)
    
    if missing_files:
        print(f"❌ 缺少文件: {', '.join(missing_files)}")
        print("请确保在正确的目录中运行此脚本")
        return
    
    # 启动智能客户端服务管理器
    manager = SmartClientServiceManager()
    manager.run()

if __name__ == "__main__":
    main() 