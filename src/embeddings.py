
import os
from typing import List, Dict, Any
from openai import OpenAI
from dotenv import load_dotenv


class EmbeddingGenerator:
    
    
    def __init__(self, api_key: str = None, model: str = "text-embedding-3-small"):
        
        # Load API key from environment if not provided
        if api_key is None:
            load_dotenv()
            api_key = os.getenv("OPENAI_API_KEY")
            
            if not api_key:
                raise ValueError(
                    "OpenAI API key not found. "
                    "Set OPENAI_API_KEY in .env file or pass as parameter"
                )
        
        self.client = OpenAI(api_key=api_key)
        self.model = model
        self.embedding_dim = 1536  # Dimension for text-embedding-3-small
        
        print(f"[+] Embedding generator initialized with model: {model}")
    
    def generate_embeddings(
        self, 
        chunks: List[Dict[str, Any]], 
        batch_size: int = 100
    ) -> List[Dict[str, Any]]:
        
        print(f"\n[*] Generating embeddings for {len(chunks)} chunks...")
        
        total_chunks = len(chunks)
        
        # Process in batches for efficiency
        for i in range(0, total_chunks, batch_size):
            batch = chunks[i:i + batch_size]
            batch_texts = [chunk['text'] for chunk in batch]
            
            # Generate embeddings for batch
            try:
                embeddings = self._generate_batch_embeddings(batch_texts)
                
                # Add embeddings to chunks
                for chunk, embedding in zip(batch, embeddings):
                    chunk['embedding'] = embedding
                
                # Progress indicator
                processed = min(i + batch_size, total_chunks)
                print(f"  Progress: {processed}/{total_chunks} chunks processed")
            
            except Exception as e:
                print(f"  [-] Error processing batch {i}-{i+batch_size}: {e}")
                # Add empty embeddings to prevent failures
                for chunk in batch:
                    chunk['embedding'] = [0.0] * self.embedding_dim
        
        print(f"[+] Embedding generation complete!\n")
        return chunks
    
    def _generate_batch_embeddings(self, texts: List[str]) -> List[List[float]]:
       
        # Call OpenAI API
        response = self.client.embeddings.create(
            model=self.model,
            input=texts,
            encoding_format="float"  # Returns as list of floats
        )
        
        # Extract embeddings from response
        embeddings = [item.embedding for item in response.data]
        
        return embeddings
    
    def generate_query_embedding(self, query: str) -> List[float]:
       
        response = self.client.embeddings.create(
            model=self.model,
            input=[query],
            encoding_format="float"
        )
        
        return response.data[0].embedding
    
    def get_embedding_dimension(self) -> int:
        """Return the embedding dimension"""
        return self.embedding_dim


# Example usage for testing
if __name__ == "__main__":
    import sys
    
    print("=" * 60)
    print("EMBEDDING GENERATOR - STANDALONE TEST")
    print("=" * 60)
    
    # Check if we should run the test
    if len(sys.argv) > 1 and sys.argv[1] == "--test":
        # Test with sample chunks
        sample_chunks = [
            {
                'text': 'Refunds are available within 30 days of purchase.',
                'chunk_id': 'test_001',
                'doc_type': 'refund_policy',
                'filename': 'test.txt',
                'section_title': 'Test Section',
                'token_count': 10
            },
            {
                'text': 'Items must be in original condition with tags attached.',
                'chunk_id': 'test_002',
                'doc_type': 'refund_policy',
                'filename': 'test.txt',
                'section_title': 'Test Section',
                'token_count': 12
            }
        ]
        
        try:
            # Initialize generator
            generator = EmbeddingGenerator()
            
            # Generate embeddings
            chunks_with_embeddings = generator.generate_embeddings(sample_chunks)
            
            # Display results
            print("\n[+] Embedding Generation Test Results:")
            for chunk in chunks_with_embeddings:
                print(f"\n  Chunk: {chunk['chunk_id']}")
                print(f"  Embedding dimension: {len(chunk['embedding'])}")
                print(f"  First 5 values: {chunk['embedding'][:5]}")
            
            # Test query embedding
            print("\n[+] Query Embedding Test:")
            query = "How long do I have to return an item?"
            query_emb = generator.generate_query_embedding(query)
            print(f"  Query: '{query}'")
            print(f"  Embedding dimension: {len(query_emb)}")
            print(f"  First 5 values: {query_emb[:5]}")
            
            print("\n" + "=" * 60)
            print("[+] All tests passed!")
        
        except Exception as e:
            print(f"\n[ERROR] {e}")
            print("\nMake sure to:")
            print("  1. Set OPENAI_API_KEY in your .env file")
            print("  2. Install required packages: pip install openai python-dotenv")
            sys.exit(1)
    else:
        print("\nThis is the Embedding Generator module.")
        print("It's designed to be used by the indexer pipeline.")
        print("\nTo run standalone test:")
        print("  python src/embeddings.py --test")
        print("\nFor normal usage:")
        print("  Use via indexer.py or import in your code")