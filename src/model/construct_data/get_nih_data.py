import os
import kagglehub

# Download NIH dataset to the default Kaggle cache (no duplication)
NIH_POINTER = "data_hybrid/nih_images"

print("Downloading NIH Chest X-ray dataset from Kaggle (skips if cached)...")
cache_path = kagglehub.dataset_download("nih-chest-xrays/data")

# Save the actual path so blend_data.py can find it
os.makedirs(NIH_POINTER, exist_ok=True)
path_file = os.path.join(NIH_POINTER, "path.txt")
with open(path_file, "w") as f:
    f.write(cache_path)

print(f"NIH dataset cached at: {cache_path}")
print(f"Path saved to: {path_file}")
