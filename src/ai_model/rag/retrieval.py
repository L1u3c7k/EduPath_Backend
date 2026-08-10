import numpy as np
from src.ai_model.utils.loader import (
    documents,
    embeddings
)


def retrieve(query_embedding, top_k=5):

    scores = embeddings @ query_embedding


    indices = np.argsort(
        scores
    )[::-1][:top_k]


    results=[]


    for i in indices:

        results.append({

            "score":
                float(scores[i]),

            "text":
                documents[i]["text"],

            "metadata":
                documents[i]["metadata"]

        })


    return results