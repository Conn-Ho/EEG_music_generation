#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Audio Generation Service
音频生成服务

负责：
1. 接收来自脑波处理服务的情绪数据
2. 根据情绪数据动态调整音乐生成参数
3. 实时生成并播放音乐
4. 提供HTTP API接口
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
from typing import List, Dict, Any, Set
from pydantic import BaseModel
import json
import time

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

# ========================================================================================
# 复杂情绪到音乐Prompt映射 (Complex Emotion to Music Prompt Mapping)
# ========================================================================================

# 复杂的情绪到音乐风格映射字典
COMPLEX_EMOTION_MAPPING = {
    # 积极情绪 (Positive Emotions)
    "Happy (开心)": {
        "base_style": "bright major scales with uplifting melody and warm harmonies",
        "instruments": "cheerful piano arpeggios, warm string sections, light acoustic guitar, gentle percussion with tambourine",
        "tempo": "moderate to fast (120-140 BPM) with steady rhythmic pulse",
        "dynamics": "growing crescendo with joyful expression, dynamic contrast between verses",
        "mood": "euphoric and celebratory with infectious energy",
        "texture": "rich layered harmonies with clear melodic lines"
    },
    
    "Excited (激动)": {
        "base_style": "energetic rhythmic patterns with dynamic chord progressions and driving bass",
        "instruments": "electric guitar with overdrive, powerful drum kit, synthesizer arpeggios, brass section stabs",
        "tempo": "fast and rhythmic (140-160 BPM) with syncopated beats",
        "dynamics": "high energy with powerful crescendos and dramatic builds",
        "mood": "electrifying and intense with pulsating excitement",
        "texture": "dense layered arrangement with punchy rhythmic elements"
    },
    
    "Surprised (惊喜)": {
        "base_style": "unexpected harmonic changes with sudden melodic shifts and chromatic movement",
        "instruments": "staccato strings with pizzicato, brass stabs, woodwind flourishes, percussion hits and cymbal crashes",
        "tempo": "variable tempo with sudden changes and rhythmic surprises",
        "dynamics": "dramatic contrasts with surprise accents and sudden dynamic shifts",
        "mood": "whimsical and unpredictable with delightful twists",
        "texture": "sparse to dense with sudden textural changes"
    },
    
    "Relaxed (放松)": {
        "base_style": "smooth flowing harmonies with peaceful chord progressions in major keys",
        "instruments": "soft acoustic piano, gentle classical guitar, warm pad synthesizers, subtle ambient textures",
        "tempo": "slow and steady (60-80 BPM) with relaxed groove",
        "dynamics": "consistently calm with gentle swells and soft expression",
        "mood": "serene and tranquil with meditative quality",
        "texture": "sparse and airy with breathing space between notes"
    },
    
    "Pleased (平静)": {
        "base_style": "balanced major chord progressions with serene melodic phrases",
        "instruments": "acoustic guitar fingerpicking, soft piano chords, light string ensemble, nature sounds",
        "tempo": "moderate and stable (80-100 BPM) with even rhythm",
        "dynamics": "even and tranquil with subtle dynamic variation",
        "mood": "content and peaceful with gentle satisfaction",
        "texture": "balanced arrangement with clear separation of instruments"
    },
    
    # 消极情绪 (Negative Emotions)
    "Sad (悲伤)": {
        "base_style": "minor key melodies with melancholic phrases and descending progressions",
        "instruments": "solo piano with sustain pedal, cello with vibrato, soft violin, gentle rain sounds",
        "tempo": "slow and reflective (50-70 BPM) with rubato expression",
        "dynamics": "soft with emotional peaks and valleys, intimate expression",
        "mood": "deeply melancholic with cathartic emotional release",
        "texture": "minimal and intimate with focus on melodic expression"
    },
    
    "Angry (愤怒)": {
        "base_style": "aggressive chord progressions with harsh dissonant harmonies and driving rhythms",
        "instruments": "distorted electric guitar with heavy palm muting, aggressive drum kit, bass guitar with overdrive, brass section fortissimo",
        "tempo": "fast and intense (150-180 BPM) with powerful rhythmic drive",
        "dynamics": "loud and forceful with sharp attacks and aggressive accents",
        "mood": "intense and confrontational with raw emotional power",
        "texture": "thick and heavy with overlapping aggressive elements"
    },
    
    "Fear (恐惧)": {
        "base_style": "dark minor chords with unsettling harmonies and chromatic voice leading",
        "instruments": "tremolo strings in low register, muted brass, timpani rolls, prepared piano, glass harmonica",
        "tempo": "variable with tension (70-120 BPM) building to climactic moments",
        "dynamics": "quiet to loud with sudden bursts and spine-chilling crescendos",
        "mood": "ominous and suspenseful with creeping dread",
        "texture": "thin and atmospheric building to dense climaxes"
    },
    
    "Depressed (沮丧)": {
        "base_style": "low register drones with minimal harmonic movement and static harmonies",
        "instruments": "deep contrabass, muted strings in low positions, sparse piano, distant ambient drones",
        "tempo": "very slow (40-60 BPM) with heavy, dragging feel",
        "dynamics": "consistently quiet with minimal variation and flat expression",
        "mood": "heavily weighted with crushing emotional burden",
        "texture": "dense and oppressive with little melodic movement"
    },
    
    # 中性和其他情绪 (Neutral and Other Emotions)
    "Neutral (中性)": {
        "base_style": "simple harmonic background with minimal melodic movement and stable progressions",
        "instruments": "soft synthesizer pads, gentle ambient sounds, subtle field recordings",
        "tempo": "moderate (80-100 BPM) with steady, unobtrusive rhythm",
        "dynamics": "stable and unobtrusive with minimal dynamic change",
        "mood": "calm and neutral without strong emotional direction",
        "texture": "simple and understated background atmosphere"
    },
    
    "Bored (无聊)": {
        "base_style": "repetitive patterns with monotonous rhythm and predictable progressions",
        "instruments": "simple drum machine, basic synthesizer chords, repetitive bass line",
        "tempo": "steady but uninspiring (90-110 BPM) with mechanical feel",
        "dynamics": "flat and unchanging with no dynamic interest",
        "mood": "monotonous and unstimulating with mechanical repetition",
        "texture": "thin and repetitive with minimal variation"
    },
    
    "Contempt (轻蔑)": {
        "base_style": "sharp dissonant intervals with cold harmonies and angular melodic lines",
        "instruments": "harsh brass with mutes, metallic percussion, processed electric guitar, industrial sounds",
        "tempo": "moderate with sharp edges (100-130 BPM) with angular rhythms",
        "dynamics": "cutting and piercing with sharp dynamic contrasts",
        "mood": "cold and dismissive with sharp-edged superiority",
        "texture": "harsh and metallic with uncomfortable timbres"
    },
    
    "Disgust (厌恶)": {
        "base_style": "atonal clusters with unpleasant textures and harsh timbral combinations",
        "instruments": "prepared piano with objects, processed vocals, noise generators, metal scraping sounds",
        "tempo": "irregular and uncomfortable with unpredictable timing",
        "dynamics": "uncomfortable and jarring with sudden unpleasant bursts",
        "mood": "repulsive and uncomfortable with visceral rejection",
        "texture": "harsh and grating with unpleasant sonic combinations"
    },
    
    "Tired (疲倦)": {
        "base_style": "slow tempo with fading energy and drooping melodic phrases",
        "instruments": "soft piano with damper pedal, muted strings, gentle acoustic guitar, soft ambient pads",
        "tempo": "very slow (50-70 BPM) with gradually decreasing energy",
        "dynamics": "decreasing with fade-outs and diminishing returns",
        "mood": "weary and exhausted with depleted energy",
        "texture": "thin and sparse with gradually fading elements"
    },
    
    "Sleepy (困倦)": {
        "base_style": "gentle lullaby-like melodies with soft, hypnotic textures",
        "instruments": "music box melody, soft piano with sustain, warm synthesizer pads, gentle nature sounds",
        "tempo": "very slow and hypnotic (40-60 BPM) with dreamlike quality",
        "dynamics": "extremely soft and soothing with minimal variation",
        "mood": "dreamy and hypnotic with sleep-inducing quality",
        "texture": "soft and enveloping with warm, comforting timbres"
    },
    
    "Miserable (痛苦)": {
        "base_style": "deep emotional expression with sorrowful themes and heart-wrenching harmonies",
        "instruments": "solo violin with intense vibrato, mournful cello, weeping brass, sparse piano",
        "tempo": "slow with emotional rubato (50-80 BPM) following emotional peaks",
        "dynamics": "intense emotional peaks and valleys with dramatic expression",
        "mood": "deeply sorrowful with intense emotional catharsis",
        "texture": "exposed and vulnerable with raw emotional expression"
    }
}

# 强度调节器 - 根据情绪强度调整音乐描述
INTENSITY_MODIFIERS = {
    (0.9, 1.0): "with overwhelming intensity and dominant presence",
    (0.7, 0.9): "with very strong character and clear influence", 
    (0.5, 0.7): "with moderate presence and noticeable impact",
    (0.3, 0.5): "with subtle influence and gentle touch",
    (0.1, 0.3): "with minimal impact and barely noticeable presence",
    (0.0, 0.1): "with almost imperceptible background influence"
}

def generate_complex_music_prompt(emotion: str, intensity: float) -> str:
    """
    根据情绪和强度生成复杂的音乐Prompt
    
    Args:
        emotion: 情绪标签 (例如: "Happy (开心)")
        intensity: 情绪强度 (0.0 - 1.0)
    
    Returns:
        str: 复杂的音乐Prompt描述
    """
    
    # 获取情绪映射，如果没有找到则使用中性情绪
    emotion_config = COMPLEX_EMOTION_MAPPING.get(emotion, COMPLEX_EMOTION_MAPPING["Neutral (中性)"])
    
    # 获取强度修饰词
    intensity_desc = "with moderate presence"
    for (min_i, max_i), desc in INTENSITY_MODIFIERS.items():
        if min_i <= intensity < max_i:
            intensity_desc = desc
            break
    
    # 构建复杂的音乐描述
    base_style = emotion_config["base_style"]
    instruments = emotion_config["instruments"] 
    tempo = emotion_config["tempo"]
    dynamics = emotion_config["dynamics"]
    mood = emotion_config["mood"]
    texture = emotion_config["texture"]
    
    # 根据强度调整描述的详细程度
    if intensity > 0.8:
        # 高强度：使用完整描述
        prompt = f"{base_style}, featuring {instruments}, {tempo}, {dynamics}, creating a {mood}, with {texture}, {intensity_desc}"
    elif intensity > 0.6:
        # 中高强度：使用主要元素
        prompt = f"{base_style}, with {instruments}, {tempo}, {dynamics}, {intensity_desc}"
    elif intensity > 0.3:
        # 中低强度：使用基础描述
        prompt = f"{base_style}, featuring {instruments}, {intensity_desc}"
    else:
        # 低强度：简化描述
        prompt = f"{base_style} {intensity_desc}"
    
    return prompt

# --- HTTP API配置 ---
API_HOST = "0.0.0.0"
API_PORT = 8080

# ========================================================================================
# 数据模型 (Data Models)
# ========================================================================================

class EmotionUpdate(BaseModel):
    emotion: str
    intensity: float
    valence: float
    arousal: float
    timestamp: float

# ========================================================================================
# 音乐生成与控制模块 (Music Generation and Control Module)
# ========================================================================================

class PromptManager:
    def __init__(self, base_prompt_text: str, base_prompt_weight: float, emotion_labels: List[str]):
        self._base_prompt_text = base_prompt_text
        self._emotion_labels = emotion_labels
        self._lock = asyncio.Lock()

        # 初始化一个包含所有prompts的字典
        self._prompts = {label: 0.0 for label in self._emotion_labels}
        self._prompts[self._base_prompt_text] = base_prompt_weight
        
        # 当前激活的情绪状态
        self.current_emotion = "Neutral (中性)"
        self.current_intensity = 0.0

    async def update_prompt_for_emotion(self, session, active_emotion: str, value: float):
        """根据情绪输入，更新动态的情绪Prompt，使用复杂映射系统"""
        async with self._lock:
            # 1. 重置所有情绪Prompt的权重为0
            for label in self._emotion_labels:
                if label in self._prompts:
                    self._prompts[label] = 0.0
            
            # 2. 使用复杂映射生成详细的音乐风格描述
            if active_emotion in self._emotion_labels:
                clamped_value = max(0.0, min(1.0, value))
                
                # 生成复杂的音乐prompt
                complex_prompt = generate_complex_music_prompt(active_emotion, clamped_value)
                
                # 清除之前的复杂prompt
                keys_to_remove = [k for k in self._prompts.keys() if k not in self._emotion_labels and k != self._base_prompt_text]
                for key in keys_to_remove:
                    del self._prompts[key]
                
                # 添加新的复杂prompt
                self._prompts[complex_prompt] = clamped_value
                
                self.current_emotion = active_emotion
                self.current_intensity = clamped_value
                
                logger.info(f"情绪更新 -> '{active_emotion}' | 强度: {clamped_value:.2f}")
                logger.info(f"复杂Prompt: {complex_prompt[:100]}...")  # 只显示前100个字符
            
            # 3. 基础Prompt的权重保持不变
            google_prompts = [
                types.WeightedPrompt(text=t, weight=w) for t, w in self._prompts.items() if w > 0
            ]
        
        if session:
            await session.set_weighted_prompts(prompts=google_prompts)

    async def get_current_status(self):
        """获取当前情绪状态"""
        async with self._lock:
            active_emotions = []
            for text, weight in self._prompts.items():
                if text in self._emotion_labels and weight > 0:
                    active_emotions.append({"emotion": text, "weight": weight})
            
            return {
                "base_prompt": self._base_prompt_text,
                "base_weight": self._prompts[self._base_prompt_text],
                "current_emotion": self.current_emotion,
                "current_intensity": self.current_intensity,
                "active_emotions": active_emotions
            }

    def get_initial_google_prompts(self) -> list[types.WeightedPrompt]:
        """获取初始化的、包含基础Prompt和情绪Prompt的完整列表"""
        return [types.WeightedPrompt(text=t, weight=w) for t, w in self._prompts.items()]

# 全局变量用于音频回调
leftover_chunk = np.array([], dtype=np.int16)

class AudioGenerator:
    def __init__(self, prompt_manager: PromptManager):
        self.prompt_manager = prompt_manager
        self.session = None
        self.is_playing = False
        self.audio_task = None
        self.client = None
        
        # 状态管理
        self.status = "stopped"  # stopped, initializing, connecting, buffering, playing, error
        self.status_message = "服务已停止"
        self.error_details = None
        self.buffer_progress = 0  # 0-100
        
    def update_status(self, status: str, message: str, error_details: str = None, buffer_progress: int = 0):
        """更新服务状态并广播给WebSocket客户端"""
        self.status = status
        self.status_message = message
        self.error_details = error_details
        self.buffer_progress = buffer_progress
        logger.info(f"状态更新: {status} - {message}")
        
        # 异步广播状态到WebSocket客户端
        status_data = self.get_status_info()
        asyncio.create_task(status_broadcaster.broadcast_status(status_data))

    async def initialize(self):
        """初始化音频生成器"""
        try:
            self.update_status("initializing", "正在初始化Google AI客户端...")
            self.client = genai.Client(api_key=GOOGLE_API_KEY, http_options={'api_version': 'v1alpha'})
            logger.info("Google AI客户端初始化成功")
            return True
        except Exception as e:
            error_msg = f"初始化Google AI客户端失败: {e}"
            self.update_status("error", "初始化失败", str(e))
            logger.error(error_msg)
            return False
    
    async def start_audio_generation(self):
        """启动音频生成和播放"""
        if self.is_playing:
            logger.warning("音频生成已在运行中")
            return
            
        try:
            self.update_status("connecting", "正在连接到Lyria音乐生成模型...")
            config = types.LiveMusicGenerationConfig(bpm=120)
            
            async with self.client.aio.live.music.connect(model=MODEL_ID) as session:
                self.session = session
                self.update_status("connected", "已连接到Lyria模型，准备开始音频生成...")
                logger.info("连接到Lyria音乐生成模型成功")
                
                # 启动音频生成任务
                self.audio_task = asyncio.create_task(
                    self.generate_and_play_audio(session, config)
                )
                self.is_playing = True
                
                logger.info("音频生成服务已启动")
                await self.audio_task
                
        except Exception as e:
            error_msg = f"音频生成启动失败: {e}"
            
            # 处理地区限制错误
            if "User location is not supported" in str(e):
                self.update_status("error", "地区限制：当前地理位置不支持该服务", str(e))
            else:
                self.update_status("error", "连接失败", str(e))
                
            logger.error(error_msg)
            self.is_playing = False
            raise
    
    async def generate_and_play_audio(self, session, config=None):
        """生成并播放音频"""
        global leftover_chunk
        CHANNELS, RATE, DTYPE = 2, 48000, 'int16'
        audio_queue = asyncio.Queue()

        def callback(outdata, frames, time, status):
            global leftover_chunk
            if status: 
                logger.warning(f"音频流状态异常: {status}")
            
            frames_needed = frames
            play_data = leftover_chunk
            
            while len(play_data) < frames_needed * CHANNELS:
                try:
                    new_chunk_bytes = audio_queue.get_nowait()
                    new_chunk_np = np.frombuffer(new_chunk_bytes, dtype=DTYPE)
                    play_data = np.concatenate((play_data, new_chunk_np))
                    audio_queue.task_done()
                except asyncio.QueueEmpty:
                    # 缓冲区为空时播放静音
                    outdata.fill(0)
                    return
                    
            chunk_to_play = play_data[:frames_needed * CHANNELS]
            leftover_chunk = play_data[frames_needed * CHANNELS:]
            outdata[:] = chunk_to_play.reshape(-1, CHANNELS)

        async def receive_audio():
            async for message in session.receive():
                if message.server_content and message.server_content.audio_chunks:
                    audio_chunk = message.server_content.audio_chunks[0].data
                    if audio_chunk: 
                        await audio_queue.put(audio_chunk)

        # 设置初始提示词
        initial_prompts = self.prompt_manager.get_initial_google_prompts()
        await session.set_weighted_prompts(prompts=initial_prompts)
        
        if config: 
            await session.set_music_generation_config(config=config)
        
        await session.play()
        
        receive_task = asyncio.create_task(receive_audio())
        
        # 预缓冲音频
        self.update_status("buffering", "正在预缓冲音频数据...", buffer_progress=0)
        buffer_target = 10
        
        while audio_queue.qsize() < buffer_target:
            if receive_task.done():
                logger.error("接收任务在预缓冲期间意外终止。")
                self.update_status("error", "音频接收任务意外终止")
                return
            
            # 更新缓冲进度
            current_buffer = audio_queue.qsize()
            progress = int((current_buffer / buffer_target) * 100)
            self.update_status("buffering", f"正在预缓冲音频数据... ({current_buffer}/{buffer_target})", buffer_progress=progress)
            
            await asyncio.sleep(0.1)
            
        self.update_status("playing", "音频流已开启，正在播放音乐", buffer_progress=100)
        logger.info("预缓冲完成，开始播放音乐")

        # 开始音频播放
        with sd.OutputStream(samplerate=RATE, channels=CHANNELS, dtype=DTYPE, callback=callback):
            logger.info("音频流已成功开启，现在可以接收情绪数据了")
            await receive_task
    
    async def update_emotion(self, emotion: str, intensity: float):
        """更新情绪状态"""
        if self.session and self.is_playing:
            await self.prompt_manager.update_prompt_for_emotion(
                self.session, emotion, intensity
            )
    
    async def stop(self):
        """停止音频生成"""
        self.update_status("stopping", "正在停止音频生成...")
        self.is_playing = False
        
        if self.audio_task:
            self.audio_task.cancel()
            try:
                await self.audio_task
            except asyncio.CancelledError:
                pass
                
        self.session = None
        self.update_status("stopped", "音频生成已停止")
        logger.info("音频生成已停止")
    
    def get_status_info(self):
        """获取详细的状态信息"""
        return {
            "status": self.status,
            "message": self.status_message,
            "is_playing": self.is_playing,
            "buffer_progress": self.buffer_progress,
            "error_details": self.error_details,
            "timestamp": time.time()
        }

# ========================================================================================
# HTTP API服务 (HTTP API Service)
# ========================================================================================

# 全局变量
audio_generator = None
websocket_connections: Set[WebSocket] = set()
app = FastAPI(title="EEG Audio Generation Service", version="1.0.0")

# WebSocket状态推送管理
class StatusBroadcaster:
    def __init__(self):
        self.connections: Set[WebSocket] = set()
    
    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.connections.add(websocket)
        logger.info(f"WebSocket客户端已连接，当前连接数: {len(self.connections)}")
    
    async def disconnect(self, websocket: WebSocket):
        self.connections.discard(websocket)
        logger.info(f"WebSocket客户端已断开，当前连接数: {len(self.connections)}")
    
    async def broadcast_status(self, status_data: dict):
        """向所有连接的客户端广播状态更新"""
        if not self.connections:
            return
            
        disconnected = set()
        for websocket in self.connections:
            try:
                await websocket.send_json(status_data)
            except Exception as e:
                logger.warning(f"向WebSocket客户端发送数据失败: {e}")
                disconnected.add(websocket)
        
        # 清理断开的连接
        for websocket in disconnected:
            self.connections.discard(websocket)

status_broadcaster = StatusBroadcaster()

@app.on_event("startup")
async def startup_event():
    """服务启动时初始化"""
    global audio_generator
    
    logger.info("启动音频生成服务...")
    
    # 检查Google API Key
    if GOOGLE_API_KEY == '你的Google API Key':
        logger.error("错误：请在代码中填入你的 Google API Key!")
        raise Exception("Google API Key未配置")
    
    # 初始化音频生成器
    base_prompt_text, base_prompt_weight = INITIAL_BASE_PROMPT
    prompt_manager = PromptManager(
        base_prompt_text=base_prompt_text,
        base_prompt_weight=base_prompt_weight,
        emotion_labels=ALL_EMOTION_LABELS
    )
    
    audio_generator = AudioGenerator(prompt_manager)
    audio_generator.update_status("starting", "服务正在启动...")
    
    # 初始化Google AI客户端
    if not await audio_generator.initialize():
        raise Exception("音频生成器初始化失败")
    
    # 在后台启动音频生成
    asyncio.create_task(audio_generator.start_audio_generation())
    
    logger.info(f"音频服务已启动，基础音乐风格: '{base_prompt_text}' (权重: {base_prompt_weight})")

@app.get("/health")
async def health_check():
    """健康检查端点"""
    return JSONResponse(content={
        "status": "healthy",
        "service": "EEG Audio Generation Service",
        "is_playing": audio_generator.is_playing if audio_generator else False,
        "timestamp": time.time()
    })

@app.post("/update_emotion")
async def update_emotion(emotion_data: EmotionUpdate):
    """接收情绪更新并调整音乐"""
    global audio_generator
    
    if not audio_generator:
        raise HTTPException(status_code=503, detail="音频生成器未初始化")
    
    if not audio_generator.is_playing:
        raise HTTPException(status_code=503, detail="音频生成器未运行")
    
    try:
        # 更新情绪状态
        await audio_generator.update_emotion(
            emotion_data.emotion, 
            emotion_data.intensity
        )
        
        logger.info(f"收到情绪更新: {emotion_data.emotion} | 强度: {emotion_data.intensity:.2f}")
        
        return JSONResponse(content={
            "status": "success",
            "message": "情绪状态已更新",
            "emotion": emotion_data.emotion,
            "intensity": emotion_data.intensity,
            "timestamp": time.time()
        })
        
    except Exception as e:
        logger.error(f"更新情绪状态失败: {e}")
        raise HTTPException(status_code=500, detail=f"更新失败: {str(e)}")

@app.get("/status")
async def get_status():
    """获取当前服务状态"""
    global audio_generator
    
    if not audio_generator:
        return JSONResponse(content={"status": "not_initialized"})
    
    try:
        prompt_status = await audio_generator.prompt_manager.get_current_status()
        return JSONResponse(content={
            "service_status": "running" if audio_generator.is_playing else "stopped",
            "audio_generation": {
                "is_playing": audio_generator.is_playing,
                "model": MODEL_ID
            },
            "prompt_status": prompt_status,
            "timestamp": time.time()
        })
    except Exception as e:
        logger.error(f"获取状态失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取状态失败: {str(e)}")

@app.get("/audio_status")
async def get_audio_status():
    """获取音频流详细状态 - 专门用于前端加载状态监控"""
    global audio_generator
    
    if not audio_generator:
        return JSONResponse(content={
            "status": "not_initialized",
            "message": "音频生成器未初始化",
            "is_playing": False,
            "buffer_progress": 0,
            "error_details": None,
            "timestamp": time.time()
        })
    
    return JSONResponse(content=audio_generator.get_status_info())

@app.websocket("/ws/audio_status")
async def websocket_audio_status(websocket: WebSocket):
    """WebSocket端点 - 实时推送音频状态"""
    await status_broadcaster.connect(websocket)
    
    try:
        # 发送当前状态
        if audio_generator:
            await websocket.send_json(audio_generator.get_status_info())
        
        # 保持连接活跃
        while True:
            # 等待客户端消息（心跳包等）
            try:
                await websocket.receive_text()
            except WebSocketDisconnect:
                break
            except Exception as e:
                logger.warning(f"WebSocket接收消息失败: {e}")
                break
                
    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.error(f"WebSocket连接异常: {e}")
    finally:
        await status_broadcaster.disconnect(websocket)

@app.post("/restart_audio")
async def restart_audio():
    """重启音频生成服务"""
    global audio_generator
    
    if not audio_generator:
        raise HTTPException(status_code=503, detail="音频生成器未初始化")
    
    try:
        logger.info("收到重启音频服务请求")
        
        # 停止当前服务
        if audio_generator.is_playing:
            await audio_generator.stop()
        
        # 重新启动
        asyncio.create_task(audio_generator.start_audio_generation())
        
        return JSONResponse(content={
            "status": "success",
            "message": "音频服务重启请求已发送",
            "timestamp": time.time()
        })
        
    except Exception as e:
        logger.error(f"重启音频服务失败: {e}")
        raise HTTPException(status_code=500, detail=f"重启失败: {str(e)}")

@app.on_event("shutdown")
async def shutdown_event():
    """服务关闭时清理资源"""
    global audio_generator
    
    if audio_generator:
        await audio_generator.stop()
        logger.info("音频生成服务已关闭")

# ========================================================================================
# 主程序入口 (Main Application Entry Point)
# ========================================================================================

def main():
    """主程序入口"""
    logger.info("启动EEG音频生成服务...")
    
    try:
        # 启动FastAPI服务
        uvicorn.run(
            "audio_service:app",
            host=API_HOST,
            port=API_PORT,
            log_level="info",
            access_log=True
        )
    except KeyboardInterrupt:
        logger.info("接收到停止信号，正在关闭服务...")
    except Exception as e:
        logger.error(f"服务启动失败: {e}")
    finally:
        logger.info("音频生成服务已退出")

if __name__ == "__main__":
    main() 