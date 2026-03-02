# Thingdom 物语

一个基于 LuckFox Pico Ultra W 的智能交互系统，集成了物体识别、语音交互和显示屏反馈功能。

## 📋 项目简介

Thindom 是一个教育机器人项目，通过摄像头进行物体识别，通过麦克风进行语音交互，并通过显示屏提供视觉反馈。系统支持 MQTT 通信，可以与远程服务器进行实时交互。

### 主要功能

- **物体识别**：使用 YOLO 模型进行实时物体检测和识别
- **语音交互**：支持语音录制、语音识别（ASR）和语音合成（TTS）
- **显示屏反馈**：在 EP1831T 显示屏上显示情绪图片、单词卡片和学习进度
- **按钮控制**：通过物理按钮控制录音和程序流程
- **MQTT 通信**：与远程服务器进行双向通信

## 🛠️ 硬件要求

### 必需硬件

- **LuckFox Pico Ultra W**
- **EP1831T 显示屏**（360x360 像素，SPI 接口）
- **按钮**（连接到 GPIO3，按下时为低电平）
- **麦克风**（支持立体声录音）
- **摄像头**（用于物体识别）

### 可选硬件

- **压力传感器**（连接到 GPIO17）
- **LED**（连接到 GPIO27）

### 硬件连接

#### 树莓派硬件连接（40 引脚）

| 引脚 | 连接对象 | 引脚 | 连接对象 |
|------|---------|------|---------|
| Pin 1 | 面包板VCC3.3V | Pin 2 | 风扇VCC |
| Pin 3 | 悬空 | Pin 4 | 面包板VCC5V |
| Pin 5 | **BUTTON** | Pin 6 | 风扇GND |
| Pin 7 | 悬空 | Pin 8 | 悬空 |
| Pin 9 | 面包板GND | Pin 10 | 悬空 |
| Pin 11 | 压力传感器DO | Pin 12 | 麦克风SCK |
| Pin 13 | LED | Pin 14 | 悬空 |
| Pin 15 | 悬空 | Pin 16 | 显示屏9脚 |
| Pin 17 | 悬空 | Pin 18 | 显示屏6脚 |
| Pin 19 | 显示屏5脚 | Pin 20 | 悬空 |
| Pin 21 | 悬空 | Pin 22 | 悬空 |
| Pin 23 | 显示屏7脚 | Pin 24 | 显示屏8脚 |
| Pin 25 | 悬空 | Pin 26 | 悬空 |
| Pin 27 | 悬空 | Pin 28 | 悬空 |
| Pin 29 | 悬空 | Pin 30 | 悬空 |
| Pin 31 | 悬空 | Pin 32 | 悬空 |
| Pin 33 | 悬空 | Pin 34 | 悬空 |
| Pin 35 | 麦克风WS | Pin 36 | 悬空 |
| Pin 37 | 悬空 | Pin 38 | 麦克风SD |
| Pin 39 | 悬空 | Pin 40 | 悬空 |

**关键连接说明：**
- **Pin 5 (GPIO3)**：按钮，按下时为低电平，用于录音控制和长按退出
- **Pin 11 (GPIO17)**：压力传感器DO（可选）
- **Pin 13 (GPIO27)**：LED（可选）
- **Pin 16 (GPIO23)**：显示屏9脚（RST复位引脚）
- **Pin 18 (GPIO24)**：显示屏6脚（DC数据/命令引脚）
- **Pin 19 (GPIO10)**：显示屏5脚（SPI MOSI）
- **Pin 23 (GPIO11)**：显示屏7脚（SPI SCLK）
- **Pin 12 (GPIO18)**：麦克风SCK（时钟）
- **Pin 35 (GPIO19)**：麦克风WS（字选择）
- **Pin 38 (GPIO20)**：麦克风SD（数据）

#### 显示屏硬件连接（EP1831T 16 引脚）

| 引脚 | 连接对象 | 说明 |
|------|---------|------|
| Pin 1 | GND | 地线 |
| Pin 2 | VCC3.3V | 3.3V 电源 |
| Pin 3 | 悬空 | 未连接 |
| Pin 4 | 悬空 | 未连接 |
| Pin 5 | 树莓派19脚 (GPIO10) | SPI MOSI |
| Pin 6 | 树莓派18脚 (GPIO24) | DC 数据/命令引脚 |
| Pin 7 | 树莓派23脚 (GPIO11) | SPI SCLK |
| Pin 8 | 树莓派24脚 (GPIO8) | SPI CS |
| Pin 9 | 树莓派16脚 (GPIO23) | RST 复位引脚 |
| Pin 10 | VCC3.3V | 3.3V 电源 |
| Pin 11 | 悬空 | 未连接 |
| Pin 12 | 悬空 | 未连接 |
| Pin 13 | 悬空 | 未连接 |
| Pin 14 | 悬空 | 未连接 |
| Pin 15 | VCC3V | 3V 电源 |
| Pin 16 | GND | 地线 |

**显示屏连接映射：**
- **RST (Pin 9)** → 树莓派 Pin 16 (GPIO23)
- **DC (Pin 6)** → 树莓派 Pin 18 (GPIO24)
- **MOSI (Pin 5)** → 树莓派 Pin 19 (GPIO10, SPI0 MOSI)
- **SCLK (Pin 7)** → 树莓派 Pin 23 (GPIO11, SPI0 SCLK)
- **CS (Pin 8)** → 树莓派 Pin 24 (GPIO8, SPI0 CE0)

## 📦 安装与配置

### 1. 系统要求

- Ubuntu22.04
- Python 3.8 或更高版本
- 已启用 SPI 接口（`raspi-config` → `Interfacing Options` → `SPI` → `Enable`）

### 2. 克隆项目

```bash
cd /home/pi/projects
git clone <repository-url> tydeus
cd tydeus
```

### 3. 安装依赖

运行自动安装脚本：

```bash
chmod +x install_dependencies.sh
./install_dependencies.sh
```

或者手动安装：

```bash
# 安装系统依赖
sudo apt update
sudo apt install -y sox mpv python3-spidev

# 安装 Python 依赖
pip3 install --break-system-packages -r requirements.txt
```

### 4. 配置 SPI 权限

确保用户已添加到 `spi` 组：

```bash
sudo usermod -aG spi $USER
```

然后重新登录以使组权限生效。

### 5. 配置 API 密钥和 MQTT 服务器

复制 `.env.example` 文件为 `.env`，并编辑 `.env` 文件配置敏感信息：

```bash
cp .env.example .env
nano .env
```

在 `.env` 文件中配置以下内容：

```bash
# API 密钥配置
DASHSCOPE_API_KEY=your-dashscope-api-key-here
MINIMAX_API_KEY=your-minimax-api-key-here

# MQTT 配置
MQTT_BROKER=your-mqtt-broker-ip
MQTT_PORT=1883
DEVICE_ID=your-device-id
```

**注意**：`.env` 文件包含敏感信息，已被 `.gitignore` 忽略，不会被提交到 Git 仓库。

## 🚀 使用方法

### 运行主程序

```bash
cd /home/pi/projects/tydeus
python3 main.py
```

### 运行独立测试

#### 1. 物体识别测试

```bash
python3 modules/1_yolo_test.py
```

功能：
- 拍摄照片
- 使用 YOLO 模型识别物体
- 发送识别结果到服务器
- 等待服务器响应并执行

#### 2. 音频交互测试

```bash
python3 modules/2_audio_test.py
```

功能：
- 等待按钮按下开始录音
- 再次按下按钮停止录音
- 进行语音识别
- 发送识别结果到服务器
- 等待服务器响应并执行

#### 3. 结束对话测试

```bash
python3 modules/3_finish_test.py
```

功能：
- 等待按钮长按（2秒）触发
- 发送结束对话消息到服务器
- 等待服务器响应并执行

## 📁 项目结构

```
tydeus/
├── main.py                 # 主程序入口
├── config.py               # 全局配置文件
├── requirements.txt        # Python 依赖列表
├── install_dependencies.sh  # 依赖安装脚本
├── .env                    # 环境变量配置文件（需自行创建）
├── .env.example            # 环境变量配置模板
├── modules/                # 功能模块目录
│   ├── 1_yolo_test.py      # 物体识别测试
│   ├── 2_audio_test.py     # 音频交互测试
│   ├── 3_finish_test.py    # 结束对话测试
│   └── play_pi.py          # 硬件执行响应（TTS、显示等）
├── hardware/               # 硬件驱动模块
│   ├── __init__.py
│   ├── button.py           # 按钮驱动
│   ├── pressure_sensor.py  # 压力传感器驱动
│   ├── camera_capture.py   # 摄像头驱动
│   ├── audio_recorder.py   # 音频录制
│   ├── audio_player.py     # 音频播放
│   └── ep1831t_driver.py   # EP1831T 显示屏驱动
├── utils/                  # 工具模块
│   ├── __init__.py
│   ├── object_detection.py # YOLO 物体检测
│   ├── speech_recognition.py  # 语音识别（ASR）
│   ├── text_to_speech.py   # 语音合成（TTS）
│   └── flashcard.py        # 单词卡片生成
├── comm/                   # 通信模块
│   └── mqtt_client.py      # MQTT 客户端
├── yolo/                   # YOLO 模型文件
├── imgs/                   # 图片资源
│   ├── moods/              # 情绪图片
│   └── waiting/            # 等待状态图片
│       ├── thinking.png    # 思考中
│       ├── recording.png   # 录音中
│       └── shutdown.png    # 关机
├── temp_data/              # 临时数据目录（Git 忽略）
└── logs/                   # 日志目录（Git 忽略）
```

## 🔧 配置说明

### GPIO 配置

在 `config.py` 中可以修改 GPIO 引脚配置：

```python
BUTTON_PIN = 3               # 按钮引脚
SENSOR_PIN = 17              # 压力传感器引脚
LED_PIN = 27                 # LED 引脚
BUTTON_LONG_PRESS_TIME = 2.0  # 按钮长按时间（秒）
```

### 音频配置

```python
HW_SAMPLE_RATE = 48000       # 硬件采样率
ASR_SAMPLE_RATE = 16000      # ASR 识别采样率
SOX_VOLUME_GAIN = 10.0       # 音量增益倍数
```

### 显示屏配置

```python
SCREEN_WIDTH = 360           # 屏幕宽度
SCREEN_HEIGHT = 360          # 屏幕高度
SCREEN_SPI_SPEED = 32000000  # SPI 速率
```

### 进度环配置

```python
PROGRESS_RING_WIDTH = 5                              # 进度环宽度（像素）
PROGRESS_RING_COLOR_COMPLETED = (76, 175, 80)        # 已完成颜色（绿色）
PROGRESS_RING_COLOR_INCOMPLETE = (200, 200, 200)     # 未完成颜色（灰色）
PROGRESS_RING_COLOR_LOCKED = (100, 100, 100)         # 锁定状态颜色（深灰色）
```

## 📝 工作流程

### 主程序流程（main.py）

1. **初始化阶段**
   - 初始化按钮和显示屏驱动
   - 启动按钮长按监控线程（全局监听）

2. **Stage 1: 物体识别**
   - 执行 `modules/1_yolo_test.py`
   - 拍摄照片并识别物体
   - 发送识别结果到服务器
   - 等待响应并执行

3. **Stage 2: 音频交互循环**
   - 初始化 MQTT、音频录音器、语音识别器
   - 循环执行以下步骤：
     - 等待按钮按下开始录音
     - 显示 `recording.png`
     - 等待按钮再次按下停止录音
     - 进行语音识别
     - 显示 `thinking.png`
     - 发送识别结果到服务器
     - 等待服务器响应并执行
   - 如果检测到按钮长按，退出循环

4. **Stage 3: 结束对话**
   - 如果检测到按钮长按：
     - 显示 `shutdown.png`
     - 执行 `modules/3_finish_test.py`
     - 发送结束对话消息
     - 等待响应并执行
     - 熄灭显示屏

### 按钮操作

- **短按**：在音频交互循环中，第一次按下开始录音，第二次按下停止录音
- **长按（2秒）**：全局中断，退出当前操作并执行结束对话流程

## 🎨 显示功能

### 情绪图片

系统支持显示情绪图片（`imgs/moods/{mood_id}.png`），用于表达机器人的情绪状态。

### 单词卡片

系统可以生成并显示单词卡片，包含：
- 英文单词
- 中文翻译
- 单词图片（如果有）
- 进度环（显示学习进度）

### 等待状态图片

- `thinking.png`：等待服务器响应时显示
- `recording.png`：录音过程中显示
- `shutdown.png`：关机时显示

### 进度环

在显示情绪图片或单词卡片时，屏幕边缘会显示一个 5 像素宽的圆形进度环，用于可视化学习进度：
- **绿色**：已完成部分
- **灰色**：未完成部分
- **深灰色**：锁定状态

## 📡 MQTT 通信

### 发布主题（Device → Server）

- `device/object_detected`：物体识别结果
- `device/user_response`：用户语音识别结果
- `device/user_stop`：用户停止请求

### 订阅主题（Server → Device）

- `server/device/{device_id}/object_detected/agent_response`：物体识别响应
- `server/device/{device_id}/user_response/agent_response`：用户响应
- `server/device/{device_id}/user_stop/response`：停止响应

### 消息格式

#### 物体识别消息

```json
{
  "object_name": "apple",
  "device_id": "tydeus123",
  "conversation_id": 123
}
```

#### 用户响应消息

```json
{
  "human_audio_message": "Hello",
  "device_id": "tydeus123",
  "conversation_id": 123,
  "verb": {...},
  "noun": {...},
  "adjective": {...},
  ...
}
```

#### 服务器响应消息

```json
{
  "message": "Hello, 小明",
  "mood_id": 1,
  "verb": null,
  "noun": null,
  "adjective": {
    "word": "red",
    "chinese_translation": "红的"
  },
  "islands_progress": [
    {
      "island_inner_id": 1,
      "learned_percentage": "50.00",
      "is_locked": false
    }
  ]
}
```

## 🐛 故障排除

### 常见问题

1. **GPIO 权限错误**
   ```bash
   sudo usermod -aG gpio $USER
   sudo usermod -aG spi $USER
   # 重新登录
   ```

2. **SPI 未启用**
   ```bash
   sudo raspi-config
   # Interfacing Options → SPI → Enable
   ```

3. **音频录制无声音**
   - 检查麦克风连接
   - 运行 `python3 -c "from hardware.audio_recorder import AudioRecorder; AudioRecorder().list_input_devices()"` 查看可用设备
   - 检查 `config.py` 中的音频配置

4. **显示屏无显示**
   - 检查 SPI 连接
   - 检查 GPIO 引脚配置
   - 查看日志文件 `logs/system.log`

5. **MQTT 连接失败**
   - 检查网络连接
   - 验证 MQTT 服务器地址和端口
   - 检查防火墙设置

### 日志文件

系统日志保存在 `logs/system.log`，可以通过以下命令查看：

```bash
tail -f /home/pi/projects/tydeus/logs/system.log
```

## 📄 许可证

详见 [LICENSE](LICENSE) 文件。

## 👥 贡献

欢迎提交 Issue 和 Pull Request！

## 📧 联系方式

如有问题或建议，请通过 Issue 反馈。

---

## 🔐 安全说明

本项目使用 `.env` 文件管理敏感信息（API 密钥、MQTT 配置等）。`.env` 文件已被 `.gitignore` 忽略，不会被提交到 Git 仓库。

**重要提示**：
- 首次使用时，请复制 `.env.example` 为 `.env` 并填写真实的配置信息
- 不要将 `.env` 文件提交到版本控制系统
- 如果需要在其他环境部署，请手动创建 `.env` 文件

