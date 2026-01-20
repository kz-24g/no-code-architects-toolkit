# Copyright (c) 2025 Stephen G. Pope
# ... (License Header) ...

import os
import ffmpeg
import logging
import requests
import subprocess
from services.file_management import download_file
from services.ffmpeg_gpu import ffmpeg_gpu  # 確保有導入這個模組

# Set the default local storage directory
STORAGE_PATH = "/tmp/"

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Define the path to the fonts directory
# [保留原設定]
FONTS_DIR = '/usr/share/fonts/custom'

# Create the FONT_PATHS dictionary by reading the fonts directory
FONT_PATHS = {}
if os.path.exists(FONTS_DIR):
    for font_file in os.listdir(FONTS_DIR):
        if font_file.endswith('.ttf') or font_file.endswith('.TTF'):
            font_name = os.path.splitext(font_file)[0]
            FONT_PATHS[font_name] = os.path.join(FONTS_DIR, font_file)
else:
    logger.warning(f"Fonts directory not found: {FONTS_DIR}")

# Create a list of acceptable font names
ACCEPTABLE_FONTS = list(FONT_PATHS.keys())

# Match font files with fontconfig names
def match_fonts():
    try:
        result = subprocess.run(['fc-list', ':family'], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if result.returncode == 0:
            fontconfig_fonts = result.stdout.split('\n')
            fontconfig_fonts = list(set(fontconfig_fonts))  # Remove duplicates
            matched_fonts = {}
            for font_file in FONT_PATHS.keys():
                for fontconfig_font in fontconfig_fonts:
                    if font_file.lower() in fontconfig_font.lower():
                        matched_fonts[font_file] = fontconfig_font.strip()

            unique_font_names = set()
            for font in matched_fonts.values():
                font_name = font.split(':')[1].strip()
                unique_font_names.add(font_name)
            
            unique_font_names = sorted(list(set(unique_font_names)))
        else:
            logger.error(f"Error matching fonts: {result.stderr}")
    except Exception as e:
        logger.error(f"Exception while matching fonts: {str(e)}")

match_fonts()

def generate_style_line(options):
    """Generate ASS style line from options."""
    style_options = {
        'Name': 'Default',
        'Fontname': options.get('font_name', 'Arial'),
        'Fontsize': options.get('font_size', 12),
        'PrimaryColour': options.get('primary_color', '&H00FFFFFF'),
        'OutlineColour': options.get('outline_color', '&H00000000'),
        'BackColour': options.get('back_color', '&H00000000'),
        'Bold': options.get('bold', 0),
        'Italic': options.get('italic', 0),
        'Underline': options.get('underline', 0),
        'StrikeOut': options.get('strikeout', 0),
        'ScaleX': 100,
        'ScaleY': 100,
        'Spacing': 0,
        'Angle': 0,
        'BorderStyle': 1,
        'Outline': options.get('outline', 1),
        'Shadow': options.get('shadow', 0),
        'Alignment': options.get('alignment', 2),
        'MarginL': options.get('margin_l', 10),
        'MarginR': options.get('margin_r', 10),
        'MarginV': options.get('margin_v', 10),
        'Encoding': options.get('encoding', 1)
    }
    return f"Style: {','.join(str(v) for v in style_options.values())}"

def process_captioning(file_url, caption_srt, caption_type, options, job_id):
    """Process video captioning using FFmpeg with GPU acceleration."""
    try:
        logger.info(f"Job {job_id}: Starting download of file from {file_url}")
        video_path = download_file(file_url, STORAGE_PATH)
        logger.info(f"Job {job_id}: File downloaded to {video_path}")

        subtitle_extension = '.' + caption_type
        srt_path = os.path.join(STORAGE_PATH, f"{job_id}{subtitle_extension}")
        options = convert_array_to_collection(options)
        caption_style = ""

        if caption_type == 'ass':
            style_string = generate_style_line(options)
            caption_style = f"""
[Script Info]
Title: Highlight Current Word
ScriptType: v4.00+
[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
{style_string}
[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
            logger.info(f"Job {job_id}: Generated ASS style string: {style_string}")

        if caption_srt.startswith("https"):
            # Download the file if caption_srt is a URL
            logger.info(f"Job {job_id}: Downloading caption file from {caption_srt}")
            response = requests.get(caption_srt)
            response.raise_for_status()
            if caption_type in ['srt','vtt']:
                with open(srt_path, 'wb') as srt_file:
                    srt_file.write(response.content)
            else:
                subtitle_content = caption_style + response.text
                with open(srt_path, 'w') as srt_file:
                    srt_file.write(subtitle_content)
            logger.info(f"Job {job_id}: Caption file downloaded to {srt_path}")
        else:
            # Write caption_srt content directly to file
            subtitle_content = caption_style + caption_srt
            with open(srt_path, 'w') as srt_file:
                srt_file.write(subtitle_content)
            logger.info(f"Job {job_id}: SRT file created at {srt_path}")

        output_path = os.path.join(STORAGE_PATH, f"{job_id}_captioned.mp4")
        logger.info(f"Job {job_id}: Output path set to {output_path}")

        # Ensure font_name is converted to the full font path
        font_name = options.get('font_name', 'Arial')
        if font_name in FONT_PATHS:
            selected_font = FONT_PATHS[font_name]
            logger.info(f"Job {job_id}: Font path set to {selected_font}")
        else:
            selected_font = FONT_PATHS.get('Arial')
            logger.warning(f"Job {job_id}: Font {font_name} not found. Using default font Arial.")

        # Construct Subtitle Filter String
        if subtitle_extension == '.ass':
            # Use the subtitles filter without force_style
            subtitle_filter = f"subtitles='{srt_path}'"
            logger.info(f"Job {job_id}: Using ASS subtitle filter: {subtitle_filter}")
        else:
            # Construct FFmpeg filter options for subtitles with detailed styling
            subtitle_filter = f"subtitles={srt_path}:force_style='"
            style_options = {
                'FontName': font_name,
                'FontSize': options.get('font_size', 24),
                'PrimaryColour': options.get('primary_color', '&H00FFFFFF'),
                'SecondaryColour': options.get('secondary_color', '&H00000000'),
                'OutlineColour': options.get('outline_color', '&H00000000'),
                'BackColour': options.get('back_color', '&H00000000'),
                'Bold': options.get('bold', 0),
                'Italic': options.get('italic', 0),
                'Underline': options.get('underline', 0),
                'StrikeOut': options.get('strikeout', 0),
                'Alignment': options.get('alignment', 2),
                'MarginV': options.get('margin_v', 10),
                'MarginL': options.get('margin_l', 10),
                'MarginR': options.get('margin_r', 10),
                'Outline': options.get('outline', 1),
                'Shadow': options.get('shadow', 0),
                'Blur': options.get('blur', 0),
                'BorderStyle': options.get('border_style', 1),
                'Encoding': options.get('encoding', 1),
                'Spacing': options.get('spacing', 0),
                'Angle': options.get('angle', 0),
                'UpperCase': options.get('uppercase', 0)
            }
            # Add only populated options to the subtitle filter
            subtitle_filter += ','.join(f"{k}={v}" for k, v in style_options.items() if v is not None)
            subtitle_filter += "'"
            logger.info(f"Job {job_id}: Using subtitle filter: {subtitle_filter}")

        # === GPU Acceleration Block ===
        try:
            # Construct FFmpeg command manually for subprocess
            cmd = [
                'ffmpeg', '-y',
                '-i', video_path,
                '-vf', subtitle_filter
            ]

            # [Key Change] Inject GPU encoding options
            # This uses the NVENC encoder if available
            cmd.extend(ffmpeg_gpu.get_encode_options())

            # Audio handling: Convert to AAC to ensure compatibility
            cmd.extend(['-c:a', 'aac'])

            # Output
            cmd.append(output_path)

            logger.info(f"Job {job_id}: Running GPU FFmpeg command: {' '.join(cmd)}")

            # Execute command
            subprocess.run(
                cmd,
                check=True,
                capture_output=True,
                text=True
            )
            
            logger.info(f"Job {job_id}: FFmpeg processing completed, output file at {output_path}")

        except subprocess.CalledProcessError as e:
            # Log the FFmpeg stderr output
            error_message = e.stderr if e.stderr else str(e)
            logger.error(f"Job {job_id}: FFmpeg error: {error_message}")
            raise e
        except Exception as e:
            logger.error(f"Job {job_id}: Error executing FFmpeg: {str(e)}")
            raise e

        # The upload process will be handled by the calling function
        return output_path

    except Exception as e:
        logger.error(f"Job {job_id}: Error in process_captioning: {str(e)}")
        # Clean up in case of error
        if 'video_path' in locals() and os.path.exists(video_path): os.remove(video_path)
        if 'srt_path' in locals() and os.path.exists(srt_path): os.remove(srt_path)
        raise

    finally:
        # Clean up local files
        if 'video_path' in locals() and os.path.exists(video_path): os.remove(video_path)
        if 'srt_path' in locals() and os.path.exists(srt_path): os.remove(srt_path)
        if 'output_path' in locals() and os.path.exists(output_path): os.remove(output_path)
        logger.info(f"Job {job_id}: Local files cleanup attempted")

def convert_array_to_collection(options):
    logger.info(f"Converting options array to dictionary: {options}")
    return {item["option"]: item["value"] for item in options}