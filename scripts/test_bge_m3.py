from FlagEmbedding import BGEM3FlagModel
import numpy as np

model = BGEM3FlagModel(
    "BAAI/bge-m3",
    use_fp16=True
)

sentences = [
    "당사는 화장품 ODM 및 OEM 사업을 영위하고 있습니다.",
    "당사는 국내외 브랜드 고객사를 대상으로 화장품을 생산합니다.",
    "당사는 온라인 플랫폼을 통해 소비자에게 직접 제품을 판매합니다."
]

embeddings = model.encode(
    sentences,
    batch_size=2,
    max_length=512
)["dense_vecs"]

def cosine_similarity(a, b):
    return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))

print("1-2 similarity:", cosine_similarity(embeddings[0], embeddings[1]))
print("1-3 similarity:", cosine_similarity(embeddings[0], embeddings[2]))
print("embedding shape:", embeddings.shape)
