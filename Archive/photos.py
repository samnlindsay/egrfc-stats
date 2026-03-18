import cv2
import os
from PIL import Image

# Input and output directories
input_folder = "/Users/samlindsay/Documents/Projects/Personal/egrfc-stats/img/old_headshots/"
output_folder = "img/headshots/"
output_size = 400  # Change to 200 if needed

# Load OpenCV's pre-trained face detection model
face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_alt2.xml")

# Ensure output folder exists
os.makedirs(output_folder, exist_ok=True)

def detect_face(image_path):
    """Detects the largest face in the image and returns its bounding box (x, y, w, h)."""
    img = cv2.imread(image_path)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    
    faces = face_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(50, 50))

    if len(faces) == 0:
        return None  # No face detected

    # Return the largest face detected
    return max(faces, key=lambda rect: rect[2] * rect[3])

def smart_crop_and_resize(image_path, output_path, output_size=400):
    """Crops image to a square based on face position and resizes it."""
    img = Image.open(image_path)
    img_cv = cv2.imread(image_path)  # Load for face detection
    face = detect_face(image_path)

    if face is not None:
        x, y, w, h = face
        center_x, center_y = x + w // 2, y + (2*h) // 2
    else:
        # No face detected, fallback to center crop
        center_x, center_y = img.width // 2, img.height // 2

    # Determine square crop dimensions
    min_side = min(img.width, img.height)
    crop_x1 = max(0, center_x - min_side // 2)
    crop_y1 = max(0, center_y - int(min_side * 0.55))  # Shift up slightly
    crop_x2 = crop_x1 + min_side
    crop_y2 = crop_y1 + min_side

    # Ensure crop is within image bounds
    crop_x2 = min(crop_x2, img.width)
    crop_y2 = min(crop_y2, img.height)

    # Perform cropping and resizing
    img_cropped = img.crop((crop_x1, crop_y1, crop_x2, crop_y2))
    img_resized = img_cropped.resize((output_size, output_size), Image.LANCZOS)

    # Save the processed image
    img_resized.save(output_path, "PNG")
    print(f"Processed: {os.path.basename(image_path)}")

# Process all PNG images in the folder
for filename in os.listdir(input_folder):
    if filename.lower().endswith(".png") or filename.lower().endswith(".jpg"):
        input_path = os.path.join(input_folder, filename)
        if filename.lower().endswith(".jpg"):
            filename = filename.replace(".jpg", ".png")
        output_path = os.path.join(output_folder, filename)
        smart_crop_and_resize(input_path, output_path, output_size)

print("Batch processing complete!")
