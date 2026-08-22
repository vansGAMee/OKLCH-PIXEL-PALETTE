"""
generate_semantic_dataset.py
Generates rich semantic training, validation, and test datasets with direct color anchors,
thematic concepts, and multilingual variations. Extracts 384-d embeddings using local
multilingual-e5-small model and saves to ml/dataset_embeddings.npz.
"""
import json
import math
import random
from pathlib import Path
import numpy as np
import onnxruntime as ort
from tokenizers import Tokenizer

ROOT = Path(__file__).resolve().parent.parent
CONCEPTS_FILE = ROOT / "ml" / "concepts_v2.json"
MODEL_DIR = ROOT / "public" / "models" / "multilingual-e5-small"
OUT_NPZ = ROOT / "ml" / "dataset_embeddings.npz"

def logit(p: float) -> float:
    p = max(1e-5, min(1.0 - 1e-5, p))
    return math.log(p / (1.0 - p))

def load_encoder():
    tok = Tokenizer.from_file(str(MODEL_DIR / "tokenizer.json"))
    sess = ort.InferenceSession(str(MODEL_DIR / "onnx" / "model_quantized.onnx"))
    return tok, sess

def embed_texts(texts: list[str], tok, sess, batch_size: int = 64) -> np.ndarray:
    all_embeddings = []
    for i in range(0, len(texts), batch_size):
        batch_texts = [f"query: {t.strip()}" for t in texts[i:i+batch_size]]
        encodings = [tok.encode(t) for t in batch_texts]
        
        max_len = max(len(e.ids) for e in encodings)
        padded_ids = []
        padded_mask = []
        for e in encodings:
            pad_len = max_len - len(e.ids)
            padded_ids.append(e.ids + [0] * pad_len)
            padded_mask.append(e.attention_mask + [0] * pad_len)
            
        input_ids = np.array(padded_ids, dtype=np.int64)
        attention_mask = np.array(padded_mask, dtype=np.int64)
        token_type_ids = np.zeros_like(input_ids)
        
        out = sess.run(None, {
            "input_ids": input_ids,
            "attention_mask": attention_mask,
            "token_type_ids": token_type_ids,
        })
        
        last_hidden = out[0] # [batch, seq_len, 384]
        mask_expanded = np.expand_dims(attention_mask, -1).astype(np.float32)
        sum_embeddings = np.sum(last_hidden * mask_expanded, axis=1)
        sum_mask = np.clip(mask_expanded.sum(axis=1), a_min=1e-9, a_max=None)
        mean_pooled = sum_embeddings / sum_mask
        norm = np.linalg.norm(mean_pooled, axis=-1, keepdims=True)
        normalized = mean_pooled / np.clip(norm, a_min=1e-12, a_max=None)
        all_embeddings.append(normalized)
        
    return np.vstack(all_embeddings).astype(np.float32)

def build_dataset_samples():
    with open(CONCEPTS_FILE, "r", encoding="utf-8") as f:
        concepts = json.load(f)

    samples = []
    
    # Prefix modifiers for augmentation
    en_light_mods = ["bright", "vibrant", "deep", "soft", "dark", "light", "pale", "intense", "glowing", "neon", "pastel", "mystic", "cozy", "pure", "vintage"]
    ru_light_mods = ["яркий", "насыщенный", "глубокий", "мягкий", "темный", "светлый", "бледный", "светящийся", "неоновый", "пастельный", "мистический", "уютный", "чистый", "винтажный"]

    # 1. Direct Color Anchors (high weight, strong supervision)
    for anchor in concepts["color_anchors"]:
        c_id = anchor["id"]
        hue = float(anchor["hue"])
        lightness = float(anchor["lightness"])
        chroma = float(anchor["relativeChroma"])
        harmony = anchor.get("harmony", "splitComplementary")
        
        # Base terms
        for term in anchor.get("en_terms", []):
            samples.append({
                "group": f"anchor_{c_id}",
                "text": term,
                "hue": hue,
                "lightness": lightness,
                "chroma": chroma,
                "harmony": harmony,
                "is_anchor": True
            })
            # Add modified versions
            for mod in en_light_mods[:6]:
                mod_l = lightness
                mod_c = chroma
                if mod in ["bright", "light", "pale", "pastel"]:
                    mod_l = min(0.85, lightness + 0.15)
                elif mod in ["dark", "deep"]:
                    mod_l = max(0.18, lightness - 0.15)
                if mod in ["vibrant", "glowing", "neon", "intense"]:
                    mod_c = min(0.95, chroma + 0.15)
                elif mod in ["soft", "pale", "pastel", "vintage"]:
                    mod_c = max(0.15, chroma - 0.20)
                samples.append({
                    "group": f"anchor_{c_id}",
                    "text": f"{mod} {term}",
                    "hue": hue,
                    "lightness": mod_l,
                    "chroma": mod_c,
                    "harmony": harmony,
                    "is_anchor": True
                })
                
        for term in anchor.get("ru_terms", []):
            samples.append({
                "group": f"anchor_{c_id}",
                "text": term,
                "hue": hue,
                "lightness": lightness,
                "chroma": chroma,
                "harmony": harmony,
                "is_anchor": True
            })
            for mod in ru_light_mods[:6]:
                mod_l = lightness
                mod_c = chroma
                if mod in ["яркий", "светлый", "бледный", "пастельный"]:
                    mod_l = min(0.85, lightness + 0.15)
                elif mod in ["темный", "глубокий"]:
                    mod_l = max(0.18, lightness - 0.15)
                if mod in ["насыщенный", "светящийся", "неоновый"]:
                    mod_c = min(0.95, chroma + 0.15)
                elif mod in ["мягкий", "бледный", "пастельный", "винтажный"]:
                    mod_c = max(0.15, chroma - 0.20)
                samples.append({
                    "group": f"anchor_{c_id}",
                    "text": f"{mod} {term}",
                    "hue": hue,
                    "lightness": mod_l,
                    "chroma": mod_c,
                    "harmony": harmony,
                    "is_anchor": True
                })

    # 2. Thematic concepts
    for theme in concepts.get("thematic_concepts", []):
        t_id = theme["id"]
        hue = float(theme["hue"])
        lightness = float(theme["lightness"])
        chroma = float(theme["relativeChroma"])
        harmony = theme.get("harmony", "splitComplementary")
        
        for phrase in theme.get("en_phrases", []):
            samples.append({
                "group": f"theme_{t_id}",
                "text": phrase,
                "hue": hue,
                "lightness": lightness,
                "chroma": chroma,
                "harmony": harmony,
                "is_anchor": False
            })
        for phrase in theme.get("ru_phrases", []):
            samples.append({
                "group": f"theme_{t_id}",
                "text": phrase,
                "hue": hue,
                "lightness": lightness,
                "chroma": chroma,
                "harmony": harmony,
                "is_anchor": False
            })

    print(f"Total raw generated samples: {len(samples)}")
    return samples

def main():
    random.seed(42)
    np.random.seed(42)
    
    samples = build_dataset_samples()
    tok, sess = load_encoder()
    
    texts = [s["text"] for s in samples]
    print(f"Extracting embeddings for {len(texts)} samples with multilingual-e5-small...")
    embeddings = embed_texts(texts, tok, sess)
    print(f"Embeddings extracted: {embeddings.shape}")
    
    # Compute targets
    hues = np.array([s["hue"] for s in samples], dtype=np.float32)
    hue_rads = hues * np.pi / 180.0
    hue_sin = np.sin(hue_rads).astype(np.float32)
    hue_cos = np.cos(hue_rads).astype(np.float32)
    
    lightnesses = np.array([s["lightness"] for s in samples], dtype=np.float32)
    lightness_logits = np.array([logit(l) for l in lightnesses], dtype=np.float32)
    
    chromas = np.array([s["chroma"] for s in samples], dtype=np.float32)
    chroma_logits = np.array([logit(c) for c in chromas], dtype=np.float32)
    
    # Harmony classes: 0 = splitComplementary, 1 = complementary, 2 = analogous
    harmony_map = {"splitComplementary": 0, "complementary": 1, "analogous": 2}
    harmonies = np.array([harmony_map.get(s["harmony"], 0) for s in samples], dtype=np.int64)
    
    is_anchors = np.array([1.0 if s["is_anchor"] else 0.0 for s in samples], dtype=np.float32)
    groups = [s["group"] for s in samples]
    
    np.savez_compressed(
        OUT_NPZ,
        embeddings=embeddings,
        texts=texts,
        hues=hues,
        hue_sin=hue_sin,
        hue_cos=hue_cos,
        lightnesses=lightnesses,
        lightness_logits=lightness_logits,
        chromas=chromas,
        chroma_logits=chroma_logits,
        harmonies=harmonies,
        is_anchors=is_anchors,
        groups=groups
    )
    print(f"Dataset embeddings saved successfully to {OUT_NPZ} ({OUT_NPZ.stat().st_size / 1024:.1f} KB)")

if __name__ == "__main__":
    main()
