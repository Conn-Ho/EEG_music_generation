#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Network Utilities for VPN Environment
VPN环境下的网络工具模块

提供多种网络配置和IP检测方法，适用于VPN环境
"""

import socket
import subprocess
import platform
import json
import requests
import netifaces
from typing import List, Dict, Optional, Tuple
import logging
import time

logger = logging.getLogger(__name__)

class NetworkDetector:
    """网络检测工具"""
    
    def __init__(self):
        self.system = platform.system().lower()
        
    def get_all_local_ips(self) -> List[Dict[str, str]]:
        """获取所有本地IP地址"""
        ips = []
        
        try:
            # 使用netifaces库获取所有网络接口
            for interface in netifaces.interfaces():
                addrs = netifaces.ifaddresses(interface)
                
                if netifaces.AF_INET in addrs:
                    for addr in addrs[netifaces.AF_INET]:
                        ip = addr.get('addr')
                        if ip and ip != '127.0.0.1':
                            # 判断IP类型
                            ip_type = self._classify_ip(ip, interface)
                            ips.append({
                                'ip': ip,
                                'interface': interface,
                                'type': ip_type,
                                'netmask': addr.get('netmask', ''),
                                'broadcast': addr.get('broadcast', '')
                            })
        except Exception as e:
            logger.warning(f"netifaces获取IP失败: {e}")
            
        # 备用方法：使用socket
        if not ips:
            ips.extend(self._get_ips_by_socket())
            
        return ips
    
    def _classify_ip(self, ip: str, interface: str) -> str:
        """分类IP地址类型"""
        interface_lower = interface.lower()
        
        # VPN接口识别
        vpn_keywords = ['tun', 'tap', 'vpn', 'ppp', 'utun', 'nordlynx', 'wg']
        if any(keyword in interface_lower for keyword in vpn_keywords):
            return 'vpn'
        
        # 局域网IP范围
        if (ip.startswith('192.168.') or 
            ip.startswith('10.') or 
            (ip.startswith('172.') and 16 <= int(ip.split('.')[1]) <= 31)):
            return 'lan'
        
        # 回环地址
        if ip.startswith('127.'):
            return 'loopback'
        
        # 其他可能是公网IP
        return 'public'
    
    def _get_ips_by_socket(self) -> List[Dict[str, str]]:
        """使用socket获取IP地址（备用方法）"""
        ips = []
        
        try:
            # 连接到不同的远程地址获取本地IP
            test_addresses = [
                ("8.8.8.8", 80),
                ("1.1.1.1", 80),
                ("114.114.114.114", 80)
            ]
            
            for addr, port in test_addresses:
                try:
                    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                    s.connect((addr, port))
                    ip = s.getsockname()[0]
                    s.close()
                    
                    if ip not in [item['ip'] for item in ips]:
                        ips.append({
                            'ip': ip,
                            'interface': 'unknown',
                            'type': self._classify_ip(ip, 'unknown'),
                            'netmask': '',
                            'broadcast': ''
                        })
                except Exception:
                    continue
                    
        except Exception as e:
            logger.warning(f"socket获取IP失败: {e}")
            
        return ips
    
    def get_recommended_ip(self) -> Optional[str]:
        """获取推荐的IP地址"""
        all_ips = self.get_all_local_ips()
        
        if not all_ips:
            return None
        
        # 优先级：局域网IP > VPN IP > 公网IP
        priorities = ['lan', 'vpn', 'public']
        
        for priority in priorities:
            for ip_info in all_ips:
                if ip_info['type'] == priority:
                    return ip_info['ip']
        
        # 如果都没找到，返回第一个非回环IP
        for ip_info in all_ips:
            if ip_info['type'] != 'loopback':
                return ip_info['ip']
                
        return '127.0.0.1'
    
    def display_network_info(self):
        """显示网络信息"""
        all_ips = self.get_all_local_ips()
        recommended = self.get_recommended_ip()
        
        print("🌐 网络接口信息:")
        print("=" * 60)
        
        if not all_ips:
            print("❌ 未检测到可用的网络接口")
            return
        
        # 按类型分组显示
        ip_by_type = {}
        for ip_info in all_ips:
            ip_type = ip_info['type']
            if ip_type not in ip_by_type:
                ip_by_type[ip_type] = []
            ip_by_type[ip_type].append(ip_info)
        
        type_names = {
            'lan': '🏠 局域网地址',
            'vpn': '🔒 VPN地址', 
            'public': '🌍 公网地址',
            'loopback': '🔄 回环地址'
        }
        
        for ip_type, type_name in type_names.items():
            if ip_type in ip_by_type:
                print(f"\n{type_name}:")
                for ip_info in ip_by_type[ip_type]:
                    status = "⭐ 推荐" if ip_info['ip'] == recommended else "  "
                    print(f"  {status} {ip_info['ip']} ({ip_info['interface']})")
        
        print(f"\n💡 推荐使用IP: {recommended}")
        print("=" * 60)

class NetworkScanner:
    """网络扫描工具"""
    
    def __init__(self):
        pass
    
    def scan_local_services(self, port: int = 8080, timeout: float = 1.0) -> List[str]:
        """扫描局域网内的服务"""
        detector = NetworkDetector()
        all_ips = detector.get_all_local_ips()
        
        # 获取局域网段
        lan_networks = []
        for ip_info in all_ips:
            if ip_info['type'] == 'lan':
                network = self._get_network_range(ip_info['ip'], ip_info['netmask'])
                if network:
                    lan_networks.append(network)
        
        # 扫描服务
        found_services = []
        for network in lan_networks:
            services = self._scan_network_services(network, port, timeout)
            found_services.extend(services)
        
        return found_services
    
    def _get_network_range(self, ip: str, netmask: str) -> Optional[str]:
        """获取网络范围"""
        try:
            import ipaddress
            if netmask:
                network = ipaddress.IPv4Network(f"{ip}/{netmask}", strict=False)
                return str(network.network_address)[:-2]  # 去掉最后的.0
            else:
                # 默认C类网络
                return '.'.join(ip.split('.')[:-1])
        except Exception:
            return '.'.join(ip.split('.')[:-1])
    
    def _scan_network_services(self, network_prefix: str, port: int, timeout: float) -> List[str]:
        """扫描网络段中的服务"""
        found_services = []
        
        # 只扫描部分IP范围以节省时间（1-20, 100-120）
        scan_ranges = list(range(1, 21)) + list(range(100, 121))
        
        print(f"🔍 扫描网络 {network_prefix}.x 端口 {port}...")
        
        for i in scan_ranges:
            ip = f"{network_prefix}.{i}"
            if self._check_service(ip, port, timeout):
                found_services.append(ip)
                print(f"✅ 发现服务: {ip}:{port}")
        
        return found_services
    
    def _check_service(self, ip: str, port: int, timeout: float) -> bool:
        """检查指定IP和端口的服务"""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            result = sock.connect_ex((ip, port))
            sock.close()
            return result == 0
        except Exception:
            return False

class VPNConfigHelper:
    """VPN配置助手"""
    
    def __init__(self):
        pass
    
    def detect_vpn_status(self) -> Dict[str, any]:
        """检测VPN状态"""
        detector = NetworkDetector()
        all_ips = detector.get_all_local_ips()
        
        vpn_ips = [ip for ip in all_ips if ip['type'] == 'vpn']
        lan_ips = [ip for ip in all_ips if ip['type'] == 'lan']
        
        return {
            'has_vpn': len(vpn_ips) > 0,
            'vpn_ips': vpn_ips,
            'lan_ips': lan_ips,
            'vpn_count': len(vpn_ips),
            'can_use_lan': len(lan_ips) > 0
        }
    
    def get_connection_recommendations(self) -> List[Dict[str, str]]:
        """获取连接建议"""
        vpn_status = self.detect_vpn_status()
        recommendations = []
        
        if vpn_status['has_vpn'] and vpn_status['can_use_lan']:
            # 有VPN但也有局域网
            recommendations.append({
                'method': 'local_lan',
                'title': '🏠 使用局域网直连（推荐）',
                'description': '绕过VPN，使用局域网IP进行直接连接',
                'ips': [ip['ip'] for ip in vpn_status['lan_ips']],
                'steps': [
                    '1. 主设备使用局域网IP启动服务',
                    '2. 客户端输入主设备的局域网IP',
                    '3. 确保两台设备在同一WiFi网络'
                ]
            })
            
        if vpn_status['has_vpn']:
            # VPN环境
            recommendations.append({
                'method': 'vpn_network',
                'title': '🔒 通过VPN网络连接',
                'description': '使用VPN虚拟网络进行连接',
                'ips': [ip['ip'] for ip in vpn_status['vpn_ips']],
                'steps': [
                    '1. 确保两台设备连接到相同的VPN服务器',
                    '2. 使用VPN分配的IP地址',
                    '3. 检查VPN是否允许P2P连接'
                ]
            })
        
        # 备用方案
        recommendations.append({
            'method': 'hotspot',
            'title': '📱 手机热点方案',
            'description': '使用手机热点创建独立网络',
            'ips': ['通常是192.168.43.x'],
            'steps': [
                '1. 一台设备开启手机热点',
                '2. 另一台设备连接该热点',
                '3. 使用热点网络IP进行连接'
            ]
        })
        
        recommendations.append({
            'method': 'cloud_relay',
            'title': '☁️ 云端中继服务',
            'description': '通过云服务器中继数据',
            'ips': ['需要配置云服务器'],
            'steps': [
                '1. 部署云端中继服务',
                '2. 两台设备连接到云服务器',
                '3. 通过云端转发情绪数据'
            ]
        })
        
        return recommendations
    
    def display_recommendations(self):
        """显示连接建议"""
        recommendations = self.get_connection_recommendations()
        
        print("🔧 VPN环境连接方案:")
        print("=" * 60)
        
        for i, rec in enumerate(recommendations, 1):
            print(f"\n方案 {i}: {rec['title']}")
            print(f"描述: {rec['description']}")
            
            if rec['ips'] and rec['ips'][0] != '需要配置云服务器':
                print(f"可用IP: {', '.join(rec['ips'])}")
            
            print("操作步骤:")
            for step in rec['steps']:
                print(f"  {step}")
        
        print("=" * 60)

def get_best_connection_config() -> Dict[str, any]:
    """获取最佳连接配置"""
    detector = NetworkDetector()
    vpn_helper = VPNConfigHelper()
    scanner = NetworkScanner()
    
    # 显示网络信息
    detector.display_network_info()
    
    # 检测VPN状态
    vpn_status = vpn_helper.detect_vpn_status()
    
    if vpn_status['has_vpn']:
        print("\n🔒 检测到VPN连接")
        vpn_helper.display_recommendations()
        
        # 让用户选择连接方式
        print("\n请选择连接方式:")
        recommendations = vpn_helper.get_connection_recommendations()
        
        for i, rec in enumerate(recommendations, 1):
            print(f"{i}. {rec['title']}")
        
        while True:
            try:
                choice = int(input(f"选择方案 (1-{len(recommendations)}): ").strip())
                if 1 <= choice <= len(recommendations):
                    selected = recommendations[choice - 1]
                    break
                else:
                    print("❌ 无效选择，请重新输入")
            except ValueError:
                print("❌ 请输入数字")
    else:
        print("\n✅ 未检测到VPN，使用标准局域网连接")
        selected = {
            'method': 'standard_lan',
            'title': '🏠 标准局域网连接',
            'ips': [detector.get_recommended_ip()]
        }
    
    # 如果选择局域网方案，尝试扫描现有服务
    if selected['method'] in ['local_lan', 'standard_lan']:
        print("\n🔍 扫描局域网中的现有服务...")
        found_services = scanner.scan_local_services()
        
        if found_services:
            print(f"\n✅ 发现 {len(found_services)} 个运行中的服务:")
            for service_ip in found_services:
                print(f"  - {service_ip}:8080")
            
            use_existing = input("\n是否连接到现有服务？(y/n): ").strip().lower()
            if use_existing in ['y', 'yes', '是']:
                selected['existing_services'] = found_services
    
    return selected

def main():
    """主函数 - 网络配置向导"""
    print("🌐 VPN环境网络配置向导")
    print("=" * 60)
    
    config = get_best_connection_config()
    
    print(f"\n✅ 推荐配置: {config['title']}")
    
    if config.get('ips'):
        print(f"建议IP: {config['ips'][0]}")
    
    if config.get('existing_services'):
        print(f"可连接的现有服务: {config['existing_services']}")

if __name__ == "__main__":
    main() 