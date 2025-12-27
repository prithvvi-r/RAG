"""
Retrieval Pipeline
Multi-Query Expansion + Hybrid Retrieval + RRF Fusion
"""

import os
from typing import List, Dict, Any
from collections import defaultdict

from dotenv import load_dotenv
from pydantic import BaseModel
from openai import OpenAI

load_dotenv()


# ───────────────────────────────────────────────────────────────
# Structured output for query expansion
# ───────────────────────────────────────────────────────────────

class QueryVariations(BaseModel):
    queries: List[str]


# ───────────────────────────────────────────────────────────────
# Retrieval Pipeline
# ───────────────────────────────────────────────────────────────

class RetrievalPipeline:
    """
    Retrieval-only pipeline:
    - Query expansion (LLM)
    - Vector search (Chroma)
    - BM25 search
    - Keyword overlap boost
    - Reciprocal Rank Fusion (RRF)
    """

    def __init__(
        self,
        vector_store,
        bm25_retriever,
        embedding_generator,
        llm_model: str = "gpt-4o-mini",
        rrf_k: int = 60
    ):
        self.vector_store = vector_store
        self.bm25 = bm25_retriever
        self.embedding_generator = embedding_generator
        self.rrf_k = rrf_k

        self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.llm_model = llm_model

        print("[+] RetrievalPipeline initialized")
        print("  - Multi-query expansion")
        print("  - BM25 + Vector + Keyword")
        print("  - Fusion: RRF")

    # -----------------------------------------------------------

    def retrieve(
        self,
        query: str,
        top_k: int = 5,
        verbose: bool = False
    ) -> List[Dict[str, Any]]:

        if verbose:
            print("\n[*] RETRIEVAL PIPELINE")
            print(f"Query: {query}")

        # 1️⃣ Expand query
        queries = self._expand_query(query)

        if verbose:
            print("\n[*] Generated query variations:")
            for q in queries:
                print(f"  - {q}")

        # 2️⃣ Collect results from all retrievers
        vector_results = []
        bm25_results = []

        for q in queries:
            # Vector search
            q_emb = self.embedding_generator.generate_query_embedding(q)
            vs_results = self.vector_store.semantic_search(q_emb, top_k=top_k * 2)
            # Convert to format with 'id' field
            vector_results.append([
                {
                    'id': doc['chunk_id'],
                    'text': doc['text'],
                    'metadata': doc['metadata']
                }
                for doc in vs_results
            ])

            # BM25 search - BM25Retriever uses invoke method
            from langchain_core.documents import Document
            bm25_docs = self.bm25.invoke(q)
            bm25_results.append([
                {
                    'id': doc.metadata.get('chunk_id', doc.id if hasattr(doc, 'id') else str(hash(doc.page_content))),
                    'text': doc.page_content,
                    'metadata': doc.metadata
                }
                for doc in bm25_docs[:top_k * 2]
            ])

        # 3️⃣ Fuse results
        fused = self._rrf_fusion(
            vector_results=vector_results,
            bm25_results=bm25_results,
            original_query=query
        )

        return fused[:top_k]

    # -----------------------------------------------------------

    def _expand_query(self, query: str) -> List[str]:
        """
        Generate multiple semantic variations of a query
        """

        prompt = f"""
Generate 3 alternative search queries that rephrase or
approach the same intent as the original question.

Original query:
{query}

Return only the rewritten queries.
"""

        response = self.client.beta.chat.completions.parse(
            model=self.llm_model,
            messages=[{"role": "user", "content": prompt}],
            response_format=QueryVariations,
            temperature=0.0
        )

        return [query] + response.choices[0].message.parsed.queries

    # -----------------------------------------------------------

    def _rrf_fusion(
        self,
        vector_results: List[List[Dict]],
        bm25_results: List[List[Dict]],
        original_query: str
    ) -> List[Dict]:

        scores = defaultdict(float)
        doc_map = {}

        def add_rrf(results):
            for docs in results:
                for rank, doc in enumerate(docs):
                    doc_id = doc["id"]
                    doc_map[doc_id] = doc
                    scores[doc_id] += 1 / (self.rrf_k + rank + 1)

        add_rrf(vector_results)
        add_rrf(bm25_results)

        # Keyword overlap boost (cheap precision)
        query_terms = set(original_query.lower().split())
        for doc_id, doc in doc_map.items():
            text = doc["text"].lower()
            overlap = sum(1 for t in query_terms if t in text)
            scores[doc_id] += overlap * 0.1

        ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)

        return [doc_map[doc_id] for doc_id, _ in ranked]
