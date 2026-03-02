#!/usr/bin/env python3
"""
YOLO物体识别测试
用于测试物体识别流程
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
from hardware import CameraCapture, PressureSensor  # 使用 /home/pi/projects/tydeus/hardware/camera_capture.py
from hardware.ep1831t_driver import EP1831TDriver
# 导入物体检测工具
from utils.object_detection import detect_object  # 使用 /home/pi/projects/tydeus/utils/object_detection.py

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
    """YOLO物体识别测试主函数"""
    ensure_temp_data_dir()
    
    # 初始化显示屏驱动
    display_driver = None
    try:
        display_driver = EP1831TDriver()
        log_system("✓ 显示屏驱动初始化成功")
    except Exception as e:
        log_system(f"⚠ 显示屏驱动初始化失败: {e}")
        log_system("  将继续运行，但无法显示图片")
    
    # 1. 初始化阶段：显示 MASTER 1.png
    master_image_path = os.path.join(PROJECT_ROOT, "imgs", "waiting", "searching.png")
    if display_driver and os.path.exists(master_image_path):
        try:
            display_driver.display_image(master_image_path)
            log_system(f"[Display] 显示初始化图片: {master_image_path}")
        except Exception as e:
            log_system(f"[Error] 显示初始化图片失败: {e}")
    elif not os.path.exists(master_image_path):
        log_system(f"[Warning] 初始化图片不存在: {master_image_path}")
    
    # 初始化压力传感器
    pressure_sensor = None
    try:
        pressure_sensor = PressureSensor()
        log_system("✓ 压力传感器初始化成功")
    except Exception as e:
        log_system(f"⚠ 压力传感器初始化失败: {e}")
        log_system("  将跳过压力传感器检测")
    
    # 2. 等待压力传感器被按下
    if pressure_sensor:
        log_system("\n[Action] 等待压力传感器被按下...")
        try:
            if pressure_sensor._initialized:
                if not pressure_sensor.wait_for_press(timeout=None):
                    log_system("[Warning] 压力传感器检测超时或失败")
            else:
                log_system("[Warning] 压力传感器未初始化，跳过等待")
        except Exception as e:
            log_system(f"[Error] 等待压力传感器失败: {e}")
    else:
        log_system("\n[Action] 压力传感器不可用，跳过等待步骤")
    
    # 初始化 MQTT
    mqtt = MqttHandler(MQTT_BROKER, MQTT_PORT, DEVICE_ID)
    
    # 订阅主题
    subscriptions = [
        TOPIC_AGENT_RESPONSE_OBJECT,
        TOPIC_AGENT_RESPONSE_USER,
        TOPIC_USER_STOP_RESPONSE
    ]
    
    mqtt.start(subscriptions=subscriptions, callback=on_server_message)
    logging.info(f"YOLO测试已启动。设备 ID: {DEVICE_ID}")
    
    # 短暂等待连接（优化：从1秒缩短到0.2秒）
    time.sleep(0.2)
    
    print("\n=== YOLO物体识别测试 ===")
    print(f"Device ID: {DEVICE_ID}")
    
    try:
        # 3. 读取物体数据阶段：拍照 + YOLO识别，直到 object_name 不为 null
        log_system("\n[Action] 开始物体识别流程...")
        
        # 使用 CameraCapture 工具进行拍照（/home/pi/projects/tydeus/hardware/camera_capture.py）
        camera = CameraCapture()
        max_attempts = 10  # 最大尝试次数，避免无限循环
        attempt = 0
        object_name = None
        
        while attempt < max_attempts:
            attempt += 1
            log_system(f"\n[Attempt {attempt}/{max_attempts}] 拍摄照片并识别...")
            
            # 拍摄照片（使用 CameraCapture.capture_and_save()）
            photo_path = camera.capture_and_save()
            if not photo_path:
                log_system("  ⚠ 拍照失败，重试...")
                # 优化：去掉等待时间，立即重试
                continue
            
            log_system(f"  ✓ 照片已保存: {photo_path}")
            
            # YOLO识别（使用 utils.object_detection.detect_object()）
            log_system("  [YOLO] 开始物体识别...")
            success = detect_object(photo_path)  # 使用 /home/pi/projects/tydeus/utils/object_detection.py
            if not success:
                log_system("  ⚠ 物体识别失败，重试...")
                # 优化：去掉等待时间，立即重试
                continue
            
            # 读取识别结果
            obj_data = read_json_file(FILE_OBJECT_NAME)
            if obj_data is None:
                log_system("  ⚠ 无法读取识别结果，重试...")
                # 优化：去掉等待时间，立即重试
                continue
            
            object_name = obj_data.get("object_name")
            log_system(f"  [YOLO] 识别结果: {object_name}")
            
            # 检查 object_name 是否为 null
            if object_name and object_name != "null" and object_name.lower() != "null":
                log_system(f"  ✓ 成功识别到物体: {object_name}")
                # 识别完成后删除原始照片，节省空间
                try:
                    if os.path.exists(photo_path):
                        os.remove(photo_path)
                        log_system(f"  ✓ 已删除原始照片: {photo_path}")
                except Exception as e:
                    log_system(f"  ⚠ 删除照片失败: {e}")
                break
            else:
                log_system(f"  ⚠ 未识别到有效物体 (object_name: {object_name})")
                # 等待用户再次按下传感器后重新拍照检测
                if pressure_sensor:
                    log_system("  [Action] 等待再次按下传感器以重新拍照检测...")
                    try:
                        if pressure_sensor._initialized:
                            if not pressure_sensor.wait_for_press(timeout=None):
                                log_system("  [Warning] 压力传感器检测超时或失败")
                        else:
                            log_system("  [Warning] 压力传感器未初始化，跳过等待")
                    except Exception as e:
                        log_system(f"  [Error] 等待压力传感器失败: {e}")
                else:
                    log_system("  [Warning] 压力传感器不可用，等待 0.5 秒后重试...")
                    time.sleep(0.5)  # 优化：从2秒缩短到0.5秒
        
        if not object_name or object_name == "null" or object_name.lower() == "null":
            log_system(f"\n[Error] 经过 {max_attempts} 次尝试，仍未识别到有效物体")
            # 删除最后一次拍摄的照片，节省空间
            try:
                if 'photo_path' in locals() and photo_path and os.path.exists(photo_path):
                    os.remove(photo_path)
                    log_system(f"  ✓ 已删除最后一次拍摄的照片: {photo_path}")
            except Exception as e:
                log_system(f"  ⚠ 删除照片失败: {e}")
            log_system("  程序将退出")
            return
        
        # 4. 构建并发送MQTT消息
        log_system("\n[Action] 构建并发送MQTT消息...")
        
        payload = {
            "device_id": DEVICE_ID,
            "timestamp": time.time(),
            "object_name": object_name,
            "conversation_id": get_conversation_id() or 0 # 处理空字符串或 null
        }
        
        # 确保 conversation_id 尽可能为 int，如果是新的则为 0
        try:
            payload["conversation_id"] = int(payload["conversation_id"])
        except:
            payload["conversation_id"] = 0

        mqtt.publish(TOPIC_OBJECT_DETECTED, json.dumps(payload))
        logging.info(f"已发布到 {TOPIC_OBJECT_DETECTED}: {payload}")
        log_system(f"  ✓ MQTT消息已发送: {payload}")
        
        # 5. 等待服务器响应（显示等待图片）
        log_system("\n[Action] 等待服务器响应...")
        wait_for_response(timeout=30, display_driver=display_driver)
        
        log_system("\n✓ YOLO物体识别测试完成")
        
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
        
        if pressure_sensor:
            try:
                pressure_sensor.cleanup()
                log_system("  ✓ 压力传感器已清理")
            except:
                pass
        
        log_system("程序已结束。")

if __name__ == "__main__":
    main()
