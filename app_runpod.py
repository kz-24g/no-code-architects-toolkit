"""
NCA Toolkit - RunPod GPU 版本入口
"""

import os
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 初始化 GPU 模組
from services.ffmpeg_gpu import ffmpeg_gpu

logger.info("=" * 50)
logger.info("🚀 NCA Toolkit - RunPod GPU Edition")
logger.info(f"🎮 GPU Available: {ffmpeg_gpu.gpu_available}")
logger.info(f"🎬 Encoder: {ffmpeg_gpu.encoder}")
logger.info("=" * 50)

# 導入原有 Flask app
from app import app

# 註冊健康檢查
from health import health_bp
app.register_blueprint(health_bp)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    logger.info(f"🌐 Server starting on http://0.0.0.0:{port}")
    app.run(host='0.0.0.0', port=port, debug=False, threaded=True)