"""
从 resdc.cn 下载 50万草地资源图样例数据
直接访问 download.aspx?FileID=4068 和 4069
"""

import time
from pathlib import Path
from playwright.sync_api import sync_playwright

TARGET_DIR = Path(r"C:\Users\WH\Desktop\gonghangbei - 副本\public_data\grassland")
TARGET_DIR.mkdir(exist_ok=True)
EDGE_USER_DATA = r"C:\Users\WH\AppData\Local\Microsoft\Edge\User Data"

def download_files():
    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir=EDGE_USER_DATA,
            channel="msedge",
            headless=False,
            accept_downloads=True,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-first-run",
                "--no-default-browser-check",
                "--disable-features=DestroyProfileOnBrowserClose",
                "--disable-popup-blocking"
            ]
        )
        page = context.pages[0] if context.pages else context.new_page()
        
        # 先访问数据页面建立session
        print("访问数据页面建立session...")
        page.goto("https://www.resdc.cn/data.aspx?DATAID=355", wait_until="networkidle", timeout=60000)
        time.sleep(3)
        
        # 下载两个文件
        file_ids = [4068, 4069]
        downloaded_files = []
        
        for file_id in file_ids:
            print(f"\n下载文件 FileID={file_id}...")
            try:
                # 监听下载事件
                downloaded = None
                
                def on_download(download, fid=file_id):
                    nonlocal downloaded
                    print(f"检测到下载: {download.suggested_filename}")
                    filename = f"resdc_{fid}_{download.suggested_filename}"
                    filepath = TARGET_DIR / filename
                    download.save_as(filepath)
                    downloaded = filepath
                    print(f"保存到: {filepath}")
                
                page.on("download", on_download)
                
                # 直接访问下载链接
                download_url = f"https://www.resdc.cn/download.aspx?FileID={file_id}"
                
                # 用 expect_download 等待下载
                with page.expect_download(timeout=60000) as download_info:
                    page.goto(download_url)
                
                download = download_info.value
                filename = f"resdc_{file_id}_{download.suggested_filename}"
                filepath = TARGET_DIR / filename
                download.save_as(filepath)
                print(f"下载完成: {filepath}")
                downloaded_files.append(filepath)
                
                page.remove_listener("download", on_download)
                time.sleep(2)
                
            except Exception as e:
                print(f"下载 FileID={file_id} 失败: {e}")
                # 尝试直接用链接下载
                try:
                    print(f"尝试直接点击下载链接...")
                    page.goto("https://www.resdc.cn/data.aspx?DATAID=355", wait_until="networkidle", timeout=60000)
                    time.sleep(2)
                    
                    # 找到对应的下载链接
                    download_link = page.locator(f"a[href*='FileID={file_id}']").first
                    if download_link.is_visible():
                        print(f"找到下载链接，点击...")
                        with page.expect_download(timeout=60000) as download_info:
                            download_link.click()
                        
                        download = download_info.value
                        filename = f"resdc_{file_id}_{download.suggested_filename}"
                        filepath = TARGET_DIR / filename
                        download.save_as(filepath)
                        print(f"下载完成: {filepath}")
                        downloaded_files.append(filepath)
                except Exception as e2:
                    print(f"直接点击也失败: {e2}")
        
        context.close()
        return downloaded_files

if __name__ == "__main__":
    print("=" * 60)
    print("50万草地资源图样例数据下载")
    print("=" * 60)
    
    files = download_files()
    
    print()
    print("=" * 60)
    if files:
        print(f"下载成功 {len(files)} 个文件:")
        for f in files:
            print(f"  {f}")
    else:
        print("下载失败")
    print("=" * 60)
