import os
from PIL import Image
import numpy as np

# === Configuration ===
input_folder = "../Photos/Headshots/png/"      # folder with originals
output_folder = "../Photos/Headshots/www/"        # where processed images will be saved
target_height = 800                # resize target height in pixels (adjust as needed)
blank_threshold = 250              # 0–255: higher = more tolerant to light backgrounds
side_crop_margin = 20              # pixels to trim from left/right if almost blank
    
os.makedirs(output_folder, exist_ok=True)

def auto_crop_top_and_sides(image: Image.Image, blank_threshold=250, side_margin=20):
    """Automatically crops top and sides with mostly blank space, keeps bottom intact."""
    # Convert to grayscale for brightness analysis
    gray = image.convert("L")
    arr = np.array(gray)

    # --- Detect top boundary ---
    # Find first row from top with any non-blank pixel
    mask = arr < blank_threshold
    non_blank_rows = np.where(mask.any(axis=1))[0]
    top = non_blank_rows[0] if len(non_blank_rows) > 0 else 0

    # --- Detect side boundaries ---
    non_blank_cols = np.where(mask.any(axis=0))[0]
    left = max(0, non_blank_cols[0] - side_margin) if len(non_blank_cols) > 0 else 0
    right = min(image.width, non_blank_cols[-1] + side_margin) if len(non_blank_cols) > 0 else image.width

    # --- Keep bottom unchanged ---
    bottom = image.height

    # Crop and return
    return image.crop((left, top, right, bottom))

def process_image(input_path, output_path, remove_bg=False):
    img = Image.open(input_path).convert("RGBA")
    arr = np.array(img)

    # Remove background (if requested)
    if remove_bg:
        
        # Create alpha mask: pixels lighter than threshold become transparent
        r, g, b, a = np.rollaxis(arr, axis=-1)
        mask = (r > blank_threshold) & (g > blank_threshold) & (b > blank_threshold)
        arr[mask, 3] = 0  # make light areas transparent

        img = Image.fromarray(arr, mode="RGBA")

    # Crop top/sides based on content (like before)
    cropped = auto_crop_top_and_sides(img, blank_threshold, side_crop_margin)

    # Resize and save
    if cropped.height > target_height:
        scale = target_height / cropped.height
        new_size = (int(cropped.width * scale), target_height)
        resized = cropped.resize(new_size, Image.LANCZOS)
    else:
        resized = cropped

    resized.save(output_path, "PNG", optimize=True)
    print(f"Processed (bg removed): {os.path.basename(input_path)}")


# === Batch process ===
for filename in os.listdir(input_folder):
    if filename.lower().endswith(".png"):
        input_path = os.path.join(input_folder, filename)
        output_path = os.path.join(output_folder, filename)
        process_image(input_path, output_path)

print("✅ Batch processing complete!")
