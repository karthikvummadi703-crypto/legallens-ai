import math
import os
import uuid
from typing import Any

from app.config import is_cloud_mode
from app.core.logging import logger

try:
    import numpy as np

    _HAS_NUMPY = True
except Exception:  # pragma: no cover - numpy is an optional accelerator
    np = None
    _HAS_NUMPY = False

COLLECTION_NAME = "legallens_legal_chunks"
VECTOR_SIZE = 768

# Global Qdrant client instance
_qdrant_client = None
_in_memory_store: dict[str, dict[str, Any]] = {}  # Fallback in-memory vector store
_memory_snapshot_loaded = False
_memory_lock = None


def _get_memory_lock():
    global _memory_lock
    if _memory_lock is None:
        import threading

        _memory_lock = threading.RLock()
    return _memory_lock


def _memory_snapshot_path() -> str:
    """Disk snapshot so fallback vectors survive backend restarts."""
    try:
        from app.config import settings

        return os.path.join(settings.DATA_DIR, "vector_memory_snapshot.json")
    except Exception:
        return os.path.join(
            os.path.dirname(__file__), "..", "..", "..", "data", "vector_memory_snapshot.json"
        )


def _load_memory_snapshot() -> None:
    """Load persisted fallback vectors once per process (best-effort)."""
    global _memory_snapshot_loaded
    if _memory_snapshot_loaded:
        return
    _memory_snapshot_loaded = True
    try:
        if is_cloud_mode():
            from app.utils import cloud_store

            data = cloud_store.load_vectors()
            if data:
                _in_memory_store.update(data)
                logger.info(
                    f"Memory Vector Store: Restored {len(data)} chunk vectors from Firebase Realtime Database."
                )
            return
        import json

        path = _memory_snapshot_path()
        if os.path.exists(path):
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                _in_memory_store.update(data)
                logger.info(
                    f"Memory Vector Store: Restored {len(data)} chunk vectors from disk snapshot."
                )
    except Exception as e:
        logger.warning(f"Memory vector snapshot load skipped ({e}).")


def _persist_memory_snapshot() -> None:
    """Atomically persist fallback vectors (best-effort)."""
    try:
        if is_cloud_mode():
            from app.utils import cloud_store

            cloud_store.save_vectors(_in_memory_store)
            return
        import json

        path = _memory_snapshot_path()
        tmp_path = path + ".tmp"
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(_in_memory_store, f)
        os.replace(tmp_path, path)
    except Exception as e:
        logger.warning(f"Memory vector snapshot persist skipped ({e}).")


def _persistent_storage_path() -> str:
    """Local on-disk directory for the Qdrant index so vectors survive restarts."""
    try:
        from app.config import settings

        return os.path.join(settings.DATA_DIR, "qdrant_storage")
    except Exception:
        return os.path.join(os.path.dirname(__file__), "..", "..", "..", "data", "qdrant_storage")


def _get_qdrant_client():
    global _qdrant_client
    if _qdrant_client is None:
        if is_cloud_mode():
            # Serverless: no persistent local disk for the embedded Qdrant index
            # (FS is read-only except /tmp). Route everything through the
            # in-memory cosine store backed by Firebase Realtime Database.
            logger.info(
                "Qdrant disabled in cloud (serverless) mode; using Firebase-backed memory vector store."
            )
            _qdrant_client = False
            return _qdrant_client
        try:
            from qdrant_client import QdrantClient
            from qdrant_client.models import Distance, VectorParams

            # Persistent local Qdrant storage: the index survives backend restarts,
            # so previously uploaded documents remain searchable.
            storage_path = _persistent_storage_path()
            os.makedirs(storage_path, exist_ok=True)
            _qdrant_client = QdrantClient(path=storage_path)

            # Initialize collection if not existing
            collections = [c.name for c in _qdrant_client.get_collections().collections]
            if COLLECTION_NAME not in collections:
                _qdrant_client.create_collection(
                    collection_name=COLLECTION_NAME,
                    vectors_config=VectorParams(size=VECTOR_SIZE, distance=Distance.COSINE),
                )
                logger.info(
                    f"Qdrant collection '{COLLECTION_NAME}' created (Vector size: {VECTOR_SIZE})."
                )

            # Payload indexes for ownership-filtered search (best-effort;
            # filtered retrieval still works without them, just slower).
            # Local (embedded) Qdrant ignores payload indexes, so its warning
            # is suppressed; server Qdrant benefits from them.
            try:
                import warnings

                from qdrant_client.models import PayloadSchemaType

                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    for field in ("user_id", "document_id"):
                        try:
                            _qdrant_client.create_payload_index(
                                collection_name=COLLECTION_NAME,
                                field_name=field,
                                field_schema=PayloadSchemaType.KEYWORD,
                            )
                        except Exception:
                            pass  # index already exists
            except Exception as e:
                logger.warning(f"Qdrant payload index setup skipped ({e}).")
        except Exception as e:
            logger.warning(
                f"Qdrant client initialization notice ({e}). Using robust in-memory vector store."
            )
            _qdrant_client = False
    return _qdrant_client


def _result_dict(score: float, payload: dict[str, Any]) -> dict[str, Any]:
    """Normalise a Qdrant/in-memory hit into the public result shape."""
    return {
        "score": float(score),
        "chunk_id": payload.get("chunk_id"),
        "document_id": payload.get("document_id"),
        "document_name": payload.get("document_name", ""),
        "user_id": payload.get("user_id"),
        "page_number": payload.get("page_number", 1),
        "section": payload.get("section", "General"),
        "clause_id": payload.get("clause_id", ""),
        "text": payload.get("text", ""),
    }


def _qdrant_search_results(
    client,
    query_vector: list[float],
    search_filter,
    top_k: int,
    document_ids: set[str] | None = None,
) -> list[dict[str, Any]]:
    """Run a Qdrant query (query_points or search API) and normalise results."""
    if hasattr(client, "query_points"):
        query_response = client.query_points(
            collection_name=COLLECTION_NAME,
            query=query_vector,
            query_filter=search_filter,
            limit=top_k,
        )
        search_results = query_response.points
    elif hasattr(client, "search"):
        search_results = client.search(
            collection_name=COLLECTION_NAME,
            query_vector=query_vector,
            query_filter=search_filter,
            limit=top_k,
        )
    else:
        search_results = []
    results = []
    for res in search_results:
        payload = res.payload
        # Enforce the document set client-side as a safety net when MatchAny
        # is not honoured by the running Qdrant build.
        if document_ids is not None and payload.get("document_id") not in document_ids:
            continue
        results.append(_result_dict(res.score, payload))
    return results


def _memory_search(
    user_id: str,
    query_vector: list[float],
    top_k: int,
    document_ids: set[str] | None = None,
) -> list[dict[str, Any]]:
    """Cosine similarity over the in-memory fallback store with strict ownership filtering.

    The search is vectorised with numpy when available (keeping tie order
    deterministic via a stable sort) and falls back to pure-Python math
    otherwise, so results are identical either way.
    """
    _load_memory_snapshot()
    candidates = [
        (c_id, entry)
        for c_id, entry in _in_memory_store.items()
        if entry["payload"].get("user_id") == user_id
        and (document_ids is None or entry["payload"].get("document_id") in document_ids)
    ]
    if not candidates:
        return []

    if _HAS_NUMPY:
        query = np.asarray(query_vector, dtype=np.float64)
        matrix = np.array([entry["vector"] for _, entry in candidates], dtype=np.float64)
        dots = matrix @ query
        denom = np.linalg.norm(matrix, axis=1) * float(np.linalg.norm(query))
        scores = np.zeros(len(candidates))
        np.divide(dots, denom, out=scores, where=denom != 0)
        order = np.argsort(-scores, kind="stable")
        return [
            _result_dict(float(scores[idx]), candidates[idx][1]["payload"]) for idx in order[:top_k]
        ]

    scored = [
        (_py_cosine_similarity(query_vector, entry["vector"]), entry["payload"])
        for _, entry in candidates
    ]
    scored.sort(key=lambda x: x[0], reverse=True)
    return [_result_dict(score, payload) for score, payload in scored[:top_k]]


class VectorDatabaseService:
    """
    Phase 4: Qdrant Vector Database Service Layer Abstraction.
    Handles embedding storage, metadata payload indexing, ownership filtering,
    and semantic similarity search.
    """

    @classmethod
    def upsert_document_chunks(
        cls,
        user_id: str,
        document_id: str,
        chunks: list[dict[str, Any]],
        embeddings: list[list[float]],
        document_name: str = "",
    ) -> bool:
        client = _get_qdrant_client()

        # Purge any old vectors for this document first (idempotent reindexing)
        cls.delete_document_vectors(user_id, document_id)

        if client:
            try:
                from qdrant_client.models import PointStruct

                points = []
                for _idx, (chunk, vector) in enumerate(zip(chunks, embeddings)):
                    p_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, chunk["chunk_id"]))
                    payload = {
                        "document_id": document_id,
                        "document_name": document_name or chunk.get("document_name", ""),
                        "user_id": user_id,
                        "chunk_id": chunk["chunk_id"],
                        "page_number": chunk["page_number"],
                        "section": chunk["section"],
                        "clause_id": chunk.get("clause_id", ""),
                        "chunk_index": chunk["chunk_index"],
                        "text": chunk["text"],
                    }
                    points.append(PointStruct(id=p_id, vector=vector, payload=payload))

                client.upsert(collection_name=COLLECTION_NAME, points=points)
                logger.info(
                    f"Qdrant: Upserted {len(points)} vectors for document {document_id} (User: {user_id})."
                )
                return True
            except Exception as e:
                logger.error(f"Qdrant upsert failed ({e}). Falling back to memory store.")

        # Fallback in-memory store (persisted to disk so vectors survive restarts)
        _load_memory_snapshot()
        with _get_memory_lock():
            for chunk, vector in zip(chunks, embeddings):
                c_id = chunk["chunk_id"]
                _in_memory_store[c_id] = {
                    "vector": vector,
                    "payload": {
                        "document_id": document_id,
                        "document_name": document_name or chunk.get("document_name", ""),
                        "user_id": user_id,
                        "chunk_id": c_id,
                        "page_number": chunk["page_number"],
                        "section": chunk["section"],
                        "clause_id": chunk.get("clause_id", ""),
                        "chunk_index": chunk["chunk_index"],
                        "text": chunk["text"],
                    },
                }
        _persist_memory_snapshot()
        logger.info(
            f"Memory Vector Store: Indexed {len(chunks)} chunks for document {document_id}."
        )
        return True

    @classmethod
    def search_similar_chunks(
        cls, user_id: str, document_id: str, query_vector: list[float], top_k: int = 5
    ) -> list[dict[str, Any]]:
        """
        Executes semantic vector similarity search.
        MANDATORY OWNERSHIP FILTERING: Strict user_id AND document_id matching.
        """
        _load_memory_snapshot()
        client = _get_qdrant_client()

        if client:
            try:
                from qdrant_client.models import FieldCondition, Filter, MatchValue

                # Strict ownership query filter
                search_filter = Filter(
                    must=[
                        FieldCondition(key="user_id", match=MatchValue(value=user_id)),
                        FieldCondition(key="document_id", match=MatchValue(value=document_id)),
                    ]
                )
                results = _qdrant_search_results(client, query_vector, search_filter, top_k)
                logger.info(
                    f"Qdrant Search: Retrieved {len(results)} chunks for doc {document_id} (User: {user_id})."
                )
                return results
            except Exception as e:
                logger.error(f"Qdrant search error ({e}). Using in-memory fallback search.")

        results = _memory_search(user_id, query_vector, top_k, document_ids={document_id})
        logger.info(
            f"In-Memory Vector Search: Retrieved {len(results)} chunks for doc {document_id}."
        )
        return results

    @classmethod
    def search_user_chunks(
        cls, user_id: str, query_vector: list[float], top_k: int = 8
    ) -> list[dict[str, Any]]:
        """
        Cross-document semantic search across ALL documents owned by the user.
        Ownership filter is user_id ONLY (no document_id restriction), so the
        assistant can answer questions spanning the user's full upload history.
        """
        _load_memory_snapshot()
        client = _get_qdrant_client()

        if client:
            try:
                from qdrant_client.models import FieldCondition, Filter, MatchValue

                search_filter = Filter(
                    must=[FieldCondition(key="user_id", match=MatchValue(value=user_id))]
                )
                results = _qdrant_search_results(client, query_vector, search_filter, top_k)
                logger.info(
                    f"Qdrant Cross-Doc Search: Retrieved {len(results)} chunks (User: {user_id})."
                )
                return results
            except Exception as e:
                logger.error(
                    f"Qdrant cross-doc search error ({e}). Using in-memory fallback search."
                )

        results = _memory_search(user_id, query_vector, top_k)
        logger.info(
            f"In-Memory Cross-Doc Search: Retrieved {len(results)} chunks (User: {user_id})."
        )
        return results

    @classmethod
    def search_filtered_chunks(
        cls, user_id: str, document_ids: list[str], query_vector: list[float], top_k: int = 8
    ) -> list[dict[str, Any]]:
        """
        Multi-document search: user_id + document_id IN [...] .
        Used for compare / 'which documents mention' and for natural-language
        reference resolution (e.g. "my employment contract").
        """
        _load_memory_snapshot()
        if not document_ids:
            return cls.search_user_chunks(user_id, query_vector, top_k)
        # Normalise to unique
        document_ids = list(dict.fromkeys(document_ids))
        wanted = set(document_ids)
        client = _get_qdrant_client()
        if client:
            try:
                from qdrant_client.models import FieldCondition, Filter, MatchAny, MatchValue

                # Qdrant MatchAny covers "document_id IN list"
                try:
                    doc_condition = FieldCondition(
                        key="document_id", match=MatchAny(any=document_ids)
                    )
                except Exception:
                    # Fallback if MatchAny signature differs
                    doc_condition = FieldCondition(
                        key="document_id", match=MatchValue(value=document_ids[0])
                    )
                search_filter = Filter(
                    must=[
                        FieldCondition(key="user_id", match=MatchValue(value=user_id)),
                        doc_condition,
                    ]
                )
                results = _qdrant_search_results(
                    client, query_vector, search_filter, top_k, document_ids=wanted
                )
                # If Qdrant returned nothing due to MatchAny issue, fallback to cross-doc + filter
                if not results:
                    all_chunks = cls.search_user_chunks(user_id, query_vector, top_k * 3)
                    results = [c for c in all_chunks if c.get("document_id") in wanted][:top_k]
                logger.info(
                    f"Qdrant Filtered Search: Retrieved {len(results)} chunks for docs {document_ids} (User: {user_id})."
                )
                return results
            except Exception as e:
                logger.error(
                    f"Qdrant filtered search error ({e}). Using in-memory fallback search."
                )

        results = _memory_search(user_id, query_vector, top_k, document_ids=wanted)
        if not results:
            # Mirror the Qdrant path: broaden to the user-wide search, then
            # keep only the requested documents.
            broad = cls.search_user_chunks(user_id, query_vector, top_k * 3)
            results = [c for c in broad if c.get("document_id") in wanted][:top_k]
            if results:
                logger.info(
                    f"In-Memory Filtered Search: Broadened to user-wide, kept {len(results)} chunks for docs {document_ids}."
                )
                return results
        logger.info(
            f"In-Memory Filtered Search: Retrieved {len(results)} chunks for docs {document_ids}."
        )
        return results

    @classmethod
    def delete_document_vectors(cls, user_id: str, document_id: str) -> bool:
        """
        Deletes all vector embeddings for a specific document and user.
        """
        _load_memory_snapshot()
        client = _get_qdrant_client()
        if client:
            try:
                from qdrant_client.models import FieldCondition, Filter, MatchValue

                client.delete(
                    collection_name=COLLECTION_NAME,
                    points_selector=Filter(
                        must=[
                            FieldCondition(key="user_id", match=MatchValue(value=user_id)),
                            FieldCondition(key="document_id", match=MatchValue(value=document_id)),
                        ]
                    ),
                )
            except Exception as e:
                logger.error(f"Qdrant vector deletion error: {e}")

        # Purge from memory store
        keys_to_delete = [
            k
            for k, v in _in_memory_store.items()
            if v["payload"].get("user_id") == user_id
            and v["payload"].get("document_id") == document_id
        ]
        for k in keys_to_delete:
            del _in_memory_store[k]
        if keys_to_delete:
            _persist_memory_snapshot()

        return True

    @classmethod
    def count_document_vectors(cls, user_id: str, document_id: str) -> int:
        """Number of indexed vectors for a document (used for health checks)."""
        _load_memory_snapshot()
        client = _get_qdrant_client()
        if client:
            try:
                from qdrant_client.models import FieldCondition, Filter, MatchValue

                result = client.count(
                    collection_name=COLLECTION_NAME,
                    count_filter=Filter(
                        must=[
                            FieldCondition(key="user_id", match=MatchValue(value=user_id)),
                            FieldCondition(key="document_id", match=MatchValue(value=document_id)),
                        ]
                    ),
                )
                return int(result.count)
            except Exception as e:
                logger.warning(f"Qdrant vector count skipped ({e}).")
        return sum(
            1
            for v in _in_memory_store.values()
            if v["payload"].get("user_id") == user_id
            and v["payload"].get("document_id") == document_id
        )

    @classmethod
    def delete_user_vectors(cls, user_id: str) -> bool:
        _load_memory_snapshot()
        client = _get_qdrant_client()
        if client:
            try:
                from qdrant_client.models import FieldCondition, Filter, MatchValue

                client.delete(
                    collection_name=COLLECTION_NAME,
                    points_selector=Filter(
                        must=[FieldCondition(key="user_id", match=MatchValue(value=user_id))]
                    ),
                )
            except Exception as e:
                logger.error(f"Qdrant user vector deletion error: {e}")

        keys_to_delete = [
            k for k, v in _in_memory_store.items() if v["payload"].get("user_id") == user_id
        ]
        for k in keys_to_delete:
            del _in_memory_store[k]
        if keys_to_delete:
            _persist_memory_snapshot()

        return True

    @staticmethod
    def _cosine_similarity(vec_a: list[float], vec_b: list[float]) -> float:
        return _py_cosine_similarity(vec_a, vec_b)


def _py_cosine_similarity(vec_a: list[float], vec_b: list[float]) -> float:
    dot = sum(a * b for a, b in zip(vec_a, vec_b))
    norm_a = math.sqrt(sum(a * a for a in vec_a))
    norm_b = math.sqrt(sum(b * b for b in vec_b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)
