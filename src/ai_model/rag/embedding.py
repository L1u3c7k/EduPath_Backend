from FlagEmbedding import BGEM3FlagModel
import numpy as np

_model = None

def init_embedding_model():
    global _model
    if _model is None:
        print("⚡ Preloading BAAI/bge-m3 model into memory...")
        _model = BGEM3FlagModel("BAAI/bge-m3", use_fp16=True)

def embed(text):
    global _model
    if _model is None:
        init_embedding_model()

    vector = _model.encode(
        [text],
        batch_size=1,
        max_length=4096
    )["dense_vecs"][0]

    vector = vector / np.linalg.norm(vector)
    return vector.astype(np.float32)