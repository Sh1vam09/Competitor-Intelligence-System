"""
Semantic Embedding Module.

Uses Jina embeddings for semantic representation and Pinecone cloud
for vector similarity search. Supports building, querying, and
managing a cloud-based vector index.
"""

import base64
from typing import Optional, Any

import numpy as np
import requests

try:
    from pinecone import Pinecone, ServerlessSpec
    from langchain_pinecone import PineconeVectorStore
    from langchain_core.documents import Document
    from langchain_core.embeddings import Embeddings
except ImportError:
    Pinecone = None
    ServerlessSpec = None
    PineconeVectorStore = None
    Document = None
    Embeddings = None

from utils.config import (
    JINA_API_KEY,
    JINA_EMBEDDING_MODEL,
    PINECONE_API_KEY,
    PINECONE_ENVIRONMENT,
    PINECONE_INDEX_NAME,
    EMBEDDING_DIMENSION,
)
from utils.logger import get_logger

logger = get_logger(__name__)


class JinaEmbeddings(Embeddings):
    """
    LangChain-compatible Jina embeddings wrapper for v5 API.
    """

    def __init__(self, api_key: str, model_name: str):
        self.api_key = api_key
        self.model_name = model_name
        self.dimension = None  # Will be detected at runtime

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Embed a list of documents."""
        return self._call_jina_api(texts)

    def embed_query(self, text: str) -> list[float]:
        """Embed a single query."""
        return self._call_jina_api([text])[0]

    def _call_jina_api(self, texts: list[str]) -> list[list[float]]:
        """Call Jina API for embeddings."""
        if not self.api_key:
            logger.warning("Jina API key not set")
            return [[] for _ in texts]

        try:
            url = "https://api.jina.ai/v1/embeddings"
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            }
            payload = {
                "model": self.model_name,
                "input": texts,
            }

            response = requests.post(url, json=payload, headers=headers, timeout=30)
            response.raise_for_status()

            data = response.json()
            embeddings = [item["embedding"] for item in data["data"]]

            # Detect dimension at runtime
            if embeddings and self.dimension is None:
                self.dimension = len(embeddings[0])
                logger.info(f"Detected Jina embedding dimension: {self.dimension}")

            return embeddings
        except Exception as e:
            logger.error(f"Jina API encoding failed: {e}")
            # Return random embeddings as fallback
            dim = self.dimension or 1024
            return [list(np.random.randn(dim).astype(np.float32)) for _ in texts]


class EmbeddingEngine:
    """
    Manages embedding generation via Jina API
    and similarity search via LangChain's PineconeVectorStore.
    """

    def __init__(self, model_name: str = JINA_EMBEDDING_MODEL):
        """
        Initialize the embedding engine.

        Args:
            model_name: Jina embedding model identifier.
        """
        logger.info("Loading Jina embedding model: %s", model_name)
        self.api_key = JINA_API_KEY
        self.model_name = model_name
        self.dimension = EMBEDDING_DIMENSION
        self.pinecone: Optional[Any] = None
        self.index: Optional[Any] = None
        self.vector_store: Optional[Any] = None
        self.embeddings: Optional[JinaEmbeddings] = None
        self._init_pinecone()

    def _init_pinecone(self) -> None:
        """Initialize Pinecone connection and get/create index."""
        if not PINECONE_API_KEY:
            logger.warning("PINECONE_API_KEY not set — Pinecone operations will fail")
            return

        try:
            self.pinecone = Pinecone(api_key=PINECONE_API_KEY)
            logger.info("Pinecone initialized")

            # Initialize LangChain embeddings
            self.embeddings = JinaEmbeddings(
                api_key=self.api_key, model_name=self.model_name
            )
        except Exception as e:
            logger.warning("Failed to initialize Pinecone: %s", e)

    def encode(self, texts: list[str]) -> np.ndarray:
        """
        Generate embeddings for a list of text strings using Jina API.

        Args:
            texts: List of text strings to embed.

        Returns:
            NumPy array of shape (len(texts), dimension).
        """
        if self.embeddings is None:
            logger.warning("Embeddings not initialized, returning zeros")
            return np.zeros((len(texts), self.dimension), dtype=np.float32)

        try:
            embeddings = self.embeddings.embed_documents(texts)
            return np.array(embeddings, dtype=np.float32)
        except Exception as e:
            logger.error("Jina API encoding failed: %s", e)
            return np.random.randn(len(texts), self.dimension).astype(np.float32)

    def encode_single(self, text: str) -> np.ndarray:
        """
        Generate embedding for a single text string.

        Args:
            text: Text string to embed.

        Returns:
            1D NumPy array of shape (dimension,).
        """
        return self.encode([text])[0]

    def build_profile_embedding(self, profile: dict) -> np.ndarray:
        """
        Build a composite embedding from key business profile fields.

        Args:
            profile: Business profile dictionary.

        Returns:
            Averaged embedding vector as NumPy array.
        """
        texts = []

        if profile.get("industry"):
            industry_text = f"Industry: {profile['industry']}"
            texts.append(industry_text)
            texts.append(industry_text)  # Double-weight industry
        if profile.get("target_customer"):
            texts.append(f"Target customer: {profile['target_customer']}")
        if profile.get("products_services"):
            products = profile["products_services"]
            if isinstance(products, list):
                texts.append(
                    f"Products and services: {', '.join(str(p) for p in products)}"
                )
            else:
                texts.append(f"Products and services: {products}")
        if profile.get("positioning_statement"):
            texts.append(str(profile["positioning_statement"]))
        if profile.get("value_proposition"):
            texts.append(str(profile["value_proposition"]))
        if profile.get("key_features"):
            features = profile["key_features"]
            if isinstance(features, list):
                texts.append(", ".join(str(f) for f in features))
            else:
                texts.append(str(features))
        if profile.get("marketing_style"):
            texts.append(str(profile["marketing_style"]))
        if profile.get("brand_name") and profile.get("industry"):
            texts.append(f"{profile['brand_name']} is a {profile['industry']} company")

        if not texts:
            logger.warning("No text available for profile embedding")
            return np.zeros(self.dimension, dtype=np.float32)

        # Encode all texts and average
        embeddings = self.encode(texts)
        avg_embedding = np.mean(embeddings, axis=0).astype(np.float32)

        # L2 normalize the averaged vector
        norm = np.linalg.norm(avg_embedding)
        if norm > 0:
            avg_embedding = avg_embedding / norm

        return avg_embedding

    def create_index(self) -> None:
        """Create a new Pinecone index if it doesn't exist."""
        if not self.pinecone:
            logger.warning("Pinecone not initialized, skipping index creation")
            return

        try:
            # Get actual dimension from Jina embeddings
            actual_dimension = (
                self.embeddings.dimension if self.embeddings else self.dimension
            )
            if actual_dimension and actual_dimension != self.dimension:
                logger.info(
                    f"Updating dimension from {self.dimension} to {actual_dimension}"
                )
                self.dimension = actual_dimension

            existing_indexes = [index.name for index in self.pinecone.list_indexes()]
            if PINECONE_INDEX_NAME not in existing_indexes:
                self.pinecone.create_index(
                    name=PINECONE_INDEX_NAME,
                    dimension=self.dimension,
                    metric="cosine",
                    spec=ServerlessSpec(cloud="aws", region=PINECONE_ENVIRONMENT),
                )
                logger.info("Created Pinecone index: %s", PINECONE_INDEX_NAME)
            else:
                logger.info("Pinecone index already exists: %s", PINECONE_INDEX_NAME)

            self.index = self.pinecone.Index(PINECONE_INDEX_NAME)

            # Create LangChain PineconeVectorStore
            if self.embeddings and PineconeVectorStore:
                self.vector_store = PineconeVectorStore(
                    index=self.index,
                    embedding=self.embeddings,
                    text_key="text",
                )

            logger.info("Connected to Pinecone index: %s", PINECONE_INDEX_NAME)
        except Exception as e:
            logger.error("Failed to create Pinecone index: %s", e)

    def add_to_index(self, embedding: np.ndarray, meta: dict) -> None:
        """
        Add a single embedding vector to the Pinecone index.

        Args:
            embedding: Embedding vector (1D array).
            meta: Metadata dict to associate with this vector.
        """
        if not self.pinecone:
            logger.warning("Pinecone not initialized, skipping add_to_index")
            return

        if self.index is None:
            self.create_index()

        try:
            # Generate a unique ID for this vector
            vector_id = str(hash(str(meta.get("url", meta.get("name", "unknown")))))
            # Convert numpy array to list for Pinecone
            vector_list = embedding.tolist()

            # Upsert the vector
            self.index.upsert(
                vectors=[{"id": vector_id, "values": vector_list, "metadata": meta}]
            )
            logger.debug("Added vector to Pinecone index: %s", vector_id)
        except Exception as e:
            logger.error("Failed to add vector to Pinecone: %s", e)

    def search(self, query_embedding: np.ndarray, top_k: int = 10) -> list[dict]:
        """
        Search the Pinecone index for the most similar vectors.

        Args:
            query_embedding: Query vector (1D array).
            top_k: Number of results to return.

        Returns:
            List of dicts with 'score' and metadata from matching entries.
        """
        if not self.pinecone or self.index is None:
            logger.warning("Pinecone not initialized or index not created")
            return []

        try:
            query_vector = query_embedding.tolist()
            results = self.index.query(
                vector=query_vector, top_k=top_k, include_metadata=True
            )

            formatted_results = []
            for match in results.get("matches", []):
                result = {
                    **match.get("metadata", {}),
                    "similarity_score": match.get("score", 0.0),
                }
                formatted_results.append(result)

            return formatted_results
        except Exception as e:
            logger.error("Pinecone search failed: %s", e)
            return []

    def get_retriever(self, k: int = 10, search_kwargs: dict = None):
        """
        Get a LangChain retriever for similarity search.

        Args:
            k: Number of results to return.
            search_kwargs: Additional search parameters.

        Returns:
            LangChain retriever instance.
        """
        if self.vector_store is None:
            logger.warning("Vector store not initialized, cannot create retriever")
            return None

        try:
            retriever_kwargs = {"k": k}
            if search_kwargs:
                retriever_kwargs.update(search_kwargs)

            retriever = self.vector_store.as_retriever(**retriever_kwargs)
            logger.info("Created retriever with k=%d", k)
            return retriever
        except Exception as e:
            logger.error("Failed to create retriever: %s", e)
            return None

    def save_index(self, name: str = "default") -> str:
        """
        Pinecone indexes are cloud-based and persist automatically.

        Args:
            name: Not used (Pinecone is cloud-native).

        Returns:
            Path indicating Pinecone cloud storage.
        """
        logger.info("Pinecone index is cloud-based and persists automatically")
        return "pinecone-cloud"

    def load_index(self, name: str = "default") -> bool:
        """
        Connect to existing Pinecone index.

        Args:
            name: Name of the Pinecone index.

        Returns:
            True if connected successfully.
        """
        if not self.pinecone:
            return False

        try:
            self.index = self.pinecone.Index(name)

            # Create LangChain PineconeVectorStore
            if self.embeddings and PineconeVectorStore:
                self.vector_store = PineconeVectorStore(
                    index=self.index,
                    embedding=self.embeddings,
                    text_key="text",
                )

            logger.info("Connected to Pinecone index: %s", name)
            return True
        except Exception as e:
            logger.error("Failed to connect to Pinecone index: %s", e)
            return False

    @staticmethod
    def embedding_to_bytes(embedding: np.ndarray) -> bytes:
        """
        Serialize an embedding vector to bytes for SQLite storage.

        Args:
            embedding: NumPy array to serialize.

        Returns:
            Bytes representation.
        """
        return embedding.tobytes()

    @staticmethod
    def bytes_to_embedding(data: bytes) -> np.ndarray:
        """
        Deserialize bytes back to an embedding vector.

        Args:
            data: Raw bytes from SQLite.

        Returns:
            NumPy array.
        """
        return np.frombuffer(data, dtype=np.float32)

    def compute_similarity(
        self, embedding_a: np.ndarray, embedding_b: np.ndarray
    ) -> float:
        """
        Compute cosine similarity between two embeddings.

        Args:
            embedding_a: First embedding vector.
            embedding_b: Second embedding vector.

        Returns:
            Cosine similarity score (float).
        """
        return float(np.dot(embedding_a, embedding_b))
