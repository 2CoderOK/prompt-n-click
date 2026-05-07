from rembg import remove
from PIL import Image
import numpy as np


def despill_green(data):
    """
    Removes green edge-spill from an RGBA numpy array.
    This works by comparing the Green channel to the Red and Blue channels.
    """
    # Separate channels
    r = data[:, :, 0].astype(int)
    g = data[:, :, 1].astype(int)
    b = data[:, :, 2].astype(int)

    # Calculate the maximum of Red or Blue for each pixel
    max_rb = np.maximum(r, b)

    # If Green is greater than the max of Red and Blue, it is color spill.
    # We cap the Green channel at the max_rb value.
    spill_mask = g > max_rb

    # Apply the cap only to the RGB channels (ignoring alpha channel 3)
    data[:, :, 1][spill_mask] = max_rb[spill_mask]

    return data


def despill_magenta(data):
    """
    Removes magenta (pink) edge-spill.
    Magenta is high Red + high Blue. We cap them based on Green.
    """
    g = data[:, :, 1].astype(int)

    # If Red is higher than Green, cap it
    r_spill = data[:, :, 0] > g
    data[:, :, 0][r_spill] = g[r_spill]

    # If Blue is higher than Green, cap it
    b_spill = data[:, :, 2] > g
    data[:, :, 2][b_spill] = g[b_spill]

    return data


def clean_asset(input_path, output_path, bg_color="green"):
    input_image = Image.open(input_path).convert("RGBA")
    output = remove(input_image)

    data = np.array(output)

    # 1. Apply VFX Despill based on the background color
    if bg_color == "green":
        data = despill_green(data)
    elif bg_color == "magenta":
        data = despill_magenta(data)

    # 2. Aggressively clip semi-transparent shadow remnants
    mask = data[:, :, 3] < 150
    data[mask] = [0, 0, 0, 0]

    final_img = Image.fromarray(data)

    # 3. AUTO-CROP to the bounding box of visible pixels
    bbox = final_img.getbbox()
    if bbox:
        # bbox returns a tuple (left, upper, right, lower)
        final_img = final_img.crop(bbox)

    final_img.save(output_path, "PNG")
