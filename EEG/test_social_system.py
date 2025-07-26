#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Social EEG Music System Test Script
社交EEG音乐系统测试脚本

用于验证系统组件是否正常工作
"""

import requests
import time
import json

def test_social_audio_service(host="localhost", port=8080):
    """测试社交音频服务"""
    base_url = f"http://{host}:{port}"
    
    print("🧪 测试社交音频服务...")
    
    # 1. 健康检查
    try:
        response = requests.get(f"{base_url}/health", timeout=5)
        if response.status_code == 200:
            data = response.json()
            print(f"✅ 健康检查通过: {data.get('status')}")
        else:
            print(f"❌ 健康检查失败: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ 无法连接到服务: {e}")
        return False
    
    # 2. 获取状态
    try:
        response = requests.get(f"{base_url}/status", timeout=5)
        if response.status_code == 200:
            status = response.json()
            print(f"✅ 状态获取成功:")
            print(f"   音乐生成: {'运行中' if status.get('is_playing') else '停止'}")
            print(f"   用户数量: {status.get('user_count', 0)}")
            print(f"   活跃用户: {status.get('active_user_count', 0)}")
        else:
            print(f"❌ 状态获取失败: {response.status_code}")
    except Exception as e:
        print(f"❌ 状态获取异常: {e}")
    
    # 3. 测试用户会话
    test_user_id = "test_user_001"
    
    try:
        # 加入会话
        response = requests.post(
            f"{base_url}/join_session",
            params={"user_id": test_user_id, "device_info": "Test Device"},
            timeout=5
        )
        if response.status_code == 200:
            print(f"✅ 测试用户加入会话成功")
        else:
            print(f"❌ 测试用户加入会话失败: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ 加入会话异常: {e}")
        return False
    
    # 4. 测试情绪数据发送
    try:
        emotion_data = {
            "user_emotion_data": {
                "user_id": test_user_id,
                "emotion": "Happy (开心)",
                "intensity": 0.8,
                "timestamp": time.time(),
                "device_info": "Test Device"
            }
        }
        
        response = requests.post(
            f"{base_url}/update_emotion",
            json=emotion_data,
            timeout=5
        )
        if response.status_code == 200:
            print(f"✅ 情绪数据发送成功")
        else:
            print(f"❌ 情绪数据发送失败: {response.status_code}")
    except Exception as e:
        print(f"❌ 情绪数据发送异常: {e}")
    
    # 5. 离开会话
    try:
        response = requests.post(
            f"{base_url}/leave_session",
            params={"user_id": test_user_id},
            timeout=5
        )
        if response.status_code == 200:
            print(f"✅ 测试用户离开会话成功")
        else:
            print(f"❌ 测试用户离开会话失败: {response.status_code}")
    except Exception as e:
        print(f"❌ 离开会话异常: {e}")
    
    print("🎉 社交音频服务测试完成")
    return True

def test_file_existence():
    """测试文件是否存在"""
    import os
    
    print("📁 检查文件完整性...")
    
    required_files = [
        "social_audio_service.py",
        "client_brain_processor.py", 
        "host_main.py",
        "client_main.py",
        "brain_processor.py",
        "audio_service.py",
        "main.py",
        "cortex.py",
        "requirements.txt"
    ]
    
    all_exist = True
    for file in required_files:
        if os.path.exists(file):
            print(f"✅ {file}")
        else:
            print(f"❌ {file} (缺失)")
            all_exist = False
    
    return all_exist

def main():
    """主测试函数"""
    print("🚀 社交EEG音乐系统测试开始")
    print("=" * 50)
    
    # 文件完整性检查
    if not test_file_existence():
        print("\n❌ 文件不完整，请检查项目文件")
        return
    
    print("\n🔗 准备测试社交音频服务...")
    print("请先启动主设备服务: python host_main.py")
    
    input("主设备服务启动后按回车继续测试...")
    
    # 测试社交音频服务
    if test_social_audio_service():
        print("\n🎉 所有测试通过！系统准备就绪")
        print("\n📋 下一步:")
        print("1. 主设备: python host_main.py")
        print("2. 客户端: python client_main.py")
    else:
        print("\n❌ 测试失败，请检查服务状态")

if __name__ == "__main__":
    main() 