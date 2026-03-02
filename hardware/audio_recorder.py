#!/usr/bin/env python3
"""
音频录音工具
录音并保存到临时文件夹
高独立性、低耦合、高鲁棒性设计
"""
import os
import sys
import time
import wave
import threading
import logging
import subprocess
from datetime import datetime
from typing import Optional, Callable

# 抑制ALSA警告 - 在导入pyaudio之前
os.environ.setdefault('PYTHONWARNINGS', 'ignore')
import warnings
warnings.filterwarnings('ignore')

# 导入配置
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import (
    HW_SAMPLE_RATE,
    HW_CHANNELS,
    HW_CHUNK,
    HW_FORMAT,
    MAX_DURATION,
    SAVE_DIR,
    SOX_VOLUME_GAIN,
    DEBUG_LOG
)

# 配置日志（减少输出）
logging.basicConfig(
    level=logging.WARNING if not DEBUG_LOG else logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class AudioRecorder:
    """
    音频录音工具类
    支持同步和异步录音
    """
    
    def __init__(self,
                 sample_rate: Optional[int] = None,
                 channels: Optional[int] = None,
                 chunk_size: Optional[int] = None,
                 audio_format: Optional[str] = None,
                 save_dir: Optional[str] = None,
                 max_duration: Optional[float] = None,
                 input_device_index: Optional[int] = None,
                 volume_gain: Optional[float] = None):
        """
        初始化音频录音工具
        
        参数:
            sample_rate: 采样率（Hz），默认使用config.py中的配置
            channels: 声道数，默认使用config.py中的配置
            chunk_size: 音频块大小，默认使用config.py中的配置
            audio_format: PyAudio格式，默认使用config.py中的配置
            save_dir: 保存目录，默认使用config.py中的配置
            max_duration: 最大录音时长（秒），默认使用config.py中的配置
            input_device_index: 输入设备索引，None表示使用默认设备
            volume_gain: 音量增益倍数，默认使用config.py中的SOX_VOLUME_GAIN
        """
        try:
            # 抑制ALSA警告 - 在导入pyaudio时
            with open(os.devnull, 'w') as devnull:
                old_stderr = sys.stderr
                sys.stderr = devnull
                try:
                    import pyaudio
                    self.pyaudio = pyaudio
                finally:
                    sys.stderr = old_stderr
        except ImportError:
            raise ImportError("PyAudio 未安装，请运行: pip3 install pyaudio")
        
        self.sample_rate = sample_rate or HW_SAMPLE_RATE
        self.channels = channels or HW_CHANNELS
        self.chunk_size = chunk_size or HW_CHUNK
        self.audio_format = audio_format or HW_FORMAT
        self.max_duration = max_duration if max_duration is not None else MAX_DURATION
        
        # 转换格式字符串为PyAudio格式常量
        if isinstance(self.audio_format, str):
            format_map = {
                'paInt32': self.pyaudio.paInt32,
                'paInt16': self.pyaudio.paInt16,
                'paInt8': self.pyaudio.paInt8,
                'paFloat32': self.pyaudio.paFloat32,
            }
            self.format = format_map.get(self.audio_format, self.pyaudio.paInt32)
        else:
            self.format = self.audio_format
        
        self.save_dir = save_dir or SAVE_DIR
        self.input_device_index = input_device_index
        self.volume_gain = volume_gain if volume_gain is not None else SOX_VOLUME_GAIN
        self._ensure_save_dir()
        
        self.audio = None
        self.recording_flag = threading.Event()
        self.stop_request = threading.Event()
        self.worker_thread = None
        
        # 如果没有指定设备索引，尝试自动检测
        if self.input_device_index is None:
            self.input_device_index = self._detect_input_device()
        
        logger.info("音频录音工具初始化完成")
        if self.input_device_index is not None:
            logger.info(f"使用输入设备索引: {self.input_device_index}")
        logger.info(f"音量增益: {self.volume_gain}x")
    
    def _ensure_save_dir(self):
        """确保保存目录存在"""
        if self.save_dir:
            abs_save_dir = os.path.abspath(self.save_dir)
            os.makedirs(abs_save_dir, exist_ok=True)
            logger.debug(f"保存目录已确保存在: {abs_save_dir}")
    
    def _process_audio_channels(self, input_file: str, output_file: str) -> bool:
        """
        处理音频声道和音量：
        1. 提取左声道（麦克风）
        2. 复制到右声道
        3. 应用音量增益
        4. 生成立体声文件
        
        参数:
            input_file: 输入音频文件路径
            output_file: 输出音频文件路径
        
        返回:
            成功返回True，失败返回False
        """
        try:
            # 方案1：使用 sox（推荐，更灵活）
            # 提取左声道并复制到双声道，同时应用音量增益
            cmd = [
                "sox",
                input_file,
                output_file,
                "remix", "1,1",  # 将左声道复制到左右两个声道
                "vol", str(self.volume_gain)  # 音量增益
            ]
            logger.debug(f"使用 sox 处理声道和音量: {' '.join(cmd)}")
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            
            if result.returncode == 0:
                logger.debug(f"sox 处理成功: {output_file}")
                return True
            else:
                logger.warning(f"sox 处理失败: {result.stderr}")
                
        except FileNotFoundError:
            logger.debug("sox 未找到，尝试使用 ffmpeg")
            # 备用方案：使用 ffmpeg
            try:
                # ffmpeg 音量增益：volume=3.0 表示3倍音量
                cmd = [
                    "ffmpeg", "-i", input_file,
                    "-af", f"pan=stereo|c0=c0|c1=c0,volume={self.volume_gain}",  # 左声道复制到左右，并应用音量增益
                    "-y", output_file
                ]
                logger.debug(f"使用 ffmpeg 处理声道和音量: {' '.join(cmd)}")
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
                
                if result.returncode == 0:
                    logger.debug(f"ffmpeg 处理成功: {output_file}")
                    return True
                else:
                    logger.warning(f"ffmpeg 处理失败: {result.stderr}")
            except FileNotFoundError:
                logger.warning("ffmpeg 也未找到，跳过声道处理")
            except Exception as e:
                logger.warning(f"ffmpeg 处理异常: {e}")
        except Exception as e:
            logger.warning(f"处理音频声道时出错: {e}")
        
        # 如果处理失败，返回False
        return False
    
    def _detect_input_device(self) -> Optional[int]:
        """
        自动检测可用的音频输入设备
        
        返回:
            输入设备索引，如果未找到则返回None（使用默认设备）
        """
        try:
            if not self.audio:
                with open(os.devnull, 'w') as devnull:
                    old_stderr = sys.stderr
                    sys.stderr = devnull
                    try:
                        self.audio = self.pyaudio.PyAudio()
                    finally:
                        sys.stderr = old_stderr
            
            device_count = self.audio.get_device_count()
            logger.debug(f"检测到 {device_count} 个音频设备")
            
            # 查找有输入通道的设备
            for i in range(device_count):
                try:
                    device_info = self.audio.get_device_info_by_index(i)
                    max_input_channels = device_info.get('maxInputChannels', 0)
                    device_name = device_info.get('name', 'Unknown')
                    
                    # 优先选择有输入通道且不是HDMI的设备
                    if max_input_channels > 0:
                        # 排除HDMI输出设备
                        if 'hdmi' not in device_name.lower() and 'bcm2835' not in device_name.lower():
                            logger.info(f"找到输入设备: {device_name} (索引: {i}, 输入通道: {max_input_channels})")
                            return i
                except Exception as e:
                    logger.debug(f"检查设备 {i} 时出错: {e}")
                    continue
            
            # 如果没有找到合适的设备，尝试使用默认输入设备
            try:
                default_input = self.audio.get_default_input_device_info()
                logger.info(f"使用默认输入设备: {default_input.get('name', 'Unknown')} (索引: {default_input.get('index', None)})")
                return default_input.get('index', None)
            except Exception as e:
                logger.warning(f"无法获取默认输入设备: {e}")
                return None
                
        except Exception as e:
            logger.warning(f"检测输入设备时出错: {e}")
            return None
    
    def _generate_filename(self, prefix: str = "recording") -> str:
        """生成录音文件名"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{prefix}_{timestamp}.wav"
        abs_save_dir = os.path.abspath(self.save_dir)
        return os.path.join(abs_save_dir, filename)
    
    def _open_stream(self):
        """打开音频输入流"""
        if not self.audio:
            # 抑制ALSA警告
            with open(os.devnull, 'w') as devnull:
                old_stderr = sys.stderr
                sys.stderr = devnull
                try:
                    self.audio = self.pyaudio.PyAudio()
                finally:
                    sys.stderr = old_stderr
        
        # 抑制ALSA警告
        with open(os.devnull, 'w') as devnull:
            old_stderr = sys.stderr
            sys.stderr = devnull
            try:
                stream_params = {
                    'format': self.format,
                    'channels': self.channels,
                    'rate': self.sample_rate,
                    'input': True,
                    'frames_per_buffer': self.chunk_size
                }
                
                # 如果指定了输入设备索引，添加到参数中
                if self.input_device_index is not None:
                    stream_params['input_device_index'] = self.input_device_index
                    logger.debug(f"使用输入设备索引: {self.input_device_index}")
                
                stream = self.audio.open(**stream_params)
                
                # 记录实际使用的设备信息
                if self.input_device_index is not None:
                    try:
                        device_info = self.audio.get_device_info_by_index(self.input_device_index)
                        logger.info(f"录音设备: {device_info.get('name', 'Unknown')}")
                    except:
                        pass
                        
            finally:
                sys.stderr = old_stderr
        
        return stream
    
    def record(self,
               output_path: Optional[str] = None,
               duration: Optional[float] = None,
               progress_callback: Optional[Callable[[float], None]] = None) -> Optional[str]:
        """
        同步录音
        
        参数:
            output_path: 输出文件路径，如果为None则自动生成
            duration: 录音时长（秒），如果为None则使用max_duration
            progress_callback: 进度回调函数，参数为已录音时长（秒）
        
        返回:
            录音文件路径，失败返回None
        """
        if self.recording_flag.is_set():
            logger.warning("已在录音中，请先停止当前录音")
            return None
        
        duration = duration if duration is not None else self.max_duration
        
        try:
            # 生成输出路径
            if not output_path:
                output_path = self._generate_filename()
            else:
                # 确保输出目录存在
                output_dir = os.path.dirname(output_path)
                if output_dir:
                    os.makedirs(output_dir, exist_ok=True)
            
            logger.info(f"开始录音: {output_path}")
            logger.info(f"采样率: {self.sample_rate}Hz, 声道: {self.channels}, 格式: {self.audio_format}")
            
            # 打开音频流
            stream = self._open_stream()
            frames = []
            start_time = time.time()
            
            try:
                while True:
                    elapsed = time.time() - start_time
                    
                    # 检查时长限制
                    if duration > 0 and elapsed >= duration:
                        logger.info(f"达到最大时长 {duration} 秒")
                        break
                    
                    # 读取音频数据
                    try:
                        data = stream.read(self.chunk_size, exception_on_overflow=False)
                        if data:
                            frames.append(data)
                        else:
                            logger.warning("读取到空音频数据")
                    except Exception as e:
                        logger.warning(f"读取音频帧异常: {e}")
                        continue
                    
                    # 进度回调
                    if progress_callback:
                        try:
                            progress_callback(elapsed)
                        except Exception as e:
                            logger.warning(f"进度回调异常: {e}")
                
                # 保存录音文件（先保存为临时文件）
                temp_output_path = output_path + ".tmp"
                logger.info("保存录音文件...")
                with wave.open(temp_output_path, 'wb') as wf:
                    # 计算采样宽度
                    if self.format == self.pyaudio.paInt32:
                        sampwidth = 4
                    elif self.format == self.pyaudio.paInt16:
                        sampwidth = 2
                    elif self.format == self.pyaudio.paInt8:
                        sampwidth = 1
                    else:
                        sampwidth = 4
                    
                    wf.setnchannels(self.channels)
                    wf.setsampwidth(sampwidth)
                    wf.setframerate(self.sample_rate)
                    wf.writeframes(b"".join(frames))
                
                # 处理声道（提取左声道并复制到左右声道）
                logger.info("处理音频声道...")
                if self._process_audio_channels(temp_output_path, output_path):
                    # 处理成功，删除临时文件
                    try:
                        if os.path.exists(temp_output_path):
                            os.remove(temp_output_path)
                            logger.debug("已删除临时文件")
                    except Exception as e:
                        logger.warning(f"删除临时文件失败: {e}")
                else:
                    # 处理失败，使用原始文件
                    logger.warning("声道处理失败，使用原始录音文件")
                    try:
                        if os.path.exists(temp_output_path):
                            os.rename(temp_output_path, output_path)
                    except Exception as e:
                        logger.warning(f"重命名临时文件失败: {e}")
                        # 如果重命名失败，尝试复制
                        try:
                            import shutil
                            shutil.copy2(temp_output_path, output_path)
                            os.remove(temp_output_path)
                        except Exception as e2:
                            logger.error(f"复制临时文件也失败: {e2}")
                
                file_size = os.path.getsize(output_path)
                total_frames = len(frames)
                total_bytes = sum(len(frame) for frame in frames)
                logger.info(f"录音完成: {output_path}")
                logger.info(f"文件大小: {file_size / 1024:.2f} KB")
                logger.info(f"录音帧数: {total_frames}, 总字节数: {total_bytes}")
                
                if file_size < 1000:  # 小于1KB
                    logger.warning("录音文件很小，可能没有录制到声音")
                
                return output_path
                
            finally:
                stream.stop_stream()
                stream.close()
                
        except Exception as e:
            logger.exception(f"录音过程异常: {e}")
            return None
    
    def start_recording(self, output_path: Optional[str] = None):
        """
        开始异步录音
        
        参数:
            output_path: 输出文件路径，如果为None则自动生成
        
        返回:
            录音文件路径（如果成功启动），失败返回None
        """
        if self.recording_flag.is_set():
            logger.warning("已在录音中")
            return None
        
        # 生成输出路径
        if not output_path:
            output_path = self._generate_filename()
        else:
            output_dir = os.path.dirname(output_path)
            if output_dir:
                os.makedirs(output_dir, exist_ok=True)
        
        self.recording_flag.set()
        self.stop_request.clear()
        self.worker_thread = threading.Thread(
            target=self._record_async,
            args=(output_path,),
            daemon=True
        )
        self.worker_thread.start()
        
        logger.info(f"开始异步录音: {output_path}")
        return output_path
    
    def stop_recording(self) -> Optional[str]:
        """
        停止异步录音
        
        返回:
            录音文件路径，失败返回None
        """
        if not self.recording_flag.is_set():
            logger.warning("当前未在录音")
            return None
        
        logger.info("停止录音请求")
        self.stop_request.set()
        
        if self.worker_thread:
            self.worker_thread.join(timeout=10)
        
        self.recording_flag.clear()
        logger.info("录音已停止")
        
        # 返回文件路径（需要从线程中获取，这里简化处理）
        return None
    
    def _record_async(self, output_path: str):
        """异步录音线程函数"""
        try:
            stream = self._open_stream()
            frames = []
            start_time = time.time()
            
            while not self.stop_request.is_set():
                elapsed = time.time() - start_time
                
                if self.max_duration > 0 and elapsed >= self.max_duration:
                    logger.info(f"达到最大时长 {self.max_duration} 秒")
                    break
                
                try:
                    data = stream.read(self.chunk_size, exception_on_overflow=False)
                    if data:
                        frames.append(data)
                    else:
                        logger.warning("读取到空音频数据")
                except Exception as e:
                    logger.warning(f"读取音频帧异常: {e}")
                    continue
            
            # 保存录音文件（先保存为临时文件）
            temp_output_path = output_path + ".tmp"
            with wave.open(temp_output_path, 'wb') as wf:
                if self.format == self.pyaudio.paInt32:
                    sampwidth = 4
                elif self.format == self.pyaudio.paInt16:
                    sampwidth = 2
                elif self.format == self.pyaudio.paInt8:
                    sampwidth = 1
                else:
                    sampwidth = 4
                
                wf.setnchannels(self.channels)
                wf.setsampwidth(sampwidth)
                wf.setframerate(self.sample_rate)
                wf.writeframes(b"".join(frames))
            
            # 处理声道（提取左声道并复制到左右声道）
            logger.info("处理音频声道...")
            if self._process_audio_channels(temp_output_path, output_path):
                # 处理成功，删除临时文件
                try:
                    if os.path.exists(temp_output_path):
                        os.remove(temp_output_path)
                        logger.debug("已删除临时文件")
                except Exception as e:
                    logger.warning(f"删除临时文件失败: {e}")
            else:
                # 处理失败，使用原始文件
                logger.warning("声道处理失败，使用原始录音文件")
                try:
                    if os.path.exists(temp_output_path):
                        os.rename(temp_output_path, output_path)
                except Exception as e:
                    logger.warning(f"重命名临时文件失败: {e}")
                    # 如果重命名失败，尝试复制
                    try:
                        import shutil
                        shutil.copy2(temp_output_path, output_path)
                        os.remove(temp_output_path)
                    except Exception as e2:
                        logger.error(f"复制临时文件也失败: {e2}")
            
            file_size = os.path.getsize(output_path)
            total_frames = len(frames)
            total_bytes = sum(len(frame) for frame in frames)
            logger.info(f"异步录音完成: {output_path}")
            logger.info(f"文件大小: {file_size / 1024:.2f} KB")
            logger.info(f"录音帧数: {total_frames}, 总字节数: {total_bytes}")
            
            if file_size < 1000:  # 小于1KB
                logger.warning("录音文件很小，可能没有录制到声音")
            
        except Exception as e:
            logger.exception(f"异步录音异常: {e}")
        finally:
            if stream:
                try:
                    stream.stop_stream()
                    stream.close()
                except Exception:
                    pass
    
    def is_recording(self) -> bool:
        """检查是否正在录音"""
        return self.recording_flag.is_set()
    
    def list_input_devices(self):
        """
        列出所有可用的音频输入设备
        
        返回:
            设备信息列表
        """
        devices = []
        try:
            if not self.audio:
                with open(os.devnull, 'w') as devnull:
                    old_stderr = sys.stderr
                    sys.stderr = devnull
                    try:
                        self.audio = self.pyaudio.PyAudio()
                    finally:
                        sys.stderr = old_stderr
            
            device_count = self.audio.get_device_count()
            print(f"\n找到 {device_count} 个音频设备:\n")
            
            for i in range(device_count):
                try:
                    device_info = self.audio.get_device_info_by_index(i)
                    max_input_channels = device_info.get('maxInputChannels', 0)
                    max_output_channels = device_info.get('maxOutputChannels', 0)
                    device_name = device_info.get('name', 'Unknown')
                    default_sample_rate = device_info.get('defaultSampleRate', 0)
                    
                    device_type = []
                    if max_input_channels > 0:
                        device_type.append(f"输入({max_input_channels}通道)")
                    if max_output_channels > 0:
                        device_type.append(f"输出({max_output_channels}通道)")
                    
                    device_str = f"设备 {i}: {device_name}"
                    if device_type:
                        device_str += f" [{', '.join(device_type)}]"
                    device_str += f" (采样率: {default_sample_rate}Hz)"
                    
                    print(device_str)
                    
                    if max_input_channels > 0:
                        devices.append({
                            'index': i,
                            'name': device_name,
                            'max_input_channels': max_input_channels,
                            'default_sample_rate': default_sample_rate
                        })
                except Exception as e:
                    print(f"设备 {i}: 无法获取信息 ({e})")
            
            print()
            return devices
            
        except Exception as e:
            logger.exception(f"列出设备时出错: {e}")
            return []
    
    def cleanup(self):
        """清理资源"""
        if self.recording_flag.is_set():
            self.stop_recording()
        
        if self.audio:
            try:
                self.audio.terminate()
                self.audio = None
            except Exception:
                pass
        
        logger.debug("资源已清理")


if __name__ == "__main__":
    # 测试代码
    print("=" * 60)
    print("音频录音工具测试")
    print("=" * 60)
    
    recorder = AudioRecorder()
    
    try:
        print("\n测试0: 列出所有输入设备")
        input_devices = recorder.list_input_devices()
        
        if input_devices:
            print(f"\n找到 {len(input_devices)} 个输入设备:")
            for dev in input_devices:
                print(f"  - 索引 {dev['index']}: {dev['name']} ({dev['max_input_channels']}通道)")
        else:
            print("\n⚠ 未找到输入设备")
        
        print("\n测试1: 同步录音（3秒）")
        print("请对着麦克风说话...")
        
        def progress_callback(elapsed):
            print(f"  录音进度: {elapsed:.1f}秒", end='\r')
        
        output_path = recorder.record(duration=3, progress_callback=progress_callback)
        
        if output_path and os.path.exists(output_path):
            file_size = os.path.getsize(output_path)
            print(f"\n  ✓ 录音成功: {output_path}")
            print(f"  文件大小: {file_size / 1024:.2f} KB")
            if file_size < 1000:
                print("  ⚠ 警告: 文件很小，可能没有录制到声音")
        else:
            print("\n  ✗ 录音失败")
        
    except KeyboardInterrupt:
        print("\n\n测试被用户中断")
    except Exception as e:
        print(f"\n错误: {e}")
        import traceback
        traceback.print_exc()
    finally:
        recorder.cleanup()

