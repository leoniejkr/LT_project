import os
import torch
import pandas as pd
from torch.utils.data import Dataset
from PIL import Image

class HybridChestDataset(Dataset):
    def __init__(self, nih_df, midrc_df, nih_img_dir, midrc_img_dir, transform=None):
        """
        nih_df: Pandas DataFrame of NIH data with one-hot columns
        midrc_df: Pandas DataFrame of MIDRC CXR data (just your COVID cases)
        """
        self.nih_df = nih_df
        self.midrc_df = midrc_df
        self.nih_img_dir = nih_img_dir
        self.midrc_img_dir = midrc_img_dir
        self.transform = transform
        
        # Define a joint classification head 
        self.classes = [
            'Atelectasis', 'Cardiomegaly', 'Consolidation', 'Edema', 'Effusion', 
            'Emphysema', 'Fibrosis', 'Hernia', 'Infiltration', 'Mass', 'Nodule', 
            'Pleural_Thickening', 'Pneumonia', 'Pneumothorax', 'Covid'
        ]

    def __len__(self):
        return len(self.nih_df) + len(self.midrc_df)

    def __getitem__(self, idx):
        # Determine if this index points to NIH or MIDRC portion
        if idx < len(self.nih_df):
            # --- Handle NIH Sample ---
            row = self.nih_df.iloc[idx]
            img_path = os.path.join(self.nih_img_dir, row['Image Index'])
            image = Image.open(img_path).convert('RGB')
            
            # Extract 14 targets, append 0 for COVID
            labels_vector = list(row[self.classes[:-1]].values.astype('float32')) + [0.0]
            
        else:
            # --- Handle MIDRC Sample ---
            midrc_idx = idx - len(self.nih_df)
            row = self.midrc_df.iloc[midrc_idx]
            
            # Your preprocessing script saves MIDRC CXR as .npy or .png
            img_path = os.path.join(self.midrc_img_dir, f"{row['object_id']}.png") 
            image = Image.open(img_path).convert('RGB')
            
            # Map MIDRC findings back to our master vector
            # For a pure COVID case, everything is 0 except the last element
            labels_vector = [0.0] * 14 + [1.0] 
            
            # (Optional) If your MIDRC case has other labels like 'effusion', 
            # you can map them here too!
            if row.get('pleural_effusion', 0) == 1:
                labels_vector[4] = 1.0

        labels = torch.tensor(labels_vector, dtype=torch.float32)

        if self.transform:
            image = self.transform(image)

        return image, labels