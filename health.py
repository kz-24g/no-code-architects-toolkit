"""
健康檢查端點
"""

import subprocess
from flask import Blueprint, jsonify
from services.ffmpeg_gpu import get_encoder_info

health_bp = Blueprint('health', __name__)

@health_bp.route('/health', methods=['GET'])
def health_check():
    info = get_encoder_info()
    return jsonify({
        'status': 'healthy',
        'gpu_available': info['gpu_available'],
        'encoder': info['encoder'],
        'version': '1.0.0-runpod'
    })

@health_bp.route('/gpu-info', methods=['GET'])
def gpu_info():
    try:
        result = subprocess.run(
            ['nvidia-smi', '--query-gpu=name,memory.total,memory.used,utilization.gpu',
             '--format=csv,noheader,nounits'],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0:
            parts = result.stdout.strip().split(', ')
            return jsonify({
                'available': True,
                'name': parts[0] if len(parts) > 0 else 'Unknown',
                'memory_total_mb': int(parts[1]) if len(parts) > 1 else 0,
                'memory_used_mb': int(parts[2]) if len(parts) > 2 else 0,
                'utilization_percent': int(parts[3]) if len(parts) > 3 else 0,
            })
        return jsonify({'available': False, 'error': result.stderr})
    except Exception as e:
        return jsonify({'available': False, 'error': str(e)})