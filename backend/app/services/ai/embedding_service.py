import hashlib
import math
import re

from app.core.logging import logger


class EmbeddingService:
    """
    Phase 3 & 4 (Optimised): Dedicated Embedding Generation Service.
    Generates 768-dimensional vector embeddings using Google Gemini API (`gemini-embedding-001`).
    Includes a deterministic semantic vector fallback for offline/unconfigured key testing.

    Optimisations:
    - Increased text cap from 2000 to 3000 chars (model supports ~3072 tokens)
    - Document/query prefixes for better asymmetric retrieval performance
    - Batched embedding generation for efficiency
    """

    VECTOR_DIMENSION = 768
    # One batched API call covers this many texts (keeps indexing fast even
    # for long documents instead of one network round-trip per chunk).
    BATCH_SIZE = 100

    # Increased from 2000 to 3000 — Gemini embedding model supports up to
    # ~3072 tokens; 3000 chars is a safe limit that captures full clause content.
    TEXT_CAP = 3000

    # Prefixes for asymmetric retrieval: documents and queries are embedded
    # with different prefixes so the model learns the retrieval relationship.
    DOC_PREFIX = "legal document passage: "
    QUERY_PREFIX = "search query: "

    @classmethod
    def generate_embedding(cls, text: str, is_query: bool = True) -> list[float]:
        """Generate a single embedding. Use is_query=True for search queries, False for document chunks."""
        embeddings = cls.generate_embeddings([text], is_query=is_query)
        return embeddings[0] if embeddings else cls._deterministic_fallback_vector(text)

    @classmethod
    def generate_embeddings(cls, texts: list[str], is_query: bool = False) -> list[list[float]]:
        """
        Generate embeddings for a batch of texts.
        is_query=False (default) for document chunks; is_query=True for search queries.
        """
        from app.services.ai.gemini_keys import gemini_key_manager

        # Apply prefix for better asymmetric retrieval with live Gemini model
        prefix = cls.QUERY_PREFIX if is_query else cls.DOC_PREFIX

        if gemini_key_manager.has_keys():
            for api_key in gemini_key_manager.iter_keys():
                try:
                    from google import genai
                    from google.genai import types

                    client = genai.Client(api_key=api_key)

                    results: list[list[float]] = []
                    for start in range(0, len(texts), cls.BATCH_SIZE):
                        batch = texts[start : start + cls.BATCH_SIZE]
                        # Prepend prefix and apply text cap for Gemini API
                        prepared = [prefix + t[: cls.TEXT_CAP] for t in batch]
                        res = client.models.embed_content(
                            model="gemini-embedding-001",
                            contents=prepared,
                            config=types.EmbedContentConfig(
                                output_dimensionality=cls.VECTOR_DIMENSION
                            ),
                        )
                        values = getattr(res, "embeddings", None) or []
                        for txt, emb in zip(batch, values):
                            if emb is not None and getattr(emb, "values", None):
                                results.append(list(emb.values))
                            else:
                                results.append(cls._deterministic_fallback_vector(txt))
                        # Pad if the API returned fewer vectors than requested.
                        while len(results) < start + len(batch):
                            results.append(
                                cls._deterministic_fallback_vector(batch[len(results) - start])
                            )
                    gemini_key_manager.report_success(api_key)
                    return results
                except Exception as e:
                    if gemini_key_manager.is_quota_error(e):
                        gemini_key_manager.report_quota_failure(api_key)
                        continue  # quota exhausted -> fail over to next key
                    logger.warning(
                        f"Gemini embedding API call failed ({e}). Utilizing deterministic semantic vector fallback."
                    )
                    break
            else:
                logger.warning(
                    "All Gemini embedding API keys exhausted; utilizing deterministic semantic vector fallback."
                )

        return [cls._deterministic_fallback_vector(t) for t in texts]

    @classmethod
    def _deterministic_fallback_vector(cls, text: str) -> list[float]:
        """
        Produces a normalized 768-dim pseudo-semantic vector derived from text words & n-grams.
        Ensures consistent, accurate cosine similarity rankings for offline test environments.
        """
        vector = [0.0] * cls.VECTOR_DIMENSION
        # Clean words
        clean_text = re.sub(r"[^a-zA-Z0-9\s]", " ", text).lower()
        words = [w for w in clean_text.split() if len(w) > 1]

        stopwords = {
            "the",
            "and",
            "for",
            "with",
            "that",
            "this",
            "from",
            "are",
            "was",
            "were",
            "what",
            "how",
        }

        for idx, word in enumerate(words):
            if word in stopwords:
                continue
            h = int(hashlib.md5(word.encode("utf-8")).hexdigest(), 16)
            pos = h % cls.VECTOR_DIMENSION
            weight = 2.0 + (1.0 / (idx + 1))
            vector[pos] += weight

        # Bigram contribution for phrase-level similarity
        for idx in range(len(words) - 1):
            w1, w2 = words[idx], words[idx + 1]
            if w1 not in stopwords and w2 not in stopwords:
                bigram = f"{w1}_{w2}"
                h = int(hashlib.md5(bigram.encode("utf-8")).hexdigest(), 16)
                pos = h % cls.VECTOR_DIMENSION
                vector[pos] += 1.5

        # L2 Normalization
        norm = math.sqrt(sum(v * v for v in vector))
        if norm > 0:
            vector = [v / norm for v in vector]

        return vector
