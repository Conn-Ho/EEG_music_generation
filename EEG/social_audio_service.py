#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Social Audio Generation Service
社交音频生成服务

负责：
1. 接收来自多个脑波处理服务的情绪数据
2. 融合多个用户的情绪状态
3. 根据融合后的情绪数据动态调整音乐生成参数
4. 实时生成并播放音乐
5. 提供HTTP API接口和WebSocket实时连接
"""

import asyncio
import logging
import numpy as np
import sounddevice as sd
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
import uvicorn
from threading import Thread
from google import genai
from google.genai import types
from typing import List, Dict, Any, Set, Optional
from pydantic import BaseModel
import json
import time
from datetime import datetime, timedelta
import uuid

# ========================================================================================
# 全局配置与日志 (Global Configuration & Logging)
# ========================================================================================

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- Google API配置 ---
GOOGLE_API_KEY = 'AIzaSyBz3Gn7w5WaWzv167mo5PoXnXEodVwAEPE'
MODEL_ID = 'models/lyria-realtime-exp'

# --- 初始基础Prompt配置 ---
INITIAL_BASE_PROMPT = ("quiet dreamcore", 0.8)

# --- 核心映射: 所有可能的情绪标签 ---
ALL_EMOTION_LABELS = [
    "Happy (开心)", "Excited (激动)", "Surprised (惊喜)", "Fear (恐惧)", 
    "Angry (愤怒)", "Contempt (轻蔑)", "Disgust (厌恶)", "Miserable (痛苦)", 
    "Sad (悲伤)", "Depressed (沮丧)", "Bored (无聊)", "Tired (疲倦)", 
    "Sleepy (困倦)", "Relaxed (放松)", "Pleased (平静)", "Neutral (中性)"
]

# --- 情绪映射到音乐风格 ---
EMOTION_TO_MUSIC_STYLE = {
    "Happy (开心)": ("upbeat pop", 0.9),
    "Excited (激动)": ("energetic rock", 0.95),
    "Surprised (惊喜)": ("dramatic cinematic", 0.8),
    "Fear (恐惧)": ("dark ambient", 0.7),
    "Angry (愤怒)": ("aggressive metal", 0.9),
    "Contempt (轻蔑)": ("cold electronic", 0.6),
    "Disgust (厌恶)": ("dissonant experimental", 0.7),
    "Miserable (痛苦)": ("melancholic piano", 0.8),
    "Sad (悲伤)": ("emotional ballad", 0.7),
    "Depressed (沮丧)": ("somber strings", 0.6),
    "Bored (无聊)": ("minimal ambient", 0.4),
    "Tired (疲倦)": ("soft acoustic", 0.5),
    "Sleepy (困倦)": ("gentle lullaby", 0.3),
    "Relaxed (放松)": ("peaceful meditation", 0.6),
    "Pleased (平静)": ("serene nature", 0.5),
    "Neutral (中性)": ("balanced instrumental", 0.5)
}

# ========================================================================================
# 数据模型 (Data Models)
# ========================================================================================

class UserEmotionData(BaseModel):
    """单个用户的情绪数据"""
    user_id: str
    emotion: str
    intensity: float
    timestamp: float
    device_info: Optional[str] = None

class SocialEmotionUpdate(BaseModel):
    """社交情绪更新请求"""
    user_emotion_data: UserEmotionData

class FusedEmotionState(BaseModel):
    """融合后的情绪状态"""
    primary_emotion: str
    secondary_emotion: Optional[str]
    fusion_intensity: float
    user_count: int
    fusion_method: str
    timestamp: float

class UserSession(BaseModel):
    """用户会话信息"""
    user_id: str
    connected_at: float
    last_emotion: Optional[str] = None
    last_intensity: Optional[float] = None
    last_update: Optional[float] = None
    is_active: bool = True

# ========================================================================================
# 情绪融合算法 (Emotion Fusion Algorithm)
# ========================================================================================

class EmotionFusionEngine:
    """情绪融合引擎"""
    
    def __init__(self):
        self.user_emotions: Dict[str, UserEmotionData] = {}
        self.emotion_history: List[FusedEmotionState] = []
        self.fusion_weights = {
            "valence": 0.4,    # 情感价值（正负性）
            "arousal": 0.4,    # 唤醒度（强度）
            "dominance": 0.2   # 支配性（主导性）
        }
        
        # 情绪的三维空间映射 (Valence, Arousal, Dominance)
        self.emotion_space = {
            "Happy (开心)": (0.8, 0.7, 0.6),
            "Excited (激动)": (0.9, 0.9, 0.8),
            "Surprised (惊喜)": (0.6, 0.8, 0.5),
            "Fear (恐惧)": (-0.7, 0.8, -0.6),
            "Angry (愤怒)": (-0.8, 0.9, 0.7),
            "Contempt (轻蔑)": (-0.5, 0.4, 0.6),
            "Disgust (厌恶)": (-0.8, 0.6, 0.3),
            "Miserable (痛苦)": (-0.9, 0.7, -0.7),
            "Sad (悲伤)": (-0.8, 0.3, -0.5),
            "Depressed (沮丧)": (-0.9, 0.2, -0.8),
            "Bored (无聊)": (-0.2, 0.1, -0.3),
            "Tired (疲倦)": (-0.3, 0.2, -0.4),
            "Sleepy (困倦)": (0.1, 0.1, -0.2),
            "Relaxed (放松)": (0.6, 0.2, 0.3),
            "Pleased (平静)": (0.7, 0.3, 0.4),
            "Neutral (中性)": (0.0, 0.0, 0.0)
        }
    
    def update_user_emotion(self, user_emotion: UserEmotionData):
        """更新用户情绪数据"""
        self.user_emotions[user_emotion.user_id] = user_emotion
        logger.info(f"更新用户情绪: {user_emotion.user_id} -> {user_emotion.emotion} ({user_emotion.intensity:.2f})")
    
    def remove_user(self, user_id: str):
        """移除用户"""
        if user_id in self.user_emotions:
            del self.user_emotions[user_id]
            logger.info(f"移除用户: {user_id}")
    
    def get_active_users(self, timeout_seconds: float = 30.0) -> List[UserEmotionData]:
        """获取活跃用户（最近更新过的）"""
        current_time = time.time()
        active_users = []
        
        for user_emotion in self.user_emotions.values():
            if current_time - user_emotion.timestamp <= timeout_seconds:
                active_users.append(user_emotion)
        
        return active_users
    
    def fuse_emotions(self, method: str = "weighted_average") -> Optional[FusedEmotionState]:
        """融合多个用户的情绪"""
        active_users = self.get_active_users()
        
        if not active_users:
            return None
        
        if len(active_users) == 1:
            # 只有一个用户，直接返回
            user = active_users[0]
            return FusedEmotionState(
                primary_emotion=user.emotion,
                secondary_emotion=None,
                fusion_intensity=user.intensity,
                user_count=1,
                fusion_method="single_user",
                timestamp=time.time()
            )
        
        if method == "weighted_average":
            return self._fuse_weighted_average(active_users)
        elif method == "dominant_emotion":
            return self._fuse_dominant_emotion(active_users)
        elif method == "harmonic_blend":
            return self._fuse_harmonic_blend(active_users)
        else:
            return self._fuse_weighted_average(active_users)
    
    def _fuse_weighted_average(self, users: List[UserEmotionData]) -> FusedEmotionState:
        """加权平均融合方法"""
        total_weight = sum(user.intensity for user in users)
        
        if total_weight == 0:
            # 所有用户强度都为0，返回中性
            return FusedEmotionState(
                primary_emotion="Neutral (中性)",
                secondary_emotion=None,
                fusion_intensity=0.0,
                user_count=len(users),
                fusion_method="weighted_average",
                timestamp=time.time()
            )
        
        # 计算加权情绪空间坐标
        fused_valence = sum(
            self.emotion_space[user.emotion][0] * user.intensity 
            for user in users
        ) / total_weight
        
        fused_arousal = sum(
            self.emotion_space[user.emotion][1] * user.intensity 
            for user in users
        ) / total_weight
        
        fused_dominance = sum(
            self.emotion_space[user.emotion][2] * user.intensity 
            for user in users
        ) / total_weight
        
        # 找到最接近的情绪
        primary_emotion = self._find_closest_emotion(fused_valence, fused_arousal, fused_dominance)
        
        # 计算融合强度（取平均值）
        fusion_intensity = total_weight / len(users)
        
        return FusedEmotionState(
            primary_emotion=primary_emotion,
            secondary_emotion=None,
            fusion_intensity=min(1.0, fusion_intensity),
            user_count=len(users),
            fusion_method="weighted_average",
            timestamp=time.time()
        )
    
    def _fuse_dominant_emotion(self, users: List[UserEmotionData]) -> FusedEmotionState:
        """主导情绪融合方法"""
        # 找到强度最高的情绪
        dominant_user = max(users, key=lambda u: u.intensity)
        
        # 找到第二强的情绪（如果存在）
        other_users = [u for u in users if u.user_id != dominant_user.user_id]
        secondary_emotion = None
        if other_users:
            secondary_user = max(other_users, key=lambda u: u.intensity)
            secondary_emotion = secondary_user.emotion
        
        return FusedEmotionState(
            primary_emotion=dominant_user.emotion,
            secondary_emotion=secondary_emotion,
            fusion_intensity=dominant_user.intensity,
            user_count=len(users),
            fusion_method="dominant_emotion",
            timestamp=time.time()
        )
    
    def _fuse_harmonic_blend(self, users: List[UserEmotionData]) -> FusedEmotionState:
        """和谐混合融合方法"""
        # 计算情绪的和谐度
        emotion_frequencies = {}
        total_intensity = 0
        
        for user in users:
            emotion = user.emotion
            intensity = user.intensity
            
            if emotion not in emotion_frequencies:
                emotion_frequencies[emotion] = 0
            emotion_frequencies[emotion] += intensity
            total_intensity += intensity
        
        # 找到最主要的两个情绪
        sorted_emotions = sorted(emotion_frequencies.items(), key=lambda x: x[1], reverse=True)
        
        primary_emotion = sorted_emotions[0][0]
        secondary_emotion = sorted_emotions[1][0] if len(sorted_emotions) > 1 else None
        
        # 融合强度考虑和谐度
        harmony_factor = len(set(user.emotion for user in users)) / len(users)  # 情绪多样性
        fusion_intensity = (total_intensity / len(users)) * (1 - harmony_factor * 0.3)
        
        return FusedEmotionState(
            primary_emotion=primary_emotion,
            secondary_emotion=secondary_emotion,
            fusion_intensity=min(1.0, fusion_intensity),
            user_count=len(users),
            fusion_method="harmonic_blend",
            timestamp=time.time()
        )
    
    def _find_closest_emotion(self, valence: float, arousal: float, dominance: float) -> str:
        """在情绪空间中找到最接近的情绪"""
        min_distance = float('inf')
        closest_emotion = "Neutral (中性)"
        
        for emotion, (v, a, d) in self.emotion_space.items():
            distance = np.sqrt(
                self.fusion_weights["valence"] * (valence - v) ** 2 +
                self.fusion_weights["arousal"] * (arousal - a) ** 2 +
                self.fusion_weights["dominance"] * (dominance - d) ** 2
            )
            
            if distance < min_distance:
                min_distance = distance
                closest_emotion = emotion
        
        return closest_emotion

# ========================================================================================
# 社交音频生成器 (Social Audio Generator)
# ========================================================================================

class SocialAudioGenerator:
    """社交音频生成器"""
    
    def __init__(self):
        # Google AI客户端初始化
        genai.configure(api_key=GOOGLE_API_KEY)
        self.client = genai.Client()
        
        # 音频参数
        self.sample_rate = 44100
        self.is_playing = False
        self.is_initialized = False
        
        # 融合引擎
        self.fusion_engine = EmotionFusionEngine()
        
        # 用户会话管理
        self.user_sessions: Dict[str, UserSession] = {}
        
        # 音乐生成参数
        self.current_prompt = INITIAL_BASE_PROMPT[0]
        self.current_intensity = INITIAL_BASE_PROMPT[1]
        self.current_fused_emotion: Optional[FusedEmotionState] = None
        
        # WebSocket连接管理
        self.websocket_connections: Set[WebSocket] = set()
        
        logger.info("社交音频生成器初始化完成")
    
    async def initialize(self):
        """初始化音频生成器"""
        try:
            logger.info("正在连接Google AI服务...")
            
            # 测试API连接
            response = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self.client.models.list()
            )
            
            logger.info("Google AI服务连接成功")
            self.is_initialized = True
            
        except Exception as e:
            logger.error(f"初始化失败: {e}")
            raise e
    
    async def add_user_session(self, user_id: str, device_info: str = None):
        """添加用户会话"""
        session = UserSession(
            user_id=user_id,
            connected_at=time.time(),
            device_info=device_info
        )
        self.user_sessions[user_id] = session
        logger.info(f"用户加入: {user_id}")
        
        # 通知所有WebSocket连接
        await self._broadcast_user_update()
    
    async def remove_user_session(self, user_id: str):
        """移除用户会话"""
        if user_id in self.user_sessions:
            del self.user_sessions[user_id]
            self.fusion_engine.remove_user(user_id)
            logger.info(f"用户离开: {user_id}")
            
            # 通知所有WebSocket连接
            await self._broadcast_user_update()
    
    async def update_user_emotion(self, user_emotion: UserEmotionData):
        """更新用户情绪并重新生成音乐"""
        # 更新用户会话
        if user_emotion.user_id in self.user_sessions:
            session = self.user_sessions[user_emotion.user_id]
            session.last_emotion = user_emotion.emotion
            session.last_intensity = user_emotion.intensity
            session.last_update = user_emotion.timestamp
        
        # 更新融合引擎
        self.fusion_engine.update_user_emotion(user_emotion)
        
        # 重新融合情绪
        fused_emotion = self.fusion_engine.fuse_emotions(method="weighted_average")
        
        if fused_emotion:
            self.current_fused_emotion = fused_emotion
            await self._update_music_from_fused_emotion(fused_emotion)
            
            # 通知所有WebSocket连接
            await self._broadcast_emotion_update(fused_emotion)
        
        logger.info(f"处理用户情绪: {user_emotion.user_id} -> {user_emotion.emotion} (强度: {user_emotion.intensity:.2f})")
    
    async def _update_music_from_fused_emotion(self, fused_emotion: FusedEmotionState):
        """根据融合后的情绪更新音乐"""
        try:
            # 获取音乐风格
            primary_style = EMOTION_TO_MUSIC_STYLE.get(
                fused_emotion.primary_emotion, 
                ("ambient instrumental", 0.5)
            )
            
            # 构建prompt
            if fused_emotion.secondary_emotion and fused_emotion.user_count > 1:
                secondary_style = EMOTION_TO_MUSIC_STYLE.get(
                    fused_emotion.secondary_emotion,
                    ("ambient instrumental", 0.5)
                )
                
                # 混合两种风格
                self.current_prompt = f"{primary_style[0]} blended with {secondary_style[0]}, social harmony, two souls"
                self.current_intensity = (primary_style[1] + secondary_style[1]) / 2 * fused_emotion.fusion_intensity
            else:
                self.current_prompt = f"{primary_style[0]}, emotional connection"
                self.current_intensity = primary_style[1] * fused_emotion.fusion_intensity
            
            logger.info(f"音乐更新: {self.current_prompt} (强度: {self.current_intensity:.2f})")
            
            # 如果正在播放，应用新的音乐参数
            if self.is_playing:
                await self._apply_music_changes()
                
        except Exception as e:
            logger.error(f"更新音乐失败: {e}")
    
    async def _apply_music_changes(self):
        """应用音乐变化（这里可以添加实际的音乐生成逻辑）"""
        # 这里应该调用Google AI的音乐生成API
        # 由于API复杂性，这里只做日志记录
        logger.info(f"🎵 应用音乐变化: {self.current_prompt}")
    
    async def start_music_generation(self):
        """开始音乐生成"""
        if not self.is_initialized:
            raise Exception("音频生成器未初始化")
        
        self.is_playing = True
        logger.info("🎵 开始社交音乐生成")
        
        # 开始音乐生成循环
        asyncio.create_task(self._music_generation_loop())
    
    async def stop_music_generation(self):
        """停止音乐生成"""
        self.is_playing = False
        logger.info("🛑 停止音乐生成")
    
    async def _music_generation_loop(self):
        """音乐生成循环"""
        while self.is_playing:
            try:
                # 这里应该是实际的音乐生成逻辑
                await asyncio.sleep(1)  # 暂时用sleep模拟
                
            except Exception as e:
                logger.error(f"音乐生成循环错误: {e}")
                await asyncio.sleep(1)
    
    async def add_websocket_connection(self, websocket: WebSocket):
        """添加WebSocket连接"""
        self.websocket_connections.add(websocket)
        logger.info(f"WebSocket连接添加，当前连接数: {len(self.websocket_connections)}")
    
    async def remove_websocket_connection(self, websocket: WebSocket):
        """移除WebSocket连接"""
        if websocket in self.websocket_connections:
            self.websocket_connections.remove(websocket)
            logger.info(f"WebSocket连接移除，当前连接数: {len(self.websocket_connections)}")
    
    async def _broadcast_user_update(self):
        """广播用户更新"""
        if not self.websocket_connections:
            return
        
        user_data = {
            "type": "user_update",
            "users": [
                {
                    "user_id": session.user_id,
                    "connected_at": session.connected_at,
                    "last_emotion": session.last_emotion,
                    "last_intensity": session.last_intensity,
                    "last_update": session.last_update,
                    "is_active": session.is_active
                }
                for session in self.user_sessions.values()
            ],
            "timestamp": time.time()
        }
        
        await self._broadcast_to_websockets(user_data)
    
    async def _broadcast_emotion_update(self, fused_emotion: FusedEmotionState):
        """广播情绪更新"""
        if not self.websocket_connections:
            return
        
        emotion_data = {
            "type": "emotion_update",
            "fused_emotion": {
                "primary_emotion": fused_emotion.primary_emotion,
                "secondary_emotion": fused_emotion.secondary_emotion,
                "fusion_intensity": fused_emotion.fusion_intensity,
                "user_count": fused_emotion.user_count,
                "fusion_method": fused_emotion.fusion_method,
                "timestamp": fused_emotion.timestamp
            },
            "current_prompt": self.current_prompt,
            "current_intensity": self.current_intensity
        }
        
        await self._broadcast_to_websockets(emotion_data)
    
    async def _broadcast_to_websockets(self, data: dict):
        """向所有WebSocket连接广播数据"""
        if not self.websocket_connections:
            return
        
        message = json.dumps(data, ensure_ascii=False)
        disconnected = set()
        
        for websocket in self.websocket_connections:
            try:
                await websocket.send_text(message)
            except Exception as e:
                logger.warning(f"WebSocket发送失败: {e}")
                disconnected.add(websocket)
        
        # 移除断开的连接
        for websocket in disconnected:
            await self.remove_websocket_connection(websocket)
    
    def get_status(self) -> dict:
        """获取系统状态"""
        active_users = self.fusion_engine.get_active_users()
        
        return {
            "is_playing": self.is_playing,
            "is_initialized": self.is_initialized,
            "user_count": len(self.user_sessions),
            "active_user_count": len(active_users),
            "websocket_connections": len(self.websocket_connections),
            "current_prompt": self.current_prompt,
            "current_intensity": self.current_intensity,
            "current_fused_emotion": self.current_fused_emotion.dict() if self.current_fused_emotion else None,
            "users": [
                {
                    "user_id": session.user_id,
                    "last_emotion": session.last_emotion,
                    "last_intensity": session.last_intensity,
                    "last_update": session.last_update,
                    "is_active": any(u.user_id == session.user_id for u in active_users)
                }
                for session in self.user_sessions.values()
            ]
        }

# ========================================================================================
# FastAPI应用 (FastAPI Application)
# ========================================================================================

app = FastAPI(title="Social EEG Audio Generation Service", version="1.0.0")

# 全局音频生成器实例
social_audio_generator: Optional[SocialAudioGenerator] = None

@app.on_event("startup")
async def startup_event():
    """应用启动事件"""
    global social_audio_generator
    social_audio_generator = SocialAudioGenerator()
    
    try:
        await social_audio_generator.initialize()
        await social_audio_generator.start_music_generation()
        logger.info("社交音频服务启动成功")
    except Exception as e:
        logger.error(f"服务启动失败: {e}")
        raise e

@app.on_event("shutdown")
async def shutdown_event():
    """应用关闭事件"""
    global social_audio_generator
    if social_audio_generator:
        await social_audio_generator.stop_music_generation()
        logger.info("社交音频服务已停止")

# ========================================================================================
# API端点 (API Endpoints)
# ========================================================================================

@app.get("/health")
async def health_check():
    """健康检查"""
    return JSONResponse(content={
        "status": "healthy",
        "service": "Social EEG Audio Generation Service",
        "is_playing": social_audio_generator.is_playing if social_audio_generator else False,
        "timestamp": time.time()
    })

@app.post("/update_emotion")
async def update_emotion(emotion_data: SocialEmotionUpdate):
    """接收情绪更新并调整音乐"""
    global social_audio_generator
    
    if not social_audio_generator:
        raise HTTPException(status_code=503, detail="音频生成器未初始化")
    
    if not social_audio_generator.is_playing:
        raise HTTPException(status_code=503, detail="音频生成器未运行")
    
    try:
        # 更新用户情绪
        await social_audio_generator.update_user_emotion(emotion_data.user_emotion_data)
        
        return JSONResponse(content={
            "status": "success",
            "message": "情绪状态已更新",
            "user_id": emotion_data.user_emotion_data.user_id,
            "emotion": emotion_data.user_emotion_data.emotion,
            "intensity": emotion_data.user_emotion_data.intensity,
            "timestamp": emotion_data.user_emotion_data.timestamp
        })
        
    except Exception as e:
        logger.error(f"处理情绪更新失败: {e}")
        raise HTTPException(status_code=500, detail=f"处理情绪更新失败: {str(e)}")

@app.post("/join_session")
async def join_session(user_id: str, device_info: str = "Unknown"):
    """用户加入会话"""
    global social_audio_generator
    
    if not social_audio_generator:
        raise HTTPException(status_code=503, detail="音频生成器未初始化")
    
    try:
        await social_audio_generator.add_user_session(user_id, device_info)
        
        return JSONResponse(content={
            "status": "success",
            "message": "用户会话已创建",
            "user_id": user_id,
            "timestamp": time.time()
        })
        
    except Exception as e:
        logger.error(f"创建用户会话失败: {e}")
        raise HTTPException(status_code=500, detail=f"创建用户会话失败: {str(e)}")

@app.post("/leave_session")
async def leave_session(user_id: str):
    """用户离开会话"""
    global social_audio_generator
    
    if not social_audio_generator:
        raise HTTPException(status_code=503, detail="音频生成器未初始化")
    
    try:
        await social_audio_generator.remove_user_session(user_id)
        
        return JSONResponse(content={
            "status": "success",
            "message": "用户会话已结束",
            "user_id": user_id,
            "timestamp": time.time()
        })
        
    except Exception as e:
        logger.error(f"结束用户会话失败: {e}")
        raise HTTPException(status_code=500, detail=f"结束用户会话失败: {str(e)}")

@app.get("/status")
async def get_status():
    """获取系统状态"""
    global social_audio_generator
    
    if not social_audio_generator:
        raise HTTPException(status_code=503, detail="音频生成器未初始化")
    
    try:
        status = social_audio_generator.get_status()
        return JSONResponse(content=status)
        
    except Exception as e:
        logger.error(f"获取状态失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取状态失败: {str(e)}")

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket端点，用于实时数据推送"""
    global social_audio_generator
    
    if not social_audio_generator:
        await websocket.close(code=4503, reason="服务未初始化")
        return
    
    await websocket.accept()
    await social_audio_generator.add_websocket_connection(websocket)
    
    try:
        # 发送初始状态
        status = social_audio_generator.get_status()
        await websocket.send_text(json.dumps({
            "type": "initial_status",
            "data": status
        }, ensure_ascii=False))
        
        # 保持连接
        while True:
            try:
                # 等待客户端消息（心跳包）
                data = await websocket.receive_text()
                message = json.loads(data)
                
                if message.get("type") == "ping":
                    await websocket.send_text(json.dumps({
                        "type": "pong",
                        "timestamp": time.time()
                    }))
                    
            except WebSocketDisconnect:
                break
            except Exception as e:
                logger.warning(f"WebSocket处理错误: {e}")
                break
                
    finally:
        await social_audio_generator.remove_websocket_connection(websocket)

# ========================================================================================
# 主程序入口 (Main Application Entry Point)
# ========================================================================================

def main():
    """主程序入口"""
    logger.info("启动社交EEG音频生成服务...")
    
    # 启动FastAPI服务
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8080,
        log_level="info",
        access_log=True
    )

if __name__ == "__main__":
    main() 