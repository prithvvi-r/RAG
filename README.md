# RAG System for Policy Document Q&A

## 🚀 Setup Instructions

### Prerequisites
- Python 
- Virtual environment tool (venv)

### Installation

1. **Clone the repository**
```bash
git clone <repository-url>
```

2. **Create and activate virtual environment**
```bash
python -m venv myenv
source myenv/bin/activate  # On Windows: myenv\Scripts\activate
```

3. **Install dependencies**
```bash
pip install -r requirements.txt
```

4. **Set up environment variables**
Create a `.env` file in the root directory:
```env
OPENAI_API_KEY=your_openai_api_key_here
```

5. **Prepare your data**
- Place raw policy documents in `data/raw/`
- Processed documents will be stored in `data/processed/`
- Vector embeddings will be stored in `data/chroma_db/`

### Running the Application



# Build the Index
```bash
python src/indexer.py --rebuild
```
# Run a evalution
```bash
python src/evaluation.py
```

---

## 🏗️ Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                     RAG SYSTEM ARCHITECTURE                  │
└─────────────────────────────────────────────────────────────┘

[Policy Documents ] 
         ↓
    ┌────────────────────┐
    │ Document Loader    │ ← document_loader.py
    └────────────────────┘
         ↓
    ┌────────────────────┐
    │ Chunking Strategy  │ ← chunking.py  │
    └────────────────────┘
         ↓
    ┌────────────────────┐
    │ Embedding Model    │ ← embeddings.py │
    └────────────────────┘
         ↓
    ┌────────────────────┐
    │ Vector Store       │ ← vector_store.py│
    └────────────────────┘
         ↓
    ┌────────────────────┐
    │ Retrieval          │ ← retrieval.py  │
    └────────────────────┘
         ↓
    ┌────────────────────┐
    │ LLM + Prompts      │ ← rag_pipeline.py + prompts.py│
    └────────────────────┘
         ↓
    [Grounded Answer with Citations]
```

**Key Components:**
- **Document Processing**: document → Text extraction → Chunking
- **Embedding Pipeline**: Text → Vector embeddings → ChromaDB storage
- **Retrieval**: Query → Similarity search → multi-query by llm -> Top-k relevant chunks
- **Generation**: Context + Query + Prompt → LLM → Grounded answer

---

## 📝 Prompts Used

The system uses optimized prompts defined in `src/prompts.py`:

### System Prompt
- **Purpose**: Defines AI assistant behavior and grounding rules
- **Key Features**:
  - Strict context-only responses (no hallucination)
  - Confidence level assessment (high/medium/low/no_information)
  - Structured response format with citations
  - Explicit handling of information gaps

### User Prompt Template
- **Purpose**: Structures each query with context and instructions
- **Components**:
  - User question
  - Retrieved document context
  - Available sources
  - Conditional response guidelines based on information availability

**View full prompts**: [`src/prompts.py`](src/prompts.py)

---

## 📊 Evaluation Results

Evaluation metrics and results are available in:

📁 **`path/evaluation_results/`**
- Contains performance metrics (accuracy, relevance, groundedness)
- Includes test case results
- Performance benchmarks across different query types

**Run evaluations**:
```bash
python src/evaluation.py
```

Results include:
-  Answer accuracy
-  Retrieval precision
-  Grounding quality (context adherence)
-  Response latency

---

##  Key Trade-offs & Future Improvements

### Current Trade-offs

| Aspect | Current Choice | Trade-off |
|--------|---------------|-----------|
| **Embedding Model** | OpenAI | Efficient With High Dimention embeddings |
| **Vector Store** | ChromaDB | Simple setup, but limited scalability vs. Pinecone/Weaviate |
| **Chunking** | Hybrid Semantic Chunking strategy. | structure-aware + size-constrained recursive splitting|
| **Retrieval** | Multi-Query Retrival with Top k similarity chunks | Simple, but no re-ranking for relevance |
| **LLM** | OpenAI | Fast inference | |

### 🚀 Planned Improvements

#### 1. **Cohere Reranking** (High Priority if document is large size and complex)
- **Problem**: Current top-k retrieval may miss nuanced relevance
- **Solution**: Add Cohere rerank API after initial retrieval
- **Benefit**: 15-30% improvement in answer quality for complex queries

#### 2. **Caching Layer**
- Cache frequent queries and embeddings
- Reduce API calls and latency
- Use Redis for production deployment

#### 3. **User Feedback Loop**
- Collect thumbs up/down on answers
- Fine-tune retrieval weights based on feedback
- Continuously improve prompt engineering

---

## 📂 Project Structure

```
ASSIGNND/
├── data/
│   ├── raw/                    # Original policy documents
│   ├── processed/              # Processed text chunks
│   ├── chroma_db/              # Vector embeddings
│   ├── test_chroma_db/         # Test database
│   ├── test_diagnostic_db/     # Diagnostic tests
|── evaluation_results/     # Evaluation metrics
├── src/
│   ├── __init__.py
│   ├── chunking.py             # Document chunking logic
│   ├── document_loader.py      # PDF processing
│   ├── embeddings.py           # Embedding generation
│   ├── evaluation.py           # Performance evaluation
│   ├── indexer.py              # Vector indexing
│   ├── prompts.py              # System/user prompts
│   ├── rag_pipeline.py         # Main RAG orchestration
│   ├── retrieval.py            # Similarity search
│   ├── vector_store.py         # ChromaDB interface
│   └── test.py                 # Unit tests
├── .env                        # Environment variables
└── README.md                   # This file
```

---


---

## 📄 License

[Add your license here]

---

