import torch
from torch.utils.data import Dataset
from PIL import Image
import numpy as np

class PatientContextMultiViewDataset(Dataset):
    def __init__(self, dataframe, class_list, transform=None):
        self.df = dataframe.reset_index(drop=True)
        self.class_list = class_list
        self.transform = transform
        
        # 🧠 Fast Lookup: Group paths by patient_id so we can find pairs instantly
        self.patient_image_groups = self.df.groupby('patient_id')['img_path'].apply(list).to_dict()

    def __len__(self):
        return len(self.df)

    def __getitem__(self, idx):
        row = self.df.iloc[idx]
        pid = str(row['patient_id'])
        primary_path = row['img_path']
        
        # 1. Load the primary target image
        img_primary = Image.open(primary_path).convert('RGB')
        
        # 2. Search Patient Context history for an alternative image
        all_patient_images = self.patient_image_groups.get(pid, [primary_path])
        
        # Filter out our current primary image to see if an alternative exists
        alternative_images = [path for path in all_patient_images if path != primary_path]
        
        if len(alternative_images) > 0:
            # Pick the first available historical/alternative view
            context_path = alternative_images[0]
            img_context = Image.open(context_path).convert('RGB')
        else:
            # Fallback: Patient has no other images. Create a black image placeholder matching dimensions
            # We use the primary image's structural size so the transformations scale uniformly
            img_context = Image.new('RGB', img_primary.size, (0, 0, 0))
            
        # 3. Extract Multi-Label Target Vector
        labels = torch.tensor(row[self.class_list].values.astype('float32'), dtype=torch.float32)
        
        # Apply standard transformations to both images symmetrically
        if self.transform:
            img_primary = self.transform(img_primary)
            img_context = self.transform(img_context)
            
        # Returns both streams side-by-side alongside the sharing target label!
        return img_primary, img_context, labels