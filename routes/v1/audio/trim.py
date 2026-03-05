from flask import Blueprint
from app_utils import *
import logging
from services.v1.audio.trim import trim_audio
from services.authentication import authenticate
from services.cloud_storage import upload_file

v1_audio_trim_bp = Blueprint('v1_audio_trim', __name__)
logger = logging.getLogger(__name__)


@v1_audio_trim_bp.route('/v1/audio/trim', methods=['POST'])
@authenticate
@validate_payload({
    "type": "object",
    "properties": {
        "audio_url": {"type": "string", "format": "uri"},
        "start": {"type": "string"},
        "end": {"type": "string"},
        "audio_codec": {"type": "string"},
        "audio_bitrate": {"type": "string"},
        "webhook_url": {"type": "string", "format": "uri"},
        "id": {"type": "string"}
    },
    "required": ["audio_url"],
    "additionalProperties": False
})
@queue_task_wrapper(bypass_queue=False)
def audio_trim(job_id, data):
    """Trim an audio file to the segment between start and end timestamps."""
    audio_url = data['audio_url']
    start = data.get('start')
    end = data.get('end')
    audio_codec = data.get('audio_codec', 'copy')
    audio_bitrate = data.get('audio_bitrate', '128k')

    logger.info(f"Job {job_id}: Received audio trim request for {audio_url}")

    try:
        output_file = trim_audio(
            audio_url=audio_url,
            start=start,
            end=end,
            job_id=job_id,
            audio_codec=audio_codec,
            audio_bitrate=audio_bitrate
        )
        logger.info(f"Job {job_id}: Audio trim completed successfully")

        cloud_url = upload_file(output_file)
        logger.info(f"Job {job_id}: Trimmed audio uploaded to {cloud_url}")

        return cloud_url, "/v1/audio/trim", 200

    except Exception as e:
        logger.error(f"Job {job_id}: Error during audio trim - {str(e)}")
        return str(e), "/v1/audio/trim", 500
