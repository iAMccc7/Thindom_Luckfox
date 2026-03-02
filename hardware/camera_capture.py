#!/usr/bin/env python3
"""
摄像头拍摄工具
用于拍摄照片并保存到临时文件夹
高独立性、低耦合、高鲁棒性设计
"""
import os
import sys
import cv2
import numpy as np
import logging
from datetime import datetime
from typing import Optional

# 导入配置
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import (
    TEMP_DATA_DIR,
    DEBUG_LOG
)

# 配置日志
logging.basicConfig(
    level=logging.DEBUG if DEBUG_LOG else logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 摄像头分辨率设置（1080p）
CAMERA_WIDTH = 1920
CAMERA_HEIGHT = 1080


class CameraCapture:
    """
    摄像头拍摄工具类
    支持USB摄像头拍摄照片
    """
    
    def __init__(self,
                 width: Optional[int] = None,
                 height: Optional[int] = None,
                 save_dir: Optional[str] = None):
        """
        初始化摄像头拍摄工具
        
        参数:
            width: 照片宽度（像素），默认1920（1080p）
            height: 照片高度（像素），默认1080（1080p）
            save_dir: 保存目录，默认使用config.py中的TEMP_DATA_DIR
        """
        self.width = width or CAMERA_WIDTH
        self.height = height or CAMERA_HEIGHT
        self.save_dir = save_dir or TEMP_DATA_DIR
        
        # 确保保存目录存在
        if self.save_dir:
            os.makedirs(self.save_dir, exist_ok=True)
            logger.debug(f"保存目录已确保存在: {self.save_dir}")
    
    def capture_photo_usb_camera(self) -> Optional[np.ndarray]:
        """
        使用USB摄像头拍摄照片
        
        返回:
            numpy.ndarray: 拍摄的照片（BGR格式），失败返回None
        """
        logger.debug("尝试使用USB摄像头...")
        cap = cv2.VideoCapture(0)
        
        if not cap.isOpened():
            logger.warning("USB摄像头无法打开")
            return None
        
        try:
            # 设置摄像头分辨率为1080p
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
            
            # 读取几帧以让摄像头调整（读取帧本身已经包含了等待时间）
            logger.debug("让摄像头调整...")
            for _ in range(5):
                ret, frame = cap.read()
                if not ret:
                    logger.warning("无法从USB摄像头读取帧")
                    return None
            
            # 拍摄照片
            logger.debug("正在拍摄照片...")
            ret, frame = cap.read()
            
            if not ret or frame is None:
                logger.warning("拍摄失败")
                return None
            
            # 获取实际分辨率
            actual_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            actual_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            logger.debug(f"实际分辨率: {actual_width}x{actual_height}")
            
            # 如果实际分辨率不是1080p，尝试调整
            if actual_width != self.width or actual_height != self.height:
                logger.debug(f"调整图像分辨率到 {self.width}x{self.height}")
                frame = cv2.resize(frame, (self.width, self.height))
            
            return frame
            
        except Exception as e:
            logger.exception(f"USB摄像头拍摄异常: {e}")
            return None
        finally:
            cap.release()
    
    def capture(self) -> Optional[np.ndarray]:
        """
        拍摄照片（使用USB摄像头）
        
        返回:
            numpy.ndarray: 拍摄的照片（BGR格式），失败返回None
        """
        return self.capture_photo_usb_camera()
    
    def save_photo(self, 
                   frame: np.ndarray,
                   filename: Optional[str] = None) -> Optional[str]:
        """
        保存照片到文件
        
        参数:
            frame: 照片数据（numpy.ndarray，BGR格式）
            filename: 文件名，如果为None则自动生成（带时间戳）
        
        返回:
            str: 保存的文件路径，失败返回None
        """
        if frame is None:
            logger.error("照片数据为空")
            return None
        
        try:
            # 生成文件名
            if filename is None:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"photo_{timestamp}.jpg"
            
            # 确保文件名有扩展名
            if not filename.lower().endswith(('.jpg', '.jpeg', '.png')):
                filename += '.jpg'
            
            # 构建完整路径
            filepath = os.path.join(self.save_dir, filename)
            
            # 保存照片
            success = cv2.imwrite(filepath, frame)
            
            if success:
                file_size = os.path.getsize(filepath)
                logger.info(f"照片保存成功: {filepath} ({file_size / 1024:.2f} KB)")
                return filepath
            else:
                logger.error(f"照片保存失败: {filepath}")
                return None
                
        except Exception as e:
            logger.exception(f"保存照片异常: {e}")
            return None
    
    def capture_and_save(self, filename: Optional[str] = None) -> Optional[str]:
        """
        拍摄照片并保存（便捷方法）
        
        参数:
            filename: 文件名，如果为None则自动生成（带时间戳）
        
        返回:
            str: 保存的文件路径，失败返回None
        """
        frame = self.capture()
        if frame is None:
            logger.error("拍摄失败")
            return None
        
        return self.save_photo(frame, filename)
    
    def cleanup(self):
        """
        清理资源（目前不需要，但保持接口一致性）
        """
        logger.debug("摄像头工具清理完成")


def capture_photo(filename: Optional[str] = None,
                 save_dir: Optional[str] = None,
                 **kwargs) -> Optional[str]:
    """
    便捷函数：快速拍摄照片并保存
    
    参数:
        filename: 文件名，如果为None则自动生成（带时间戳）
        save_dir: 保存目录，默认使用config.py中的TEMP_DATA_DIR
        **kwargs: 其他参数传递给CameraCapture构造函数
    
    返回:
        str: 保存的文件路径，失败返回None
    
    示例:
        >>> path = capture_photo()
        >>> print(f"照片已保存到: {path}")
    """
    camera = CameraCapture(save_dir=save_dir, **kwargs)
    return camera.capture_and_save(filename)


if __name__ == "__main__":
    # 测试代码
    print("=" * 60)
    print("摄像头拍摄工具测试")
    print("=" * 60)
    
    camera = CameraCapture()
    
    print("\n正在拍摄照片...")
    filepath = camera.capture_and_save()
    
    if filepath:
        print(f"\n✓ 成功！照片已保存到: {filepath}")
        file_size = os.path.getsize(filepath)
        print(f"  文件大小: {file_size / 1024:.2f} KB")
    else:
        print("\n✗ 失败！")
    
    camera.cleanup()

