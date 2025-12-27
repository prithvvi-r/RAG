# RAG Pipeline Implementation Summary

## ✅ Completed Features

### 1. **Retrieved Context Passed to LLM** ✓
- Retrieval pipeline retrieves relevant documents from ChromaDB (vector search) and BM25
- Documents are formatted into context strings with source labels
- Context is passed to LLM with clear instructions to use only this context

**Files:**
- `src/retrieval.py` - Hybrid retrieval (BM25 + Vector + RRF fusion)
- `src/rag_pipeline.py` - Main RAG pipeline that combines retrieval + generation

### 2. **Prompt Engineering** ✓

Created `src/prompts.py` with three prompt versions:

#### Version 1: Initial Prompt
- Basic prompt without strict grounding rules
- Minimal instructions
- Risk of hallucination

#### Version 2: Improved Prompt (Current Default)
- **Explicit grounding rules**: "ONLY from provided context"
- **Confidence level system**: high/medium/low/no_information
- **Structured format requirements**: headings, bullet points
- **Source citation instructions**
- **Three-scenario handling**: fully answerable, partially answerable, no information
- **Clear "I don't know" instructions**: better to say unknown than guess

#### Version 3: Advanced Prompt
- Step-by-step reasoning process
- More detailed confidence criteria
- Structured answer template
- Quality check reminders
- Related information suggestions

**What Changed and Why:**
- **Added strict grounding** → Prevents hallucination
- **Added confidence levels** → Improves transparency and trust
- **Added structure requirements** → Better UX and readability
- **Added source citations** → Enables verification and debugging
- **Added missing info handling** → Clear user communication

### 3. **Evaluation Framework** ✓

Created comprehensive evaluation with `src/evaluation.py`:

#### Test Suite (11+ test cases):
1. **Answerable questions** (3) - Should have high confidence
   - "How long do I have to return an item?"
   - "What is the refund policy for damaged items?"
   - "How much does standard shipping cost?"

2. **Partially answerable** (2) - Should have medium confidence
   - "Can I return items bought during a sale?"
   - "What happens if my package is lost during shipping?"

3. **Unanswerable** (3) - Should have no_information confidence
   - "What are your hours of operation?"
   - "Do you offer gift wrapping services?"
   - "Can I use multiple discount codes on one order?"

4. **Edge cases** (3)
   - Empty query
   - Nonsense query
   - Out-of-scope question

#### Evaluation Criteria:
- ✅ **Accuracy**: Is the information factually correct?
- ✅ **Grounding**: Is the answer based only on retrieved context?
- ✅ **Completeness**: Addresses all parts of the question?
- ✅ **No Hallucination**: No made-up information?
- ✅ **Clarity**: Well-structured and readable?

#### Scoring System:
- ✅ Excellent (exceeds expectations)
- ✓ Good (meets expectations)
- ⚠️ Partial (partially meets expectations)
- ❌ Poor (does not meet expectations)

#### Features:
- Manual scoring (recommended)
- Automated scoring (experimental)
- Detailed reporting
- JSON export for results
- Category breakdowns

### 4. **Edge Case Handling** ✓

Implemented in `src/rag_pipeline.py`:

#### Case 1: Empty Query
```python
if not question or not question.strip():
    return RAGResponse(
        answer="I received an empty question. Please provide a specific question...",
        confidence="no_information",
        ...
    )
```

#### Case 2: No Relevant Documents Found
```python
if not retrieved_docs:
    return RAGResponse(
        answer="I could not find any relevant information in the policy documents...",
        confidence="no_information",
        ...
    )
```

#### Case 3: Question Outside Knowledge Base
- Handled via confidence level "no_information"
- System explicitly states information not available
- Suggests related topics that ARE covered (if any)

#### Case 4: Generation Errors
- Graceful error handling with fallback responses
- User-friendly error messages

## 📁 File Structure

```
src/
├── indexer.py          # Document indexing pipeline
├── retrieval.py        # Hybrid retrieval (BM25 + Vector + RRF)
├── rag_pipeline.py     # Complete RAG pipeline (retrieval + generation)
├── prompts.py          # Prompt engineering (initial, improved, advanced)
├── evaluation.py       # Comprehensive evaluation framework
├── embeddings.py       # Embedding generation
├── vector_store.py     # ChromaDB vector store
├── document_loader.py  # Document loading
└── chunking.py         # Document chunking
```

## 🚀 Usage

### 1. Build the Index
```bash
python src/indexer.py --rebuild
```

### 2. Run a Query

**Option A: Use the test script (Recommended)**
```bash
python test_rag_query.py
```

**Option B: Manual initialization (Full code)**
```python
import sys
import json
from pathlib import Path

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
```

### 3. Run Evaluation
```bash
python src/evaluation.py --run
```

### 4. Switch Prompt Versions
```python
rag_pipeline.set_prompt_version("advanced")  # or "initial", "improved"
```

## 🔧 Key Implementation Details

### Retrieval Pipeline
- **Multi-query expansion**: Generates 3 query variations using LLM
- **Hybrid retrieval**: Combines semantic (vector) and keyword (BM25) search
- **RRF fusion**: Reciprocal Rank Fusion to combine results
- **Keyword boost**: Adds relevance boost for keyword matches

### RAG Pipeline
- **Strict grounding**: LLM instructed to use ONLY retrieved context
- **Structured output**: Pydantic model for consistent responses
- **Confidence assessment**: LLM determines confidence level
- **Source citation**: References to document sources included

### Prompt Engineering
- **Versioned prompts**: Easy to compare and iterate
- **Context-aware**: Different instructions based on information availability
- **Transparent**: Clear confidence levels and limitations

## 📊 Evaluation Results Format

Results are saved to `evaluation_results/evaluation_TIMESTAMP.json` with:
- Question and response
- Scores for each criterion
- Overall statistics
- Category breakdowns




