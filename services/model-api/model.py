import os
import types
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

    Optional attribute:
      * ``.gradcam_target_layer`` - a torch module whose output is a 4D
        ``(B, C, H, W)`` feature map to feed Grad-CAM. Defaults to
        ``.backbone.features`` when absent (ConvNeXt path).
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


def preprocess_crop_box(input_size, pil_img):
    """(left, top, right, bottom) box of the pre-pad content inside the square.

    Mirrors ResizeLongest + SquarePad: the longer side is scaled to
    `input_size`, the shorter side padded symmetrically with black. Returns the
    content box so Grad-CAM overlays (and any displayed image) can be cropped
    back to the actual anatomy, hiding the padding the model was trained with.
    """
    w, h = pil_img.size
    scale = input_size / max(w, h)
    new_w, new_h = round(w * scale), round(h * scale)
    left = (input_size - new_w) // 2
    top = (input_size - new_h) // 2
    return (left, top, left + new_w, top + new_h)


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


class _SwinSpatialFeatures(nn.Module):
    """Swin encoder wrapped to the standard (B, C, H, W) map layout.

    torchvision's SwinTransformer keeps channels LAST: ``features(x)`` returns
    ``(B, H, W, C)``. Grad-CAM reads the channel axis at index 1 and the spatial
    axes at 2/3, so a plain wrapper over ``backbone.features`` would silently
    compute a wrong (but shape-valid) CAM. This wrapper reproduces the
    post-features steps (``features -> norm -> permute``) so the exposed map is
    exactly what feeds the head, delivered channels-first for Grad-CAM.

    When used as a Grad-CAM target the module MUST sit in the model's forward
    graph (pytorch_grad_cam fires backward hooks on it), which
    SwinTransformerChestModel arranges by rerouting the backbone's forward
    through it. It is deliberately NOT registered as a submodule: a plain
    ``nn.Module`` attribute would duplicate every backbone key under
    ``gradcam_target_layer.*`` and break ``load_state_dict(strict=True)``, so
    the backbone reference is attached with ``object.__setattr__`` and the
    wrapper keeps an empty state_dict while sharing the backbone's parameters.
    """

    def __init__(self, backbone):
        super().__init__()
        object.__setattr__(self, "_backbone", backbone)

    def forward(self, x):
        x = self._backbone.features(x)          # (B, H, W, C)
        x = self._backbone.norm(x)              # LayerNorm over the channels (last dim)
        x = self._backbone.permute(x)           # (B, C, H, W)
        return x


def _swin_spatial_forward(self, x):
    """forward() for torchvision's SwinTransformer that runs the encoder through
    _SwinSpatialFeatures (so Grad-CAM hooks fire on a channels-first map), then
    reproduces the stock head path: avgpool -> flatten -> head."""
    x = self._gradcam_target(x)                 # (B, C, H, W)
    x = self.avgpool(x)                         # (B, C, 1, 1)
    x = self.flatten(x)                         # (B, C)
    x = self.head(x)
    return x


class SwinTransformerChestModel(ChestClassifier, pl.LightningModule):
    """Swin-B transformer classifier trained on the NIH + MIDRC hybrid dataset.

    Mirrors the Swin training class in ml/model/train/models. Input geometry is
    exactly what training produced: longer side scaled to INPUT_SIZE (224),
    shorter side padded with black, then dataset normalization. Keep this class
    structurally IDENTICAL to the training class where it matters (backbone +
    head + both pos_weight placements), because the deployed checkpoint is
    loaded with ``strict=True`` and any key mismatch aborts.
    """

    INPUT_SIZE = 224
    BATCH_SIZE = 24

    def __init__(self, num_classes=15, pos_weight=None):
        super().__init__()
        # Backbone from scratch (weights=None): the trained checkpoint contains
        # the full pretrained backbone weights, so no download is needed at
        # runtime and the container stays offline-capable.
        self.backbone = models.swin_b(weights=None)
        num_ftrs = self.backbone.head.in_features
        self.backbone.head = nn.Linear(num_ftrs, num_classes)

        # Registered buffer so we can strict-load the training checkpoint that
        # also stored `pos_weight`. A fresh tensor if none is provided.
        if pos_weight is None:
            pos_weight = torch.ones(num_classes)
        self.register_buffer("pos_weight", pos_weight)
        self.loss_fn = nn.BCEWithLogitsLoss(pos_weight=self.pos_weight)

        # Helper name is not part of the checkpoint (embeds the same params).
        # Grad-CAM target (not part of the checkpoint): the unregistered 4D
        # wrapper, attached via object.__setattr__ so the state_dict never gains
        # `gradcam_target_layer.*` keys, with the backbone's forward rerouted
        # through it so hooks fire. Exposed to Grad-CAM via the property below.
        object.__setattr__(
            self.backbone, "_gradcam_target", _SwinSpatialFeatures(self.backbone)
        )
        self.backbone.forward = types.MethodType(_swin_spatial_forward, self.backbone)

    @property
    def gradcam_target_layer(self):
        """The Swin encoder as a (B, C, H, W) map, in the forward graph."""
        return object.__getattribute__(self.backbone, "_gradcam_target")

    def forward(self, x):
        return self.backbone(x)

    @classmethod
    def preprocess(cls, apply_normalize=True):
        """Build the training-matching transform for arbitrary input images.

        Same contract as ConvNeXtChestModel.preprocess; only the resolution
        (224) and the backbone differ.
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


def get_swin_model(checkpoint_path=None) -> SwinTransformerChestModel:
    """Load the trained Swin-B classifier (cached).

    `checkpoint_path` defaults to $SWIN_CHECKPOINT_PATH / the swin checkpoint.
    """
    global _model_instances
    if "swin" in _model_instances:
        return _model_instances["swin"]

    device = _resolve_device()
    logger.info("Using device: %s", device)

    checkpoint_path = checkpoint_path or os.getenv(
        "SWIN_CHECKPOINT_PATH", os.path.join(REPO_ROOT, "checkpoints", "swin-224px_final.pth")
    )
    logger.info("Loading Swin-B checkpoint from %s", checkpoint_path)

    model = SwinTransformerChestModel(num_classes=15)
    checkpoint = torch.load(checkpoint_path, map_location=device, weights_only=False)
    state_dict = checkpoint.get("state_dict", checkpoint)
    # Same strict contract as ConvNeXt: pos_weight lives both as a standalone
    # buffer and inside the loss module; our class registers both, so a silent
    # mismatch must never pass.
    model.load_state_dict(state_dict, strict=True)
    model.to(device)
    model.eval()

    logger.info("Swin model loaded successfully on %s", device)
    _model_instances["swin"] = model
    return model
