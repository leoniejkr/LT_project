import torch
from torch.utils.data import Dataset
from PIL import Image

class PatientContextMultiViewDataset(Dataset):
    def __init__(self, dataframe, class_list, transform=None):
        """
        Custom Dataset that retrieves a primary chest X-ray and its accompanying 
        patient context image (or a black placeholder if no alternative image exists).
        """
        self.df = dataframe.reset_index(drop=True)
        self.class_list = class_list
        self.transform = transform
        
        # Fast Dictionary Lookup: Group all physical paths by patient_id
        self.patient_image_groups = self.df.groupby('patient_id')['img_path'].apply(list).to_dict()

    def __len__(self):
        return len(self.df)

    def __getitem__(self, idx):
        row = self.df.iloc[idx]
        pid = str(row['patient_id'])
        primary_path = row['img_path']
        
        # 1. Load the target primary image
        img_primary = Image.open(primary_path).convert('RGB')
        
        # 2. Look for an alternative image in the patient's history
        all_patient_images = self.patient_image_groups.get(pid, [primary_path])
        alternative_images = [path for path in all_patient_images if path != primary_path]
        
        if len(alternative_images) > 0:
            context_path = alternative_images[0]
            img_context = Image.open(context_path).convert('RGB')
        else:
            # Fallback: Create a black placeholder image matching the size
            img_context = Image.new('RGB', img_primary.size, (0, 0, 0))
            
        # 3. Extract the 15 binary class targets
        labels = torch.tensor(row[self.class_list].values.astype('float32'), dtype=torch.float32)
        
        # 4. Apply transforms to both streams symmetrically
        if self.transform:
            img_primary = self.transform(img_primary)
            img_context = self.transform(img_context)
            
        return img_primary, img_context, labels