import os
import logging

import torch
import torch.nn as nn
import torchvision.models as models
from torchvision import transforms
import pytorch_lightning as pl

logger = logging.getLogger(__name__)

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# Normalization statistics used during hybrid-dataset training. These come from
# ml/model/train/dataset_stats.json (computed over the NIH + MIDRC images) and
# MUST be used at inference so inputs match the training distribution exactly.
RESOLUTION = 384
DATASET_MEAN = [0.49688172340393066, 0.49688172340393066, 0.49688172340393066]
DATASET_STD = [0.2517261505126953, 0.2517261505126953, 0.2517261505126953]


class ChestClassifier:
    """Interface every classifier in the modelling service must satisfy.

    A classifier is a torch module that additionally exposes:

      * ``.backbone``        - a module with a ``.features`` Sequential
                               (used by Grad-CAM to pick a target layer)
      * ``preprocess()``     - a torchvision transform mapping an ARBITRARY
                               PIL image to the exact distribution the model
                               was trained on (aspect-preserving geometry +
                               the dataset mean/std). See ConvNeXtChestModel.
      * ``INPUT_SIZE``       - the spatial size the model was trained at.

    This is the extension point for future architectures: add a transformer
    (e.g. Swin/ViT) or an ensemble (a wrapper that averages several
    classifiers) as a new class here, plus a factory in models_registry.py,
    and it becomes selectable end-to-end.
    """


class ResizeLongest:
    """Scale an image so its longer side becomes `size`, preserving aspect ratio.

    Mirrors ml/model/train/train.py. Never distorts anatomy: a portrait 2925px
    image becomes (733, 1024), a landscape one (1024, 800), etc. The result is
    then made square by SquarePad before entering the network.
    """

    def __init__(self, size):
        self.size = size

    def __call__(self, img):
        w, h = img.size
        scale = self.size / max(w, h)
        new_w, new_h = round(w * scale), round(h * scale)
        return transforms.functional.resize(img, (new_h, new_w))

    def __repr__(self):
        return f"{self.__class__.__name__}({self.size})"


class SquarePad:
    """Pad the shorter side symmetrically with black to make the image square."""

    def __init__(self, fill=0):
        self.fill = fill

    def __call__(self, img):
        w, h = img.size
        if w == h:
            return img
        max_side = max(w, h)
        pad_l = (max_side - w) // 2
        pad_r = max_side - w - pad_l
        pad_t = (max_side - h) // 2
        pad_b = max_side - h - pad_t
        return transforms.functional.pad(
            img, (pad_l, pad_t, pad_r, pad_b), fill=(self.fill, self.fill, self.fill))

    def __repr__(self):
        return f"{self.__class__.__name__}(fill={self.fill})"


class ConvNeXtChestModel(ChestClassifier, pl.LightningModule):
    """ConvNeXt-Base classifier trained on the NIH + MIDRC hybrid dataset.

    Mirrors ml/model/train/models/chest_model.py. Input geometry is exactly
    what training produced: the longer side is scaled to INPUT_SIZE, the shorter
    side is padded with black to a square, then normalized with the dataset
    mean/std from dataset_stats.json. Any input image -- square, portrait,
    landscape, any resolution -- is handled without distortion in
    `preprocess`.
    """

    INPUT_SIZE = RESOLUTION
    BATCH_SIZE = 16

    def __init__(self, num_classes=15, pos_weight=None):
        super().__init__()
        # Backbone from scratch (weights=None): the trained checkpoint contains
        # the full pretrained backbone weights, so no download is needed at
        # runtime and the container stays offline-capable.
        self.backbone = models.convnext_base(weights=None)
        num_ftrs = self.backbone.classifier[2].in_features
        self.backbone.classifier[2] = nn.Linear(num_ftrs, num_classes)

        # Registered buffer so we can strict-load the training checkpoint that
        # also stored `pos_weight`. A fresh tensor if none is provided.
        if pos_weight is None:
            pos_weight = torch.ones(num_classes)
        self.register_buffer("pos_weight", pos_weight)
        self.loss_fn = nn.BCEWithLogitsLoss(pos_weight=self.pos_weight)

    def forward(self, x):
        return self.backbone(x)

    @classmethod
    def preprocess(cls, apply_normalize=True):
        """Build the training-matching transform for arbitrary input images.

        apply_normalize=True  -> full pipeline (used for the model input).
        apply_normalize=False -> geometry-only pipeline (used for the Grad-CAM
                                 overlay, which expects a plain 0..1 RGB image
                                 in the same spatial size as the input tensor).
        """
        transforms_list = [
            ResizeLongest(cls.INPUT_SIZE),
            SquarePad(fill=0),
            transforms.ToTensor(),
        ]
        if apply_normalize:
            transforms_list.append(transforms.Normalize(
                mean=DATASET_MEAN,
                std=DATASET_STD,
            ))
        return transforms.Compose(transforms_list)


ALL_CLASSES = [
    "Atelectasis",
    "Cardiomegaly",
    "Consolidation",
    "Edema",
    "Effusion",
    "Emphysema",
    "Fibrosis",
    "Hernia",
    "Infiltration",
    "Mass",
    "Nodule",
    "Pleural_Thickening",
    "Pneumonia",
    "Pneumothorax",
    "Covid",
]

_model_instances = {}


def _resolve_device():
    return torch.device(
        "cuda" if torch.cuda.is_available()
        else "mps" if torch.backends.mps.is_available()
        else "cpu"
    )


def get_convnext_model(checkpoint_path=None) -> ConvNeXtChestModel:
    """Load the trained ConvNeXt-Base classifier (cached).

    `checkpoint_path` defaults to $CHECKPOINT_PATH / the convnext checkpoint.
    """
    global _model_instances
    if "convnext" in _model_instances:
        return _model_instances["convnext"]

    device = _resolve_device()
    logger.info("Using device: %s", device)

    checkpoint_path = checkpoint_path or os.getenv(
        "CHECKPOINT_PATH", os.path.join(REPO_ROOT, "checkpoints", "covnext348.pth")
    )
    logger.info("Loading ConvNeXt checkpoint from %s", checkpoint_path)

    model = ConvNeXtChestModel(num_classes=15)
    checkpoint = torch.load(checkpoint_path, map_location=device, weights_only=False)
    state_dict = checkpoint.get("state_dict", checkpoint)
    # The saved module stores pos_weight both as a standalone buffer and inside
    # the loss module's state; our class registers both, so load everything
    # strict -- a silent mismatch must never pass.
    model.load_state_dict(state_dict, strict=True)
    model.to(device)
    model.eval()

    logger.info("ConvNeXt model loaded successfully on %s", device)
    _model_instances["convnext"] = model
    return model
