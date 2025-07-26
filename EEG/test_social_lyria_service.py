#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Social Audio Service with Google Lyria - Test Script
社交音频服务（Google Lyria版本）测试脚本

演示如何使用增强版的社交音频服务：
1. 多用户情绪输入
2. 实时音乐生成
3. WebSocket状态监听
"""

import asyncio
import aiohttp
import json
import time
import random
from typing import List, Dict
import websockets

# 服务配置
SERVICE_URL = "http://localhost:8080"
WEBSOCKET_URL = "ws://localhost:8080/ws"

# 模拟的情绪标签
EMOTIONS = [
    "Happy (开心)", "Excited (激动)", "Surprised (惊喜)", "Fear (恐惧)", 
    "Angry (愤怒)", "Contempt (轻蔑)", "Disgust (厌恶)", "Miserable (痛苦)", 
    "Sad (悲伤)", "Depressed (沮丧)", "Bored (无聊)", "Tired (疲倦)", 
    "Sleepy (困倦)", "Relaxed (放松)", "Pleased (平静)", "Neutral (中性)"
]

class SocialAudioTester:
    """社交音频服务测试器"""
    
    def __init__(self, service_url: str = SERVICE_URL):
        self.service_url = service_url
        self.session = None
        self.users = []
        
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    async def check_health(self):
        """检查服务健康状态"""
        try:
            async with self.session.get(f"{self.service_url}/health") as response:
                data = await response.json()
                print(f"✅ 服务健康状态: {data}")
                return data.get("status") == "healthy"
        except Exception as e:
            print(f"❌ 健康检查失败: {e}")
            return False
    
    async def get_status(self):
        """获取系统状态"""
        try:
            async with self.session.get(f"{self.service_url}/status") as response:
                data = await response.json()
                print(f"📊 系统状态:")
                print(f"   - 播放状态: {data.get('is_playing')}")
                print(f"   - 初始化状态: {data.get('is_initialized')}")
                print(f"   - Google AI可用: {data.get('google_ai_available')}")
                print(f"   - 用户数量: {data.get('user_count')}")
                print(f"   - 活跃用户数量: {data.get('active_user_count')}")
                print(f"   - WebSocket连接数: {data.get('websocket_connections')}")
                return data
        except Exception as e:
            print(f"❌ 获取状态失败: {e}")
            return None
    
    async def get_lyria_status(self):
        """获取Google Lyria详细状态"""
        try:
            async with self.session.get(f"{self.service_url}/lyria_status") as response:
                data = await response.json()
                lyria_engine = data.get("lyria_engine", {})
                prompt_manager = data.get("prompt_manager", {})
                
                print(f"🎵 Google Lyria状态:")
                print(f"   - 状态: {lyria_engine.get('status')}")
                print(f"   - 消息: {lyria_engine.get('message')}")
                print(f"   - 播放中: {lyria_engine.get('is_playing')}")
                print(f"   - 缓冲进度: {lyria_engine.get('buffer_progress')}%")
                
                print(f"🎼 Prompt管理器状态:")
                print(f"   - 当前情绪: {prompt_manager.get('current_emotion')}")
                print(f"   - 当前强度: {prompt_manager.get('current_intensity'):.2f}")
                print(f"   - 基础Prompt: {prompt_manager.get('base_prompt')}")
                
                return data
        except Exception as e:
            print(f"❌ 获取Lyria状态失败: {e}")
            return None
    
    async def join_session(self, user_id: str, device_info: str = "Test Device"):
        """用户加入会话"""
        try:
            params = {"user_id": user_id, "device_info": device_info}
            async with self.session.post(f"{self.service_url}/join_session", params=params) as response:
                data = await response.json()
                if data.get("status") == "success":
                    self.users.append(user_id)
                    print(f"👤 用户 {user_id} 加入会话成功")
                    return True
                else:
                    print(f"❌ 用户 {user_id} 加入会话失败: {data}")
                    return False
        except Exception as e:
            print(f"❌ 用户 {user_id} 加入会话异常: {e}")
            return False
    
    async def leave_session(self, user_id: str):
        """用户离开会话"""
        try:
            params = {"user_id": user_id}
            async with self.session.post(f"{self.service_url}/leave_session", params=params) as response:
                data = await response.json()
                if data.get("status") == "success":
                    if user_id in self.users:
                        self.users.remove(user_id)
                    print(f"👋 用户 {user_id} 离开会话成功")
                    return True
                else:
                    print(f"❌ 用户 {user_id} 离开会话失败: {data}")
                    return False
        except Exception as e:
            print(f"❌ 用户 {user_id} 离开会话异常: {e}")
            return False
    
    async def update_emotion(self, user_id: str, emotion: str, intensity: float):
        """更新用户情绪"""
        try:
            emotion_data = {
                "user_emotion_data": {
                    "user_id": user_id,
                    "emotion": emotion,
                    "intensity": intensity,
                    "timestamp": time.time(),
                    "device_info": "Test Device"
                }
            }
            
            async with self.session.post(
                f"{self.service_url}/update_emotion", 
                json=emotion_data
            ) as response:
                data = await response.json()
                if data.get("status") == "success":
                    print(f"😊 用户 {user_id} 情绪更新: {emotion} (强度: {intensity:.2f})")
                    return True
                else:
                    print(f"❌ 用户 {user_id} 情绪更新失败: {data}")
                    return False
        except Exception as e:
            print(f"❌ 用户 {user_id} 情绪更新异常: {e}")
            return False
    
    async def websocket_listener(self, duration: int = 30):
        """WebSocket状态监听器"""
        try:
            async with websockets.connect(WEBSOCKET_URL) as websocket:
                print(f"🔗 WebSocket连接已建立，监听 {duration} 秒...")
                
                start_time = time.time()
                while time.time() - start_time < duration:
                    try:
                        # 发送心跳包
                        await websocket.send(json.dumps({"type": "ping"}))
                        
                        # 等待消息
                        message = await asyncio.wait_for(websocket.recv(), timeout=1.0)
                        data = json.loads(message)
                        
                        msg_type = data.get("type")
                        if msg_type == "initial_status":
                            print(f"📡 收到初始状态")
                        elif msg_type == "emotion_update":
                            fused_emotion = data.get("fused_emotion", {})
                            print(f"🎭 情绪融合更新: {fused_emotion.get('primary_emotion')} "
                                  f"(强度: {fused_emotion.get('fusion_intensity'):.2f}, "
                                  f"用户数: {fused_emotion.get('user_count')})")
                        elif msg_type == "user_update":
                            users = data.get("users", [])
                            print(f"👥 用户更新: {len(users)} 个用户在线")
                        elif msg_type == "pong":
                            pass  # 心跳回应
                        else:
                            print(f"📨 WebSocket消息: {msg_type}")
                            
                    except asyncio.TimeoutError:
                        continue
                    except Exception as e:
                        print(f"❌ WebSocket消息处理错误: {e}")
                        break
                        
        except Exception as e:
            print(f"❌ WebSocket连接失败: {e}")

async def simulate_user_emotions(tester: SocialAudioTester, user_id: str, duration: int = 30):
    """模拟用户情绪变化"""
    print(f"🎭 开始模拟用户 {user_id} 的情绪变化...")
    
    start_time = time.time()
    while time.time() - start_time < duration:
        # 随机选择情绪和强度
        emotion = random.choice(EMOTIONS)
        intensity = random.uniform(0.1, 1.0)
        
        await tester.update_emotion(user_id, emotion, intensity)
        
        # 等待3-8秒再更新
        await asyncio.sleep(random.uniform(3, 8))

async def main():
    """主测试函数"""
    print("🚀 开始测试社交音频服务（Google Lyria版本）...")
    
    async with SocialAudioTester() as tester:
        # 1. 检查服务健康状态
        print("\n" + "="*50)
        print("1️⃣ 检查服务健康状态")
        print("="*50)
        
        if not await tester.check_health():
            print("❌ 服务不可用，请先启动服务")
            return
        
        # 2. 获取初始状态
        print("\n" + "="*50)
        print("2️⃣ 获取系统状态")
        print("="*50)
        
        await tester.get_status()
        
        # 3. 获取Lyria状态
        print("\n" + "="*50)
        print("3️⃣ 获取Google Lyria状态")
        print("="*50)
        
        await tester.get_lyria_status()
        
        # 4. 添加用户会话
        print("\n" + "="*50)
        print("4️⃣ 添加用户会话")
        print("="*50)
        
        users = ["Alice", "Bob", "Charlie"]
        for user in users:
            await tester.join_session(user)
            await asyncio.sleep(1)
        
        # 5. 启动WebSocket监听器
        print("\n" + "="*50)
        print("5️⃣ 启动WebSocket监听器")
        print("="*50)
        
        # 启动WebSocket监听任务
        websocket_task = asyncio.create_task(
            tester.websocket_listener(duration=60)
        )
        
        # 6. 模拟用户情绪变化
        print("\n" + "="*50)
        print("6️⃣ 模拟多用户情绪变化")
        print("="*50)
        
        # 启动多个用户的情绪模拟任务
        emotion_tasks = []
        for user in users:
            task = asyncio.create_task(
                simulate_user_emotions(tester, user, duration=45)
            )
            emotion_tasks.append(task)
            await asyncio.sleep(2)  # 错开启动时间
        
        # 7. 等待所有任务完成
        print("\n⏳ 等待测试完成...")
        await asyncio.gather(*emotion_tasks)
        
        # 8. 获取最终状态
        print("\n" + "="*50)
        print("8️⃣ 获取最终状态")
        print("="*50)
        
        await tester.get_status()
        await tester.get_lyria_status()
        
        # 9. 清理用户会话
        print("\n" + "="*50)
        print("9️⃣ 清理用户会话")
        print("="*50)
        
        for user in users:
            await tester.leave_session(user)
            await asyncio.sleep(1)
        
        # 停止WebSocket监听
        websocket_task.cancel()
        try:
            await websocket_task
        except asyncio.CancelledError:
            pass
        
        print("\n✅ 测试完成！")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 用户中断测试")
    except Exception as e:
        print(f"\n❌ 测试异常: {e}") 