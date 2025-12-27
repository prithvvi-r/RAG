"""
RAG Pipeline - Complete Retrieval-Augmented Generation System
Combines retrieval with LLM generation for accurate, grounded answers
"""

import os
from typing import List, Dict, Any, Optional
from pydantic import BaseModel
from dotenv import load_dotenv
from openai import OpenAI

# Handle imports for both module and script execution
try:
    from .retrieval import RetrievalPipeline
    from .prompts import get_prompt, format_user_prompt
except ImportError:
    from retrieval import RetrievalPipeline
    from prompts import get_prompt, format_user_prompt

load_dotenv()


class RAGResponse(BaseModel):
    """Structured response from RAG system"""
    answer: str
    confidence: str  # "high", "medium", "low", "no_information"
    sources: List[str]
    reasoning: Optional[str] = None


class RAGPipeline:
    """
    Complete RAG Pipeline:
    1. Retrieve relevant documents
    2. Generate answer using LLM with strict grounding
    3. Handle edge cases (no documents, partial info, out-of-scope)
    """
    
    def __init__(
        self,
        retriever: RetrievalPipeline,
        llm_model: str = "gpt-4o-mini",
        temperature: float = 0.0  # Low temperature for factual answers
    ):
        """
        Initialize RAG pipeline
        
        Args:
            retriever: Configured HybridRetriever instance
            llm_model: OpenAI model for answer generation
            temperature: Generation temperature (0.0 for deterministic)
        """
        self.retriever = retriever
        self.llm_model = llm_model
        self.temperature = temperature
        self.openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.prompt_version = "improved"  # Can be "initial", "improved", or "advanced"
        
        print(f"[+] RAG Pipeline initialized")
        print(f"  - Model: {llm_model}")
        print(f"  - Temperature: {temperature}")
        print(f"  - Prompt version: {self.prompt_version}")
    
    def query(
        self,
        question: str,
        top_k: int = 5,
        verbose: bool = False
    ) -> RAGResponse:
        """
        Main RAG query method
        
        Args:
            question: User's question
            top_k: Number of documents to retrieve
            verbose: Print detailed pipeline execution
            
        Returns:
            Structured RAG response with answer, confidence, and sources
        """
        if not question or not question.strip():
            # Edge case: Empty query
            return RAGResponse(
                answer="I received an empty question. Please provide a specific question about the policy documents.",
                confidence="no_information",
                sources=[],
                reasoning="Empty query provided"
            )
        
        if verbose:
            print("\n" + "="*80)
            print("[*] RAG PIPELINE EXECUTION")
            print("="*80)
            print(f"Question: {question}\n")
        
        # Step 1: Retrieve relevant documents
        retrieved_docs = self.retriever.retrieve(
            query=question,
            top_k=top_k,
            verbose=verbose
        )
        
        if verbose:
            print(f"\n[*] Retrieved {len(retrieved_docs)} documents")
        
        # Edge case: No documents retrieved
        if not retrieved_docs:
            return RAGResponse(
                answer=f"I could not find any relevant information in the policy documents to answer your question: '{question}'. The question may be outside the scope of the available policy documents (refund policy, shipping policy, cancellation policy).",
                confidence="no_information",
                sources=[],
                reasoning="No relevant documents retrieved from vector store or BM25"
            )
        
        # Step 2: Generate answer with LLM
        response = self._generate_answer(question, retrieved_docs, verbose)
        
        # Edge case: If LLM indicates no information but we have docs, check if docs are truly relevant
        if response.confidence == "no_information" and retrieved_docs:
            # Re-check relevance by looking at similarity scores or text content
            # This is a safety check
            pass
        
        if verbose:
            print("\n" + "="*80)
            print("[+] RAG PIPELINE COMPLETE")
            print("="*80 + "\n")
        
        return response
    
    def _generate_answer(
        self,
        question: str,
        retrieved_docs: List[Dict[str, Any]],
        verbose: bool = False
    ) -> RAGResponse:
        """
        Generate answer using LLM with retrieved context
        
        Handles three scenarios:
        1. Sufficient information available → High confidence answer
        2. Partial information available → Medium confidence, acknowledge gaps
        3. No relevant information → Explicitly state "no information"
        
        Args:
            question: User's question
            retrieved_docs: Retrieved document chunks
            verbose: Print generation details
            
        Returns:
            Structured RAG response
        """
        # Format context from retrieved documents
        context = self._format_context(retrieved_docs)
        
        # Build prompt with strict grounding instructions
        prompt = self._build_prompt(question, context, retrieved_docs)
        
        if verbose:
            print("\n[*] Generating answer with LLM...")
            print(f"  Context length: {len(context)} chars")
            print(f"  Number of sources: {len(retrieved_docs)}")
            print(f"  Prompt version: {self.prompt_version}")
        
        try:
            # Get system and user prompts based on version
            system_prompt, _ = get_prompt(self.prompt_version)
            
            # Generate structured response
            response = self.openai_client.beta.chat.completions.parse(
                model=self.llm_model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt}
                ],
                response_format=RAGResponse,
                temperature=self.temperature
            )
            
            rag_response = response.choices[0].message.parsed
            
            if verbose:
                print(f"  Confidence: {rag_response.confidence}")
                print(f"  Sources used: {len(rag_response.sources)}")
            
            return rag_response
        
        except Exception as e:
            print(f"[ERROR] Generation error: {e}")
            # Fallback response for errors
            return RAGResponse(
                answer="I encountered an error while generating the answer. This could be due to a technical issue. Please try rephrasing your question or try again later.",
                confidence="low",
                sources=[],
                reasoning=f"Generation error occurred: {str(e)}"
            )
    
    def set_prompt_version(self, version: str):
        """
        Set the prompt version to use
        
        Args:
            version: "initial", "improved", or "advanced"
        """
        valid_versions = ["initial", "improved", "advanced"]
        if version.lower() in valid_versions:
            self.prompt_version = version.lower()
            print(f"[+] Prompt version set to: {self.prompt_version}")
        else:
            print(f"[!] Invalid prompt version. Using default: {self.prompt_version}")
    
    def _get_system_prompt(self) -> str:
        """
        Get system prompt based on current version
        """
        system_prompt, _ = get_prompt(self.prompt_version)
        return system_prompt

    def _build_prompt(
        self,
        question: str,
        context: str,
        retrieved_docs: List[Dict[str, Any]]
    ) -> str:
        """
        Build the user prompt with context and question
        
        Args:
            question: User's question
            context: Formatted context from retrieved documents
            retrieved_docs: List of retrieved documents (for source info)
            
        Returns:
            Formatted prompt string
        """
        # Build source list for citation
        sources_info = "\n".join([
            f"[{i+1}] {doc['metadata']['filename']} - {doc['metadata']['section_title']}"
            for i, doc in enumerate(retrieved_docs)
        ])
        
        # Use prompt formatting from prompts.py
        prompt = format_user_prompt(
            question=question,
            context=context,
            sources_info=sources_info,
            prompt_version=self.prompt_version
        )

        return prompt
    
    def _format_context(self, retrieved_docs: List[Dict[str, Any]]) -> str:
        """
        Format retrieved documents into context string
        
        Args:
            retrieved_docs: List of retrieved document chunks
            
        Returns:
            Formatted context string with source labels
        """
        if not retrieved_docs:
            return "No relevant documents found."
        
        context_parts = []
        for i, doc in enumerate(retrieved_docs, 1):
            source_label = f"[Source {i}] {doc['metadata']['filename']} - {doc['metadata']['section_title']}"
            chunk_text = doc['text']
            
            context_parts.append(f"{source_label}\n{chunk_text}\n")
        
        return "\n---\n\n".join(context_parts)
    
    def format_response(self, response: RAGResponse) -> str:
        """
        Format RAG response for display
        
        Args:
            response: RAG response object
            
        Returns:
            Formatted string for display
        """
        output = []
        
        # Confidence indicator
        confidence_label = {
            "high": "[HIGH]",
            "medium": "[MEDIUM]", 
            "low": "[LOW]",
            "no_information": "[NO INFO]"
        }
        
        output.append(f"\n{confidence_label.get(response.confidence, '[UNKNOWN]')} Confidence: {response.confidence.upper()}")
        output.append("\n" + "="*80)
        
        # Answer
        output.append("\n[*] ANSWER:")
        output.append(response.answer)
        
        # Sources (if any)
        if response.sources:
            output.append("\n\n[*] SOURCES:")
            for i, source in enumerate(response.sources, 1):
                output.append(f"  {i}. {source}")
        
        # Reasoning (if provided)
        if response.reasoning:
            output.append(f"\n\n[*] REASONING:\n{response.reasoning}")
        
        output.append("\n" + "="*80)
        
        return "\n".join(output)


# Evaluation Framework
class RAGEvaluator:
    """
    Simple evaluation framework for RAG system
    
    Evaluates:
    - Accuracy: Is the answer correct?
    - Grounding: Is the answer based on retrieved context?
    - Completeness: Does the answer address all parts of the question?
    - Hallucination: Does the answer contain made-up information?
    - Clarity: Is the answer well-structured and clear?
    """
    
    def __init__(self, rag_pipeline: RAGPipeline):
        self.rag_pipeline = rag_pipeline
    
    def evaluate_query(
        self,
        question: str,
        expected_answer: Optional[str] = None,
        should_have_info: bool = True
    ) -> Dict[str, Any]:
        """
        Evaluate a single query
        
        Args:
            question: Question to test
            expected_answer: Expected answer (for comparison)
            should_have_info: Whether info should be available
            
        Returns:
            Evaluation results
        """
        print(f"\n{'='*80}")
        print(f"📊 EVALUATING: {question}")
        print(f"{'='*80}")
        
        # Get response
        response = self.rag_pipeline.query(question, verbose=True)
        
        # Display formatted response
        print(self.rag_pipeline.format_response(response))
        
        # Manual evaluation prompts
        evaluation = {
            "question": question,
            "response": response.model_dump(),
            "expected_info_available": should_have_info,
            "scores": {}
        }
        
        print("\n📋 MANUAL EVALUATION:")
        print("Please score the following (✅ Good / ⚠️  Partial / ❌ Poor):\n")
        
        print(f"1. Accuracy: Is the answer factually correct?")
        print(f"   Expected info available: {should_have_info}")
        if expected_answer:
            print(f"   Expected: {expected_answer}")
        
        print(f"\n2. Grounding: Is the answer based only on retrieved context?")
        print(f"   Check: No external knowledge or assumptions used")
        
        print(f"\n3. Completeness: Does it address all parts of the question?")
        print(f"   Confidence level: {response.confidence}")
        
        print(f"\n4. No Hallucination: Are there any made-up facts?")
        print(f"   Sources cited: {len(response.sources)}")
        
        print(f"\n5. Clarity: Is the answer well-structured and clear?")
        print(f"   Check: Uses headings, bullets, clear language")
        
        return evaluation
    
    def run_evaluation_suite(self, test_cases: List[Dict[str, Any]]):
        """
        Run full evaluation suite
        
        Args:
            test_cases: List of test cases with questions and expected behaviors
        """
        print("\n" + "="*80)
        print("🧪 RAG SYSTEM EVALUATION SUITE")
        print("="*80)
        
        results = []
        
        for i, test_case in enumerate(test_cases, 1):
            print(f"\n\n{'#'*80}")
            print(f"TEST CASE {i}/{len(test_cases)}")
            print(f"{'#'*80}")
            
            result = self.evaluate_query(
                question=test_case["question"],
                expected_answer=test_case.get("expected_answer"),
                should_have_info=test_case.get("should_have_info", True)
            )
            
            results.append(result)
            
            print("\n" + "-"*80)
            print("Press Enter to continue to next test case...")
            input()
        
        print("\n\n" + "="*80)
        print("✅ EVALUATION SUITE COMPLETE")
        print("="*80)
        print(f"\nEvaluated {len(results)} test cases")
        print("\nSummary:")
        for i, result in enumerate(results, 1):
            conf = result['response']['confidence']
            print(f"  {i}. [{conf}] {result['question'][:60]}...")


# Example test cases for evaluation
EVALUATION_TEST_CASES = [
    # Answerable questions - should have high confidence
    {
        "question": "How long do I have to return an item?",
        "should_have_info": True,
        "expected_answer": "Should mention specific time period (e.g., 30 days)"
    },
    {
        "question": "What is the refund policy for damaged items?",
        "should_have_info": True,
        "expected_answer": "Should describe process for damaged items"
    },
    {
        "question": "How much does standard shipping cost?",
        "should_have_info": True,
        "expected_answer": "Should state shipping cost or that it's free"
    },
    
    # Partially answerable - should have medium confidence
    {
        "question": "Can I return items bought during a sale?",
        "should_have_info": True,
        "expected_answer": "May have partial info about sale items"
    },
    {
        "question": "What happens if my package is lost during shipping?",
        "should_have_info": True,
        "expected_answer": "Should mention shipping issues/insurance"
    },
    
    # Unanswerable - should have no_information confidence
    {
        "question": "What are your hours of operation?",
        "should_have_info": False,
        "expected_answer": "Should clearly state this info is not available"
    },
    {
        "question": "Do you ship internationally?",
        "should_have_info": False,
        "expected_answer": "May not be in policy docs"
    },
    {
        "question": "Can I use multiple discount codes on one order?",
        "should_have_info": False,
        "expected_answer": "Likely not in basic policy docs"
    }
]


# Example usage
if __name__ == "__main__":
    import sys
    import json
    from pathlib import Path
    
    # Handle imports
    try:
        from .vector_store import ChromaVectorStore
        from .embeddings import EmbeddingGenerator
        from .retrieval import RetrievalPipeline
    except ImportError:
        from vector_store import ChromaVectorStore
        from embeddings import EmbeddingGenerator
        from retrieval import RetrievalPipeline
    
    from langchain_community.retrievers import BM25Retriever
    from langchain_core.documents import Document
    
    print("="*80)
    print("🤖 RAG PIPELINE - COMPLETE SYSTEM TEST")
    print("="*80)
    
    if len(sys.argv) > 1 and sys.argv[1] == "--test":
        try:
            # Initialize components
            print("\n1. Loading RAG components...")
            
            vector_store = ChromaVectorStore(
                persist_directory="data/chroma_db",
                collection_name="policy_documents"
            )
            
            metadata_path = Path("data/chroma_db/chunks_metadata.json")
            with open(metadata_path, 'r', encoding='utf-8') as f:
                chunks_metadata = json.load(f)
            
            # Convert to LangChain Documents for BM25
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
            
            embedding_generator = EmbeddingGenerator()
            
            retriever = RetrievalPipeline(
                vector_store=vector_store,
                bm25_retriever=bm25_retriever,
                embedding_generator=embedding_generator,
                #use_multi_query=True
            )
            
            rag_pipeline = RAGPipeline(
                retriever=retriever,
                llm_model="gpt-4o-mini"
            )
            
            print("\n2. Running sample queries...")
            
            # Test queries
            test_queries = [
                "How long do I have to return an item?",
                "What happens if my order is damaged?",
                "Do you offer gift wrapping services?"  # Likely unanswerable
            ]
            
            for query in test_queries:
                response = rag_pipeline.query(query, verbose=True)
                print(rag_pipeline.format_response(response))
                print("\n" + "-"*80 + "\n")
            
            # Run evaluation
            print("\n3. Starting evaluation suite...")
            print("\nWould you like to run the full evaluation? (y/n): ", end="")
            
            if input().lower() == 'y':
                evaluator = RAGEvaluator(rag_pipeline)
                evaluator.run_evaluation_suite(EVALUATION_TEST_CASES)
            
            print("\n✅ RAG Pipeline test complete!")
        
        except FileNotFoundError as e:
            print(f"\n❌ Error: {e}")
            print("\nMake sure to run indexing first:")
            print("  python src/indexer.py")
            sys.exit(1)
        
        except Exception as e:
            print(f"\n❌ Test failed: {e}")
            import traceback
            traceback.print_exc()
            sys.exit(1)
    
    else:
        print("\nRAG Pipeline - Complete Retrieval-Augmented Generation System")
        print("\nFeatures:")
        print("  ✓ Hybrid retrieval (BM25 + Semantic + RRF)")
        print("  ✓ LLM generation with strict grounding")
        print("  ✓ Confidence scoring")
        print("  ✓ Source citation")
        print("  ✓ Edge case handling (no info, partial info)")
        print("  ✓ Evaluation framework")
        print("\nTo run test:")
        print("  python src/rag_pipeline.py --test")