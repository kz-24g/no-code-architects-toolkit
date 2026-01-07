"""
RunPod Serverless Handler - 帶自動 GPU 編碼器替換
"""

import runpod
import requests
import subprocess
import time
import os
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

flask_process = None

def start_flask_server():
    global flask_process
    if flask_process is not None:
        return
    
    logger.info("🚀 Starting Flask server...")
    flask_process = subprocess.Popen(
        ['python', 'app_runpod.py'],
        env={**os.environ, 'PORT': '8080'}
    )
    
    for i in range(30):
        try:
            response = requests.get('http://localhost:8080/health', timeout=2)
            if response.status_code == 200:
                logger.info(f"✅ Flask ready (attempt {i+1})")
                return
        except:
            pass
        time.sleep(1)
    
    raise RuntimeError("Flask server startup timeout")


def check_nvenc_available() -> bool:
    """檢查 NVENC 是否可用"""
    try:
        result = subprocess.run(
            ['ffmpeg', '-hide_banner', '-encoders'],
            capture_output=True, text=True, timeout=10
        )
        return 'h264_nvenc' in result.stdout
    except:
        return False


GPU_AVAILABLE = None  # 延遲初始化


def auto_replace_encoder(body: dict) -> dict:
    """自動將 CPU 編碼器替換為 GPU 編碼器"""
    global GPU_AVAILABLE
    
    if GPU_AVAILABLE is None:
        GPU_AVAILABLE = check_nvenc_available()
        logger.info(f"🎮 GPU NVENC available: {GPU_AVAILABLE}")
    
    if not GPU_AVAILABLE:
        return body
    
    # 深拷貝避免修改原始數據
    import copy
    body = copy.deepcopy(body)
    
    outputs = body.get('outputs', [])
    for output in outputs:
        options = output.get('options', [])
        for opt in options:
            option_name = opt.get('option', '')
            if option_name in ['-c:v', '-codec:v', '-vcodec']:
                original = opt.get('argument', '')
                if original == 'libx264':
                    opt['argument'] = 'h264_nvenc'
                    logger.info("🎮 Auto-replaced: libx264 → h264_nvenc")
                elif original == 'libx265':
                    opt['argument'] = 'hevc_nvenc'
                    logger.info("🎮 Auto-replaced: libx265 → hevc_nvenc")
    
    # 如果沒有指定編碼器，添加 GPU 編碼器
    has_video_codec = any(
        opt.get('option') in ['-c:v', '-codec:v', '-vcodec']
        for output in outputs
        for opt in output.get('options', [])
    )
    
    if not has_video_codec and outputs:
        outputs[0].setdefault('options', []).extend([
            {'option': '-c:v', 'argument': 'h264_nvenc'},
            {'option': '-preset', 'argument': 'p4'},
            {'option': '-rc', 'argument': 'vbr'},
            {'option': '-cq', 'argument': '23'},
        ])
        logger.info("🎮 Auto-added h264_nvenc encoder options")
    
    return body


def handler(event):
    try:
        start_flask_server()
        
        input_data = event.get('input', {})
        endpoint = input_data.get('endpoint', '/health')
        method = input_data.get('method', 'GET').upper()
        body = input_data.get('body', {})
        
        # 自動替換編碼器為 GPU 版本
        if endpoint == '/v1/ffmpeg/compose' and method == 'POST':
            body = auto_replace_encoder(body)
        
        url = f"http://localhost:8080{endpoint}"
        logger.info(f"📨 {method} {endpoint}")
        
        if method == 'POST':
            response = requests.post(url, json=body, timeout=600)
        else:
            response = requests.get(url, timeout=60)
        
        try:
            response_body = response.json()
        except:
            response_body = response.text
        
        return {'status_code': response.status_code, 'body': response_body}
        
    except Exception as e:
        logger.exception("Handler error")
        return {'error': str(e)}


if __name__ == '__main__':
    logger.info("🎮 RunPod Serverless Handler starting")
    runpod.serverless.start({'handler': handler})