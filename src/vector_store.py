

import chromadb
from chromadb.config import Settings
from typing import List, Dict, Optional, Any
import json


class ChromaVectorStore:
   
    
    def __init__(
        self, 
        persist_directory: str = "data/chroma_db",
        collection_name: str = "policy_documents"
    ):
        self.persist_directory = persist_directory
        self.collection_name = collection_name
        
        # Initialize ChromaDB client with persistence
        self.client = chromadb.PersistentClient(path=persist_directory)
        
        # Get or create collection
        # Using cosine similarity for semantic search
        self.collection = self.client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"}  # Cosine similarity for embeddings
        )
        
        print(f"✓ ChromaDB initialized at: {persist_directory}")
        print(f"✓ Collection: {collection_name} (Documents: {self.collection.count()})")
    
    def add_chunks(self, chunks: List[Dict[str, Any]]) -> None:
        
        # Prepare data for ChromaDB
        ids = []
        embeddings = []
        documents = []
        metadatas = []
        
        for chunk in chunks:
            ids.append(chunk['chunk_id'])
            embeddings.append(chunk['embedding'])
            documents.append(chunk['text'])
            
            # Store metadata (exclude embedding and text to save space)
            metadata = {
                'doc_type': chunk['doc_type'],
                'filename': chunk['filename'],
                'section_title': chunk['section_title'],
                'token_count': chunk['token_count']
            }
            metadatas.append(metadata)
        
        # Add to collection in batches (ChromaDB recommends <41666 per batch)
        batch_size = 5000
        total = len(ids)
        
        print(f"\n💾 Adding {total} chunks to vector store...")
        
        for i in range(0, total, batch_size):
            end_idx = min(i + batch_size, total)
            
            self.collection.add(
                ids=ids[i:end_idx],
                embeddings=embeddings[i:end_idx],
                documents=documents[i:end_idx],
                metadatas=metadatas[i:end_idx]
            )
            
            print(f"  Added batch: {i+1}-{end_idx}/{total}")
        
        print(f"✓ All chunks added to vector store!\n")
    
    def semantic_search(
        self, 
        query_embedding: List[float], 
        top_k: int = 10,
        filter_metadata: Optional[Dict] = None
    ) -> List[Dict[str, Any]]:
        
        # Query the collection
        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            where=filter_metadata,  # Metadata filtering
            include=['documents', 'metadatas', 'distances']
        )
        
        # Format results
        formatted_results = []
        
        # ChromaDB returns nested lists, so we extract the first element
        for i in range(len(results['ids'][0])):
            formatted_results.append({
                'chunk_id': results['ids'][0][i],
                'text': results['documents'][0][i],
                'metadata': results['metadatas'][0][i],
                'similarity_score': 1 - results['distances'][0][i],  # Convert distance to similarity
                'rank': i + 1
            })
        
        return formatted_results
    
    def get_chunk_by_id(self, chunk_id: str) -> Optional[Dict[str, Any]]:
        
        try:
            result = self.collection.get(
                ids=[chunk_id],
                include=['documents', 'metadatas', 'embeddings']
            )
            
            if result['ids']:
                return {
                    'chunk_id': result['ids'][0],
                    'text': result['documents'][0],
                    'metadata': result['metadatas'][0],
                    'embedding': result['embeddings'][0]
                }
        except Exception as e:
            print(f"Error retrieving chunk {chunk_id}: {e}")
        
        return None
    
    def delete_collection(self) -> None:
        """Delete the entire collection (useful for rebuilding)"""
        try:
            self.client.delete_collection(name=self.collection_name)
            print(f"✓ Collection '{self.collection_name}' deleted")
        except Exception as e:
            print(f"Error deleting collection: {e}")
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get statistics about the vector store
        
        Returns:
            Dict with collection statistics
        """
        count = self.collection.count()
        
        # Get sample to check metadata
        sample = self.collection.peek(limit=1)
        
        stats = {
            'total_chunks': count,
            'collection_name': self.collection_name,
            'persist_directory': self.persist_directory
        }
        
        if sample['metadatas']:
            # Get unique document types
            all_metadata = self.collection.get(include=['metadatas'])
            doc_types = set(m['doc_type'] for m in all_metadata['metadatas'])
            stats['document_types'] = list(doc_types)
            stats['documents_by_type'] = {
                dt: sum(1 for m in all_metadata['metadatas'] if m['doc_type'] == dt)
                for dt in doc_types
            }
        
        return stats
    
    def rebuild_index(self, chunks: List[Dict[str, Any]]) -> None:
        
        print("\n Rebuilding vector store index...")
        
        # Delete existing collection
        self.delete_collection()
        
        # Recreate collection
        self.collection = self.client.get_or_create_collection(
            name=self.collection_name,
            metadata={"hnsw:space": "cosine"}
        )
        
        # Add all chunks
        self.add_chunks(chunks)
        
        print("✓ Index rebuild complete!")


# Example usage for testing
if __name__ == "__main__":
    # Sample chunks with embeddings (normally from embedding generator)
    sample_chunks = [
        {
            'chunk_id': 'refund_001',
            'text': 'Refunds are available within 30 days of purchase.',
            'doc_type': 'refund_policy',
            'filename': 'refund_policy.txt',
            'section_title': 'Refund Eligibility',
            'token_count': 20,
            'embedding': [0.1] * 1536  # Mock embedding
        },
        {
            'chunk_id': 'shipping_001',
            'text': 'Standard shipping takes 5-7 business days.',
            'doc_type': 'shipping_policy',
            'filename': 'shipping_policy.txt',
            'section_title': 'Delivery Times',
            'token_count': 15,
            'embedding': [0.2] * 1536  # Mock embedding
        }
    ]
    
    # Initialize vector store
    vector_store = ChromaVectorStore(
        persist_directory="data/test_chroma_db",
        collection_name="test_collection"
    )
    
    # Add chunks
    vector_store.add_chunks(sample_chunks)
    
    # Get statistics
    stats = vector_store.get_stats()
    print("\n Vector Store Statistics:")
    print(json.dumps(stats, indent=2))
    
    # Test semantic search (with mock query embedding)
    query_embedding = [0.15] * 1536
    results = vector_store.semantic_search(query_embedding, top_k=2)
    
    print("\n Search Results:")
    for result in results:
        print(f"\n  Rank {result['rank']}: {result['chunk_id']}")
        print(f"  Similarity: {result['similarity_score']:.4f}")
        print(f"  Text: {result['text'][:80]}...")
    
    # Cleanup
    # vector_store.delete_collection()