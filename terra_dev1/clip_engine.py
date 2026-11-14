from functools import lru_cache
from pathlib import Path
import numpy as np
import torch
import open_clip
from PIL import Image
from .config import CLIP_MODEL, CLIP_PRETRAINED

@lru_cache(maxsize=1)
def load_clip():
    device = "cuda" if torch.cuda.is_available() else "cpu"
    model, _, preprocess = open_clip.create_model_and_transforms(
        CLIP_MODEL, pretrained=CLIP_PRETRAINED
    )
    tokenizer = open_clip.get_tokenizer(CLIP_MODEL)
    model = model.to(device).eval()
    return model, preprocess, tokenizer, device

def _open_image(path):
    p = Path(path).expanduser().resolve()
    if not p.is_file():
        raise ValueError(f"Image not found: {path}")
    try:
        return Image.open(p).convert("RGB")
    except Exception as exc:
        raise ValueError(f"Could not read image: {path}") from exc

def image_embedding(path):
    model, preprocess, _, device = load_clip()
    image = preprocess(_open_image(path)).unsqueeze(0).to(device)
    with torch.no_grad():
        features = model.encode_image(image)
        features = features / features.norm(dim=-1, keepdim=True)
    return features.cpu().numpy()[0]

def score_image_against_prompts(image_path, prompts):
    if not isinstance(prompts, list) or not prompts or len(prompts) > 50:
        raise ValueError("prompts must be a list containing 1 to 50 strings")
    if any(not isinstance(p, str) or not p.strip() or len(p) > 300 for p in prompts):
        raise ValueError("Each prompt must be a non-empty string of at most 300 characters")
    model, preprocess, tokenizer, device = load_clip()
    image = preprocess(_open_image(image_path)).unsqueeze(0).to(device)
    tokens = tokenizer(prompts).to(device)
    with torch.no_grad():
        image_features = model.encode_image(image)
        text_features = model.encode_text(tokens)
        image_features /= image_features.norm(dim=-1, keepdim=True)
        text_features /= text_features.norm(dim=-1, keepdim=True)
        cosine = (image_features @ text_features.T).squeeze(0)
        # Softmax is a relative distribution over the supplied prompts only,
        # not a calibrated probability of real-world suitability.
        relative = torch.softmax(cosine * 100.0, dim=0)
    rows = [{
        "prompt": prompts[i],
        "cosine_similarity": round(float(cosine[i].cpu()), 6),
        "relative_prompt_score": round(float(relative[i].cpu()), 6)
    } for i in range(len(prompts))]
    rows.sort(key=lambda x: x["cosine_similarity"], reverse=True)
    return {
        "model": f"{CLIP_MODEL}/{CLIP_PRETRAINED}",
        "device": device,
        "interpretation": "Semantic similarity only; not a probability or scientific suitability score.",
        "matches": rows
    }

def compare_images(image_a, image_b):
    a = image_embedding(image_a)
    b = image_embedding(image_b)
    similarity = float(np.dot(a, b))
    return {
        "cosine_similarity": round(similarity, 6),
        "similarity_percent_display_only": round((similarity + 1) * 50, 2),
        "interpretation": "CLIP embedding similarity; not a scientific equivalence or suitability measure."
    }
