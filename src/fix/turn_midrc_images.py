import os
from PIL import Image
from tqdm import tqdm

def rotate_images(input_folder, output_folder, rotation_angle=90):
    """
    Reads all images in input_folder, rotates them by rotation_angle,
    and saves them into output_folder.
    
    rotation_angle options: 
    90  -> Counter-clockwise
    180 -> Upside down
    270 -> Clockwise (often what's needed for sideways camera inputs)
    """
    # Create output directory if it doesn't exist
    os.makedirs(output_folder, exist_ok=True)
    
    # Supported extensions
    valid_extensions = ('.png', '.jpg', '.jpeg', '.png', '.PNG', '.JPG')
    
    # Get all image files
    image_files = [f for f in os.listdir(input_folder) if f.endswith(valid_extensions)]
    
    if not image_files:
        print(f"No images found in {input_folder}!")
        return

    print(f"🔄 Rotating {len(image_files)} images by {rotation_angle} degrees...")
    
    # Process with a progress bar
    for file_name in tqdm(image_files):
        input_path = os.path.join(input_folder, file_name)
        output_path = os.path.join(output_folder, file_name)
        
        try:
            with Image.open(input_path) as img:
                # Rotate the image. 
                # Image.ROTATE_90, Image.ROTATE_180, Image.ROTATE_270
                # Using the integer directly works smoothly in modern Pillow:
                if rotation_angle == 90:
                    rotated_img = img.transpose(Image.ROTATE_90)
                elif rotation_angle == 180:
                    rotated_img = img.transpose(Image.ROTATE_180)
                elif rotation_angle == 270:
                    rotated_img = img.transpose(Image.ROTATE_270)
                else:
                    # Fallback for arbitrary rotation (preserves original dimensions)
                    rotated_img = img.rotate(rotation_angle, expand=True)
                
                # Save the corrected image
                rotated_img.save(output_path)
                
        except Exception as e:
            print(f"Error processing {file_name}: {e}")

    print(f"Finished! All rotated images are saved in: {output_folder}")

if __name__ == '__main__':
    # ─── CONFIGURATION ──────────────────────────────────────────────────
    # Change these paths to match your actual dataset directories!
    SOURCE_DIR = "data_hybrid/midrc_images"
    TARGET_DIR = "data_hybrid/midrc_rotated_images"
    
    # Try 90 or 270 depending on which way they are turned sideways
    ANGLE = 270 
    # ────────────────────────────────────────────────────────────────────

    rotate_images(SOURCE_DIR, TARGET_DIR, rotation_angle=ANGLE)