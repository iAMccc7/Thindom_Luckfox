#!/usr/bin/env python3
"""
音频交互测试
用于测试语音交互流程
"""
import sys
import os
import time
import json
import threading
import logging
from datetime import datetime
from config import *
from comm.mqtt_client import MqttHandler
# 导入同目录下的 play_pi.py 文件中的 execute_response
import importlib.util
_play_pi_file_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "play_pi.py")
_play_pi_spec = importlib.util.spec_from_file_location("play_pi_file", _play_pi_file_path)
_play_pi_module = importlib.util.module_from_spec(_play_pi_spec)
_play_pi_spec.loader.exec_module(_play_pi_module)
execute_response = _play_pi_module.execute_response
# 导入硬件工具
from hardware.button import Button
from hardware.audio_recorder import AudioRecorder
from hardware.ep1831t_driver import EP1831TDriver
# 导入语音识别工具
from utils.speech_recognition import SpeechRecognition

# --- 全局同步事件 ---
response_received_event = threading.Event()

# --- 日志设置 ---
if not os.path.exists(LOG_DIR):
    os.makedirs(LOG_DIR)

logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    encoding='utf-8'
)

def log_system(message):
    """辅助函数：同时打印到控制台和写入日志文件。"""
    print(message)
    logging.info(message)

# --- 文件处理辅助函数 ---

def ensure_temp_data_dir():
    """确保临时数据目录和必要文件存在。"""
    if not os.path.exists(TEMP_DATA_DIR):
        os.makedirs(TEMP_DATA_DIR)
    if not os.path.exists(FILE_CONVERSATION_ID):
        with open(FILE_CONVERSATION_ID, 'w', encoding='utf-8') as f:
            f.write("")
    # 确保 words_data.json 存在
    if not os.path.exists(FILE_WORDS_DATA):
        default_words = {
            "verb": None, "noun": None, "adjective": None,
            "exclamation": None, "discourse_marker": None, "adverb": None
        }
        with open(FILE_WORDS_DATA, 'w', encoding='utf-8') as f:
            json.dump(default_words, f, ensure_ascii=False, indent=4)

def get_conversation_id():
    """从本地文件读取 conversation_id。"""
    try:
        if os.path.exists(FILE_CONVERSATION_ID):
            with open(FILE_CONVERSATION_ID, 'r', encoding='utf-8') as f:
                return f.read().strip()
    except Exception as e:
        log_system(f"[Error] 无法读取 conversation_id: {e}")
    return ""

def save_conversation_id(conv_id):
    """保存 conversation_id 到本地文件。"""
    try:
        with open(FILE_CONVERSATION_ID, 'w', encoding='utf-8') as f:
            f.write(str(conv_id))
        logging.info(f"Conversation ID 已更新: {conv_id}")
    except Exception as e:
        log_system(f"[Error] 无法保存 conversation_id: {e}")

def read_json_file(filepath):
    """读取 JSON 文件并返回字典。如果失败返回 None。"""
    try:
        if not os.path.exists(filepath):
            log_system(f"[Error] 文件未找到: {filepath}")
            return None
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read().strip()
            if not content:
                return {}
            return json.loads(content)
    except json.JSONDecodeError:
        log_system(f"[Error] 文件 {filepath} JSON 格式无效")
        return None
    except Exception as e:
        log_system(f"[Error] 读取 {filepath} 时出错: {e}")
        return None

def get_words_data():
    """读取用户手动管理的词汇数据。"""
    data = read_json_file(FILE_WORDS_DATA)
    if not data:
        return {
            "verb": None, "noun": None, "adjective": None,
            "exclamation": None, "discourse_marker": None, "adverb": None
        }
    return data

# --- MQTT 消息处理器 ---

def on_server_message(topic, payload):
    """
    当从服务器收到消息时的回调函数。
    """
    try:
        logging.info(f"收到 MQTT 消息，主题 {topic}: {payload}")
        data = json.loads(payload)
        
        # 1. 检查是否是停止对话的响应
        if topic == TOPIC_USER_STOP_RESPONSE:
            summary = data.get("conversation_summary", "未提供总结。")
            log_system(f"\n[System] 对话结束。总结: {summary}")
            response_received_event.set()
            return

        # 2. 正常交互响应
        # 提取并更新 conversation_id（如果存在）
        new_conv_id = data.get("conversation_id")
        if new_conv_id:
            save_conversation_id(new_conv_id)
            
        # 3. 调用硬件执行
        success = execute_response(data)
        if success:
            log_system("[System] 硬件执行成功完成。")
        else:
            log_system("[System] 硬件执行遇到问题。")
            
    except json.JSONDecodeError:
        log_system(f"[Error] 无法解码来自主题 {topic} 的 JSON 负载")
    except Exception as e:
        log_system(f"[Error] 处理服务器消息时出错: {e}")
    finally:
        # 只要处理完消息（如果是预期的流程），就释放等待锁
        response_received_event.set()

# --- 动画效果 ---

def wait_for_response(timeout=30, display_driver=None):
    """
    阻塞并打印加载动画，直到 response_received_event 被设置或超时。
    同时显示等待图片。
    """
    start_time = time.time()
    response_received_event.clear()
    
    # 显示等待图片（thinking.png）
    if display_driver:
        thinking_image_path = os.path.join(PROJECT_ROOT, "imgs", "waiting", "thinking.png")
        if os.path.exists(thinking_image_path):
            try:
                display_driver.display_image(thinking_image_path)
                log_system(f"[Display] 显示等待图片: {thinking_image_path}")
            except Exception as e:
                log_system(f"[Error] 显示等待图片失败: {e}")
    
    print("等待回复 ", end="", flush=True)
    dot_count = 0
    
    while not response_received_event.is_set():
        if time.time() - start_time > timeout:
            print("\n[Timeout] 服务器响应超时。")
            return
            
        time.sleep(0.1)  # 优化：从0.5秒缩短到0.1秒，加快响应
        print(".", end="", flush=True)
        dot_count += 1
        if dot_count >= 6:
            # 退格符用于重置点号 (简单的视觉黑魔法)
            print("\b" * 6 + "      " + "\b" * 6, end="", flush=True)
            dot_count = 0
            
    print("\n") # 响应后的换行

# --- 主逻辑 ---

def main():
    """音频交互测试主函数"""
    ensure_temp_data_dir()
    
    # 初始化 MQTT
    mqtt = MqttHandler(MQTT_BROKER, MQTT_PORT, DEVICE_ID)
    
    # 订阅主题
    subscriptions = [
        TOPIC_AGENT_RESPONSE_OBJECT,
        TOPIC_AGENT_RESPONSE_USER,
        TOPIC_USER_STOP_RESPONSE
    ]
    
    mqtt.start(subscriptions=subscriptions, callback=on_server_message)
    logging.info(f"音频测试已启动。设备 ID: {DEVICE_ID}")
    
    # 短暂等待连接（优化：从1秒缩短到0.2秒）
    time.sleep(0.2)
    
    print("\n=== 音频交互测试 ===")
    print(f"Device ID: {DEVICE_ID}")
    
    # 初始化显示屏驱动
    display_driver = None
    try:
        display_driver = EP1831TDriver()
        log_system("✓ 显示屏驱动初始化成功")
    except Exception as e:
        log_system(f"⚠ 显示屏驱动初始化失败: {e}")
        log_system("  将继续运行，但无法显示图片")
    
    # 初始化按钮
    button = None
    try:
        button = Button()
        log_system("✓ 按钮初始化成功")
    except Exception as e:
        log_system(f"⚠ 按钮初始化失败: {e}")
        log_system("  将跳过按钮检测")
    
    # 初始化音频录音器
    audio_recorder = None
    try:
        audio_recorder = AudioRecorder()
        log_system("✓ 音频录音器初始化成功")
    except Exception as e:
        log_system(f"⚠ 音频录音器初始化失败: {e}")
        log_system("  将跳过录音功能")
    
    # 初始化语音识别器
    speech_recognizer = None
    try:
        speech_recognizer = SpeechRecognition()
        log_system("✓ 语音识别器初始化成功")
    except Exception as e:
        log_system(f"⚠ 语音识别器初始化失败: {e}")
        log_system("  将跳过语音识别功能")
    
    try:
        # 1. 录音和识别阶段
        if button and audio_recorder and speech_recognizer:
            log_system("\n[Action] 开始录音和识别流程...")
            
            # 等待用户按下按钮开始录音
            log_system("  [等待] 请按下按钮开始录音...")
            if button._initialized:
                if not button.wait_for_press(timeout=None):
                    log_system("  ⚠ 等待按下按钮超时或失败")
                    return
                # 等待按钮释放，避免立即检测到按下状态
                log_system("  [等待] 请释放按钮...")
                if not button.wait_for_release(timeout=None):
                    log_system("  ⚠ 等待释放按钮超时或失败")
                    return
                # 添加短暂延迟，确保按钮状态稳定
                time.sleep(0.3)
                # 再次确认按钮处于未按下状态
                if button.is_pressed():
                    log_system("  ⚠ 按钮仍处于按下状态，请释放后再试")
                    return
            else:
                log_system("  ⚠ 按钮未初始化，跳过等待")
            
            # 开始录音
            log_system("  [录音] 开始录音...")
            audio_file_path = audio_recorder.start_recording()
            if not audio_file_path:
                log_system("  ⚠ 开始录音失败")
                return
            
            log_system(f"  ✓ 录音已开始: {audio_file_path}")
            
            # 显示录音等待图片（recording.png）
            if display_driver:
                recording_image_path = os.path.join(PROJECT_ROOT, "imgs", "waiting", "recording.png")
                if os.path.exists(recording_image_path):
                    try:
                        display_driver.display_image(recording_image_path)
                        log_system(f"[Display] 显示录音图片: {recording_image_path}")
                    except Exception as e:
                        log_system(f"[Error] 显示录音图片失败: {e}")
            
            log_system("  [等待] 请再次按下按钮停止录音...")
            
            # 等待用户再次按下按钮停止录音
            if button._initialized:
                # 先确保按钮处于未按下状态（避免立即检测到按下）
                while button.is_pressed():
                    time.sleep(0.1)
                # 等待新的按下事件
                if not button.wait_for_press(timeout=None):
                    log_system("  ⚠ 等待停止录音超时或失败")
                    audio_recorder.stop_recording()
                    return
            else:
                log_system("  ⚠ 按钮未初始化，跳过等待")
            
            # 停止录音
            log_system("  [录音] 停止录音...")
            audio_recorder.stop_recording()
            log_system("  ✓ 录音已停止")
            
            # 等待一小段时间确保录音文件已保存（stop_recording 会等待线程完成，但再等待一下更保险）
            time.sleep(0.5)
            
            # 识别录音文件
            if audio_file_path and os.path.exists(audio_file_path):
                log_system("  [识别] 开始语音识别...")
                result_file = speech_recognizer.recognize(
                    audio_file_path,
                    delete_after_recognition=True,
                    convert_audio=True
                )
                if result_file:
                    log_system(f"  ✓ 语音识别完成，结果已保存: {result_file}")
                else:
                    log_system("  ⚠ 语音识别失败")
                    return
            else:
                log_system(f"  ⚠ 录音文件不存在: {audio_file_path}")
                return
        else:
            log_system("\n[Warning] 按钮、录音或识别工具不可用，跳过录音识别流程")
        
        # 2. 数据准备阶段
        print("\n[Action] 触发语音交互...")
        
        voice_data = read_json_file(FILE_VOICE_OUTPUT)
        words_data = get_words_data()
        
        if voice_data is None:
            print("[Error] 无法读取语音数据。")
            return
        
        # 根据 API 要求，从 'human_message' 更改为 'human_audio_message'
        human_audio_message = voice_data.get("human_message") 
        # 注意：合作伙伴在文件中写入 "human_message"，但 API 在 payload 中期望 "human_audio_message"
        
        conversation_id = get_conversation_id()
        try:
            conversation_id = int(conversation_id) if conversation_id else 0
        except:
            conversation_id = 0

        payload = {
            "human_audio_message": human_audio_message,
            "device_id": DEVICE_ID,
            "conversation_id": conversation_id,
            # 合并词汇数据
            "verb": words_data.get("verb"),
            "noun": words_data.get("noun"),
            "adjective": words_data.get("adjective"),
            "exclamation": words_data.get("exclamation"),
            "discourse_marker": words_data.get("discourse_marker"),
            "adverb": words_data.get("adverb")
        }
        
        mqtt.publish(TOPIC_USER_RESPONSE, json.dumps(payload))
        logging.info(f"已发布到 {TOPIC_USER_RESPONSE}: {payload}")
        
        wait_for_response(timeout=30, display_driver=display_driver)
        
        print("\n✓ 音频交互测试完成")
        
    except KeyboardInterrupt:
        print("\n检测到中断，正在退出...")
    except Exception as e:
        print(f"\n[Error] 测试过程中出错: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # 清理资源
        log_system("\n[Cleanup] 清理资源...")
        mqtt.stop()
        log_system("  ✓ MQTT连接已关闭")
        
        if button:
            try:
                button.cleanup()
                log_system("  ✓ 按钮已清理")
            except:
                pass
        
        if audio_recorder:
            try:
                audio_recorder.cleanup()
                log_system("  ✓ 音频录音器已清理")
            except:
                pass
        
        if display_driver:
            try:
                display_driver.cleanup()
                log_system("  ✓ 显示屏驱动已清理")
            except:
                pass
        
        print("程序已结束。")

if __name__ == "__main__":
    main()

