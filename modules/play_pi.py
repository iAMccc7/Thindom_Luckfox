import json
import os
import sys
import time

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utils.text_to_speech import synthesize_text
from hardware.audio_player import AudioPlayer
from hardware.ep1831t_driver import EP1831TDriver
from utils.flashcard import FlashCardMaker
from config import PROJECT_ROOT, TEMP_DATA_DIR

# 全局硬件驱动实例（延迟初始化）
_display_driver = None
_audio_player = None
_flashcard_maker = None

def _get_display_driver():
    """获取显示屏驱动实例（单例模式）"""
    global _display_driver
    if _display_driver is None:
        try:
            _display_driver = EP1831TDriver()
            print("✓ 显示屏驱动初始化成功")
        except Exception as e:
            print(f"⚠ 显示屏驱动初始化失败: {e}")
            _display_driver = False  # 标记为失败，避免重复尝试
    return _display_driver if _display_driver is not False else None

def _get_audio_player():
    """获取音频播放器实例（单例模式）"""
    global _audio_player
    if _audio_player is None:
        _audio_player = AudioPlayer()
    return _audio_player

def _get_flashcard_maker():
    """获取单词卡片制作器实例（单例模式）"""
    global _flashcard_maker
    if _flashcard_maker is None:
        _flashcard_maker = FlashCardMaker()
    return _flashcard_maker

def execute_response(data_dict: dict) -> bool:
    """
    在硬件上执行响应（TTS语音合成、表情、动作）。
    
    参数:
        data_dict (dict): 包含 'message' (消息), 'mood_id' (情绪ID) 等字段的数据字典。
        
    返回:
        bool: 如果执行成功返回 True，否则返回 False。

    输入格式示例：
    {
        "message": "Hello, 小明",       # (String) 需要TTS播放的文本
        "mood_id": 1,                   # (Int) 情绪ID，用于控制机器人动作/表情
        # 以下词性字段只会存在1-2个，其余为 null
        "verb": None,
        "noun": None,
        "adjective": {
            "word": "red",
            "chinese_translation": "红的"
        },
        "exclamation": None,
        "discourse_marker": None,
        "adverb": None,
        "islands_progress": [
        {
            "island_inner_id": 1,
            "learned_percentage": "50.00",
            "is_locked": false
        },
        {
            "island_inner_id": 2,
            "learned_percentage": "0.00",
            "is_locked": true
        }
        ] | null
    }
    """
    try:
        print("\n--- [硬件执行开始] ---")
        
        # 1. TTS / 语音输出（后台播放）
        audio_player = None
        audio_path = None
        message = data_dict.get("message")
        if message:
            print(f"🔊 [TTS] 正在合成并播放: \"{message}\"")
            try:
                # 合成音频
                audio_path = synthesize_text(message)
                if audio_path and os.path.exists(audio_path):
                    print(f"  ✓ 音频合成成功: {audio_path}")
                    # 开始播放音频（不等待，后台播放）
                    audio_player = _get_audio_player()
                    if audio_player:
                        success = audio_player.play_file(audio_path, wait=False, delete_after_play=True)
                        if success:
                            print("  ✓ 音频播放已开始（后台播放）")
                        else:
                            print("  ⚠ 音频播放失败")
                    else:
                        print("  ⚠ 音频播放器不可用")
                else:
                    print("  ⚠ 音频合成失败")
            except Exception as e:
                print(f"  ⚠ TTS处理异常: {e}")
        else:
            print("🔊 [TTS] 没有可播放的消息。")

        # 2. 情绪 / 表情（立即显示）
        mood_id = data_dict.get("mood_id")
        islands_progress = data_dict.get("islands_progress")  # 获取进度信息
        mood_displayed = False
        if mood_id is not None:
            print(f"😊 [Expression] 设置情绪 ID: {mood_id}")
            try:
                # 构建表情图片路径
                mood_image_path = os.path.join(PROJECT_ROOT, "imgs", "moods", f"{mood_id}.png")
                
                if os.path.exists(mood_image_path):
                    display_driver = _get_display_driver()
                    if display_driver:
                        # 传递进度信息，用于绘制进度环
                        display_driver.display_image(mood_image_path, islands_progress=islands_progress)
                        print(f"  ✓ 表情图片已显示: {mood_image_path}")
                        mood_displayed = True
                    else:
                        print("  ⚠ 显示屏驱动不可用")
                else:
                    print(f"  ⚠ 表情图片不存在: {mood_image_path}")
            except Exception as e:
                print(f"  ⚠ 表情显示异常: {e}")
        
        # 如果显示了mood图片，等待至少2秒后再显示单词卡片
        # 这样可以确保mood图片有足够的显示时间
        if mood_displayed:
            time.sleep(2)

        # 3. 动作 (检查特定的词性)
        noun = data_dict.get("noun")
        verb = data_dict.get("verb")
        adjective = data_dict.get("adjective")
        
        # 记录单词卡片开始显示的时间
        flashcard_start_time = None
        
        # 默认图片路径
        default_word_image = os.path.join(PROJECT_ROOT, "imgs", "words", "apple.png")
        
        # 处理名词
        if noun:
            print(f"🤖 [Movement] 针对名词做出反应: {noun}")
            try:
                display_driver = _get_display_driver()
                flashcard_maker = _get_flashcard_maker()
                
                if display_driver and flashcard_maker:
                    # 名词可能是一个字典，例如 {"word": "apple", "chinese_translation": "苹果"}
                    if isinstance(noun, dict):
                        english_word = noun.get("word", "")
                        chinese_word = noun.get("chinese_translation", "")
                    else:
                        english_word = str(noun)
                        chinese_word = ""
                    
                    # 尝试使用单词对应的图片，如果不存在则使用默认图片
                    word_image_path = os.path.join(PROJECT_ROOT, "imgs", "words", f"{english_word}.png")
                    if not os.path.exists(word_image_path):
                        word_image_path = default_word_image
                        print(f"  ⚠ 单词图片不存在，使用默认图片: {word_image_path}")
                    
                    # 名词：英文单词和中文翻译都要有
                    flashcard_maker.create_and_display(
                        image_path=word_image_path,
                        english_word=english_word,
                        chinese_word=chinese_word,
                        display_driver=display_driver,
                        islands_progress=islands_progress  # 传递进度信息
                    )
                    if flashcard_start_time is None:
                        flashcard_start_time = time.time()
                    print(f"  ✓ 名词单词卡片已显示: {english_word} - {chinese_word}")
                else:
                    print("  ⚠ 显示屏或单词卡片工具不可用")
            except Exception as e:
                print(f"  ⚠ 名词处理异常: {e}")
        
        # 处理动词
        if verb:
            print(f"🤖 [Movement] 针对动词做出反应: {verb}")
            try:
                display_driver = _get_display_driver()
                flashcard_maker = _get_flashcard_maker()
                
                if display_driver and flashcard_maker:
                    # 动词可能是一个字典，例如 {"word": "run", "chinese_translation": "跑"}
                    if isinstance(verb, dict):
                        english_word = verb.get("word", "")
                        chinese_word = verb.get("chinese_translation", "")
                    else:
                        english_word = str(verb)
                        chinese_word = ""
                    
                    # 尝试使用单词对应的图片，如果不存在则使用默认图片
                    word_image_path = os.path.join(PROJECT_ROOT, "imgs", "words", f"{english_word}.png")
                    if not os.path.exists(word_image_path):
                        word_image_path = default_word_image
                        print(f"  ⚠ 单词图片不存在，使用默认图片: {word_image_path}")
                    
                    # 动词：英文单词和中文翻译都要有
                    flashcard_maker.create_and_display(
                        image_path=word_image_path,
                        english_word=english_word,
                        chinese_word=chinese_word,
                        display_driver=display_driver,
                        islands_progress=islands_progress  # 传递进度信息
                    )
                    if flashcard_start_time is None:
                        flashcard_start_time = time.time()
                    print(f"  ✓ 动词单词卡片已显示: {english_word} - {chinese_word}")
                else:
                    print("  ⚠ 显示屏或单词卡片工具不可用")
            except Exception as e:
                print(f"  ⚠ 动词处理异常: {e}")
        
        # 处理形容词
        if adjective:
            print(f"🤖 [Movement] 针对形容词做出反应: {adjective}")
            try:
                display_driver = _get_display_driver()
                flashcard_maker = _get_flashcard_maker()
                
                if display_driver and flashcard_maker:
                    # 形容词可能是一个字典，例如 {"word": "red", "chinese_translation": "红的"}
                    if isinstance(adjective, dict):
                        english_word = adjective.get("word", "")
                        chinese_word = adjective.get("chinese_translation", "")
                    else:
                        english_word = str(adjective)
                        chinese_word = ""
                    
                    # 尝试使用单词对应的图片，如果不存在则使用默认图片
                    word_image_path = os.path.join(PROJECT_ROOT, "imgs", "words", f"{english_word}.png")
                    if not os.path.exists(word_image_path):
                        word_image_path = default_word_image
                        print(f"  ⚠ 单词图片不存在，使用默认图片: {word_image_path}")
                    
                    # 形容词：英文单词和中文翻译都要有
                    flashcard_maker.create_and_display(
                        image_path=word_image_path,
                        english_word=english_word,
                        chinese_word=chinese_word,
                        display_driver=display_driver,
                        islands_progress=islands_progress  # 传递进度信息
                    )
                    if flashcard_start_time is None:
                        flashcard_start_time = time.time()
                    print(f"  ✓ 形容词单词卡片已显示: {english_word} - {chinese_word}")
                else:
                    print("  ⚠ 显示屏或单词卡片工具不可用")
            except Exception as e:
                print(f"  ⚠ 形容词处理异常: {e}")

        # 4. 等待音频播放完成，同时确保单词卡片至少显示1秒
        if audio_player and audio_path:
            print("⏳ [等待] 等待音频播放完成...")
            try:
                # 等待音频播放完成
                while audio_player.is_playing():
                    time.sleep(0.1)  # 每100ms检查一次
                
                # 确保单词卡片至少显示1秒
                if flashcard_start_time is not None:
                    elapsed_time = time.time() - flashcard_start_time
                    if elapsed_time < 1.0:
                        remaining_time = 1.0 - elapsed_time
                        print(f"  ⏳ 确保单词卡片至少显示1秒，还需等待 {remaining_time:.2f} 秒")
                        time.sleep(remaining_time)
                
                # 删除音频文件
                if os.path.exists(audio_path):
                    try:
                        os.remove(audio_path)
                        print(f"  ✓ 已删除音频文件: {audio_path}")
                    except Exception as e:
                        print(f"  ⚠ 删除音频文件失败: {e}")
                
                print("  ✓ 音频播放完成")
            except Exception as e:
                print(f"  ⚠ 等待音频播放时出错: {e}")

        print("--- [硬件执行结束] ---\n")
        return True

    except Exception as e:
        print(f"❌ [Hardware Error] execute_response 失败: {e}")
        import traceback
        traceback.print_exc()
        return False

