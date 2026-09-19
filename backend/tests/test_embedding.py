from app.services.ai.embedding_service import EmbeddingService


def test_deterministic_fallback_is_consistent():
    v1 = EmbeddingService._deterministic_fallback_vector("confidentiality clause")
    v2 = EmbeddingService._deterministic_fallback_vector("confidentiality clause")
    assert v1 == v2
    assert len(v1) > 0


def test_deterministic_fallback_distinguishes_topics():
    a = EmbeddingService._deterministic_fallback_vector("confidentiality clause")
    b = EmbeddingService._deterministic_fallback_vector("payment termination terms")
    assert a != b
    assert len(a) == len(b)


def test_generate_embeddings_returns_vectors(monkeypatch):
    from app.services.ai.gemini_keys import gemini_key_manager

    monkeypatch.setattr(gemini_key_manager, "has_keys", lambda: False)
    vecs = EmbeddingService.generate_embeddings(["first", "second"])
    assert len(vecs) == 2
    for v in vecs:
        assert isinstance(v, list) and len(v) > 0
