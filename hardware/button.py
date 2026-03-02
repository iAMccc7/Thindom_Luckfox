#!/usr/bin/env python3
"""
按钮检测工具
检测按钮的按下状态（低电平触发）
高独立性、低耦合、高鲁棒性设计
"""
import os
import sys
import time
import logging
from typing import Optional, Callable

# 导入配置
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import (
    USE_GPIO,
    BUTTON_PIN,
    DEBOUNCE_TIME,
    BUTTON_LONG_PRESS_TIME,
    DEBUG_LOG
)

# 配置日志
logging.basicConfig(
    level=logging.DEBUG if DEBUG_LOG else logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class Button:
    """
    按钮检测工具类
    支持低电平触发（按下时为低电平，未按下时为高电平）
    支持轮询、长按检测等功能
    """
    
    def __init__(self,
                 pin: Optional[int] = None,
                 debounce_time: Optional[float] = None,
                 use_gpio: Optional[bool] = None):
        """
        初始化按钮检测工具
        
        参数:
            pin: GPIO引脚（BCM编号），默认使用config.py中的配置
            debounce_time: 消抖时间（秒），默认使用config.py中的配置
            use_gpio: 是否使用GPIO，默认使用config.py中的配置
        """
        self.pin = pin if pin is not None else BUTTON_PIN
        self.debounce_time = debounce_time if debounce_time is not None else DEBOUNCE_TIME
        self.use_gpio = use_gpio if use_gpio is not None else USE_GPIO
        
        self.gpio_chip = None
        self._initialized = False
        
        if self.use_gpio:
            self._init_gpio()
        else:
            logger.warning("GPIO未启用，按钮检测功能不可用")
    
    def _init_gpio(self):
        """初始化GPIO（使用上拉电阻，按下时为低电平）"""
        try:
            import lgpio
            self.gpio_chip = lgpio.gpiochip_open(4)
            # 使用上拉电阻，按下时GPIO读取为0（低电平），未按下时为1（高电平）
            lgpio.gpio_claim_input(self.gpio_chip, self.pin, lgpio.SET_PULL_UP)
            self._initialized = True
            logger.info(f"按钮初始化成功，引脚 BCM {self.pin}（低电平触发）")
        except ImportError:
            logger.error("lgpio 未安装，请运行: pip3 install lgpio")
            self._initialized = False
        except Exception as e:
            logger.exception(f"GPIO初始化失败: {e}")
            self._initialized = False
    
    def is_pressed(self) -> bool:
        """
        检测按钮是否被按下
        
        返回:
            True表示按下（低电平），False表示未按下（高电平）
        """
        if not self._initialized:
            logger.warning("GPIO未初始化，无法检测")
            return False
        
        try:
            import lgpio
            # 读取GPIO状态，0表示按下（低电平），1表示未按下（高电平）
            state = lgpio.gpio_read(self.gpio_chip, self.pin)
            return state == 0  # 低电平表示按下
        except Exception as e:
            logger.exception(f"读取GPIO状态失败: {e}")
            return False
    
    def wait_for_press(self, timeout: Optional[float] = None) -> bool:
        """
        等待按钮被按下（带消抖）
        
        参数:
            timeout: 超时时间（秒），None表示无限等待
        
        返回:
            True表示检测到按下，False表示超时
        """
        if not self._initialized:
            logger.warning("GPIO未初始化，无法检测")
            return False
        
        start_time = time.time()
        last_press_time = 0
        
        while True:
            if timeout and (time.time() - start_time) > timeout:
                logger.debug("等待按下超时")
                return False
            
            if self.is_pressed():
                now = time.time()
                # 消抖处理
                if now - last_press_time >= self.debounce_time:
                    logger.debug("检测到按下")
                    return True
                time.sleep(0.01)
            else:
                last_press_time = 0
                time.sleep(0.01)
    
    def wait_for_release(self, timeout: Optional[float] = None) -> bool:
        """
        等待按钮释放（带消抖）
        
        参数:
            timeout: 超时时间（秒），None表示无限等待
        
        返回:
            True表示检测到释放，False表示超时
        """
        if not self._initialized:
            logger.warning("GPIO未初始化，无法检测")
            return False
        
        start_time = time.time()
        last_release_time = 0
        
        while True:
            if timeout and (time.time() - start_time) > timeout:
                logger.debug("等待释放超时")
                return False
            
            if not self.is_pressed():
                now = time.time()
                # 消抖处理
                if now - last_release_time >= self.debounce_time:
                    logger.debug("检测到释放")
                    return True
                time.sleep(0.01)
            else:
                last_release_time = 0
                time.sleep(0.01)
    
    def wait_for_long_press(self, long_press_time: Optional[float] = None, timeout: Optional[float] = None) -> bool:
        """
        等待按钮长按
        
        参数:
            long_press_time: 长按时间（秒），默认使用config.py中的配置
            timeout: 超时时间（秒），None表示无限等待
        
        返回:
            True表示检测到长按，False表示超时或提前释放
        """
        if not self._initialized:
            logger.warning("GPIO未初始化，无法检测")
            return False
        
        long_press_duration = long_press_time if long_press_time is not None else BUTTON_LONG_PRESS_TIME
        start_time = time.time()
        
        # 先等待按下
        if not self.wait_for_press(timeout=timeout):
            return False
        
        press_start_time = time.time()
        logger.debug(f"检测到按下，开始计时长按（需要 {long_press_duration} 秒）...")
        
        # 持续检测是否保持按下状态
        while self.is_pressed():
            elapsed = time.time() - press_start_time
            
            # 检查是否达到长按时间
            if elapsed >= long_press_duration:
                logger.debug(f"检测到长按（持续 {elapsed:.2f} 秒）")
                return True
            
            # 检查总超时时间
            if timeout and (time.time() - start_time) > timeout:
                logger.debug("等待长按超时")
                return False
            
            time.sleep(0.01)
        
        # 如果提前释放，返回False
        logger.debug("按钮提前释放，未达到长按时间")
        return False
    
    def monitor(self, press_callback: Optional[Callable[[], None]] = None,
                release_callback: Optional[Callable[[], None]] = None,
                poll_interval: float = 0.01):
        """
        持续监控按钮状态（阻塞）
        
        参数:
            press_callback: 按下时的回调函数
            release_callback: 释放时的回调函数
            poll_interval: 轮询间隔（秒）
        """
        if not self._initialized:
            logger.warning("GPIO未初始化，无法监控")
            return
        
        last_state = False
        last_change_time = 0
        
        logger.info("开始监控按钮...")
        
        try:
            while True:
                current_state = self.is_pressed()
                
                # 状态变化检测（带消抖）
                if current_state != last_state:
                    now = time.time()
                    if now - last_change_time >= self.debounce_time:
                        last_state = current_state
                        last_change_time = now
                        
                        if current_state:
                            logger.debug("检测到按下")
                            if press_callback:
                                try:
                                    press_callback()
                                except Exception as e:
                                    logger.exception(f"按下回调异常: {e}")
                        else:
                            logger.debug("检测到释放")
                            if release_callback:
                                try:
                                    release_callback()
                                except Exception as e:
                                    logger.exception(f"释放回调异常: {e}")
                
                time.sleep(poll_interval)
                
        except KeyboardInterrupt:
            logger.info("监控被用户中断")
        except Exception as e:
            logger.exception(f"监控过程异常: {e}")
    
    def cleanup(self):
        """清理资源"""
        if self.gpio_chip:
            try:
                import lgpio
                # 检查GPIO是否已分配，避免重复清理
                try:
                    lgpio.gpio_free(self.gpio_chip, self.pin)
                except Exception as free_error:
                    # GPIO可能已经被释放或未分配，忽略此错误
                    if "not allocated" not in str(free_error).lower():
                        logger.debug(f"释放GPIO时出错（可忽略）: {free_error}")
                
                try:
                    lgpio.gpiochip_close(self.gpio_chip)
                except Exception as close_error:
                    logger.debug(f"关闭GPIO芯片时出错（可忽略）: {close_error}")
                
                self.gpio_chip = None
                self._initialized = False
                logger.info("资源已清理")
            except Exception as e:
                # 如果错误是"GPIO not allocated"，这是正常的，可以忽略
                if "not allocated" not in str(e).lower():
                    logger.warning(f"清理资源时出错: {e}")
                else:
                    logger.debug(f"清理资源时GPIO未分配（可忽略）: {e}")


if __name__ == "__main__":
    # 测试代码
    print("=" * 60)
    print("按钮检测工具测试")
    print("=" * 60)
    
    button = Button()
    
    try:
        if not button._initialized:
            print("⚠ GPIO未初始化，跳过测试")
        else:
            print("\n测试1: 检测当前状态")
            print(f"  当前状态: {'按下' if button.is_pressed() else '未按下'}")
            
            print("\n测试2: 等待按下（5秒超时）")
            if button.wait_for_press(timeout=5):
                print("  ✓ 检测到按下")
                print("\n测试3: 等待释放（5秒超时）")
                if button.wait_for_release(timeout=5):
                    print("  ✓ 检测到释放")
            else:
                print("  ⚠ 超时，未检测到按下")
            
            print(f"\n测试4: 等待长按（{BUTTON_LONG_PRESS_TIME}秒，10秒超时）")
            if button.wait_for_long_press(timeout=10):
                print("  ✓ 检测到长按")
            else:
                print("  ⚠ 未检测到长按")
            
            print("\n测试5: 持续监控（按Ctrl+C退出）")
            press_count = [0]
            
            def on_press():
                press_count[0] += 1
                print(f"  按下 #{press_count[0]}")
            
            button.monitor(press_callback=on_press)
            
    except KeyboardInterrupt:
        print("\n\n测试被用户中断")
    except Exception as e:
        print(f"\n错误: {e}")
        import traceback
        traceback.print_exc()
    finally:
        button.cleanup()



