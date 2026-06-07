import logging

from chromadb import EmbeddingFunction
from chromadb.api import ClientAPI

from src.core.enums import NoticeField
from src.core.interfaces import SearchEngineProtocol
from src.core.utils import extract_text_for_embedding

logger = logging.getLogger(__name__)


class SemanticEngine(SearchEngineProtocol):
    """Semantic indexing and search engine over tender notices.

    Wraps ChromaDB to provide vector-based similarity search using
    sentence embeddings. Notices are indexed by concatenating their
    title and description into a single text representation.
    Supports multilingual queries through the configured embedding model.

    Attributes:
        embedding_func: Callable that converts text into dense vectors.
        client: ChromaDB client managing the persistent vector store.
        collection: The ChromaDB collection holding all indexed embeddings.
    """

    def __init__(
        self, client: ClientAPI, embedding_func: EmbeddingFunction, collection_name: str
    ) -> None:
        """Initializes the engine and connects to the ChromaDB collection.

        Creates the collection if it does not already exist, making
        initialization safe to call on both fresh and existing databases.

        Args:
            client: An active ChromaDB client instance.
            embedding_func: Embedding function used to vectorize notice text.
            collection_name: Name of the ChromaDB collection to use or create.
        """
        self.embedding_func = embedding_func
        self.client = client
        self.collection = self.client.get_or_create_collection(
            name=collection_name, embedding_function=self.embedding_func
        )

    def add_notices(self, notices: list[dict]) -> None:
        """Computes and stores embeddings for a batch of notices.

        Extracts text from each notice, generates embeddings via the
        configured function, and upserts them into ChromaDB. Uses upsert
        rather than insert to remain idempotent on re-runs.

        Args:
            notices: List of validated notice dictionaries with keys
                matching StandardNotice field names.
        """
        if not notices:
            logger.warning("add_notices called with empty list. Nothing to index.")
            return

        chroma_ids = []
        texts = []
        for notice in notices:
            notice_id = notice.get(NoticeField.ID)
            if notice_id:
                chroma_ids.append(notice_id)
                texts.append(extract_text_for_embedding(notice))

        if chroma_ids:
            seen = set()
            unique_ids = []
            unique_texts = []
            for cid, text in zip(chroma_ids, texts):
                if cid not in seen:
                    seen.add(cid)
                    unique_ids.append(cid)
                    unique_texts.append(text)
            chroma_ids = unique_ids
            texts = unique_texts
            embeddings = self.embedding_func(texts)
            logger.info(f"Indexing {len(chroma_ids)} notices into ChromaDB.")
            self.collection.upsert(ids=chroma_ids, embeddings=embeddings)
            logger.info("ChromaDB indexing complete.")
        else:
            logger.warning("No valid (id + text) pairs found. Nothing indexed.")

    def search(self, query: str, k: int = 5) -> list[dict]:
        """Finds the k most semantically similar notices for a query.

        Embeds the query using the same function used during indexing
        and retrieves the nearest neighbours from ChromaDB. Returns
        cosine distances rather than similarities — lower is better.

        Args:
            query: Natural language search query.
            k: Number of results to return.

        Returns:
            A list of dicts, each containing 'id' and 'score' keys,
            where score is the cosine distance rounded to 4 decimal places.
        """
        logger.info(f"Searching ChromaDB for: '{query}'")

        results = self.collection.query(
            query_texts=[query],
            n_results=k,
        )
        raw_distances = results["distances"]
        if raw_distances:
            found_ids = results["ids"][0]
            found_distances = raw_distances[0]
        else:
            return []

        return [
            {"id": doc_id, "score": round(distance, 4)}
            for doc_id, distance in zip(found_ids, found_distances)
        ]

    def search_multi_query(self, queries: list[str], k: int = 50) -> dict[str, float]:
        """Finds the best semantic match per notice across multiple queries.

        Queries ChromaDB once with all keywords simultaneously and returns
        the maximum similarity score per notice ID across all queries.
        This is the core of profile-based search — a notice matches the
        profile if it is close to ANY of the profile's keywords.

        Args:
            queries: List of keyword strings to search with simultaneously.
            k: Number of candidates to retrieve per query.

        Returns:
            A dict mapping notice ID to its best similarity score (0 to 1),
            where higher is more relevant.
        """
        if not queries:
            return {}

        logger.info(f"Multi-query search with {len(queries)} keywords.")

        results = self.collection.query(
            query_texts=queries,
            n_results=k,
        )

        best_scores: dict[str, float] = {}
        res_distances = results["distances"]
        if not res_distances:
            res_distances = []
        for ids_per_query, distances_per_query in zip(results["ids"], res_distances):
            for doc_id, distance in zip(ids_per_query, distances_per_query):
                similarity = max(0.0, round(1.0 - distance, 4))
                if doc_id not in best_scores or similarity > best_scores[doc_id]:
                    best_scores[doc_id] = similarity

        logger.info(f"Multi-query returned {len(best_scores)} unique candidates.")
        return best_scores
