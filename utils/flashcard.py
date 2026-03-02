#!/usr/bin/env python3
"""
单词卡片制作工具
适用于 360x360 圆形LCD屏幕
高独立性、低耦合、高鲁棒性设计
"""
import os
import sys
import logging
from typing import Optional, Tuple
from PIL import Image, ImageDraw, ImageFont

# 导入配置
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import (
    SCREEN_WIDTH,
    SCREEN_HEIGHT,
    CARD_BG_COLOR,
    CARD_CIRCLE_COLOR,
    CARD_TEXT_COLOR,
    CARD_IMAGE_SIZE,
    CARD_IMAGE_Y_OFFSET,
    FONT_EN_PATH,
    FONT_CN_PATH,
    FONT_EN_SIZE,
    FONT_CN_SIZE,
    DEBUG_LOG
)

# 配置日志
logging.basicConfig(
    level=logging.DEBUG if DEBUG_LOG else logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class FlashCardMaker:
    """
    单词卡片制作工具类
    可以独立使用，也可以配合EP1831T驱动显示
    """
    
    def __init__(self,
                 screen_width: Optional[int] = None,
                 screen_height: Optional[int] = None,
                 bg_color: Optional[Tuple[int, int, int]] = None,
                 circle_color: Optional[Tuple[int, int, int]] = None,
                 text_color: Optional[Tuple[int, int, int]] = None,
                 font_en_path: Optional[str] = None,
                 font_cn_path: Optional[str] = None,
                 font_en_size: Optional[int] = None,
                 font_cn_size: Optional[int] = None):
        """
        初始化单词卡片制作工具
        
        参数:
            screen_width: 屏幕宽度，默认使用config.py中的配置
            screen_height: 屏幕高度，默认使用config.py中的配置
            bg_color: 背景颜色，默认使用config.py中的配置
            circle_color: 圆形背景颜色，默认使用config.py中的配置
            text_color: 文字颜色，默认使用config.py中的配置
            font_en_path: 英文字体路径，默认使用config.py中的配置
            font_cn_path: 中文字体路径，默认使用config.py中的配置
            font_en_size: 英文字体大小，默认使用config.py中的配置
            font_cn_size: 中文字体大小，默认使用config.py中的配置
        """
        self.screen_width = screen_width or SCREEN_WIDTH
        self.screen_height = screen_height or SCREEN_HEIGHT
        self.bg_color = bg_color or CARD_BG_COLOR
        self.circle_color = circle_color or CARD_CIRCLE_COLOR
        self.text_color = text_color or CARD_TEXT_COLOR
        
        self.font_en_path = font_en_path or FONT_EN_PATH
        self.font_cn_path = font_cn_path or FONT_CN_PATH
        self.font_en_size = font_en_size or FONT_EN_SIZE
        self.font_cn_size = font_cn_size or FONT_CN_SIZE
        
        self.center = self.screen_width // 2
        self.circle_radius = self.center - 20
        
        # 加载字体
        self.font_en = None
        self.font_cn = None
        self._load_fonts()
        
        logger.info("单词卡片制作工具初始化完成")
    
    def _load_fonts(self):
        """加载字体"""
        try:
            # 加载英文字体
            if os.path.exists(self.font_en_path):
                self.font_en = ImageFont.truetype(self.font_en_path, self.font_en_size)
                logger.debug(f"英文字体加载成功: {self.font_en_path}")
            else:
                logger.warning(f"英文字体文件不存在: {self.font_en_path}，使用默认字体")
                self.font_en = ImageFont.load_default()
        except Exception as e:
            logger.warning(f"加载英文字体失败: {e}，使用默认字体")
            self.font_en = ImageFont.load_default()
        
        try:
            # 加载中文字体
            if os.path.exists(self.font_cn_path):
                self.font_cn = ImageFont.truetype(self.font_cn_path, self.font_cn_size)
                logger.debug(f"中文字体加载成功: {self.font_cn_path}")
            else:
                logger.warning(f"中文字体文件不存在: {self.font_cn_path}，使用默认字体")
                self.font_cn = ImageFont.load_default()
        except Exception as e:
            logger.warning(f"加载中文字体失败: {e}，使用默认字体")
            self.font_cn = ImageFont.load_default()
    
    def create_card(self,
                   image_path: str,
                   english_word: str,
                   chinese_word: str,
                   image_size: Optional[int] = None,
                   image_y_offset: Optional[int] = None) -> Image.Image:
        """
        创建单词记忆卡片
        
        参数:
            image_path: 图片路径
            english_word: 英文单词
            chinese_word: 中文翻译
            image_size: 图片大小（像素），默认使用config.py中的配置
            image_y_offset: 图片Y轴偏移（像素），默认使用config.py中的配置
        
        返回:
            PIL.Image对象（360x360）
        """
        if not os.path.exists(image_path):
            raise FileNotFoundError(f"图片文件不存在: {image_path}")
        
        image_size = image_size if image_size is not None else CARD_IMAGE_SIZE
        image_y_offset = image_y_offset if image_y_offset is not None else CARD_IMAGE_Y_OFFSET
        
        logger.info(f"创建单词卡片: {english_word} - {chinese_word}")
        
        try:
            # 创建底图
            canvas = Image.new('RGB', (self.screen_width, self.screen_height), self.bg_color)
            draw = ImageDraw.Draw(canvas)
            
            # 1. 绘制白色圆形背景
            self._draw_circle_background(draw)
            
            # 2. 加载并粘贴图片
            img = Image.open(image_path)
            img = img.convert('RGBA')
            
            # 调整图片大小
            img.thumbnail((image_size, image_size), Image.Resampling.LANCZOS)
            
            # 计算图片位置（中间偏上）
            img_x = self.center - img.width // 2
            img_y = self.center - img.height // 2 + image_y_offset
            
            # 粘贴图片（支持透明背景）
            canvas.paste(img, (img_x, img_y), img)
            
            # 3. 绘制文字
            self._draw_text(draw, english_word, chinese_word, img_y + img.height)
            
            logger.info("单词卡片创建完成")
            return canvas
            
        except Exception as e:
            logger.exception(f"创建单词卡片失败: {e}")
            raise
    
    def _draw_circle_background(self, draw: ImageDraw.Draw):
        """绘制白色圆形背景（比屏幕小，露出紫色边缘）"""
        try:
            margin = self.center - self.circle_radius
            x0 = margin
            y0 = margin
            x1 = self.screen_width - margin
            y1 = self.screen_height - margin
            
            draw.ellipse([x0, y0, x1, y1], 
                        fill=self.circle_color, outline=self.circle_color)
            logger.debug("圆形背景绘制完成")
        except Exception as e:
            logger.exception(f"绘制圆形背景失败: {e}")
            raise
    
    def _draw_text(self, draw: ImageDraw.Draw, english: str, chinese: str, start_y: int):
        """
        绘制居中的英文和中文文字
        
        参数:
            draw: ImageDraw对象
            english: 英文单词
            chinese: 中文翻译
            start_y: 起始Y坐标（图片底部）
        """
        try:
            spacing = 20  # 文字间距
            
            # 英文单词
            bbox_en = draw.textbbox((0, 0), english, font=self.font_en)
            text_width_en = bbox_en[2] - bbox_en[0]
            text_height_en = bbox_en[3] - bbox_en[1]
            
            x_en = self.center - text_width_en // 2
            y_en = start_y + spacing
            
            # 中文翻译
            bbox_cn = draw.textbbox((0, 0), chinese, font=self.font_cn)
            text_width_cn = bbox_cn[2] - bbox_cn[0]
            text_height_cn = bbox_cn[3] - bbox_cn[1]
            
            x_cn = self.center - text_width_cn // 2
            y_cn = y_en + text_height_en + spacing
            
            # 绘制文字
            draw.text((x_en, y_en), english, fill=self.text_color, font=self.font_en)
            draw.text((x_cn, y_cn), chinese, fill=self.text_color, font=self.font_cn)
            
            logger.debug("文字绘制完成")
        except Exception as e:
            logger.exception(f"绘制文字失败: {e}")
            raise
    
    def create_and_save(self,
                       image_path: str,
                       english_word: str,
                       chinese_word: str,
                       output_path: str,
                       image_size: Optional[int] = None,
                       image_y_offset: Optional[int] = None) -> str:
        """
        创建并保存单词卡片到文件
        
        参数:
            image_path: 图片路径
            english_word: 英文单词
            chinese_word: 中文翻译
            output_path: 输出文件路径
            image_size: 图片大小（像素），默认使用config.py中的配置
            image_y_offset: 图片Y轴偏移（像素），默认使用config.py中的配置
        
        返回:
            输出文件路径
        """
        try:
            card = self.create_card(image_path, english_word, chinese_word,
                                  image_size, image_y_offset)
            
            # 确保输出目录存在
            output_dir = os.path.dirname(output_path)
            if output_dir:
                os.makedirs(output_dir, exist_ok=True)
            
            card.save(output_path)
            logger.info(f"单词卡片已保存: {output_path}")
            return output_path
        except Exception as e:
            logger.exception(f"保存单词卡片失败: {e}")
            raise
    
    def create_and_display(self,
                          image_path: str,
                          english_word: str,
                          chinese_word: str,
                          display_driver,
                          image_size: Optional[int] = None,
                          image_y_offset: Optional[int] = None,
                          islands_progress: Optional[list] = None):
        """
        创建并显示单词卡片到显示屏
        
        参数:
            image_path: 图片路径
            english_word: 英文单词
            chinese_word: 中文翻译
            display_driver: EP1831TDriver实例
            image_size: 图片大小（像素），默认使用config.py中的配置
            image_y_offset: 图片Y轴偏移（像素），默认使用config.py中的配置
            islands_progress: 可选，章节学习进度列表，用于绘制进度环
        """
        try:
            card = self.create_card(image_path, english_word, chinese_word,
                                  image_size, image_y_offset)
            
            logger.info("显示单词卡片到显示屏...")
            display_driver.display_image(card, islands_progress=islands_progress)
            logger.info("单词卡片显示完成")
        except Exception as e:
            logger.exception(f"显示单词卡片失败: {e}")
            raise


def create_flashcard(image_path: str,
                    english_word: str,
                    chinese_word: str,
                    output_path: Optional[str] = None,
                    **kwargs) -> Image.Image:
    """
    便捷函数：快速创建单词卡片
    
    参数:
        image_path: 图片路径
        english_word: 英文单词
        chinese_word: 中文翻译
        output_path: 输出文件路径（可选），如果提供则保存文件
        **kwargs: 其他参数传递给FlashCardMaker.create_card()
    
    返回:
        PIL.Image对象
    
    示例:
        >>> card = create_flashcard("apple.png", "Apple", "苹果")
        >>> card.save("card.png")
    """
    maker = FlashCardMaker()
    card = maker.create_card(image_path, english_word, chinese_word, **kwargs)
    
    if output_path:
        maker.create_and_save(image_path, english_word, chinese_word, output_path, **kwargs)
    
    return card


if __name__ == "__main__":
    # 测试代码
    print("=" * 60)
    print("单词卡片制作工具测试")
    print("=" * 60)
    
    maker = FlashCardMaker()
    
    # 测试图片路径
    test_image = "/home/pi/projects/tydeus/imgs/apple.png"
    
    if os.path.exists(test_image):
        try:
            # 测试1: 创建卡片
            print("\n测试1: 创建单词卡片")
            card = maker.create_card(
                image_path=test_image,
                english_word="Apple",
                chinese_word="苹果"
            )
            print(f"✓ 卡片创建成功，尺寸: {card.size}")
            
            # 测试2: 保存卡片
            print("\n测试2: 保存单词卡片")
            output_path = "/home/pi/projects/tydeus/temp_data/test_card.png"
            maker.create_and_save(
                image_path=test_image,
                english_word="Apple",
                chinese_word="苹果",
                output_path=output_path
            )
            print(f"✓ 卡片已保存: {output_path}")
            
        except Exception as e:
            print(f"\n✗ 测试失败: {e}")
            import traceback
            traceback.print_exc()
    else:
        print(f"\n⚠ 测试图片不存在: {test_image}")

