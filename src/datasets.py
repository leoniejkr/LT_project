import torch
from torch.utils.data import Dataset
from PIL import Image

class Hybrid2DChestDataset(Dataset):
    def __init__(self, dataframe, class_list, transform=None):
        self.df = dataframe
        self.class_list = class_list
        self.transform = transform

    def __len__(self):
        return len(self.df)

    def __getitem__(self, idx):
        row = self.df.iloc[idx]
        
        # Load standard image directly as RGB (3-channel) 
        # Pretrained Torchvision/MONAI models expect 3 input channels!
        image = Image.open(row['img_path']).convert('RGB')
        
        # Extract 15 binary targets
        labels = torch.tensor(row[self.class_list].values.astype('float32'), dtype=torch.float32)
        
        if self.transform:
            image = self.transform(image)
            
        return image, labels