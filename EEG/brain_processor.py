#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
EEG Brain Wave Data Processor Service for Social Audio System
用于社交音频系统的脑波数据处理主服务

负责：
1. 连接Emotiv EEG设备获取脑波数据
2. 实时分析情绪状态
3. 通过HTTP API向社交音频服务发送情绪数据
"""

import math
import logging
import asyncio
import requests
import time
import socket
import uuid
from cortex import Cortex
from typing import Dict, Any
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

# --- 社交音频服务配置 ---
SOCIAL_AUDIO_SERVICE_URL = 'http://localhost:8080'
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

API_METRIC_ORDER = ['eng', 'exc', 'lex', 'str', 'rel', 'int']
METRIC_RANGES = {
    'eng': (0, 1), 'exc': (0, 1), 'lex': (0, 1), 'str': (0, 1),
    'rel': (0, 1), 'int': (0, 1)
}
WEIGHTS = {
    'arousal': {'exc': 0.4, 'str': 0.3, 'lex': 0.2, 'int': 0.15, 'eng': 0.1, 'rel': -0.4},
    'valence': {'rel': 0.35, 'int': 0.25, 'eng': 0.2, 'lex': 0.2, 'exc': 0.1, 'str': -0.5}
}

def normalize_to_neg_one_to_one(value, min_val, max_val):
    if max_val == min_val: 
        return 0
    return 2 * ((value - min_val) / (max_val - min_val)) - 1

def calculate_emotion_scores(metrics, weights):
    arousal = sum(weights['arousal'][key] * metrics[key] for key in API_METRIC_ORDER)
    valence = sum(weights['valence'][key] * metrics[key] for key in API_METRIC_ORDER)
    return max(-1, min(1, valence)), max(-1, min(1, arousal))

def get_precise_emotion(valence, arousal, neutral_threshold=0.1):
    intensity_raw = math.sqrt(valence**2 + arousal**2)
    
    # 原始强度归一化到0-100范围
    intensity_normalized = min(100, (intensity_raw / math.sqrt(2)) * 100)
    
    # 数学运算：归一化到0-1 -> 开平方 -> 乘10 -> 回到0-100范围
    intensity_0_to_1 = intensity_normalized / 100.0
    intensity_sqrt = math.sqrt(intensity_0_to_1)
    intensity_amplified = intensity_sqrt * 10
    intensity_final = min(100, intensity_amplified * 10)
    
    if intensity_raw < neutral_threshold:
        return "Neutral (中性)", intensity_final
        
    angle = math.degrees(math.atan2(arousal, valence))
    if angle < 0: 
        angle += 360
    
    emotion_label = "Neutral"

    if intensity_raw >= neutral_threshold:
        if 0 <= angle < 30: emotion_label = "Happy"
        elif 30 <= angle < 60: emotion_label = "Excited"
        elif 60 <= angle < 90: emotion_label = "Surprised"
        elif 90 <= angle < 112.5: emotion_label = "Fear"
        elif 112.5 <= angle < 135: emotion_label = "Angry"
        elif 135 <= angle < 157.5: emotion_label = "Contempt"
        elif 157.5 <= angle < 180: emotion_label = "Disgust"
        elif 180 <= angle < 198: emotion_label = "Miserable"
        elif 198 <= angle < 216: emotion_label = "Sad"
        elif 216 <= angle < 234: emotion_label = "Depressed"
        elif 234 <= angle < 252: emotion_label = "Bored"
        elif 252 <= angle < 270: emotion_label = "Tired"
        elif 270 <= angle < 300: emotion_label = "Sleepy"
        elif 300 <= angle < 330: emotion_label = "Relaxed"
        elif 330 <= angle < 360: emotion_label = "Pleased"
    
    return EMOTION_MAP.get(emotion_label, emotion_label), intensity_final

def analyze_emotion_from_sample(sample_list):
    raw_data = dict(zip(API_METRIC_ORDER, sample_list))
    normalized_metrics = {k: normalize_to_neg_one_to_one(v, *METRIC_RANGES[k]) for k, v in raw_data.items()}
    v, a = calculate_emotion_scores(normalized_metrics, WEIGHTS)
    emotion, intensity = get_precise_emotion(v, a)
    
    return emotion, intensity, v, a

# ========================================================================================
# 社交音频服务通信模块 (Social Audio Service Communication Module)
# ========================================================================================

class SocialAudioServiceClient:
    """社交音频服务客户端"""
    
    def __init__(self, service_url: str, user_id: str):
        self.service_url = service_url
        self.user_id = user_id
        self.device_info = self._get_device_info()
        self.session_active = False
        self.session = requests.Session()
        self.last_emotion_time = 0
        
        logger.info(f"初始化社交音频服务客户端: {service_url}")
        logger.info(f"主机用户ID: {user_id}")
        logger.info(f"设备信息: {self.device_info}")
    
    def _get_device_info(self) -> str:
        """获取设备信息"""
        try:
            hostname = socket.gethostname()
            ip = socket.gethostbyname(hostname)
            return f"Host_{hostname}({ip})"
        except Exception:
            return "Host_Unknown_Device"
    
    def check_service_health(self) -> bool:
        """检查社交音频服务健康状态"""
        try:
            response = self.session.get(f"{self.service_url}/health", timeout=3)
            if response.status_code == 200:
                data = response.json()
                logger.info(f"社交音频服务状态: {data.get('status')}")
                return data.get('status') == 'healthy'
            return False
        except requests.exceptions.RequestException as e:
            logger.warning(f"检查服务健康状态失败: {e}")
            return False
    
    def join_session(self) -> bool:
        """加入会话"""
        try:
            response = self.session.post(
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
            response = self.session.post(
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
        """发送情绪数据到社交音频服务"""
        try:
            # 构建符合社交音频服务要求的请求数据
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
            response = self.session.post(
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
# EEG数据处理模块 (EEG Data Processing Module)
# ========================================================================================

class EEGDataProcessor:
    def __init__(self, app_client_id, app_client_secret, audio_client: SocialAudioServiceClient, **kwargs):
        logger.info("正在初始化Cortex客户端...")
        self.cortex = Cortex(app_client_id, app_client_secret, debug_mode=False, **kwargs)
        self.cortex.bind(new_met_data=self.on_new_met_data)
        self.cortex.bind(inform_error=self.on_inform_error)
        self.cortex.bind(create_session_done=self.on_create_session_done)
        self.audio_client = audio_client
        self.is_connected = False
        
        # 控制输出频率的变量
        self.last_output_time = 0
        self.output_interval = 5.0  # 5秒输出一次
        self.latest_emotion_data = None  # 存储最新的情绪数据
        
    def start(self, streams, headset_id=''):
        """启动EEG数据采集"""
        self.streams = streams
        if headset_id != '': 
            self.cortex.set_wanted_headset(headset_id)
        self.cortex.open()

    def subscribe_streams(self, streams):
        """订阅数据流"""
        logger.info("发送数据订阅请求...")
        self.cortex.sub_request(streams)

    def on_new_met_data(self, *args, **kwargs):
        """处理新的EEG情绪数据"""
        try:
            met_values = kwargs.get('data')['met']
            numerical_values = [met_values[i] for i in [1, 3, 5, 8, 10, 12]]
            emotion, intensity, v, a = analyze_emotion_from_sample(numerical_values)
            
            # 更新最新的情绪数据
            self.latest_emotion_data = {
                'emotion': emotion,
                'intensity': intensity,
                'valence': v,
                'arousal': a,
                'timestamp': time.time()
            }
            
            # 检查是否到了输出时间（每5秒输出一次）
            current_time = time.time()
            if current_time - self.last_output_time >= self.output_interval:
                # 控制台输出
                print(f"[{time.strftime('%H:%M:%S')}] 💭 主机情绪: {emotion} | 强度: {intensity:.2f}/100 | (V: {v:.2f}, A: {a:.2f})")
                
                # 发送到社交音频服务（强度转换为0-1范围）
                success = self.audio_client.send_emotion_data(emotion, intensity/100.0)
                if success:
                    logger.info(f"🎵 已发送情绪数据到社交音频服务: {emotion} ({intensity:.1f}%)")
                else:
                    logger.warning("❌ 向社交音频服务发送情绪数据失败")
                
                # 更新最后输出时间
                self.last_output_time = current_time
                
        except IndexError:
            logger.error(f"接收到的 'met' 数据格式不完整: {kwargs.get('data')}")
        except Exception as e:
            logger.error(f"处理EEG数据时发生错误: {e}")

    def get_latest_emotion_status(self):
        """获取最新的情绪状态信息"""
        if self.latest_emotion_data:
            data = self.latest_emotion_data
            time_since_last = time.time() - data['timestamp']
            return f"最新情绪: {data['emotion']} | 强度: {data['intensity']:.1f}% | 更新于 {time_since_last:.1f}秒前"
        else:
            return "暂无情绪数据"

    def on_create_session_done(self, *args, **kwargs):
        """Cortex会话创建完成回调"""
        logger.info("Cortex 会话创建成功, 准备订阅数据。")
        logger.info(f"情绪数据将每 {self.output_interval} 秒输出一次")
        self.is_connected = True
        self.subscribe_streams(self.streams)

    def on_inform_error(self, *args, **kwargs):
        """Cortex错误回调"""
        logger.error(f"Cortex 错误: {kwargs.get('error_data')}")
        self.is_connected = False

# ========================================================================================
# 主程序入口 (Main Application Entry Point)
# ========================================================================================

def main():
    """主程序入口"""
    logger.info("启动主机EEG脑波数据处理服务...")
    
    # 检查凭证配置
    if YOUR_APP_CLIENT_ID == '你的Client ID' or YOUR_APP_CLIENT_SECRET == '你的Client Secret':
        logger.error("错误：请在代码中填入你的 Emotiv App Client ID 和 Client Secret!")
        return
    
    # 生成主机用户ID
    hostname = socket.gethostname()
    host_user_id = f"host_{hostname}_{str(uuid.uuid4())[:8]}"
    
    # 初始化社交音频服务客户端
    audio_client = SocialAudioServiceClient(SOCIAL_AUDIO_SERVICE_URL, host_user_id)
    
    # 检查社交音频服务健康状态
    logger.info("检查社交音频服务状态...")
    if not audio_client.check_service_health():
        logger.error("❌ 社交音频服务不可用，请先启动 host_main.py")
        logger.error("   请确保运行: python host_main.py")
        return
    
    # 加入会话
    logger.info("加入社交音频会话...")
    if not audio_client.join_session():
        logger.error("❌ 无法加入社交音频会话")
        return
    
    # 启动EEG数据处理
    try:
        logger.info("启动EEG数据处理器...")
        eeg_processor = EEGDataProcessor(YOUR_APP_CLIENT_ID, YOUR_APP_CLIENT_SECRET, audio_client)
        
        streams = ['met']  # 只需要情绪数据流
        eeg_processor.start(streams)
        
        logger.info("=" * 60)
        logger.info("🧠 主机EEG脑波数据处理服务已启动")
        logger.info(f"👤 主机用户ID: {host_user_id}")
        logger.info(f"🎵 连接到社交音频服务: {SOCIAL_AUDIO_SERVICE_URL}")
        logger.info("💭 主机的情绪数据将与其他用户融合生成音乐")
        logger.info("⏹️  按 Ctrl+C 停止服务")
        logger.info("=" * 60)
        
        # 保持运行
        while True:
            time.sleep(1)
            
    except KeyboardInterrupt:
        logger.info("\n👋 用户请求停止服务...")
    except Exception as e:
        logger.error(f"❌ 服务运行出错: {e}")
    finally:
        # 清理资源
        logger.info("🧹 清理资源...")
        try:
            audio_client.leave_session()
        except Exception as e:
            logger.warning(f"离开会话失败: {e}")
        
        logger.info("✅ 主机EEG脑波数据处理服务已停止")

if __name__ == "__main__":
    main() 