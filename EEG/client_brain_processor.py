#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Client EEG Brain Wave Data Processor Service
客户端脑波数据处理服务

负责：
1. 连接Emotiv EEG设备获取脑波数据
2. 实时分析情绪状态
3. 通过HTTP API向主设备的社交音频服务发送情绪数据
4. 不生成音乐，仅作为情绪数据源
"""

import math
import logging
import asyncio
import requests
import time
import socket
import uuid
from cortex import Cortex
from typing import Dict, Any, Optional
import json

# ========================================================================================
# 全局配置与日志 (Global Configuration & Logging)
# ========================================================================================

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- 凭证配置 ---
# Emotiv App Credentials
YOUR_APP_CLIENT_ID = '6OV53rWuPZiJo6419CHi4ppabSdqKpTgfYCU5mvV'
YOUR_APP_CLIENT_SECRET = 'XMWhqlpRTnQfe8a0b363jYFD976u7Ar17mQw2IWJT6eS2Z5LllaMckJbfbrSEqJYZ2LBpru6cvusWDapvjPSPutglsUwgNXYUzzcLKZqIhYOV52Rcy0YilZDJwoaQWnE'

# --- 主设备配置 ---
# 用户需要配置主设备的IP地址
HOST_DEVICE_IP = '30.201.218.19'  # 主设备的实际IP地址
HOST_DEVICE_PORT = 8080
SOCIAL_AUDIO_SERVICE_URL = f'http://{HOST_DEVICE_IP}:{HOST_DEVICE_PORT}'
EMOTION_UPDATE_ENDPOINT = '/update_emotion'
JOIN_SESSION_ENDPOINT = '/join_session'
LEAVE_SESSION_ENDPOINT = '/leave_session'

# ========================================================================================
# 情绪识别模块 (Emotion Recognition Module)
# ========================================================================================

EMOTION_MAP = {
    "Happy": "Happy (开心)",
    "Excited": "Excited (激动)",
    "Surprised": "Surprised (惊喜)",
    "Fear": "Fear (恐惧)",
    "Angry": "Angry (愤怒)",
    "Contempt": "Contempt (轻蔑)",
    "Disgust": "Disgust (厌恶)",
    "Miserable": "Miserable (痛苦)",
    "Sad": "Sad (悲伤)",
    "Depressed": "Depressed (沮丧)",
    "Bored": "Bored (无聊)",
    "Tired": "Tired (疲倦)",
    "Sleepy": "Sleepy (困倦)",
    "Relaxed": "Relaxed (放松)",
    "Pleased": "Pleased (平静)",
    "Neutral": "Neutral (中性)"
}

def normalize_emotion_name(emotion: str) -> str:
    """标准化情绪名称"""
    return EMOTION_MAP.get(emotion, "Neutral (中性)")

def calculate_emotion_intensity(emotion_data: Dict[str, Any]) -> float:
    """计算情绪强度"""
    try:
        # 从情绪数据中提取强度值
        if 'score' in emotion_data:
            return min(max(emotion_data['score'], 0.0), 1.0)
        elif 'confidence' in emotion_data:
            return min(max(emotion_data['confidence'], 0.0), 1.0)
        else:
            # 如果没有明确的强度值，使用默认值
            return 0.5
    except Exception as e:
        logger.warning(f"计算情绪强度失败: {e}")
        return 0.5

# ========================================================================================
# 社交音频服务客户端 (Social Audio Service Client)
# ========================================================================================

class SocialAudioServiceClient:
    """社交音频服务客户端"""
    
    def __init__(self, service_url: str, user_id: str):
        self.service_url = service_url
        self.user_id = user_id
        self.device_info = self._get_device_info()
        self.session_active = False
        
        logger.info(f"初始化社交音频服务客户端: {service_url}")
        logger.info(f"用户ID: {user_id}")
        logger.info(f"设备信息: {self.device_info}")
    
    def _get_device_info(self) -> str:
        """获取设备信息"""
        try:
            hostname = socket.gethostname()
            ip = socket.gethostbyname(hostname)
            return f"{hostname}({ip})"
        except Exception:
            return "Unknown Device"
    
    def check_service_health(self) -> bool:
        """检查社交音频服务健康状态"""
        try:
            response = requests.get(f"{self.service_url}/health", timeout=3)
            if response.status_code == 200:
                data = response.json()
                logger.info(f"主设备服务状态: {data.get('status')}")
                return data.get('status') == 'healthy'
            return False
        except requests.exceptions.RequestException as e:
            logger.warning(f"检查服务健康状态失败: {e}")
            return False
    
    def join_session(self) -> bool:
        """加入会话"""
        try:
            response = requests.post(
                f"{self.service_url}{JOIN_SESSION_ENDPOINT}",
                params={
                    "user_id": self.user_id,
                    "device_info": self.device_info
                },
                timeout=5
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get('status') == 'success':
                    self.session_active = True
                    logger.info(f"成功加入会话: {data.get('message')}")
                    return True
            
            logger.error(f"加入会话失败: {response.status_code} - {response.text}")
            return False
            
        except requests.exceptions.RequestException as e:
            logger.error(f"加入会话请求失败: {e}")
            return False
    
    def leave_session(self) -> bool:
        """离开会话"""
        try:
            response = requests.post(
                f"{self.service_url}{LEAVE_SESSION_ENDPOINT}",
                params={"user_id": self.user_id},
                timeout=5
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get('status') == 'success':
                    self.session_active = False
                    logger.info(f"成功离开会话: {data.get('message')}")
                    return True
            
            logger.warning(f"离开会话失败: {response.status_code} - {response.text}")
            return False
            
        except requests.exceptions.RequestException as e:
            logger.warning(f"离开会话请求失败: {e}")
            return False
    
    def send_emotion_data(self, emotion: str, intensity: float) -> bool:
        """发送情绪数据到主设备"""
        try:
            # 构建请求数据
            emotion_data = {
                "user_emotion_data": {
                    "user_id": self.user_id,
                    "emotion": emotion,
                    "intensity": intensity,
                    "timestamp": time.time(),
                    "device_info": self.device_info
                }
            }
            
            # 发送POST请求
            response = requests.post(
                f"{self.service_url}{EMOTION_UPDATE_ENDPOINT}",
                json=emotion_data,
                timeout=3,
                headers={'Content-Type': 'application/json'}
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get('status') == 'success':
                    logger.debug(f"情绪数据发送成功: {emotion} ({intensity:.2f})")
                    return True
                else:
                    logger.warning(f"情绪数据处理失败: {data.get('message')}")
                    return False
            else:
                logger.warning(f"发送情绪数据失败: {response.status_code} - {response.text}")
                return False
                
        except requests.exceptions.RequestException as e:
            logger.warning(f"发送情绪数据网络错误: {e}")
            return False
        except Exception as e:
            logger.error(f"发送情绪数据失败: {e}")
            return False

# ========================================================================================
# 客户端EEG数据处理器 (Client EEG Data Processor)
# ========================================================================================

class ClientEEGDataProcessor:
    """客户端EEG数据处理器"""
    
    def __init__(self, client_id: str, client_secret: str, audio_client: SocialAudioServiceClient):
        self.client_id = client_id
        self.client_secret = client_secret
        self.audio_client = audio_client
        
        # Cortex相关
        self.cortex = None
        self.streams = ['met']  # 只需要情绪数据流
        self.is_connected = False
        
        # 情绪数据缓存和状态管理
        self.last_emotion_time = 0
        self.emotion_update_interval = 5.0  # 5秒更新一次
        self.current_emotion = "Neutral (中性)"
        self.current_intensity = 0.0
        
        # 统计信息
        self.total_data_received = 0
        self.total_emotions_sent = 0
        self.connection_attempts = 0
        
        logger.info(f"客户端EEG数据处理器初始化完成 (用户: {audio_client.user_id})")
    
    def start(self, streams: list):
        """启动EEG数据采集"""
        try:
            logger.info("初始化Cortex连接...")
            
            # 初始化Cortex
            self.cortex = Cortex(user=self.client_id, 
                               password=self.client_secret,
                               debug=False)
            
            # 设置回调函数
            self.cortex.bind(create_session_done=self.on_create_session_done)
            self.cortex.bind(query_headset_done=self.on_query_headset_done) 
            self.cortex.bind(connect_headset_done=self.on_connect_headset_done)
            self.cortex.bind(request_access_done=self.on_request_access_done)
            self.cortex.bind(authorize_done=self.on_authorize_done)
            self.cortex.bind(create_record_done=self.on_create_record_done)
            self.cortex.bind(stop_record_done=self.on_stop_record_done)
            self.cortex.bind(export_record_done=self.on_export_record_done)
            self.cortex.bind(warn_stream_stop=self.on_warn_stream_stop)
            self.cortex.bind(new_met_data=self.on_new_met_data)
            self.cortex.bind(inform_error=self.on_inform_error)
            
            # 保存流信息
            self.streams = streams
            
            # 开始连接流程
            logger.info("开始Cortex认证流程...")
            self.cortex.set_wanted_streams(streams)
            self.cortex.open()
            
        except Exception as e:
            logger.error(f"启动EEG数据采集失败: {e}")
            self.is_connected = False
    
    def on_create_session_done(self, *args, **kwargs):
        """会话创建完成回调"""
        logger.info("Cortex会话创建完成")
        self.is_connected = True
    
    def on_query_headset_done(self, *args, **kwargs):
        """头戴设备查询完成回调"""
        logger.info("头戴设备查询完成")
    
    def on_connect_headset_done(self, *args, **kwargs):
        """头戴设备连接完成回调"""
        logger.info("头戴设备连接完成")
    
    def on_request_access_done(self, *args, **kwargs):
        """访问请求完成回调"""
        logger.info("访问权限请求完成")
    
    def on_authorize_done(self, *args, **kwargs):
        """授权完成回调"""
        logger.info("Cortex授权完成")
    
    def on_create_record_done(self, *args, **kwargs):
        """记录创建完成回调"""
        logger.info("记录创建完成")
    
    def on_stop_record_done(self, *args, **kwargs):
        """记录停止完成回调"""
        logger.info("记录停止完成")
    
    def on_export_record_done(self, *args, **kwargs):
        """记录导出完成回调"""
        logger.info("记录导出完成")
    
    def on_warn_stream_stop(self, *args, **kwargs):
        """流停止警告回调"""
        logger.warning("数据流停止警告")
    
    def on_new_met_data(self, *args, **kwargs):
        """新的情绪数据回调"""
        try:
            self.total_data_received += 1
            
            # 获取情绪数据
            data = kwargs.get('data')
            if not data:
                return
            
            # 解析情绪数据
            emotion_scores = {}
            
            # 从数据中提取情绪评分
            if 'fac' in data:
                # 面部表情数据
                fac_data = data['fac']
                for i, score in enumerate(fac_data):
                    if i < len(list(EMOTION_MAP.keys())):
                        emotion_name = list(EMOTION_MAP.keys())[i]
                        emotion_scores[emotion_name] = abs(score) if score is not None else 0
            
            # 找到最强烈的情绪
            if emotion_scores:
                dominant_emotion = max(emotion_scores.items(), key=lambda x: x[1])
                emotion_name = dominant_emotion[0]
                emotion_intensity = dominant_emotion[1]
                
                # 标准化情绪名称
                normalized_emotion = normalize_emotion_name(emotion_name)
                
                # 计算情绪强度（0-1范围）
                intensity = min(max(emotion_intensity / 100.0, 0.0), 1.0)
                
                # 更新当前情绪状态
                self.current_emotion = normalized_emotion
                self.current_intensity = intensity
                
                # 检查是否需要发送情绪更新
                current_time = time.time()
                if current_time - self.last_emotion_time >= self.emotion_update_interval:
                    self._send_emotion_update(normalized_emotion, intensity)
                    self.last_emotion_time = current_time
            
        except Exception as e:
            logger.error(f"处理情绪数据时出错: {e}")
    
    def _send_emotion_update(self, emotion: str, intensity: float):
        """发送情绪更新到主设备"""
        try:
            success = self.audio_client.send_emotion_data(emotion, intensity)
            
            if success:
                self.total_emotions_sent += 1
                logger.info(f"💭 情绪更新: {emotion} | 强度: {intensity:.2f} | 已发送: {self.total_emotions_sent}")
            else:
                logger.warning(f"情绪数据发送失败: {emotion} ({intensity:.2f})")
                
        except Exception as e:
            logger.error(f"发送情绪更新失败: {e}")
    
    def get_status(self) -> Dict[str, Any]:
        """获取处理器状态"""
        return {
            "is_connected": self.is_connected,
            "user_id": self.audio_client.user_id,
            "session_active": self.audio_client.session_active,
            "current_emotion": self.current_emotion,
            "current_intensity": self.current_intensity,
            "total_data_received": self.total_data_received,
            "total_emotions_sent": self.total_emotions_sent,
            "connection_attempts": self.connection_attempts,
            "last_emotion_time": self.last_emotion_time,
            "device_info": self.audio_client.device_info,
            "host_device": f"{HOST_DEVICE_IP}:{HOST_DEVICE_PORT}"
        }
    
    def subscribe_streams(self, streams):
        """订阅数据流"""
        logger.info(f"订阅数据流: {streams}")
        self.cortex.sub_request(streams)

    def on_inform_error(self, *args, **kwargs):
        """Cortex错误回调"""
        logger.error(f"Cortex 错误: {kwargs.get('error_data')}")
        self.is_connected = False

# ========================================================================================
# 主程序入口 (Main Application Entry Point)
# ========================================================================================

def get_host_ip_input():
    """获取用户输入的主设备IP地址"""
    global HOST_DEVICE_IP, SOCIAL_AUDIO_SERVICE_URL
    
    # 首先检查环境变量（智能启动器会设置）
    env_host_ip = os.environ.get('HOST_DEVICE_IP')
    env_network_method = os.environ.get('NETWORK_METHOD')
    
    if env_host_ip:
        print("=" * 60)
        print("🔗 EEG音乐社交系统 - 智能客户端")
        print("=" * 60)
        print(f"✅ 从智能启动器获取主设备IP: {env_host_ip}")
        if env_network_method:
            print(f"🔗 连接方法: {env_network_method}")
        
        HOST_DEVICE_IP = env_host_ip
        SOCIAL_AUDIO_SERVICE_URL = f'http://{HOST_DEVICE_IP}:{HOST_DEVICE_PORT}'
        print(f"📡 目标服务: {SOCIAL_AUDIO_SERVICE_URL}")
        print("=" * 60)
        return
    
    # 传统手动输入模式
    print("=" * 60)
    print("🔗 EEG音乐社交系统 - 客户端")
    print("=" * 60)
    print("请输入主设备的IP地址 (运行社交音频服务的设备)")
    print("如果主设备和客户端在同一局域网，通常是192.168.x.x格式")
    print("如果不确定，可以在主设备上运行 'ipconfig' (Windows) 或 'ifconfig' (Mac/Linux) 查看")
    print()
    print("💡 提示：使用 smart_client_main.py 可以自动发现主设备")
    print()
    
    while True:
        user_input = input(f"主设备IP地址 (当前: {HOST_DEVICE_IP}): ").strip()
        
        if not user_input:
            # 用户直接回车，使用默认值
            break
        
        # 简单验证IP地址格式
        parts = user_input.split('.')
        if len(parts) == 4 and all(part.isdigit() and 0 <= int(part) <= 255 for part in parts):
            HOST_DEVICE_IP = user_input
            SOCIAL_AUDIO_SERVICE_URL = f'http://{HOST_DEVICE_IP}:{HOST_DEVICE_PORT}'
            print(f"✅ 主设备地址设置为: {SOCIAL_AUDIO_SERVICE_URL}")
            break
        else:
            print("❌ 无效的IP地址格式，请重新输入 (例如: 192.168.1.100)")

def generate_user_id():
    """生成用户ID"""
    # 使用主机名 + 随机字符串
    try:
        hostname = socket.gethostname()
        random_suffix = str(uuid.uuid4())[:8]
        return f"{hostname}_{random_suffix}"
    except Exception:
        return f"client_{str(uuid.uuid4())[:8]}"

def main():
    """主程序入口"""
    logger.info("启动客户端EEG脑波数据处理服务...")
    
    # 检查凭证配置
    if YOUR_APP_CLIENT_ID == '你的Client ID' or YOUR_APP_CLIENT_SECRET == '你的Client Secret':
        logger.error("错误：请在代码中填入你的 Emotiv App Client ID 和 Client Secret!")
        return
    
    # 获取主设备IP地址
    get_host_ip_input()
    
    # 生成用户ID
    user_id = generate_user_id()
    
    # 初始化社交音频服务客户端
    audio_client = SocialAudioServiceClient(SOCIAL_AUDIO_SERVICE_URL, user_id)
    
    # 检查主设备服务是否可用
    logger.info("检查主设备服务连接...")
    max_retries = 10  # 最多等待10秒
    retry_count = 0
    
    while retry_count < max_retries:
        if audio_client.check_service_health():
            logger.info("✅ 主设备服务连接成功!")
            break
        else:
            logger.info(f"⏳ 等待主设备服务启动... ({retry_count + 1}/{max_retries})")
            time.sleep(1)
            retry_count += 1
    
    if retry_count >= max_retries:
        logger.error("❌ 无法连接到主设备服务!")
        logger.error(f"请检查：")
        logger.error(f"1. 主设备是否已启动社交音频服务")
        logger.error(f"2. IP地址是否正确: {HOST_DEVICE_IP}")
        logger.error(f"3. 网络连接是否正常")
        return
    
    # 加入会话
    logger.info("加入音乐会话...")
    if not audio_client.join_session():
        logger.error("❌ 无法加入音乐会话!")
        return
    
    # 初始化客户端EEG数据处理器
    client_processor = ClientEEGDataProcessor(
        YOUR_APP_CLIENT_ID, 
        YOUR_APP_CLIENT_SECRET,
        audio_client
    )
    
    # 启动EEG数据采集
    logger.info("启动客户端EEG数据采集...")
    logger.info("请戴上你的Emotiv设备并确保Cortex服务正在运行。")
    logger.info("💡 系统将每5秒向主设备发送一次情绪状态")
    
    try:
        client_processor.start(['met'])
        
        # 保持程序运行
        logger.info("🧠 客户端EEG脑波数据处理服务正在运行...")
        logger.info("📡 情绪数据将实时发送到主设备进行音乐生成")
        logger.info("🎵 请在主设备上查看融合后的情绪状态和音乐变化")
        logger.info("按Ctrl+C停止服务")
        
        # 定期输出状态信息
        last_status_time = time.time()
        status_interval = 30.0  # 30秒输出一次状态
        
        while True:
            time.sleep(1)
            
            # 定期输出状态
            current_time = time.time()
            if current_time - last_status_time >= status_interval:
                status = client_processor.get_status()
                logger.info(f"📊 状态报告:")
                logger.info(f"   连接状态: {'✅ 已连接' if status['is_connected'] else '❌ 未连接'}")
                logger.info(f"   会话状态: {'✅ 活跃' if status['session_active'] else '❌ 未活跃'}")
                logger.info(f"   当前情绪: {status['current_emotion']} ({status['current_intensity']:.2f})")
                logger.info(f"   数据统计: 接收 {status['total_data_received']} | 发送 {status['total_emotions_sent']}")
                last_status_time = current_time
            
            # 检查连接状态
            if not client_processor.is_connected:
                logger.warning("⚠️  EEG设备连接丢失，尝试重新连接...")
                
    except KeyboardInterrupt:
        logger.info("接收到停止信号，正在关闭服务...")
    except Exception as e:
        logger.error(f"程序运行出错: {e}")
    finally:
        # 离开会话
        logger.info("离开音乐会话...")
        audio_client.leave_session()
        logger.info("客户端EEG脑波数据处理服务已退出。")

if __name__ == "__main__":
    main() 