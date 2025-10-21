import time
import os
import logging
import pyautogui
import asyncio
from playwright.async_api import async_playwright  # 改成异步 API

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


class BrowserTools:
    vm_ip = "127.0.0.1"
    chromium_port = 9222  # 默认 Chrome Remote Debugging Port

    @classmethod
    async def _chrome_open_tabs_setup(cls, urls_to_open):
        """
        连接到已启动的 Chrome 并打开指定的标签页 (async 版本)
        """
        host = cls.vm_ip
        port = cls.chromium_port
        remote_debugging_url = f"http://{host}:{port}"
        logger.info("Connect to Chrome @: %s", remote_debugging_url)
        logger.debug("PLAYWRIGHT ENV: %s", repr(os.environ))

        for attempt in range(15):
            if attempt > 0:
                await asyncio.sleep(5)   # 异步 sleep

            try:
                playwright = await async_playwright().start()
                browser = await playwright.chromium.connect_over_cdp(remote_debugging_url)
            except Exception as e:
                if attempt < 14:
                    logger.error(f"Attempt {attempt + 1}: Failed to connect, retrying. Error: {e}")
                    continue
                else:
                    logger.error(f"Failed to connect after multiple attempts: {e}")
                    raise e

            if not browser:
                return None, None

            logger.info("Opening %s...", urls_to_open)
            context = browser.contexts[0]

            for i, url in enumerate(urls_to_open):
                page = await context.new_page()
                try:
                    await page.goto(url, timeout=60000)
                except Exception:
                    logger.warning("Opening %s exceeds time limit", url)

                logger.info(f"Opened tab {i + 1}: {url}")

                if i == 0:
                    # 关闭默认的空白页
                    default_page = context.pages[0]
                    if default_page != page:
                        await default_page.close()

            return browser, context

    # ====== Chrome Pages (全改成 async) ======
    @classmethod
    async def chrome_open_tabs_setup(cls, url):
        return await cls._chrome_open_tabs_setup([url])
    @classmethod
    async def open_profile_settings(cls):
        return await cls._chrome_open_tabs_setup(["chrome://settings/people"])

    @classmethod
    async def open_password_settings(cls):
        return await cls._chrome_open_tabs_setup(["chrome://settings/autofill"])

    @classmethod
    async def open_privacy_settings(cls):
        return await cls._chrome_open_tabs_setup(["chrome://settings/privacy"])

    @classmethod
    async def open_appearance_settings(cls):
        return await cls._chrome_open_tabs_setup(["chrome://settings/appearance"])

    @classmethod
    async def open_search_engine_settings(cls):
        return await cls._chrome_open_tabs_setup(["chrome://settings/search"])

    @classmethod
    async def open_extensions(cls):
        return await cls._chrome_open_tabs_setup(["chrome://extensions"])

    @classmethod
    async def open_bookmarks(cls):
        return await cls._chrome_open_tabs_setup(["chrome://bookmarks"])

    # ====== Keyboard Shortcut Actions (保持同步) ======
    @classmethod
    def bring_back_last_tab(cls):
        """恢复上次关闭的标签页 (Ctrl+Shift+T)"""
        pyautogui.hotkey('ctrl', 'shift', 't')
        logger.info("Brought back last tab")

    @classmethod
    def print(cls):
        """打开打印对话框 (Ctrl+P)"""
        pyautogui.hotkey('ctrl', 'p')
        logger.info("Opened print option")

    @classmethod
    def delete_browsing_data(cls):
        """打开清除浏览数据窗口 (Ctrl+Shift+Del)"""
        pyautogui.hotkey('ctrl', 'shift', 'del')
        logger.info("Deleted browsing data dialog opened")

    @classmethod
    def bookmark_page(cls):
        """收藏当前页面 (Ctrl+D)"""
        pyautogui.hotkey('ctrl', 'd')
        logger.info("Bookmarked current page")


# 示例用法
if __name__ == "__main__":
    async def main():
        BrowserTools.vm_ip = "127.0.0.1"
        BrowserTools.chromium_port = 9222

        await BrowserTools.open_privacy_settings()  # 现在用 await 调用
        await asyncio.sleep(1)
        BrowserTools.bring_back_last_tab()  # 依旧同步调用

    asyncio.run(main())
