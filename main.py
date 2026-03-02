#!/usr/bin/env python3
"""
主程序
整合物体识别、音频交互和结束对话流程
"""
import sys
import os
import time
import threading
import logging
import json
from config import *
from hardware.button import Button
from comm.mqtt_client import MqttHandler

# 导入三个测试文件的 main 函数
import importlib.util

# 导入 1_yolo_test.py
_yolo_test_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "modules", "1_yolo_test.py")
_yolo_spec = importlib.util.spec_from_file_location("yolo_test", _yolo_test_path)
_yolo_module = importlib.util.module_from_spec(_yolo_spec)
_yolo_spec.loader.exec_module(_yolo_module)
yolo_main = _yolo_module.main

# 导入 2_audio_test.py
_audio_test_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "modules", "2_audio_test.py")
_audio_spec = importlib.util.spec_from_file_location("audio_test", _audio_test_path)
_audio_module = importlib.util.module_from_spec(_audio_spec)
_audio_spec.loader.exec_module(_audio_module)
audio_main = _audio_module.main

# 导入 3_finish_test.py
_finish_test_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "modules", "3_finish_test.py")
_finish_spec = importlib.util.spec_from_file_location("finish_test", _finish_test_path)
_finish_module = importlib.util.module_from_spec(_finish_spec)
_finish_spec.loader.exec_module(_finish_module)
finish_main = _finish_module.main

# --- 全局标志 ---
long_press_detected = threading.Event()  # 长按检测事件
should_stop = threading.Event()  # 停止标志
interrupt_flag = threading.Event()  # 中断标志，用于中断正在进行的操作

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

def monitor_button_long_press(button):
    """
    在后台线程中全局监控按钮长按
    当检测到长按时，设置 long_press_detected 事件和中断标志
    """
    if not button or not button._initialized:
        return
    
    log_system("[Monitor] 按钮长按监控线程已启动")
    
    try:
        long_press_duration = BUTTON_LONG_PRESS_TIME
        press_start_time = None
        
        while not should_stop.is_set():
            if button.is_pressed():
                # 按钮被按下
                if press_start_time is None:
                    # 记录按下开始时间
                    press_start_time = time.time()
                else:
                    # 检查是否达到长按时间
                    elapsed = time.time() - press_start_time
                    if elapsed >= long_press_duration:
                        log_system("\n[Monitor] 检测到按钮长按！准备执行结束流程...")
                        long_press_detected.set()
                        interrupt_flag.set()  # 设置中断标志
                        should_stop.set()  # 设置停止标志
                        break
            else:
                # 按钮未按下，重置计时
                press_start_time = None
            
            time.sleep(0.05)  # 轮询间隔，50ms
    except Exception as e:
        log_system(f"[Error] 按钮监控线程出错: {e}")
    finally:
        log_system("[Monitor] 按钮长按监控线程已退出")

def run_yolo_test():
    """执行物体识别测试"""
    log_system("\n" + "=" * 60)
    log_system("[Stage 1] 开始执行物体识别流程...")
    log_system("=" * 60)
    
    try:
        yolo_main()
        log_system("\n[Stage 1] 物体识别流程完成")
        return True
    except Exception as e:
        log_system(f"\n[Error] 物体识别流程出错: {e}")
        import traceback
        traceback.print_exc()
        return False

def run_audio_cycle_once(mqtt, button, audio_recorder, speech_recognizer, display_driver=None):
    """
    执行一次音频交互循环
    
    流程：
    1. 等待按钮按下开始录音
    2. 等待按钮按下停止录音
    3. 把录音转文字
    4. 把文字发到服务器
    5. 等待服务器回复
    
    参数:
        mqtt: MQTT客户端实例
        button: 按钮实例
        audio_recorder: 音频录音器实例
        speech_recognizer: 语音识别器实例
        display_driver: 显示屏驱动实例（可选）
    
    返回:
        True表示成功，False表示失败或被中断
    """
    try:
        # 检查中断标志
        if interrupt_flag.is_set():
            log_system("\n[Info] 检测到中断信号，停止当前操作")
            return False
        
        log_system("\n[Action] 开始录音和识别流程...")
        
        # 1. 等待按钮按下开始录音
        log_system("  [等待] 请按下按钮开始录音...")
        if not button or not button._initialized:
            log_system("  ⚠ 按钮未初始化")
            return False
        
        # 等待按钮按下（检查中断标志）
        while not button.is_pressed():
            if interrupt_flag.is_set():
                log_system("  [Info] 检测到中断信号，停止等待")
                return False
            time.sleep(0.05)
        
        # 等待按钮释放
        log_system("  [等待] 请释放按钮...")
        while button.is_pressed():
            if interrupt_flag.is_set():
                log_system("  [Info] 检测到中断信号，停止等待")
                return False
            time.sleep(0.05)
        
        # 添加短暂延迟，确保按钮状态稳定
        time.sleep(0.3)
        
        # 检查中断标志
        if interrupt_flag.is_set():
            log_system("  [Info] 检测到中断信号，停止操作")
            return False
        
        # 2. 开始录音
        log_system("  [录音] 开始录音...")
        audio_file_path = audio_recorder.start_recording()
        if not audio_file_path:
            log_system("  ⚠ 开始录音失败")
            return False
        
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
        
        # 3. 等待按钮按下停止录音
        # 先确保按钮处于未按下状态
        while button.is_pressed():
            if interrupt_flag.is_set():
                log_system("  [Info] 检测到中断信号，停止录音")
                audio_recorder.stop_recording()
                return False
            time.sleep(0.1)
        
        # 等待新的按下事件
        while not button.is_pressed():
            if interrupt_flag.is_set():
                log_system("  [Info] 检测到中断信号，停止录音")
                audio_recorder.stop_recording()
                return False
            time.sleep(0.05)
        
        # 4. 停止录音
        log_system("  [录音] 停止录音...")
        audio_recorder.stop_recording()
        log_system("  ✓ 录音已停止")
        
        # 检查中断标志
        if interrupt_flag.is_set():
            log_system("  [Info] 检测到中断信号，停止操作")
            return False
        
        # 等待一小段时间确保录音文件已保存
        time.sleep(0.5)
        
        # 5. 识别录音文件（把录音转文字）
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
                return False
        else:
            log_system(f"  ⚠ 录音文件不存在: {audio_file_path}")
            return False
        
        # 检查中断标志
        if interrupt_flag.is_set():
            log_system("  [Info] 检测到中断信号，停止操作")
            return False
        
        # 6. 读取识别结果并发送到服务器（把文字发到服务器）
        log_system("\n[Action] 触发语音交互...")
        
        voice_data = read_json_file(FILE_VOICE_OUTPUT)
        words_data = get_words_data()
        
        if voice_data is None:
            log_system("[Error] 无法读取语音数据。")
            return False
        
        human_audio_message = voice_data.get("human_message")
        
        conversation_id = get_conversation_id()
        try:
            conversation_id = int(conversation_id) if conversation_id else 0
        except:
            conversation_id = 0

        payload = {
            "human_audio_message": human_audio_message,
            "device_id": DEVICE_ID,
            "conversation_id": conversation_id,
            "verb": words_data.get("verb"),
            "noun": words_data.get("noun"),
            "adjective": words_data.get("adjective"),
            "exclamation": words_data.get("exclamation"),
            "discourse_marker": words_data.get("discourse_marker"),
            "adverb": words_data.get("adverb")
        }
        
        mqtt.publish(TOPIC_USER_RESPONSE, json.dumps(payload))
        logging.info(f"已发布到 {TOPIC_USER_RESPONSE}: {payload}")
        log_system(f"  ✓ MQTT消息已发送")
        
        # 7. 等待服务器回复
        response_received = threading.Event()
        
        def on_server_message(topic, payload):
            """MQTT消息回调"""
            try:
                logging.info(f"收到 MQTT 消息，主题 {topic}: {payload}")
                data = json.loads(payload)
                
                if topic == TOPIC_USER_STOP_RESPONSE:
                    summary = data.get("conversation_summary", "未提供总结。")
                    log_system(f"\n[System] 对话结束。总结: {summary}")
                else:
                    # 正常交互响应
                    new_conv_id = data.get("conversation_id")
                    if new_conv_id:
                        save_conversation_id(new_conv_id)
                    
                    # 调用硬件执行
                    from modules.play_pi import execute_response
                    success = execute_response(data)
                    if success:
                        log_system("[System] 硬件执行成功完成。")
                    else:
                        log_system("[System] 硬件执行遇到问题。")
                
                response_received.set()
            except Exception as e:
                log_system(f"[Error] 处理服务器消息时出错: {e}")
                response_received.set()
        
        # 设置回调（保存原始回调）
        original_callback = mqtt.on_message_callback
        mqtt.on_message_callback = on_server_message
        # 确保 on_message 处理器已设置
        mqtt.client.on_message = mqtt.on_message
        
        log_system("\n[Action] 等待服务器响应...")
        
        # 显示等待图片（thinking.png）
        if display_driver:
            thinking_image_path = os.path.join(PROJECT_ROOT, "imgs", "waiting", "thinking.png")
            if os.path.exists(thinking_image_path):
                try:
                    display_driver.display_image(thinking_image_path)
                    log_system(f"[Display] 显示等待图片: {thinking_image_path}")
                except Exception as e:
                    log_system(f"[Error] 显示等待图片失败: {e}")
        
        response_received.clear()
        timeout = 60
        start_time = time.time()
        
        print("等待回复 ", end="", flush=True)
        dot_count = 0
        
        while not response_received.is_set():
            # 检查中断标志
            if interrupt_flag.is_set():
                print("\n[Info] 检测到中断信号，停止等待响应")
                mqtt.on_message_callback = original_callback
                if original_callback:
                    mqtt.client.on_message = mqtt.on_message
                else:
                    mqtt.client.on_message = None
                return False
            
            if time.time() - start_time > timeout:
                print("\n[Timeout] 服务器响应超时。")
                break
            
            time.sleep(0.1)
            print(".", end="", flush=True)
            dot_count += 1
            if dot_count >= 6:
                print("\b" * 6 + "      " + "\b" * 6, end="", flush=True)
                dot_count = 0
        
        print("\n")
        
        # 恢复原始回调
        mqtt.on_message_callback = original_callback
        if original_callback:
            mqtt.client.on_message = mqtt.on_message
        else:
            mqtt.client.on_message = None
        
        log_system("\n✓ 音频交互流程完成")
        return True
        
    except Exception as e:
        log_system(f"\n[Error] 音频交互流程出错: {e}")
        import traceback
        traceback.print_exc()
        return False

def run_finish_test():
    """执行结束对话测试"""
    log_system("\n" + "=" * 60)
    log_system("[Stage 3] 开始执行结束对话流程...")
    log_system("=" * 60)
    
    try:
        finish_main()
        log_system("\n[Stage 3] 结束对话流程完成")
        return True
    except Exception as e:
        log_system(f"\n[Error] 结束对话流程出错: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """主程序入口"""
    log_system("\n" + "=" * 60)
    log_system("主程序启动")
    log_system("=" * 60)
    
    # 初始化按钮（用于长按监控和录音控制）
    button = None
    try:
        button = Button()
        log_system("✓ 按钮初始化成功")
    except Exception as e:
        log_system(f"⚠ 按钮初始化失败: {e}")
        log_system("  将无法检测长按，程序将按正常流程运行")
    
    # 启动按钮长按监控线程（全局监听）
    monitor_thread = None
    if button and button._initialized:
        monitor_thread = threading.Thread(
            target=monitor_button_long_press,
            args=(button,),
            daemon=True
        )
        monitor_thread.start()
        log_system("✓ 按钮长按监控线程已启动（全局监听）")
    
    try:
        # Stage 1: 执行物体识别流程
        if should_stop.is_set():
            log_system("\n[Info] 检测到停止信号，跳过物体识别流程")
        else:
            if not run_yolo_test():
                log_system("\n[Warning] 物体识别流程失败，但继续执行后续流程")
        
        # 检查是否检测到长按
        if long_press_detected.is_set():
            log_system("\n[Info] 检测到按钮长按，准备执行结束流程")
        else:
            # Stage 2: 初始化音频交互所需的资源（只初始化一次）
            log_system("\n[Stage 2] 初始化音频交互资源...")
            
            # 初始化显示屏驱动（用于显示等待图片）
            display_driver = None
            try:
                from hardware.ep1831t_driver import EP1831TDriver
                display_driver = EP1831TDriver()
                log_system("  ✓ 显示屏驱动初始化成功")
            except Exception as e:
                log_system(f"  ⚠ 显示屏驱动初始化失败: {e}")
                log_system("  将继续运行，但无法显示等待图片")
            
            # 初始化 MQTT（用于音频交互）
            mqtt_audio = MqttHandler(MQTT_BROKER, MQTT_PORT, DEVICE_ID)
            subscriptions_audio = [
                TOPIC_AGENT_RESPONSE_OBJECT,
                TOPIC_AGENT_RESPONSE_USER,
                TOPIC_USER_STOP_RESPONSE
            ]
            mqtt_audio.start(subscriptions=subscriptions_audio, callback=None)  # 回调在循环中处理
            time.sleep(0.2)
            log_system("  ✓ MQTT已初始化")
            
            # 初始化音频录音器
            audio_recorder = None
            try:
                from hardware.audio_recorder import AudioRecorder
                audio_recorder = AudioRecorder()
                log_system("  ✓ 音频录音器初始化成功")
            except Exception as e:
                log_system(f"  ⚠ 音频录音器初始化失败: {e}")
            
            # 初始化语音识别器
            speech_recognizer = None
            try:
                from utils.speech_recognition import SpeechRecognition
                speech_recognizer = SpeechRecognition()
                log_system("  ✓ 语音识别器初始化成功")
            except Exception as e:
                log_system(f"  ⚠ 语音识别器初始化失败: {e}")
            
            # Stage 2: 循环执行音频交互流程
            audio_cycle_count = 0
            while not should_stop.is_set() and not long_press_detected.is_set():
                # 检查是否检测到长按（在开始新循环前检查）
                if long_press_detected.is_set():
                    log_system("\n[Info] 检测到按钮长按，准备执行结束流程")
                    break
                
                audio_cycle_count += 1
                log_system(f"\n[Cycle] 音频交互循环 #{audio_cycle_count}")
                log_system("=" * 60)
                
                # 执行一次音频交互循环
                # 这个函数会等待按钮按下，所以不会立即循环
                try:
                    success = run_audio_cycle_once(mqtt_audio, button, audio_recorder, speech_recognizer, display_driver)
                    if not success:
                        if interrupt_flag.is_set():
                            # 被中断，退出循环
                            log_system("\n[Info] 操作被中断，准备执行结束流程")
                            break
                        else:
                            log_system("\n[Warning] 音频交互流程失败，继续下一次循环")
                            # 如果失败，等待一小段时间再继续（避免无限快速循环）
                            time.sleep(1.0)
                except Exception as e:
                    if interrupt_flag.is_set():
                        log_system("\n[Info] 操作被中断，准备执行结束流程")
                        break
                    log_system(f"\n[Error] 音频交互流程异常: {e}")
                    import traceback
                    traceback.print_exc()
                    # 如果出现异常，等待一段时间再继续
                    time.sleep(1.0)
                
                # 检查是否检测到长按（在执行完成后检查）
                if long_press_detected.is_set():
                    log_system("\n[Info] 检测到按钮长按，准备执行结束流程")
                    break
            
            # 清理音频交互资源
            if 'mqtt_audio' in locals():
                try:
                    mqtt_audio.stop()
                    log_system("  ✓ MQTT（音频）连接已关闭")
                except Exception as e:
                    log_system(f"  ⚠ 关闭MQTT（音频）时出错: {e}")
            
            if 'audio_recorder' in locals() and audio_recorder:
                try:
                    audio_recorder.cleanup()
                    log_system("  ✓ 音频录音器已清理")
                except Exception as e:
                    log_system(f"  ⚠ 清理音频录音器时出错: {e}")
            
            if 'display_driver' in locals() and display_driver:
                try:
                    display_driver.cleanup()
                    log_system("  ✓ 显示屏驱动已清理")
                except Exception as e:
                    log_system(f"  ⚠ 清理显示屏驱动时出错: {e}")
        
        # Stage 3: 执行结束对话流程（如果检测到长按）
        if long_press_detected.is_set():
            # 立即显示shutdown.png
            display_driver_shutdown = None
            try:
                from hardware.ep1831t_driver import EP1831TDriver
                display_driver_shutdown = EP1831TDriver()
                shutdown_image_path = os.path.join(PROJECT_ROOT, "imgs", "waiting", "shutdown.png")
                if os.path.exists(shutdown_image_path):
                    try:
                        display_driver_shutdown.display_image(shutdown_image_path)
                        log_system(f"[Display] 显示关闭图片: {shutdown_image_path}")
                    except Exception as e:
                        log_system(f"[Error] 显示关闭图片失败: {e}")
            except Exception as e:
                log_system(f"[Warning] 无法初始化显示屏驱动显示shutdown图片: {e}")
            
            # 等待监控线程结束
            if monitor_thread and monitor_thread.is_alive():
                log_system("[Info] 等待按钮监控线程结束...")
                time.sleep(0.2)
            
            run_finish_test()
            
            # 程序运行完毕后，熄灭显示屏
            if display_driver_shutdown:
                try:
                    display_driver_shutdown.fill_color(0, 0, 0)  # 填充黑色，熄灭显示屏
                    log_system("  ✓ 显示屏已熄灭")
                    display_driver_shutdown.cleanup()
                    log_system("  ✓ 显示屏驱动已清理")
                except Exception as e:
                    log_system(f"  ⚠ 熄灭显示屏失败: {e}")
        else:
            log_system("\n[Info] 未检测到长按，程序正常结束")
        
        log_system("\n" + "=" * 60)
        log_system("主程序执行完成")
        log_system("=" * 60)
        
    except KeyboardInterrupt:
        log_system("\n[Info] 检测到用户中断（Ctrl+C）")
        should_stop.set()
        interrupt_flag.set()
    except Exception as e:
        log_system(f"\n[Error] 主程序执行出错: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # 设置停止标志
        should_stop.set()
        
        # 清理资源
        log_system("\n[Cleanup] 清理资源...")
        
        # 熄灭显示屏（如果有初始化）
        if 'display_driver' in locals() and display_driver:
            try:
                display_driver.fill_color(0, 0, 0)  # 填充黑色，熄灭显示屏
                log_system("  ✓ 显示屏已熄灭")
            except Exception as e:
                log_system(f"  ⚠ 熄灭显示屏失败: {e}")
        
        if button:
            try:
                button.cleanup()
                log_system("  ✓ 按钮已清理")
            except Exception as e:
                log_system(f"  ⚠ 清理按钮时出错: {e}")
        
        # 等待监控线程结束
        if monitor_thread and monitor_thread.is_alive():
            log_system("[Info] 等待按钮监控线程结束...")
            monitor_thread.join(timeout=1.0)
        
        log_system("程序已结束。")

if __name__ == "__main__":
    main()

