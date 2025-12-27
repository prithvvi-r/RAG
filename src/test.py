import os
import json
from pathlib import Path
import sys

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))


from vector_store import ChromaVectorStore
from embeddings import EmbeddingGenerator
from retrieval import RetrievalPipeline
from rag_pipeline import RAGPipeline
from langchain_community.retrievers import BM25Retriever
from langchain_core.documents import Document

# Step 1: Load Vector Store
vector_store = ChromaVectorStore(
    persist_directory="data/chroma_db",
    collection_name="policy_documents"
)

# Step 2: Load BM25 Retriever
metadata_path = Path("data/chroma_db/chunks_metadata.json")
with open(metadata_path, 'r', encoding='utf-8') as f:
    chunks_metadata = json.load(f)

bm25_documents = []
for chunk in chunks_metadata:
    doc = Document(
        page_content=chunk['text'],
        metadata={
            'chunk_id': chunk['chunk_id'],
            'doc_type': chunk['doc_type'],
            'filename': chunk['filename'],
            'section_title': chunk['section_title'],
            'token_count': chunk['token_count']
        }
    )
    bm25_documents.append(doc)

bm25_retriever = BM25Retriever.from_documents(
    documents=bm25_documents,
    k=10
)

# Step 3: Initialize Embedding Generator
embedding_generator = EmbeddingGenerator()

# Step 4: Create Retrieval Pipeline
retriever = RetrievalPipeline(
    vector_store=vector_store,
    bm25_retriever=bm25_retriever,
    embedding_generator=embedding_generator
)

# Step 5: Create RAG Pipeline
rag_pipeline = RAGPipeline(
    retriever=retriever,
    llm_model="gpt-4o-mini"
)

# Step 6: Run a query
response = rag_pipeline.query("How long do I have to return an item?", verbose=True)
print(rag_pipeline.format_response(response))

