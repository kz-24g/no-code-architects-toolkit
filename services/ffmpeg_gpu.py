"""
FFmpeg GPU 編碼輔助模組
"""

import subprocess
import logging

logger = logging.getLogger(__name__)

class FFmpegGPU:
    def __init__(self):
        self.gpu_available = self._check_nvenc()
        self.encoder = 'h264_nvenc' if self.gpu_available else 'libx264'
        logger.info(f"🎮 GPU={self.gpu_available}, Encoder={self.encoder}")
    
    def _check_nvenc(self) -> bool:
        try:
            result = subprocess.run(
                ['ffmpeg', '-hide_banner', '-encoders'],
                capture_output=True, text=True, timeout=10
            )
            return 'h264_nvenc' in result.stdout
        except Exception as e:
            logger.warning(f"NVENC check failed: {e}")
            return False
    
    def get_encode_options(self, preset='p4', cq=23) -> list:
        if self.gpu_available:
            return [
                '-c:v', 'h264_nvenc',
                '-preset', preset,
                '-rc', 'vbr',
                '-cq', str(cq),
                '-pix_fmt', 'yuv420p',
            ]
        else:
            return [
                '-c:v', 'libx264',
                '-preset', 'fast',
                '-crf', str(cq),
                '-pix_fmt', 'yuv420p',
            ]

ffmpeg_gpu = FFmpegGPU()

def get_encoder_info() -> dict:
    return {
        'gpu_available': ffmpeg_gpu.gpu_available,
        'encoder': ffmpeg_gpu.encoder,
    }