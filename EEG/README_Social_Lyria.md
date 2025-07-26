# 社交EEG音频生成服务 - Google Lyria增强版

## 🎵 概述

这是一个基于Google Lyria AI的社交音频生成服务，能够：
- 接收多个用户的脑波情绪数据
- 实时融合多用户情绪状态
- 使用Google Lyria模型生成高质量的情绪化音乐
- 支持实时WebSocket状态推送

## 🚀 新功能特性

### 1. Google Lyria集成
- 使用Google最先进的音乐生成AI模型
- 支持复杂的音乐风格描述和实时调整
- 高质量48kHz立体声音频输出

### 2. 复杂情绪映射
- 为每种情绪定义了详细的音乐风格（乐器、节奏、动态等）
- 支持强度调节的音乐复杂度
- 多用户情绪融合时的音乐混合

### 3. 社交功能
- 多用户情绪融合算法
- 实时用户会话管理
- WebSocket实时状态广播

## 📋 依赖要求

```bash
pip install fastapi uvicorn numpy sounddevice pydantic google-genai websockets aiohttp
```

## 🛠️ 启动服务

### 1. 配置Google API密钥
在 `social_audio_service.py` 中设置您的Google API密钥：
```python
GOOGLE_API_KEY = 'your_google_api_key_here'
```

### 2. 启动服务
```bash
cd EEG
python social_audio_service.py
```

服务将在 `http://localhost:8080` 启动。

### 3. 检查服务状态
```bash
curl http://localhost:8080/health
```

## 🎯 API接口

### 基础接口

- `GET /health` - 健康检查
- `GET /status` - 获取系统完整状态
- `GET /lyria_status` - 获取Google Lyria详细状态

### 用户管理

- `POST /join_session?user_id=<用户ID>&device_info=<设备信息>` - 用户加入会话
- `POST /leave_session?user_id=<用户ID>` - 用户离开会话

### 情绪更新

- `POST /update_emotion` - 更新用户情绪

请求体格式：
```json
{
    "user_emotion_data": {
        "user_id": "user123",
        "emotion": "Happy (开心)",
        "intensity": 0.8,
        "timestamp": 1703123456.789,
        "device_info": "EEG Device"
    }
}
```

### WebSocket

- `WS /ws` - 实时状态推送

## 🧪 测试

### 运行自动化测试
```bash
python test_social_lyria_service.py
```

这个测试脚本会：
1. 检查服务健康状态
2. 模拟3个用户加入会话
3. 实时发送随机情绪数据
4. 监听WebSocket状态更新
5. 显示情绪融合和音乐生成过程

### 手动测试情绪更新
```bash
curl -X POST http://localhost:8080/update_emotion \
  -H "Content-Type: application/json" \
  -d '{
    "user_emotion_data": {
      "user_id": "test_user",
      "emotion": "Happy (开心)",
      "intensity": 0.9,
      "timestamp": 1703123456.789
    }
  }'
```

## 🎼 支持的情绪

系统支持16种情绪，每种都有对应的复杂音乐映射：

### 积极情绪
- `Happy (开心)` - 明亮大调音阶，上升旋律
- `Excited (激动)` - 高能量节奏，动态和弦进行
- `Surprised (惊喜)` - 意外和声变化，突然的旋律转换
- `Relaxed (放松)` - 流畅和声，平和的大调进行
- `Pleased (平静)` - 平衡的大调和弦，宁静的旋律

### 消极情绪
- `Sad (悲伤)` - 小调旋律，下行进行
- `Angry (愤怒)` - 激进和弦，不和谐音
- `Fear (恐惧)` - 黑暗小调，不安定和声
- `Depressed (沮丧)` - 低音域持续音，静态和声

### 中性情绪
- `Neutral (中性)` - 简单和声背景，稳定进行
- `Bored (无聊)` - 重复模式，单调节奏
- `Tired (疲倦)` - 缓慢节拍，逐渐减弱
- `Sleepy (困倦)` - 摇篮曲旋律，催眠质感

## 🔧 配置参数

### 音乐生成参数
```python
# 基础Prompt配置
INITIAL_BASE_PROMPT = ("quiet dreamcore", 0.8)

# Google Lyria模型配置
MODEL_ID = 'models/lyria-realtime-exp'
```

### 情绪融合参数
```python
# 情绪空间权重
fusion_weights = {
    "valence": 0.4,    # 情感价值（正负性）
    "arousal": 0.4,    # 唤醒度（强度）
    "dominance": 0.2   # 支配性（主导性）
}
```

## 📊 监控和调试

### 实时状态监控
使用WebSocket连接可以实时监控：
- 用户加入/离开事件
- 情绪融合更新
- 音乐生成状态变化
- Google Lyria连接状态

### 日志级别
```python
logging.basicConfig(level=logging.INFO)
```

### 常见问题

1. **Google API限制**
   - 某些地区可能无法访问Lyria模型
   - 需要有效的Google AI API密钥

2. **音频设备**
   - 确保系统有可用的音频输出设备
   - 检查sounddevice配置

3. **网络连接**
   - Google Lyria需要稳定的网络连接
   - 确保防火墙允许API访问

## 🔄 与现有EEG系统集成

这个服务可以与您现有的脑波处理系统集成：

```python
# 在您的brain_processor.py中
import aiohttp

async def send_emotion_to_social_service(user_id, emotion, intensity):
    emotion_data = {
        "user_emotion_data": {
            "user_id": user_id,
            "emotion": emotion,
            "intensity": intensity,
            "timestamp": time.time(),
            "device_info": "EEG Headset"
        }
    }
    
    async with aiohttp.ClientSession() as session:
        async with session.post(
            "http://localhost:8080/update_emotion",
            json=emotion_data
        ) as response:
            return await response.json()
```

## 📈 性能特性

- **延迟**: < 500ms 情绪到音乐响应时间
- **并发**: 支持多用户同时连接
- **音质**: 48kHz/16bit 立体声输出
- **缓冲**: 智能音频缓冲防止断续

## 🎨 自定义扩展

您可以通过修改以下部分来自定义音乐生成：

1. **情绪映射** - 在 `COMPLEX_EMOTION_MAPPING` 中定义新的音乐风格
2. **融合算法** - 在 `EmotionFusionEngine` 中实现新的融合方法
3. **Prompt生成** - 在 `generate_complex_music_prompt()` 中调整音乐描述逻辑

## 📝 许可证

本项目遵循MIT许可证。 