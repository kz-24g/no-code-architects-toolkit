import os
import uuid
import logging
import numpy as np
from PIL import Image
from services.file_management import download_file
from config import LOCAL_STORAGE_PATH

logger = logging.getLogger(__name__)

# --- Border detection constants ---
# Pixels with brightness (grayscale) below this value are considered "dark" / border
DARK_THRESHOLD = 40
# A row or column is classified as border if this fraction of its pixels are dark
DARK_RATIO = 0.85
# Safety limit: never trim more than this fraction of the cell from any single edge
MAX_TRIM_FRACTION = 0.25


def _is_border_line(gray_arr, axis, index, threshold=DARK_THRESHOLD, ratio=DARK_RATIO):
    """Check if a row (axis=0) or column (axis=1) is a dark border line.

    Args:
        gray_arr: 2-D numpy array (grayscale, uint8).
        axis: 0 → test row ``index``; 1 → test column ``index``.
        index: Row or column index to test.
        threshold: Max brightness for a pixel to count as dark.
        ratio: Min fraction of dark pixels to classify the line as border.

    Returns:
        True if the line qualifies as a border line.
    """
    if axis == 0:
        line = gray_arr[index, :]
    else:
        line = gray_arr[:, index]
    dark_pixels = np.sum(line < threshold)
    return (dark_pixels / len(line)) >= ratio


def _trim_borders(cell_img):
    """Detect and remove dark (black) borders from all four edges of a cell image.

    Uses a grayscale projection to find contiguous dark rows/columns from each edge
    and crops them away, respecting MAX_TRIM_FRACTION to avoid over-trimming.

    Args:
        cell_img: PIL.Image of a single grid cell.

    Returns:
        PIL.Image with borders removed.
    """
    gray = np.array(cell_img.convert("L"))
    h, w = gray.shape

    max_top = int(h * MAX_TRIM_FRACTION)
    max_bottom = int(h * MAX_TRIM_FRACTION)
    max_left = int(w * MAX_TRIM_FRACTION)
    max_right = int(w * MAX_TRIM_FRACTION)

    # Scan from top
    top = 0
    while top < max_top and _is_border_line(gray, axis=0, index=top):
        top += 1

    # Scan from bottom
    bottom = h
    while (h - bottom) < max_bottom and bottom > top and _is_border_line(gray, axis=0, index=bottom - 1):
        bottom -= 1

    # Scan from left
    left = 0
    while left < max_left and _is_border_line(gray, axis=1, index=left):
        left += 1

    # Scan from right
    right = w
    while (w - right) < max_right and right > left and _is_border_line(gray, axis=1, index=right - 1):
        right -= 1

    if top == 0 and bottom == h and left == 0 and right == w:
        return cell_img  # no border detected

    logger.debug(f"Trimmed borders: top={top}, bottom={h - bottom}, left={left}, right={w - right}")
    return cell_img.crop((left, top, right, bottom))


def _parse_aspect_ratio(aspect_ratio_str):
    """Parse an aspect ratio string like '9:16' into (w, h) integers.

    Returns:
        tuple[int, int] or None if not provided / invalid.
    """
    if not aspect_ratio_str:
        return None
    try:
        parts = str(aspect_ratio_str).split(':')
        if len(parts) == 2:
            return int(parts[0]), int(parts[1])
    except (ValueError, TypeError):
        pass
    return None


def _resize_to_aspect(cell_img, aspect_wh):
    """Resize a cell image so it exactly matches the target aspect ratio.

    The image is scaled to fill the target aspect ratio (using the larger
    dimension as anchor) and then center-cropped to the exact ratio, so
    no content is stretched — only a tiny amount may be cropped if the
    trimmed cell is slightly off-ratio.

    Args:
        cell_img: PIL.Image after border trimming.
        aspect_wh: (aspect_w, aspect_h) e.g. (9, 16).

    Returns:
        PIL.Image resized to the exact aspect ratio.
    """
    aw, ah = aspect_wh
    cw, ch = cell_img.size

    target_ratio = aw / ah  # e.g. 9/16 = 0.5625
    current_ratio = cw / ch

    if abs(current_ratio - target_ratio) < 0.005:
        return cell_img  # already close enough

    # Determine crop box to match target ratio (center crop)
    if current_ratio > target_ratio:
        # too wide → crop width
        new_w = int(ch * target_ratio)
        offset = (cw - new_w) // 2
        cell_img = cell_img.crop((offset, 0, offset + new_w, ch))
    else:
        # too tall → crop height
        new_h = int(cw / target_ratio)
        offset = (ch - new_h) // 2
        cell_img = cell_img.crop((0, offset, cw, offset + new_h))

    return cell_img


def process_slice_grid(image_url, rows, cols, total_count, job_id, aspect_ratio=None):
    """Download a grid image, slice it into rows×cols cells, trim black borders,
    and save each cell to disk.

    Args:
        image_url (str): Public URL of the grid image.
        rows (int): Number of rows in the grid.
        cols (int): Number of columns in the grid.
        total_count (int): How many cells to output (1-based, left→right, top→bottom).
        job_id (str): Unique job identifier.
        aspect_ratio (str, optional): Target aspect ratio e.g. '9:16'. If provided,
            each cell is adjusted to this ratio after border trimming.

    Returns:
        list[str]: List of local file paths for the sliced cell images.
    """
    aspect_wh = _parse_aspect_ratio(aspect_ratio)
    max_cells = rows * cols
    if total_count > max_cells:
        total_count = max_cells

    # Download source image
    image_path = download_file(image_url, LOCAL_STORAGE_PATH)
    logger.info(f"Job {job_id}: Downloaded grid image to {image_path}")

    img = Image.open(image_path).convert("RGB")
    img_w, img_h = img.size
    logger.info(f"Job {job_id}: Grid image size {img_w}x{img_h}, grid {rows}x{cols}, outputting {total_count} cells")

    cell_w = img_w / cols
    cell_h = img_h / rows

    output_paths = []
    count = 0
    for r in range(rows):
        for c in range(cols):
            if count >= total_count:
                break

            # Crop the cell region (use float boundaries, round to int)
            x1 = round(c * cell_w)
            y1 = round(r * cell_h)
            x2 = round((c + 1) * cell_w)
            y2 = round((r + 1) * cell_h)
            cell = img.crop((x1, y1, x2, y2))

            # Trim black borders
            cell = _trim_borders(cell)

            # Restore target aspect ratio if specified
            if aspect_wh:
                cell = _resize_to_aspect(cell, aspect_wh)

            # Save
            out_name = f"{job_id}_cell_{count + 1}.png"
            out_path = os.path.join(LOCAL_STORAGE_PATH, out_name)
            cell.save(out_path, format="PNG")
            output_paths.append(out_path)
            logger.info(f"Job {job_id}: Saved cell {count + 1} → {out_path} (size {cell.size})")

            count += 1
        if count >= total_count:
            break

    # Clean up source file
    try:
        os.remove(image_path)
    except OSError:
        pass

    return output_paths
