#!/usr/bin/env python3
"""
语音识别工具
将录音上传到云端识别，获取文本，保存在临时文件夹，然后删除录音文件
高独立性、低耦合、高鲁棒性设计
"""
import os
import sys
import subprocess
import logging
import base64
import requests
import json
from typing import Optional

# 导入配置
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import (
    DASHSCOPE_API_KEY,
    ASR_SAMPLE_RATE,
    ASR_MODEL,
    ASR_FORMAT,
    SOX_VOLUME_GAIN,
    OUTPUT_DIR,
    TEMP_DATA_DIR,
    FILE_VOICE_OUTPUT,
    DEBUG_LOG
)

# 配置日志
logging.basicConfig(
    level=logging.DEBUG if DEBUG_LOG else logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class SpeechRecognition:
    """
    语音识别工具类
    使用DashScope API进行语音识别
    """
    
    def __init__(self,
                 api_key: Optional[str] = None,
                 model: Optional[str] = None,
                 sample_rate: Optional[int] = None,
                 audio_format: Optional[str] = None):
        """
        初始化语音识别工具
        
        参数:
            api_key: DashScope API密钥，默认使用config.py中的配置
            model: ASR模型，默认使用config.py中的配置
            sample_rate: 采样率（Hz），默认使用config.py中的配置
            audio_format: 音频格式，默认使用config.py中的配置
        """
        try:
            from dashscope.audio.asr import Transcription
            import dashscope
            self.Transcription = Transcription
            self.dashscope = dashscope
        except ImportError:
            raise ImportError("dashscope SDK 未安装，请运行: pip3 install dashscope")
        
        self.api_key = api_key or DASHSCOPE_API_KEY
        self.model = model or ASR_MODEL
        self.sample_rate = sample_rate or ASR_SAMPLE_RATE
        self.audio_format = audio_format or ASR_FORMAT
        
        if not self.api_key:
            raise ValueError("API密钥未设置，请在config.py中设置DASHSCOPE_API_KEY或传入api_key参数")
        
        self.dashscope.api_key = self.api_key
        logger.info("语音识别工具初始化完成")
    
    def _convert_audio(self, input_file: str, output_file: str) -> bool:
        """
        使用sox转换音频格式
        
        参数:
            input_file: 输入音频文件路径
            output_file: 输出音频文件路径
        
        返回:
            成功返回True，失败返回False
        """
        try:
            cmd = [
                "sox",
                input_file,
                "-r", str(self.sample_rate),  # 降采样到目标采样率
                "-c", "1",                     # 输出单声道
                "-b", "16",                    # 16-bit
                output_file,
                "remix", "1",                  # 提取左声道
                "vol", str(SOX_VOLUME_GAIN)    # 音量增益
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            
            if result.returncode != 0:
                logger.error(f"sox转换失败: {result.stderr}")
                return False
            
            logger.debug(f"音频转换成功: {output_file}")
            return True
            
        except FileNotFoundError:
            logger.error("sox未安装！请执行: sudo apt install -y sox")
            return False
        except Exception as e:
            logger.exception(f"转换音频出错: {e}")
            return False
    
    def _download_transcription(self, url: str) -> Optional[str]:
        """
        从URL下载识别结果
        
        参数:
            url: 识别结果URL
        
        返回:
            识别文本，失败返回None
        """
        try:
            logger.debug(f"正在下载识别结果: {url}")
            response = requests.get(url, timeout=30)
            
            if response.status_code == 200:
                result_data = response.json()
                logger.debug(f"下载的结果: {result_data}")
                
                # 提取文本
                if 'transcripts' in result_data:
                    text = result_data['transcripts'][0]['text']
                    return text
                elif 'text' in result_data:
                    return result_data['text']
                else:
                    logger.warning(f"无法从结果中提取文本: {result_data}")
                    return None
            else:
                logger.error(f"下载失败，状态码: {response.status_code}")
                return None
                
        except Exception as e:
            logger.exception(f"下载识别结果出错: {e}")
            return None
    
    def recognize(self,
                  audio_file: str,
                  delete_after_recognition: bool = True,
                  convert_audio: bool = True) -> Optional[str]:
        """
        识别音频文件
        
        参数:
            audio_file: 音频文件路径
            delete_after_recognition: 识别后是否删除录音文件，默认True
            convert_audio: 是否需要转换音频格式，默认True
        
        返回:
            识别文本文件路径，失败返回None
        """
        if not os.path.exists(audio_file):
            logger.error(f"音频文件不存在: {audio_file}")
            return None
        
        try:
            # 转换音频格式（如果需要）
            audio_file_to_recognize = None
            if convert_audio:
                # 生成转换后的文件路径
                base_name = os.path.splitext(audio_file)[0]
                converted_file = f"{base_name}_asr.wav"
                
                logger.info("转换音频格式...")
                if not self._convert_audio(audio_file, converted_file):
                    logger.error("音频转换失败")
                    # 转换失败时，如果设置了删除，也要删除原始文件
                    if delete_after_recognition:
                        self._delete_audio_files(audio_file, None, False)
                    return None
                
                audio_file_to_recognize = converted_file
            else:
                audio_file_to_recognize = audio_file
            
            # 读取音频文件
            logger.info(f"读取音频文件: {audio_file_to_recognize}")
            file_size = os.path.getsize(audio_file_to_recognize)
            logger.info(f"文件大小: {file_size / 1024:.2f} KB")
            
            with open(audio_file_to_recognize, 'rb') as f:
                audio_data = f.read()
            
            # 转换为base64
            audio_base64 = base64.b64encode(audio_data).decode('utf-8')
            
            # 调用识别API
            logger.info("正在调用DashScope API...")
            result = self.Transcription.call(
                model=self.model,
                format=self.audio_format,
                sample_rate=self.sample_rate,
                file_urls=[f'data:audio/{self.audio_format};base64,{audio_base64}']
            )
            
            if result.status_code == 200:
                logger.info("✓ API调用成功")
                
                output = result.output
                logger.debug(f"API返回的完整输出: {output}")
                
                if 'results' in output and len(output['results']) > 0:
                    transcription = output['results'][0]
                    logger.debug(f"识别结果对象: {transcription}")
                    
                    # 先尝试直接获取文本
                    full_text = transcription.get('transcription', '').strip()
                    logger.debug(f"直接获取的文本: '{full_text}'")
                    
                    # 如果直接文本为空，尝试从URL下载
                    if not full_text and 'transcription_url' in transcription:
                        transcription_url = transcription['transcription_url']
                        logger.info("文本为空，尝试从URL下载结果")
                        full_text = self._download_transcription(transcription_url)
                        logger.debug(f"从URL下载的文本: '{full_text}'")
                    
                    # 尝试其他可能的字段名
                    if not full_text:
                        # 尝试 'text' 字段
                        full_text = transcription.get('text', '').strip()
                        logger.debug(f"从'text'字段获取的文本: '{full_text}'")
                    
                    if not full_text:
                        # 尝试 'sentence' 字段
                        full_text = transcription.get('sentence', '').strip()
                        logger.debug(f"从'sentence'字段获取的文本: '{full_text}'")
                    
                    if full_text:
                        logger.info(f"✓ 识别结果: {full_text}")
                        
                        # 保存识别结果到 voice_output.txt（JSON格式）
                        # 确保目录存在
                        os.makedirs(TEMP_DATA_DIR, exist_ok=True)
                        
                        # 构建输出数据
                        output_data = {
                            "human_message": full_text
                        }
                        
                        # 覆盖写入到指定文件
                        with open(FILE_VOICE_OUTPUT, 'w', encoding='utf-8') as f:
                            json.dump(output_data, f, ensure_ascii=False, indent=4)
                        
                        logger.info(f"识别结果已保存: {FILE_VOICE_OUTPUT}")
                        
                        # 删除录音文件
                        if delete_after_recognition:
                            self._delete_audio_files(audio_file, audio_file_to_recognize, convert_audio)
                        
                        return FILE_VOICE_OUTPUT
                    else:
                        logger.error("无法获取识别结果文本")
                        logger.error(f"识别结果对象的所有字段: {list(transcription.keys()) if transcription else 'None'}")
                        logger.error(f"识别结果对象的完整内容: {transcription}")
                        # 即使识别失败，如果设置了删除，也要删除文件
                        if delete_after_recognition:
                            self._delete_audio_files(audio_file, audio_file_to_recognize, convert_audio)
                        return None
                else:
                    logger.warning(f"API返回结果为空: {output}")
                    # 即使识别失败，如果设置了删除，也要删除文件
                    if delete_after_recognition:
                        self._delete_audio_files(audio_file, audio_file_to_recognize, convert_audio)
                    return None
            else:
                logger.error(f"API调用失败 (状态码 {result.status_code}): {result.message}")
                # 即使识别失败，如果设置了删除，也要删除文件
                if delete_after_recognition:
                    self._delete_audio_files(audio_file, audio_file_to_recognize, convert_audio)
                return None
                
        except Exception as e:
            logger.exception(f"识别过程出错: {e}")
            # 即使出现异常，如果设置了删除，也要尝试删除文件
            if delete_after_recognition:
                try:
                    audio_file_to_recognize = f"{os.path.splitext(audio_file)[0]}_asr.wav" if convert_audio else audio_file
                    self._delete_audio_files(audio_file, audio_file_to_recognize, convert_audio)
                except Exception:
                    pass
            return None
    
    def _delete_audio_files(self, audio_file: str, audio_file_to_recognize: Optional[str], convert_audio: bool):
        """
        删除音频文件（原始文件和转换后的文件）
        
        参数:
            audio_file: 原始音频文件路径
            audio_file_to_recognize: 用于识别的音频文件路径
            convert_audio: 是否转换了音频
        """
        try:
            # 删除原始录音文件
            if os.path.exists(audio_file):
                os.remove(audio_file)
                logger.info(f"已删除录音文件: {audio_file}")
            
            # 删除转换后的文件（如果存在）
            if convert_audio and audio_file_to_recognize and os.path.exists(audio_file_to_recognize):
                os.remove(audio_file_to_recognize)
                logger.debug(f"已删除转换文件: {audio_file_to_recognize}")
        except Exception as e:
            logger.warning(f"删除文件失败: {e}")


def recognize_audio(audio_file: str, **kwargs) -> Optional[str]:
    """
    便捷函数：快速识别音频文件
    
    参数:
        audio_file: 音频文件路径
        **kwargs: 其他参数传递给SpeechRecognition.recognize()
    
    返回:
        识别文本文件路径，失败返回None
    
    示例:
        >>> txt_file = recognize_audio("recording.wav")
        >>> print(f"识别结果保存在: {txt_file}")
    """
    recognizer = SpeechRecognition()
    return recognizer.recognize(audio_file, **kwargs)


if __name__ == "__main__":
    # 测试代码
    print("=" * 60)
    print("语音识别工具测试")
    print("=" * 60)
    
    # 需要提供测试音频文件
    test_audio = input("请输入测试音频文件路径（留空跳过）: ").strip()
    
    if test_audio and os.path.exists(test_audio):
        recognizer = SpeechRecognition()
        
        print(f"\n识别音频文件: {test_audio}")
        txt_file = recognizer.recognize(test_audio, delete_after_recognition=False)
        
        if txt_file and os.path.exists(txt_file):
            with open(txt_file, 'r', encoding='utf-8') as f:
                text = f.read()
            print(f"\n✓ 识别成功！")
            print(f"识别结果: {text}")
            print(f"结果文件: {txt_file}")
        else:
            print("\n✗ 识别失败")
    else:
        print("跳过测试（未提供测试文件）")

