from flask import Blueprint
from app_utils import validate_payload, queue_task_wrapper
import logging
from services.v1.image.slice_grid import process_slice_grid
from services.authentication import authenticate
from services.cloud_storage import upload_file

v1_image_slice_bp = Blueprint('v1_image_slice', __name__)
logger = logging.getLogger(__name__)


@v1_image_slice_bp.route('/v1/image/slice', methods=['POST'])
@authenticate
@validate_payload({
    "type": "object",
    "properties": {
        "image_url": {"type": "string", "format": "uri"},
        "rows": {"type": ["integer", "string"], "minimum": 1, "maximum": 10},
        "cols": {"type": ["integer", "string"], "minimum": 1, "maximum": 10},
        "total_count": {"type": ["integer", "string"], "minimum": 1, "maximum": 100},
        "aspect_ratio": {"type": "string", "pattern": "^[0-9]+:[0-9]+$"},
        "webhook_url": {"type": "string", "format": "uri"},
        "id": {"type": "string"}
    },
    "required": ["image_url", "rows", "cols", "total_count"],
    "additionalProperties": False
})
@queue_task_wrapper(bypass_queue=False)
def slice_image(job_id, data):
    image_url = data.get('image_url')
    rows = int(data.get('rows'))
    cols = int(data.get('cols'))
    total_count = int(data.get('total_count'))
    aspect_ratio = data.get('aspect_ratio')  # e.g. "9:16" or "16:9"

    logger.info(f"Job {job_id}: Slice grid request – {rows}x{cols} grid, outputting {total_count} cells, aspect_ratio={aspect_ratio}")

    try:
        # Slice the grid image into individual cells
        cell_paths = process_slice_grid(image_url, rows, cols, total_count, job_id, aspect_ratio=aspect_ratio)

        # Upload each cell and collect URLs
        output_urls = []
        for path in cell_paths:
            url = upload_file(path)
            output_urls.append(url)
            logger.info(f"Job {job_id}: Uploaded cell → {url}")

        logger.info(f"Job {job_id}: All {len(output_urls)} cells uploaded successfully")

        return output_urls, "/v1/image/slice", 200

    except Exception as e:
        logger.error(f"Job {job_id}: Error slicing grid image: {str(e)}", exc_info=True)
        return str(e), "/v1/image/slice", 500
