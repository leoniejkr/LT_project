import logging

import torch
import torch.nn as nn

from model import ChestClassifier

logger = logging.getLogger(__name__)


class EnsembleInputs:
    """Per-member preprocessed inputs for one image.

    ``pairs`` is a list of ``(member, input_tensor, rgb_map)`` where the tensor
    is ``(1, C, H, W)`` in the member's own input geometry (its INPUT_SIZE +
    dataset normalization) and ``rgb_map`` is the ``(H, W, 3)`` 0..1 image for
    Grad-CAM overlays at the same geometry.
    """

    def __init__(self, pairs):
        self.pairs = pairs
        self.member_confs = None  # (num_members, 1, num_classes); set by forward()

    def tensor_for(self, member):
        for m, tensor, _ in self.pairs:
            if m is member:
                return tensor
        raise KeyError(f"no input for member {member}")

    def rgb_for(self, member):
        for m, _, rgb in self.pairs:
            if m is member:
                return rgb
        raise KeyError(f"no rgb map for member {member}")


class _EnsembleTransform:
    def __init__(self, members, apply_normalize):
        self.members = members
        self.apply_normalize = apply_normalize  # kept for ChestClassifier parity

    def __call__(self, pil_img):
        pairs = []
        for member in self.members:
            tensor = member.preprocess(apply_normalize=True)(pil_img).unsqueeze(0)
            rgb = member.preprocess(apply_normalize=False)(pil_img).permute(1, 2, 0).numpy()
            pairs.append((member, tensor, rgb))
        return EnsembleInputs(pairs)


class EnsembleChestModel(ChestClassifier, nn.Module):
    """Inference-time ensemble of already-trained classifiers (no retraining).

    Each member is preprocessed with ITS OWN geometry (member.INPUT_SIZE +
    dataset mean/std) and the per-class sigmoid probabilities are averaged —
    soft-voting across architectures such as ConvNeXt + Swin typically lifts
    ROC-AUC over any single member. Selectable end-to-end via the registry id
    ``ensemble``.

    Grad-CAM has no single target layer for the group; gradcam.py resolves the
    heatmap from the member that contributed the most to the class probability.
    """

    def __init__(self, models):
        super().__init__()
        if not models:
            raise ValueError("an ensemble needs at least one member model")
        self.models = nn.ModuleList(models)

    def preprocess(self, apply_normalize=True):
        return _EnsembleTransform(list(self.models), apply_normalize)

    def forward(self, inputs):
        device = next(self.parameters()).device
        probs = [
            torch.sigmoid(model(inputs.tensor_for(model).to(device)))
            for model in self.models
        ]
        stacked = torch.stack(probs, dim=0)  # (num_members, 1, num_classes)
        inputs.member_confs = stacked.detach()
        return torch.mean(stacked, dim=0)  # (1, num_classes)


_ensemble_instance = None


def get_ensemble_model(member_ids=None) -> EnsembleChestModel:
    """Build the ensemble strictly from the registered models, cached.

    Members are the registry's non-ensemble classifiers (loaded from their
    registered checkpoint paths), resolved through ``CLASSIFIER_REGISTRY`` so
    registering/retraining a model automatically joins the ensemble without any
    extra wiring. Members reuse the per-model caches, so no checkpoint is
    loaded twice and nothing is retrained.

    ``member_ids`` may override which registered ids participate.
    """
    global _ensemble_instance
    if _ensemble_instance is not None:
        return _ensemble_instance

    from models_registry import CLASSIFIER_REGISTRY, get_classifier

    member_ids = member_ids if member_ids is not None else [
        id_ for id_ in CLASSIFIER_REGISTRY if id_ != "ensemble"
    ]
    members = [get_classifier(id_) for id_ in member_ids]
    if not members:
        raise ValueError("ensemble needs at least one registered member model")

    ensemble = EnsembleChestModel(members)
    logger.info("Ensemble created with %d members: %s",
                len(members), ", ".join(type(m).__name__ for m in members))
    _ensemble_instance = ensemble
    return ensemble


def build_ensemble_from_checkpoints(model_specs):
    """Build an EnsembleChestModel from explicit (model_class, checkpoint_path)
    pairs — the `model_class` + `checkpoint_paths` style of loader.

    Useful for multiple seeds of one architecture or freshly trained
    checkpoints (e.g. the newly trained ``convnext-384px_final.pth``). Each
    member is a fresh instance (not the cached default models), strict-loaded
    exactly like the individual ``get_*_model`` loaders.
    """
    if not model_specs:
        raise ValueError("model_specs must contain at least one (model_class, path) pair")

    device = torch.device(
        "cuda" if torch.cuda.is_available()
        else "mps" if torch.backends.mps.is_available()
        else "cpu"
    )

    members = []
    for model_class, checkpoint_path in model_specs:
        logger.info("Loading ensemble member %s from %s", model_class.__name__, checkpoint_path)
        model = model_class(num_classes=15)
        checkpoint = torch.load(checkpoint_path, map_location=device, weights_only=False)
        state_dict = checkpoint.get("state_dict", checkpoint)
        model.load_state_dict(state_dict, strict=True)
        model.to(device)
        model.eval()
        members.append(model)

    ensemble = EnsembleChestModel(members)
    logger.info("Ensemble built from %d explicit checkpoints", len(members))
    return ensemble