from sentence_transformers import SentenceTransformer


embedding_model = SentenceTransformer("all-MiniLM-L6-v2")


def embed_chunks(chunks_list):
    chunk_content = [chunk.content for chunk in chunks_list]

    embeddings = embedding_model.encode(chunk_content)

    chunks_and_embeddings = zip(chunks_list, embeddings)
    for chunk, vector in chunks_and_embeddings:
        chunk.embedding = vector.tolist()

    return chunks_list
