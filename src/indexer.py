"""
Indexer Module
Integrates document loading, chunking, embedding, and indexing
Main pipeline to build the RAG knowledge base
"""

import os
import json
from typing import List, Dict, Any
from pathlib import Path

# Handle imports for both module and script execution
try:
    from .document_loader import DocumentLoader
    from .chunking import PolicyDocumentChunker
    from .embeddings import EmbeddingGenerator
    from .vector_store import ChromaVectorStore
except ImportError:
    # Fallback for script execution
    from document_loader import DocumentLoader
    from chunking import PolicyDocumentChunker
    from embeddings import EmbeddingGenerator
    from vector_store import ChromaVectorStore

from langchain_community.retrievers import BM25Retriever
from langchain_core.documents import Document


class RAGIndexer:
    
    
    def __init__(
        self,
        data_dir: str = "data/raw",
        persist_dir: str = "data/chroma_db",
        collection_name: str = "policy_documents",
        max_chunk_tokens: int = 800
    ):
        
        self.data_dir = data_dir
        self.persist_dir = persist_dir
        
        # Initialize components
        print("[*] Initializing RAG Indexer...")
        print("="*60)
        
        self.loader = DocumentLoader(data_dir)
        self.chunker = PolicyDocumentChunker(max_chunk_tokens=max_chunk_tokens)
        self.embedding_generator = EmbeddingGenerator()
        self.vector_store = ChromaVectorStore(
            persist_directory=persist_dir,
            collection_name=collection_name
        )
        self.bm25_retriever = None  # Will be initialized after chunks are ready
        
        print("="*60)
        print("[+] All components initialized!\n")
    
    def build_index(self, rebuild: bool = False) -> Dict[str, Any]:
        
        print("\n" + "="*70)
        print("[*] BUILDING RAG INDEX")
        print("="*70)
        
        # Step 1: Load documents
        print("\n[STEP 1] Loading Documents")
        print("-"*70)
        documents = self.loader.load_documents()
        
        if not documents:
            raise ValueError("No documents found! Add policy documents to data/raw/")
        
        # Step 2: Chunk documents
        print("\n[STEP 2] Chunking Documents")
        print("-"*70)
        chunks = self.chunker.chunk_documents(documents)
        
        # Step 3: Generate embeddings
        print("\n[STEP 3] Generating Embeddings")
        print("-"*70)
        chunks_with_embeddings = self.embedding_generator.generate_embeddings(
            chunks, 
            batch_size=100
        )
        
        # Step 4: Index in vector store
        print("\n[STEP 4] Indexing in Vector Store (ChromaDB)")
        print("-"*70)
        
        if rebuild:
            self.vector_store.rebuild_index(chunks_with_embeddings)
        else:
            # Check if collection already has data
            if self.vector_store.collection.count() > 0:
                print("[!] Warning: Collection already contains data!")
                print("    Use rebuild=True to replace existing index")
                response = input("    Continue and add to existing? (y/n): ")
                if response.lower() != 'y':
                    print("    Indexing cancelled.")
                    return {}
            
            self.vector_store.add_chunks(chunks_with_embeddings)
        
        # Step 5: Index in BM25
        print("\n[STEP 5] Building BM25 Index")
        print("-"*70)
        
        # Convert chunks to LangChain Documents for BM25
        bm25_documents = []
        for chunk in chunks_with_embeddings:
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
        
        # Create BM25 retriever from documents
        self.bm25_retriever = BM25Retriever.from_documents(
            documents=bm25_documents,
            k=10  # Default number of documents to retrieve
        )
        print(f"  [+] BM25 index built with {len(bm25_documents)} documents")
        
        # Step 6: Save chunks to disk for BM25 persistence
        self._save_chunks_metadata(chunks_with_embeddings)
        
        # Get statistics
        stats = self._get_index_stats(documents, chunks_with_embeddings)
        
        # Display final summary
        print("\n" + "="*70)
        print("[+] INDEX BUILD COMPLETE!")
        print("="*70)
        self._display_stats(stats)
        
        return stats
    
    def _save_chunks_metadata(self, chunks: List[Dict[str, Any]]) -> None:
       
        metadata_path = Path(self.persist_dir) / "chunks_metadata.json"
        metadata_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Extract only necessary fields (no embeddings to save space)
        chunks_metadata = [
            {
                'chunk_id': chunk['chunk_id'],
                'text': chunk['text'],
                'doc_type': chunk['doc_type'],
                'filename': chunk['filename'],
                'section_title': chunk['section_title'],
                'token_count': chunk['token_count']
            }
            for chunk in chunks
        ]
        
        with open(metadata_path, 'w', encoding='utf-8') as f:
            json.dump(chunks_metadata, f, indent=2)
        
        print(f"  [+] Chunk metadata saved to: {metadata_path}")
    
    def load_chunks_metadata(self) -> List[Dict[str, Any]]:
        
        metadata_path = Path(self.persist_dir) / "chunks_metadata.json"
        
        if not metadata_path.exists():
            raise FileNotFoundError(
                f"Chunk metadata not found at {metadata_path}. "
                "Run build_index() first."
            )
        
        with open(metadata_path, 'r', encoding='utf-8') as f:
            chunks_metadata = json.load(f)
        
        return chunks_metadata
    
    def _get_index_stats(
        self, 
        documents: List[Dict[str, str]], 
        chunks: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Collect indexing statistics"""
        
        # Document statistics
        doc_types = {}
        for doc in documents:
            doc_type = doc['doc_type']
            doc_types[doc_type] = doc_types.get(doc_type, 0) + 1
        
        # Chunk statistics
        chunks_by_doc = {}
        total_tokens = 0
        for chunk in chunks:
            doc_type = chunk['doc_type']
            chunks_by_doc[doc_type] = chunks_by_doc.get(doc_type, 0) + 1
            total_tokens += chunk['token_count']
        
        # Vector store stats
        vs_stats = self.vector_store.get_stats()
        
        return {
            'total_documents': len(documents),
            'document_types': doc_types,
            'total_chunks': len(chunks),
            'chunks_by_document': chunks_by_doc,
            'avg_tokens_per_chunk': total_tokens / len(chunks) if chunks else 0,
            'total_tokens': total_tokens,
            'vector_store': vs_stats
        }
    
    def _display_stats(self, stats: Dict[str, Any]) -> None:
        """Display indexing statistics in a readable format"""
        
        print(f"\n[STATS] INDEXING STATISTICS")
        print(f"{'─'*70}")
        
        print(f"\n  Documents:")
        print(f"    Total: {stats['total_documents']}")
        for doc_type, count in stats['document_types'].items():
            print(f"    - {doc_type}: {count}")
        
        print(f"\n  Chunks:")
        print(f"    Total: {stats['total_chunks']}")
        print(f"    Avg tokens per chunk: {stats['avg_tokens_per_chunk']:.0f}")
        print(f"    Total tokens: {stats['total_tokens']:,}")
        
        print(f"\n  By Document Type:")
        for doc_type, count in stats['chunks_by_document'].items():
            print(f"    - {doc_type}: {count} chunks")
        
        print(f"\n  Vector Store:")
        print(f"    Collection: {stats['vector_store']['collection_name']}")
        print(f"    Total vectors: {stats['vector_store']['total_chunks']}")
        print(f"    Location: {stats['vector_store']['persist_directory']}")
        
        print(f"\n{'─'*70}")


# Main execution for building index
if __name__ == "__main__":
    import sys
    from pathlib import Path
    
    # Add src directory to path for script execution
    src_dir = Path(__file__).parent
    if str(src_dir) not in sys.path:
        sys.path.insert(0, str(src_dir))
    
    # Parse command line arguments
    rebuild = "--rebuild" in sys.argv
    
    try:
        # Initialize indexer
        indexer = RAGIndexer(
            data_dir="data/raw",
            persist_dir="data/chroma_db",
            max_chunk_tokens=800
        )
        
        # Build index
        stats = indexer.build_index(rebuild=rebuild)
        
        print("\n[+] Indexing completed successfully!")
        print("\nNext steps:")
        print("  1. Test retrieval with: python src/retrieval.py")
        print("  2. Run evaluation with: python evaluation/evaluate.py")
        
    except FileNotFoundError as e:
        print(f"\n[ERROR] {e}")
        print("\nMake sure you have policy documents in data/raw/")
        print("Expected files: refund_policy.txt, shipping_policy.txt, etc.")
        sys.exit(1)
    
    except Exception as e:
        print(f"\n[ERROR] Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)