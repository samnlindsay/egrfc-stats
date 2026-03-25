from __future__ import annotations

import argparse
from pathlib import Path

import cv2
from PIL import Image


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_INPUT_DIR = PROJECT_ROOT / "img" / "headshots"
FACE_CASCADE = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_alt2.xml")


def build_content_mask(image: Image.Image, alpha_threshold: int, blank_threshold: int) -> Image.Image:
    rgba_image = image.convert("RGBA")
    alpha = rgba_image.getchannel("A")

    if alpha.getbbox():
        return alpha.point(lambda value: 255 if value > alpha_threshold else 0)

    rgb_image = rgba_image.convert("RGB")
    grayscale = rgb_image.convert("L")
    return grayscale.point(lambda value: 0 if value >= blank_threshold else 255)


def detect_face_bounds(image_path: Path, alpha_threshold: int) -> tuple[int, int, int, int] | None:
    image = cv2.imread(str(image_path), cv2.IMREAD_UNCHANGED)
    if image is None:
        return None

    if image.ndim == 3 and image.shape[2] == 4:
        alpha = image[:, :, 3]
        grayscale = cv2.cvtColor(image[:, :, :3], cv2.COLOR_BGR2GRAY)
        grayscale[alpha <= alpha_threshold] = 255
    else:
        grayscale = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    faces = FACE_CASCADE.detectMultiScale(
        grayscale,
        scaleFactor=1.05,
        minNeighbors=5,
        minSize=(40, 40),
    )
    if len(faces) == 0:
        return None

    x, y, width, height = max(faces, key=lambda rect: rect[2] * rect[3])
    return int(x), int(y), int(width), int(height)


def face_centered_crop_box(
    image: Image.Image,
    face_bounds: tuple[int, int, int, int],
    *,
    crop_scale: float,
    top_padding_ratio: float,
) -> tuple[int, int, int, int] | None:
    face_x, face_y, face_width, face_height = face_bounds
    crop_size = int(round(max(face_width, face_height) * crop_scale))
    crop_size = max(1, min(crop_size, image.width, image.height))

    center_x = face_x + face_width / 2
    left = int(round(center_x - crop_size / 2))
    top = int(round(face_y - face_height * top_padding_ratio))

    left = min(max(0, left), max(0, image.width - crop_size))
    top = min(max(0, top), max(0, image.height - crop_size))

    return left, top, left + crop_size, top + crop_size


def square_crop_box(
    image: Image.Image,
    *,
    image_path: Path | None,
    use_face_crop: bool,
    alpha_threshold: int,
    blank_threshold: int,
    side_margin: int,
    top_margin: int,
    face_crop_scale: float,
    face_top_padding_ratio: float,
) -> tuple[int, int, int, int] | None:
    if use_face_crop and image_path is not None:
        face_bounds = detect_face_bounds(image_path, alpha_threshold)
        if face_bounds is not None:
            face_crop = face_centered_crop_box(
                image,
                face_bounds,
                crop_scale=face_crop_scale,
                top_padding_ratio=face_top_padding_ratio,
            )
            if face_crop is not None:
                return face_crop

    mask = build_content_mask(image, alpha_threshold=alpha_threshold, blank_threshold=blank_threshold)
    bbox = mask.getbbox()
    if bbox is None:
        return None

    left, top, right, _bottom = bbox
    left = max(0, left - side_margin)
    right = min(image.width, right + side_margin)
    top = max(0, top - top_margin)

    crop_width = right - left
    if crop_width <= 0:
        return None

    bottom = min(image.height, top + crop_width)

    # Fallback for unexpectedly short images.
    if bottom - top < crop_width:
        top = max(0, image.height - crop_width)
        bottom = image.height

    return left, top, right, bottom


def process_image(
    input_path: Path,
    output_path: Path,
    *,
    use_face_crop: bool,
    alpha_threshold: int,
    blank_threshold: int,
    side_margin: int,
    top_margin: int,
    face_crop_scale: float,
    face_top_padding_ratio: float,
) -> None:
    with Image.open(input_path) as image:
        crop_box = square_crop_box(
            image,
            image_path=input_path,
            use_face_crop=use_face_crop,
            alpha_threshold=alpha_threshold,
            blank_threshold=blank_threshold,
            side_margin=side_margin,
            top_margin=top_margin,
            face_crop_scale=face_crop_scale,
            face_top_padding_ratio=face_top_padding_ratio,
        )

        if crop_box is None:
            cropped = image.copy()
        else:
            cropped = image.crop(crop_box)

        output_path.parent.mkdir(parents=True, exist_ok=True)
        cropped.save(output_path, format="PNG", optimize=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Trim empty space from headshots and crop to a square by trimming the bottom."
    )
    parser.add_argument(
        "--use-face-crop",
        action="store_true",
        help="Use face-centered square crops (may crop top/sides). Disabled by default.",
    )
    parser.add_argument(
        "--input-dir",
        type=Path,
        default=DEFAULT_INPUT_DIR,
        help="Directory containing source headshots.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Directory for processed headshots. Defaults to in-place overwrite in the input directory.",
    )
    parser.add_argument(
        "--alpha-threshold",
        type=int,
        default=8,
        help="Minimum alpha treated as visible content.",
    )
    parser.add_argument(
        "--blank-threshold",
        type=int,
        default=245,
        help="Brightness threshold for non-transparent backgrounds.",
    )
    parser.add_argument(
        "--side-margin",
        type=int,
        default=12,
        help="Extra pixels to preserve on the left and right after trimming.",
    )
    parser.add_argument(
        "--top-margin",
        type=int,
        default=0,
        help="Extra pixels to preserve above the detected content.",
    )
    parser.add_argument(
        "--face-crop-scale",
        type=float,
        default=2.15,
        help="Square crop size as a multiple of detected face size for head-and-shoulders framing.",
    )
    parser.add_argument(
        "--face-top-padding-ratio",
        type=float,
        default=0.22,
        help="Extra padding above the detected face, expressed as a multiple of face height.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    input_dir = args.input_dir.resolve()
    output_dir = args.output_dir.resolve() if args.output_dir else input_dir

    if not input_dir.exists():
        raise FileNotFoundError(f"Input directory does not exist: {input_dir}")

    image_paths = sorted(
        path for path in input_dir.iterdir() if path.is_file() and path.suffix.lower() in {".png", ".jpg", ".jpeg"}
    )

    if not image_paths:
        print(f"No headshot images found in {input_dir}")
        return

    processed_count = 0
    for input_path in image_paths:
        output_name = input_path.with_suffix(".png").name
        output_path = output_dir / output_name
        process_image(
            input_path,
            output_path,
            use_face_crop=args.use_face_crop,
            alpha_threshold=args.alpha_threshold,
            blank_threshold=args.blank_threshold,
            side_margin=args.side_margin,
            top_margin=args.top_margin,
            face_crop_scale=args.face_crop_scale,
            face_top_padding_ratio=args.face_top_padding_ratio,
        )
        processed_count += 1
        print(f"Processed {input_path.name} -> {output_name}")

    print(f"Completed square crops for {processed_count} headshots in {output_dir}")


if __name__ == "__main__":
    main()