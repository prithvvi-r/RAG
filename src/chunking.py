"""
Chunking Module
Implements header-based semantic chunking with recursive fallback
Optimized for policy documents with clear section structure
"""

import re
from typing import List, Dict, Any
import tiktoken


class PolicyDocumentChunker:
    """
    Header-based semantic chunking for policy documents
    Falls back to recursive chunking for oversized sections
    """
    
    def __init__(
        self, 
        max_chunk_tokens: int = 800,
        min_chunk_tokens: int = 100,
        overlap_tokens: int = 100,
        encoding_name: str = "cl100k_base"  # OpenAI's tokenizer
    ):
        self.max_chunk_tokens = max_chunk_tokens
        self.min_chunk_tokens = min_chunk_tokens
        self.overlap_tokens = overlap_tokens
        
        # Initialize tokenizer
        try:
            self.encoding = tiktoken.get_encoding(encoding_name)
        except Exception:
            print("Warning: tiktoken not available, using rough estimation")
            self.encoding = None
    
    def chunk_documents(self, documents: List[Dict[str, str]]) -> List[Dict[str, Any]]:
     
        all_chunks = []
        
        for doc in documents:
            doc_chunks = self._chunk_single_document(doc)
            all_chunks.extend(doc_chunks)
        
        print(f"\n[*] Total chunks created: {len(all_chunks)}")
        print(f"[*] Avg tokens per chunk: {sum(c['token_count'] for c in all_chunks) / len(all_chunks):.0f}")
        
        return all_chunks
    
    def _chunk_single_document(self, document: Dict[str, str]) -> List[Dict[str, Any]]:
        
        content = document['content']
        chunks = []
        
        # Step 1: Detect sections using header patterns
        sections = self._detect_sections(content)
        
        print(f"\n  Chunking {document['filename']}: {len(sections)} sections detected")
        
        # Step 2: Process each section
        for section_idx, section in enumerate(sections):
            section_text = section['text']
            section_title = section['title']
            
            # Count tokens in this section
            token_count = self._count_tokens(section_text)
            
            # If section is small enough, keep as single chunk
            if token_count <= self.max_chunk_tokens:
                chunks.append({
                    'text': section_text,
                    'doc_type': document['doc_type'],
                    'filename': document['filename'],
                    'section_title': section_title,
                    'chunk_id': f"{document['doc_type']}_s{section_idx}_c0",
                    'token_count': token_count
                })
            
            # If section is too large, apply recursive chunking
            else:
                print(f"    [!] Section '{section_title}' has {token_count} tokens, applying recursive split")
                sub_chunks = self._recursive_split(section_text)
                
                for sub_idx, sub_chunk in enumerate(sub_chunks):
                    chunks.append({
                        'text': sub_chunk,
                        'doc_type': document['doc_type'],
                        'filename': document['filename'],
                        'section_title': section_title,
                        'chunk_id': f"{document['doc_type']}_s{section_idx}_c{sub_idx}",
                        'token_count': self._count_tokens(sub_chunk)
                    })
        
        return chunks
    
    def _detect_sections(self, text: str) -> List[Dict[str, str]]:
       
        sections = []
        
        # Combined regex pattern for header detection
        header_pattern = (
            r'(?:^|\n)(?:'
            r'(#{1,3}\s+.+)|'                # Markdown: # Header
            r'(\d+\.(?:\d+\.)*\s+[A-Z].+)|'  # Numbered: 1.2 Header
            r'([A-Z][A-Z\s]{3,}(?=\n))|'     # ALL CAPS HEADER
            r'(.+\n[=\-]{3,})'               # Underlined header
            r')(?=\n|$)'
        )
        
        # Find all header positions
        headers = list(re.finditer(header_pattern, text, re.MULTILINE))
        
        # If no headers found, treat entire document as one section
        if not headers:
            return [{
                'title': 'Full Document',
                'text': text.strip()
            }]
        
        # Extract sections between headers
        for i, header in enumerate(headers):
            # Extract header text
            header_text = header.group(0).strip()
            # Clean header (remove #, numbers, underlines)
            header_title = re.sub(r'^#+\s*|\d+\.(?:\d+\.)*\s*|[=\-]+', '', header_text).strip()
            
            # Get section content (from this header to next header or end)
            start_pos = header.end()
            end_pos = headers[i + 1].start() if i + 1 < len(headers) else len(text)
            
            section_text = text[start_pos:end_pos].strip()
            
            # Skip empty sections
            if section_text:
                # Include header in section text for context
                full_section = f"{header_title}\n\n{section_text}"
                
                sections.append({
                    'title': header_title,
                    'text': full_section
                })
        
        return sections
    
    def _recursive_split(self, text: str) -> List[str]:
        
        chunks = []
        
        # Split by paragraphs first (double newline)
        paragraphs = text.split('\n\n')
        
        current_chunk = ""
        current_tokens = 0
        
        for para in paragraphs:
            para = para.strip()
            if not para:
                continue
            
            para_tokens = self._count_tokens(para)
            
            # If single paragraph exceeds limit, split by sentences
            if para_tokens > self.max_chunk_tokens:
                # Save current chunk if exists
                if current_chunk:
                    chunks.append(current_chunk.strip())
                    current_chunk = ""
                    current_tokens = 0
                
                # Split oversized paragraph by sentences
                sentences = re.split(r'(?<=[.!?])\s+', para)
                for sentence in sentences:
                    sent_tokens = self._count_tokens(sentence)
                    
                    if current_tokens + sent_tokens <= self.max_chunk_tokens:
                        current_chunk += " " + sentence
                        current_tokens += sent_tokens
                    else:
                        if current_chunk:
                            chunks.append(current_chunk.strip())
                        
                        # Apply overlap from previous chunk
                        if chunks and self.overlap_tokens > 0:
                            overlap_text = self._get_last_n_tokens(chunks[-1], self.overlap_tokens)
                            current_chunk = overlap_text + " " + sentence
                            current_tokens = self._count_tokens(current_chunk)
                        else:
                            current_chunk = sentence
                            current_tokens = sent_tokens
            
            # Normal case: add paragraph to current chunk
            elif current_tokens + para_tokens <= self.max_chunk_tokens:
                current_chunk += "\n\n" + para
                current_tokens += para_tokens
            
            # Current chunk is full, start new one with overlap
            else:
                chunks.append(current_chunk.strip())
                
                # Add overlap from previous chunk
                if self.overlap_tokens > 0:
                    overlap_text = self._get_last_n_tokens(current_chunk, self.overlap_tokens)
                    current_chunk = overlap_text + "\n\n" + para
                else:
                    current_chunk = para
                
                current_tokens = self._count_tokens(current_chunk)
        
        # Add final chunk
        if current_chunk.strip():
            chunks.append(current_chunk.strip())
        
        return chunks
    
    def _count_tokens(self, text: str) -> int:
        
        if self.encoding:
            return len(self.encoding.encode(text))
        else:
            # Rough estimation: ~4 characters per token
            return len(text) // 4
    
    def _get_last_n_tokens(self, text: str, n_tokens: int) -> str:
        
        if self.encoding:
            tokens = self.encoding.encode(text)
            if len(tokens) <= n_tokens:
                return text
            overlap_tokens = tokens[-n_tokens:]
            return self.encoding.decode(overlap_tokens)
        else:
            # Rough estimation: take last n*4 characters
            return text[-(n_tokens * 4):]


# Example usage for testing
if __name__ == "__main__":
    # Import the DocumentLoader
    import sys
    sys.path.append('.')  # Add current directory to path
    
    try:
        from document_loader import DocumentLoader
        
        # Load all documents from data directory
        print("Loading documents...")
        loader = DocumentLoader("data/raw")
        documents = loader.load_documents()
        
        # Chunk all loaded documents
        print("\nChunking documents...")
        chunker = PolicyDocumentChunker(max_chunk_tokens=800)
        chunks = chunker.chunk_documents(documents)
        
        # Display results grouped by document
        print("\n" + "="*60)
        print("CHUNKING RESULTS")
        print("="*60)
        
        current_doc = None
        for i, chunk in enumerate(chunks, 1):
            # Print document separator when switching to new document
            if current_doc != chunk['filename']:
                current_doc = chunk['filename']
                print(f"\n{'─'*60}")
                print(f"📄 Document: {current_doc}")
                print(f"{'─'*60}")
            
            print(f"\n  Chunk {i}:")
            print(f"    ID: {chunk['chunk_id']}")
            print(f"    Section: {chunk['section_title']}")
            print(f"    Tokens: {chunk['token_count']}")
            print(f"    Text preview: {chunk['text'][:100]}...")
    
    except ImportError:
        print("DocumentLoader not found. Testing with sample data...")
        
        # Fallback: Sample policy document for testing
        sample_doc = {
            'content': """# Refund Policy

Our company is committed to customer satisfaction.

## Eligibility Criteria

1. Refunds are available within 30 days of purchase
2. Items must be in original condition
3. Proof of purchase is required

## Process

To request a refund:
- Contact customer support
- Provide order number
- Explain reason for refund

## Exceptions

The following items are not eligible for refunds:
- Digital products after download
- Customized items
- Sale items marked as final sale

## Processing Time

Refunds typically take 5-7 business days to process.""",
            'filename': 'refund_policy.txt',
            'doc_type': 'refund_policy'
        }
        
        # Test chunking with sample
        chunker = PolicyDocumentChunker(max_chunk_tokens=200)
        chunks = chunker.chunk_documents([sample_doc])
        
        # Display results
        print("\n" + "="*60)
        for i, chunk in enumerate(chunks, 1):
            print(f"\nChunk {i}:")
            print(f"  ID: {chunk['chunk_id']}")
            print(f"  Section: {chunk['section_title']}")
            print(f"  Tokens: {chunk['token_count']}")
            print(f"  Text preview: {chunk['text'][:150]}...")