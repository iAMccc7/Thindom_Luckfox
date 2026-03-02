"""
项目全局配置文件
包含所有硬件参数、API配置、音频参数等
"""
import os
from dotenv import load_dotenv

# 加载 .env 文件中的环境变量
load_dotenv()

# ====== API 配置 ======
# DashScope API (语音识别)
DASHSCOPE_API_KEY = os.getenv("DASHSCOPE_API_KEY", "")

# MiniMax API (语音合成)
MINIMAX_API_KEY = os.getenv("MINIMAX_API_KEY", "")

# ====== GPIO 硬件配置 ======
USE_GPIO = True
SENSOR_PIN = 17              # 压力传感器引脚 (BCM 编号)
BUTTON_PIN = 3               # 按钮引脚 (BCM 编号，GPIO3，按下时为低电平)
LED_PIN = 27                 # LED 引脚 (BCM 编号)
DEBOUNCE_TIME = 0.3          # 消抖时间（秒）
BUTTON_LONG_PRESS_TIME = 2.0  # 按钮长按时间（秒）

# ====== 显示屏配置 (EP1831T) ======
SCREEN_RST_PIN = 23          # 复位引脚
SCREEN_DC_PIN = 24           # 数据/命令引脚
SCREEN_WIDTH = 360           # 屏幕宽度
SCREEN_HEIGHT = 360          # 屏幕高度
SCREEN_SPI_SPEED = 32000000  # SPI 速率 (32MHz)

# ====== 音频录制参数 ======
# 硬件麦克风参数
HW_SAMPLE_RATE = 48000       # 硬件采样率 (Hz)
HW_CHANNELS = 2              # 硬件声道数
HW_CHUNK = 9600              # 音频块大小
HW_FORMAT = 'paInt32'        # PyAudio 格式 (S32_LE)

# ASR 识别参数
ASR_SAMPLE_RATE = 16000      # ASR 要求的采样率 (Hz)
ASR_CHANNELS = 1             # ASR 声道数（单声道）
ASR_BITDEPTH = 16            # ASR 位深度

# 录音限制
MAX_DURATION = 30            # 最大录音时长（秒）

# ====== 语音合成参数 (MiniMax TTS) ======
TTS_MODEL = "speech-2.6-hd"
TTS_VOICE_ID = "male-qn-qingse"
TTS_SPEED = 1                # 语速
TTS_VOLUME = 1               # 音量
TTS_PITCH = 0                # 音调
TTS_SAMPLE_RATE = 32000      # 输出采样率
TTS_BITRATE = 128000         # 比特率
TTS_FORMAT = "mp3"           # 音频格式
TTS_CHANNEL = 1              # 声道数

# ====== 文件路径配置 ======
# 项目根目录
PROJECT_ROOT = "/home/pi/projects/tydeus"
TEMP_DATA_DIR = "/home/pi/projects/tydeus/temp_data"  # 临时数据目录（绝对路径）

SAVE_DIR = TEMP_DATA_DIR       # 录音文件保存目录
OUTPUT_DIR = TEMP_DATA_DIR     # 输出文件目录

# MQTT 相关文件路径
FILE_OBJECT_NAME = f"{TEMP_DATA_DIR}/object_name.txt"
FILE_VOICE_OUTPUT = f"{TEMP_DATA_DIR}/voice_output.txt"
FILE_CONVERSATION_ID = f"{TEMP_DATA_DIR}/conversation_id.txt"
FILE_WORDS_DATA = f"{TEMP_DATA_DIR}/words_data.json"

# ====== 日志配置 ======
DEBUG_LOG = True             # 是否启用调试日志
LOG_FORMAT = '%(asctime)s - %(levelname)s - %(message)s'
LOG_DIR = os.path.join(PROJECT_ROOT, "logs")  # 使用绝对路径
LOG_FILE = os.path.join(LOG_DIR, "system.log")  # 使用绝对路径

# ====== 单词卡片配置 ======
CARD_BG_COLOR = (246, 235, 255)      # 背景色 #F6EBFF
CARD_CIRCLE_COLOR = (255, 255, 255)  # 圆形背景色
CARD_TEXT_COLOR = (0, 0, 0)          # 文字颜色
CARD_IMAGE_SIZE = 120                # 默认图片大小
CARD_IMAGE_Y_OFFSET = -30            # 图片 Y 轴偏移

# ====== 进度环配置 ======
PROGRESS_RING_WIDTH = 5                              # 进度环宽度（像素）
PROGRESS_RING_COLOR_COMPLETED = (76, 175, 80)        # 已完成部分颜色（绿色）
PROGRESS_RING_COLOR_INCOMPLETE = (200, 200, 200)     # 未完成部分颜色（灰色）
PROGRESS_RING_COLOR_LOCKED = (100, 100, 100)         # 锁定状态颜色（深灰色）

# ====== 字体路径 ======
FONT_EN_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
FONT_CN_PATH = "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc"
FONT_EN_SIZE = 48
FONT_CN_SIZE = 32

# ====== SOX 音频转换参数 ======
SOX_VOLUME_GAIN = 10.0        # 音量增益倍数

# ====== ASR 识别参数 ======
ASR_MODEL = "paraformer-v2"  # DashScope ASR模型
ASR_FORMAT = "wav"           # 音频格式

# ====== MQTT 配置 ======
MQTT_BROKER = os.getenv("MQTT_BROKER", "47.110.250.41")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
DEVICE_ID = os.getenv("DEVICE_ID", "tydeus123")

# Topics - Outbound (Device -> Server)
TOPIC_OBJECT_DETECTED = "device/object_detected"
TOPIC_USER_RESPONSE = "device/user_response"
TOPIC_USER_STOP = "device/user_stop"

# Topics - Inbound (Server -> Device)
# format: server/device/{device_id}/...
TOPIC_AGENT_RESPONSE_OBJECT = f"server/device/{DEVICE_ID}/object_detected/agent_response"
TOPIC_AGENT_RESPONSE_USER = f"server/device/{DEVICE_ID}/user_response/agent_response"
TOPIC_USER_STOP_RESPONSE = f"server/device/{DEVICE_ID}/user_stop/response"