import os
import subprocess
import logging
import uuid
from services.file_management import download_file
from config import LOCAL_STORAGE_PATH

logger = logging.getLogger(__name__)


def time_to_seconds(time_str):
    """Convert HH:MM:SS[.mmm] or plain seconds string to float seconds."""
    if not time_str:
        return None
    try:
        parts = time_str.split(':')
        if len(parts) == 3:
            h, m, s = parts
            return int(h) * 3600 + int(m) * 60 + float(s)
        elif len(parts) == 2:
            m, s = parts
            return int(m) * 60 + float(s)
        else:
            return float(time_str)
    except ValueError:
        raise ValueError(f"Invalid time format: {time_str}. Expected HH:MM:SS[.mmm] or seconds.")


def trim_audio(audio_url, start=None, end=None, duration=None, job_id=None, audio_codec='copy', audio_bitrate='128k'):
    """
    Trim an audio file to the segment between start and end (or start + duration).

    Args:
        audio_url (str): URL of the audio file to trim.
        start (str, optional): Start timestamp (keep audio from here). Default: beginning.
        end (str, optional): End timestamp (keep audio until here). Mutually exclusive with duration.
        duration (float, optional): Duration in seconds to keep from start. Mutually exclusive with end.
        job_id (str, optional): Unique job identifier.
        audio_codec (str, optional): Audio codec for re-encoding (default: 'copy' = no re-encode).
        audio_bitrate (str, optional): Audio bitrate used when re-encoding (default: '128k').

    Returns:
        str: Path to the trimmed output file.
    """
    if not job_id:
        job_id = str(uuid.uuid4())

    input_filename = download_file(audio_url, os.path.join(LOCAL_STORAGE_PATH, f"{job_id}_input"))
    logger.info(f"Job {job_id}: Downloaded audio to {input_filename}")

    try:
        _, ext = os.path.splitext(input_filename)
        output_filename = os.path.join(LOCAL_STORAGE_PATH, f"{job_id}_output{ext}")

        # Probe duration
        probe_cmd = [
            'ffprobe', '-v', 'error',
            '-show_entries', 'format=duration',
            '-of', 'default=noprint_wrappers=1:nokey=1',
            input_filename
        ]
        probe_result = subprocess.run(probe_cmd, capture_output=True, text=True)
        try:
            file_duration = float(probe_result.stdout.strip())
        except (ValueError, AttributeError):
            logger.warning(f"Job {job_id}: Could not determine duration, using 24h fallback")
            file_duration = 86400

        start_seconds = time_to_seconds(start) if start else 0

        if duration is not None:
            trim_duration = float(duration)
        elif end is not None:
            end_seconds = time_to_seconds(end)
            if end_seconds > file_duration:
                end_seconds = file_duration
            trim_duration = end_seconds - start_seconds
        else:
            trim_duration = file_duration - start_seconds

        if start_seconds < 0:
            start_seconds = 0
        if trim_duration <= 0:
            raise ValueError(f"Computed trim duration is <= 0. Check start/end/duration values.")

        cmd = ['ffmpeg', '-y']

        if start_seconds > 0:
            cmd.extend(['-ss', str(start_seconds)])

        cmd.extend(['-i', input_filename])

        cmd.extend(['-t', str(trim_duration)])

        if audio_codec == 'copy':
            cmd.extend(['-c:a', 'copy'])
        else:
            cmd.extend(['-c:a', audio_codec, '-b:a', audio_bitrate])

        cmd.extend(['-vn', output_filename])

        logger.info(f"Job {job_id}: Running FFmpeg: {' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode != 0:
            raise RuntimeError(f"FFmpeg error: {result.stderr}")

        if not os.path.exists(output_filename):
            raise FileNotFoundError(f"Output file not created: {output_filename}")

        return output_filename

    finally:
        if os.path.exists(input_filename):
            os.remove(input_filename)
