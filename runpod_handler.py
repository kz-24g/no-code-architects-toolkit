"""
RunPod Serverless Handler (Debug Version)
"""

import runpod
import requests
import subprocess
import time
import os
import logging
import sys

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

flask_process = None

def start_flask_server():
    global flask_process
    if flask_process is not None:
        if flask_process.poll() is None:
            return
        else:
            logger.warning("⚠️ Old Flask process is dead, restarting...")

    logger.info("🚀 Starting Flask server...")
    
    # [修正] 移除 env 參數，讓它直接繼承系統環境變數，確保能吃到 Dockerfile 設定
    # 使用 sys.executable 確保用的是同一個 Python 解譯器
    flask_process = subprocess.Popen(
        [sys.executable, 'app_runpod.py'],
        env=os.environ.copy() 
    )
    
    # 等待服務器啟動 (增加到 60秒，並加入崩潰偵測)
    for i in range(60):
        # 1. 檢查 Flask 是否已經死掉 (Crash Detection)
        return_code = flask_process.poll()
        if return_code is not None:
            # 如果進程結束了，拋出錯誤，這樣 Logs 就會顯示 Flask 為什麼死掉
            raise RuntimeError(f"🔥 Flask server crashed immediately with exit code: {return_code}. Check logs above for ImportError or SyntaxError.")

        # 2. 嘗試連線
        try:
            response = requests.get('http://localhost:8080/health', timeout=1)
            if response.status_code == 200:
                logger.info(f"✅ Flask ready (attempt {i+1})")
                return
        except requests.exceptions.ConnectionError:
            pass # 服務還沒起來，繼續等
        except Exception as e:
            logger.warning(f"Health check warning: {e}")

        time.sleep(1)
    
    # 如果跑完迴圈還沒好，殺掉進程並報錯
    flask_process.terminate()
    raise RuntimeError("⏳ Flask server startup timeout (60s). It did not crash, but is not responding.")

def handler(event):
    try:
        start_flask_server()
        
        input_data = event.get('input', {})
        
        # 1. 解析 n8n 傳來的參數
        if 'endpoint' in input_data:
            endpoint = input_data.get('endpoint')
            method = input_data.get('method', 'POST')
            body = input_data.get('body', {})
        else:
            endpoint = '/health'
            method = 'GET'
            body = {}
        
        url = f"http://localhost:8080{endpoint}"
        logger.info(f"📨 Forwarding to: {method} {endpoint}")

        # ======================================================
        # [關鍵修改] 從 RunPod 環境變數讀取 API Key
        # ======================================================
        # 我們不再 Hardcode，直接讀取你在 RunPod 設定的 "API_KEY"
        api_key = os.environ.get('API_KEY')
        
        if not api_key:
            # 如果讀不到，記錄警告 (方便除錯)
            logger.warning("⚠️ Warning: API_KEY not found in environment variables!")

        # 建立 Headers，把 Key 放進去
        headers = {
            'Content-Type': 'application/json',
            'x-api-key': api_key  # 這裡將變數傳給 Flask
        }
        
        # ======================================================
        # 發送請求時，務必帶上 headers
        # ======================================================
        if method == 'POST':
            response = requests.post(url, json=body, headers=headers, timeout=600)
        else:
            response = requests.get(url, headers=headers, timeout=60)
        
        try:
            return response.json()
        except:
            return response.text
            
    except Exception as e:
        logger.exception("Handler error")
        return {'error': str(e)}


if __name__ == '__main__':
    logger.info("🎮 RunPod Serverless Handler starting")
    runpod.serverless.start({'handler': handler})