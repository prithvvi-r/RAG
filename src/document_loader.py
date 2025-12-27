

import os
import re
from typing import List, Dict
from pathlib import Path


class DocumentLoader:
    
    
    def __init__(self, data_dir: str = "data/raw"):
        
        self.data_dir = Path(data_dir)
        self.supported_formats = ['.txt', '.md', '.pdf']
    
    def load_documents(self) -> List[Dict[str, str]]:
        
        documents = []
        
        if not self.data_dir.exists():
            raise FileNotFoundError(f"Data directory not found: {self.data_dir}")
        
        # Iterate through all files in directory
        for file_path in self.data_dir.iterdir():
            if file_path.suffix.lower() in self.supported_formats:
                try:
                    doc = self._load_single_document(file_path)
                    documents.append(doc)
                    print(f"[+] Loaded: {file_path.name}")
                except Exception as e:
                    print(f"[-] Failed to load {file_path.name}: {e}")
        
        print(f"\n[*] Total documents loaded: {len(documents)}")
        return documents
    
    def _load_single_document(self, file_path: Path) -> Dict[str, str]:
        
        suffix = file_path.suffix.lower()
        
        if suffix == '.pdf':
            content = self._load_pdf(file_path)
        elif suffix in ['.txt', '.md']:
            content = self._load_text(file_path)
        else:
            raise ValueError(f"Unsupported format: {suffix}")
        
        # Clean the content
        content = self._clean_text(content)
        
        return {
            'content': content,
            'filename': file_path.name,
            'doc_type': file_path.stem  # e.g., 'refund_policy'
        }
    
    def _load_pdf(self, file_path: Path) -> str:
        
        try:
            from pypdf import PdfReader
        except ImportError:
            raise ImportError("pypdf not installed. Run: pip install pypdf")
        
        reader = PdfReader(file_path)
        text = ""
        
        # Extract text from all pages
        for page in reader.pages:
            text += page.extract_text() + "\n"
        
        return text
    
    def _load_text(self, file_path: Path) -> str:
        
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()
    
    def _clean_text(self, text: str) -> str:
        
        # Remove excessive whitespace
        text = re.sub(r'\n{3,}', '\n\n', text)  # Max 2 consecutive newlines
        text = re.sub(r' {2,}', ' ', text)      # Remove multiple spaces
        
        # Remove special characters that might cause issues
        text = text.replace('\x00', '')  # Null bytes
        text = text.replace('\r', '\n')  # Normalize line endings
        
        # Strip leading/trailing whitespace
        text = text.strip()
        
        return text


# Example usage for testing
if __name__ == "__main__":
    # Test the loader
    loader = DocumentLoader("data/raw")
    
    try:
        docs = loader.load_documents()
        
        # Print summary of loaded documents
        for doc in docs:
            print(f"\n--- {doc['filename']} ---")
            print(f"Type: {doc['doc_type']}")
            print(f"Length: {len(doc['content'])} characters")
            print(f"Preview: {doc['content'][:200]}...")
    
    except Exception as e:
        print(f"Error: {e}")