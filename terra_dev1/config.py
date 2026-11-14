import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.getenv("DATA_DIR", BASE_DIR / "data"))
IMAGE_DIR = DATA_DIR / "images"
METADATA_DIR = DATA_DIR / "metadata"
for directory in (DATA_DIR, IMAGE_DIR, METADATA_DIR):
    directory.mkdir(parents=True, exist_ok=True)

NASA_API_KEY = os.getenv("NASA_API_KEY", "DEMO_KEY")
CLIP_MODEL = os.getenv("CLIP_MODEL", "ViT-B-32")
CLIP_PRETRAINED = os.getenv("CLIP_PRETRAINED", "laion2b_s34b_b79k")
