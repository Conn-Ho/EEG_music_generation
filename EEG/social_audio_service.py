#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Social Audio Generation Service - WITH GOOGLE LYRIA REAL-TIME MUSIC GENERATION
社交音频生成服务 - 具备Google Lyria实时音乐生成功能

负责：
1. 接收来自多个脑波处理服务的情绪数据
2. 融合多个用户的情绪状态
3. 根据融合后的情绪数据动态调整Google Lyria音乐生成参数
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
import math
try:
    # 尝试使用新版本的Google AI SDK
    from google import genai
    from google.genai import types
    GOOGLE_AI_AVAILABLE = True
except ImportError:
    try:
        # 备用：尝试旧版本
        import google.generativeai as genai
        from google.generativeai import types
        GOOGLE_AI_AVAILABLE = True
    except ImportError:
        # 如果都没有，创建模拟对象
        GOOGLE_AI_AVAILABLE = False
        
        class MockGenAI:
            def configure(self, api_key): pass
            def Client(self): return MockClient()
        
        class MockClient:
            def models(self): return MockModels()
            
        class MockTypes:
            class WeightedPrompt:
                def __init__(self, text, weight): 
                    self.text = text
                    self.weight = weight
            class LiveMusicGenerationConfig:
                def __init__(self, bpm=120):
                    self.bpm = bpm
        
        class MockModels:
            def list(self): return []
        
        genai = MockGenAI()
        types = MockTypes()
        
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

# --- 情绪映射到音乐风格和音频参数 ---
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
# Google Lyria音乐生成管理 (Google Lyria Music Generation Management)
# ========================================================================================

class PromptManager:
    """Google Lyria音乐生成的Prompt管理器"""
    
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
        self.current_complex_prompt = ""

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
                self.current_complex_prompt = complex_prompt
                
                logger.info(f"情绪更新 -> '{active_emotion}' | 强度: {clamped_value:.2f}")
                logger.info(f"复杂Prompt: {complex_prompt[:100]}...")  # 只显示前100个字符
            
            # 3. 基础Prompt的权重保持不变
            if GOOGLE_AI_AVAILABLE:
                google_prompts = [
                    types.WeightedPrompt(text=t, weight=w) for t, w in self._prompts.items() if w > 0
                ]
            else:
                google_prompts = []
        
        if session and GOOGLE_AI_AVAILABLE:
            try:
                await session.set_weighted_prompts(prompts=google_prompts)
            except Exception as e:
                logger.error(f"设置weighted prompts失败: {e}")

    async def update_prompt_for_fused_emotion(self, session, fused_emotion, secondary_emotion=None):
        """根据融合后的情绪更新Prompt"""
        try:
            primary_emotion = fused_emotion.primary_emotion
            fusion_intensity = fused_emotion.fusion_intensity
            
            if secondary_emotion and fused_emotion.user_count > 1:
                # 多用户情况：混合两种情绪
                primary_prompt = generate_complex_music_prompt(primary_emotion, fusion_intensity * 0.7)
                secondary_prompt = generate_complex_music_prompt(secondary_emotion, fusion_intensity * 0.3)
                
                # 创建混合prompt
                mixed_prompt = f"Blending {primary_prompt} with elements of {secondary_prompt}, creating social harmony between {fused_emotion.user_count} souls"
                
                async with self._lock:
                    # 清除旧的复杂prompt
                    keys_to_remove = [k for k in self._prompts.keys() if k not in self._emotion_labels and k != self._base_prompt_text]
                    for key in keys_to_remove:
                        del self._prompts[key]
                    
                    # 添加混合prompt
                    self._prompts[mixed_prompt] = fusion_intensity
                    self.current_complex_prompt = mixed_prompt
                    
                logger.info(f"🎵 混合情绪音乐: {primary_emotion} + {secondary_emotion} (用户数: {fused_emotion.user_count})")
                logger.info(f"混合Prompt: {mixed_prompt[:100]}...")
                
            else:
                # 单一情绪或单用户
                await self.update_prompt_for_emotion(session, primary_emotion, fusion_intensity)
                
        except Exception as e:
            logger.error(f"更新融合情绪Prompt失败: {e}")

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
                "current_complex_prompt": self.current_complex_prompt,
                "active_emotions": active_emotions
            }

    def get_initial_google_prompts(self):
        """获取初始化的、包含基础Prompt和情绪Prompt的完整列表"""
        if GOOGLE_AI_AVAILABLE:
            return [types.WeightedPrompt(text=t, weight=w) for t, w in self._prompts.items()]
        else:
            return []

# ========================================================================================
# Google Lyria音频生成引擎 (Google Lyria Audio Generation Engine)
# ========================================================================================

# 全局变量用于音频回调
leftover_chunk = np.array([], dtype=np.int16)

class GoogleLyriaAudioEngine:
    """Google Lyria音频生成引擎"""
    
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
        """更新服务状态"""
        self.status = status
        self.status_message = message
        self.error_details = error_details
        self.buffer_progress = buffer_progress
        logger.info(f"Google Lyria状态更新: {status} - {message}")

    async def initialize(self):
        """初始化Google Lyria音频生成器"""
        if not GOOGLE_AI_AVAILABLE:
            logger.warning("Google AI SDK不可用，跳过Lyria初始化")
            return False
            
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
        """启动Google Lyria音频生成和播放"""
        if not GOOGLE_AI_AVAILABLE:
            logger.warning("Google AI不可用，无法启动Lyria音频生成")
            return False
            
        if self.is_playing:
            logger.warning("Google Lyria音频生成已在运行中")
            return True
            
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
                
                logger.info("Google Lyria音频生成服务已启动")
                await self.audio_task
                
        except Exception as e:
            error_msg = f"Google Lyria音频生成启动失败: {e}"
            
            # 处理地区限制错误
            if "User location is not supported" in str(e):
                self.update_status("error", "地区限制：当前地理位置不支持该服务", str(e))
            else:
                self.update_status("error", "连接失败", str(e))
                
            logger.error(error_msg)
            self.is_playing = False
            return False
    
    async def generate_and_play_audio(self, session, config=None):
        """生成并播放Google Lyria音频"""
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
        if initial_prompts:
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
            
        self.update_status("playing", "Google Lyria音频流已开启，正在播放音乐", buffer_progress=100)
        logger.info("Google Lyria预缓冲完成，开始播放音乐")

        # 开始音频播放
        with sd.OutputStream(samplerate=RATE, channels=CHANNELS, dtype=DTYPE, callback=callback):
            logger.info("Google Lyria音频流已成功开启")
            await receive_task
    
    async def update_emotion(self, emotion: str, intensity: float):
        """更新情绪状态"""
        if self.session and self.is_playing:
            await self.prompt_manager.update_prompt_for_emotion(
                self.session, emotion, intensity
            )
    
    async def update_fused_emotion(self, fused_emotion, secondary_emotion=None):
        """更新融合后的情绪状态"""
        if self.session and self.is_playing:
            await self.prompt_manager.update_prompt_for_fused_emotion(
                self.session, fused_emotion, secondary_emotion
            )
    
    async def stop(self):
        """停止Google Lyria音频生成"""
        self.update_status("stopping", "正在停止音频生成...")
        self.is_playing = False
        
        if self.audio_task:
            self.audio_task.cancel()
            try:
                await self.audio_task
            except asyncio.CancelledError:
                pass
                
        self.session = None
        self.update_status("stopped", "Google Lyria音频生成已停止")
        logger.info("Google Lyria音频生成已停止")
    
    def get_status_info(self):
        """获取详细的状态信息"""
        return {
            "status": self.status,
            "message": self.status_message,
            "is_playing": self.is_playing,
            "buffer_progress": self.buffer_progress,
            "error_details": self.error_details,
            "google_ai_available": GOOGLE_AI_AVAILABLE,
            "timestamp": time.time()
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
# 社交音频生成器 (Enhanced Social Audio Generator)
# ========================================================================================

class SocialAudioGenerator:
    """增强版社交音频生成器 - 具备Google Lyria实时音乐生成功能"""
    
    def __init__(self):
        # 初始化Prompt管理器
        base_prompt_text, base_prompt_weight = INITIAL_BASE_PROMPT
        self.prompt_manager = PromptManager(
            base_prompt_text=base_prompt_text,
            base_prompt_weight=base_prompt_weight,
            emotion_labels=ALL_EMOTION_LABELS
        )
        
        # Google Lyria音频引擎
        self.lyria_engine = GoogleLyriaAudioEngine(self.prompt_manager)
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
        
        logger.info("增强版社交音频生成器初始化完成（Google Lyria版本）")
    
    async def initialize(self):
        """初始化音频生成器"""
        try:
            logger.info("正在初始化社交音频生成器...")
            
            # 初始化Google Lyria引擎
            lyria_success = await self.lyria_engine.initialize()
            
            if lyria_success:
                logger.info("Google Lyria引擎初始化成功")
            else:
                logger.warning("Google Lyria引擎初始化失败")
            
            self.is_initialized = True
            return True
            
        except Exception as e:
            logger.error(f"初始化失败: {e}")
            self.is_initialized = True  # 即使失败也设为已初始化，允许降级运行
            return True
    
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
                self.current_prompt = f"{primary_style[0]} blended with {secondary_style[0]}, social harmony, {fused_emotion.user_count} souls"
                self.current_intensity = (primary_style[1] + secondary_style[1]) / 2 * fused_emotion.fusion_intensity
                
                # 更新Google Lyria引擎
                await self.lyria_engine.update_fused_emotion(fused_emotion, fused_emotion.secondary_emotion)
            else:
                self.current_prompt = f"{primary_style[0]}, emotional connection"
                self.current_intensity = primary_style[1] * fused_emotion.fusion_intensity
                
                # 更新Google Lyria引擎
                await self.lyria_engine.update_fused_emotion(fused_emotion)
            
            logger.info(f"🎵 Google Lyria音乐已更新: {fused_emotion.primary_emotion} -> {self.current_prompt}")
                
        except Exception as e:
            logger.error(f"更新音乐失败: {e}")
    
    async def start_music_generation(self):
        """开始音乐生成和播放"""
        if not self.is_initialized:
            raise Exception("音频生成器未初始化")
        
        self.is_playing = True
        
        # 启动Google Lyria音频生成
        if GOOGLE_AI_AVAILABLE:
            lyria_task = asyncio.create_task(self.lyria_engine.start_audio_generation())
        
        logger.info("🎵 开始社交音乐生成和播放（Google Lyria版本）")
        
        # 开始音乐生成循环
        asyncio.create_task(self._music_generation_loop())
    
    async def stop_music_generation(self):
        """停止音乐生成和播放"""
        self.is_playing = False
        await self.lyria_engine.stop()
        logger.info("🛑 停止音乐生成和播放")
    
    async def _music_generation_loop(self):
        """音乐生成循环"""
        while self.is_playing:
            try:
                # 检查是否有活跃用户
                active_users = self.fusion_engine.get_active_users()
                
                if not active_users:
                    # 没有活跃用户时可以设置默认状态
                    if self.current_fused_emotion is None and GOOGLE_AI_AVAILABLE:
                        # 设置默认中性情绪
                        default_emotion = FusedEmotionState(
                            primary_emotion="Neutral (中性)",
                            secondary_emotion=None,
                            fusion_intensity=0.3,
                            user_count=0,
                            fusion_method="default",
                            timestamp=time.time()
                        )
                        await self.lyria_engine.update_fused_emotion(default_emotion)
                
                await asyncio.sleep(5)  # 每5秒检查一次
                
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
            "current_intensity": self.current_intensity,
            "lyria_status": self.lyria_engine.get_status_info()
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
            "google_ai_available": GOOGLE_AI_AVAILABLE,
            "lyria_status": self.lyria_engine.get_status_info(),
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

app = FastAPI(title="Social EEG Audio Generation Service (Google Lyria)", version="2.0.0")

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
        logger.info("社交音频服务启动成功（Google Lyria版本）")
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
        "service": "Social EEG Audio Generation Service (Google Lyria)",
        "is_playing": social_audio_generator.is_playing if social_audio_generator else False,
        "google_ai_available": GOOGLE_AI_AVAILABLE,
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

@app.get("/lyria_status")
async def get_lyria_status():
    """获取Google Lyria详细状态"""
    global social_audio_generator
    
    if not social_audio_generator:
        raise HTTPException(status_code=503, detail="音频生成器未初始化")
    
    try:
        lyria_status = social_audio_generator.lyria_engine.get_status_info()
        prompt_status = await social_audio_generator.prompt_manager.get_current_status()
        
        return JSONResponse(content={
            "lyria_engine": lyria_status,
            "prompt_manager": prompt_status,
            "timestamp": time.time()
        })
        
    except Exception as e:
        logger.error(f"获取Lyria状态失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取Lyria状态失败: {str(e)}")

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
    logger.info("启动社交EEG音频生成服务（Google Lyria增强版）...")
    
    # 检查Google AI SDK
    if GOOGLE_AI_AVAILABLE:
        logger.info("✅ Google AI SDK 可用")
    else:
        logger.warning("❌ Google AI SDK 不可用，将使用降级模式")
    
    # 检查音频设备
    try:
        devices = sd.query_devices()
        logger.info(f"可用音频设备: {len(devices)} 个")
        logger.info(f"默认输出设备: {sd.query_devices(sd.default.device[1])['name']}")
    except Exception as e:
        logger.warning(f"音频设备检查失败: {e}")
    
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