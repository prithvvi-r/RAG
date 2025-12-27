
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from enum import Enum
import json
from pathlib import Path
from datetime import datetime

try:
    from .rag_pipeline import RAGPipeline, RAGResponse
except ImportError:
    from rag_pipeline import RAGPipeline, RAGResponse


class EvaluationScore(Enum):
    """Scoring system for evaluation"""
    EXCELLENT = ""  # Exceeds expectations
    GOOD = ""       # Meets expectations
    PARTIAL = "-"   # Partially meets expectations
    POOR = ""      # Does not meet expectations
    NA = "—"         # Not applicable

@dataclass
class TestCase:
    """Individual test case for evaluation"""
    question: str
    category: str  # "answerable", "partial", "unanswerable", "edge_case"
    expected_confidence: str  # "high", "medium", "low", "no_information"
    expected_content: Optional[str] = None  # Key information that should be present
    should_avoid: Optional[List[str]] = None  # Content that shouldn't appear (hallucinations)
    notes: Optional[str] = None
    
    # Results (filled during evaluation)
    response: Optional[RAGResponse] = None
    scores: Dict[str, EvaluationScore] = field(default_factory=dict)
    evaluator_notes: Optional[str] = None


@dataclass
class EvaluationResults:
    """Results from evaluation suite"""
    test_cases: List[TestCase]
    timestamp: str
    overall_scores: Dict[str, Dict[str, int]] = field(default_factory=dict)
    
    def calculate_summary(self):
        """Calculate summary statistics"""
        categories = ["accuracy", "grounding", "completeness", "no_hallucination", "clarity"]
        
        for category in categories:
            self.overall_scores[category] = {
                "excellent": 0,
                "good": 0,
                "partial": 0,
                "poor": 0,
                "total": 0
            }
            
            for test_case in self.test_cases:
                if category in test_case.scores:
                    score = test_case.scores[category]
                    self.overall_scores[category]["total"] += 1
                    
                    if score == EvaluationScore.EXCELLENT:
                        self.overall_scores[category]["excellent"] += 1
                    elif score == EvaluationScore.GOOD:
                        self.overall_scores[category]["good"] += 1
                    elif score == EvaluationScore.PARTIAL:
                        self.overall_scores[category]["partial"] += 1
                    elif score == EvaluationScore.POOR:
                        self.overall_scores[category]["poor"] += 1


class RAGEvaluator:
    
    
    def __init__(self, rag_pipeline: RAGPipeline):
        self.rag_pipeline = rag_pipeline
    
    def evaluate_single(
        self,
        test_case: TestCase,
        auto_score: bool = False,
        verbose: bool = True
    ) -> TestCase:
    
        if verbose:
            print(f"\n{'='*80}")
            print(f"[*] TEST CASE: {test_case.category.upper()}")
            print(f"{'='*80}")
            print(f"Question: {test_case.question}")
            print(f"Expected Confidence: {test_case.expected_confidence}")
            if test_case.expected_content:
                print(f"Should Contain: {test_case.expected_content}")
            if test_case.should_avoid:
                print(f"Should Avoid: {', '.join(test_case.should_avoid)}")
            print()
        
        # Get response from RAG system
        response = self.rag_pipeline.query(test_case.question, verbose=verbose)
        test_case.response = response
        
        # Display formatted response
        if verbose:
            print(self.rag_pipeline.format_response(response))
        
        # Scoring
        if auto_score:
            test_case.scores = self._auto_score(test_case)
        else:
            test_case.scores = self._manual_score(test_case, verbose)
        
        return test_case
    
    def _manual_score(self, test_case: TestCase, verbose: bool) -> Dict[str, EvaluationScore]:
        """Interactive manual scoring"""
        scores = {}
        
        if verbose:
            print(f"\n{'─'*80}")
            print("[*] MANUAL EVALUATION")
            print(f"{'─'*80}\n")
        
        criteria = [
            ("accuracy", "Accuracy: Is the information factually correct?"),
            ("grounding", "Grounding: Based only on retrieved context?"),
            ("completeness", "Completeness: Addresses all parts of question?"),
            ("no_hallucination", "No Hallucination: No made-up information?"),
            ("clarity", "Clarity: Well-structured and readable?")
        ]
        
        print("Score each criterion:")
        print("  1 = [EXCELLENT] Excellent")
        print("  2 = [GOOD] Good")
        print("  3 = [PARTIAL] Partial")
        print("  4 = [POOR] Poor")
        print("  (press Enter to skip)\n")
        
        for key, description in criteria:
            while True:
                score_input = input(f"{description} [1-4]: ").strip()
                
                if not score_input:  # Skip
                    scores[key] = EvaluationScore.NA
                    break
                
                try:
                    score_num = int(score_input)
                    if score_num == 1:
                        scores[key] = EvaluationScore.EXCELLENT
                        break
                    elif score_num == 2:
                        scores[key] = EvaluationScore.GOOD
                        break
                    elif score_num == 3:
                        scores[key] = EvaluationScore.PARTIAL
                        break
                    elif score_num == 4:
                        scores[key] = EvaluationScore.POOR
                        break
                    else:
                        print("  Invalid input. Use 1-4 or press Enter to skip.")
                except ValueError:
                    print("  Invalid input. Use 1-4 or press Enter to skip.")
        
        # Optional notes
        notes = input("\nAdditional notes (optional): ").strip()
        if notes:
            test_case.evaluator_notes = notes
        
        return scores
    
    def _auto_score(self, test_case: TestCase) -> Dict[str, EvaluationScore]:
        
        scores = {}
        response = test_case.response
        
        # Check confidence match
        confidence_match = (response.confidence == test_case.expected_confidence)
        
        # Check expected content
        content_present = True
        if test_case.expected_content:
            content_present = test_case.expected_content.lower() in response.answer.lower()
        
        # Check for avoided content (hallucinations)
        avoided_content = True
        if test_case.should_avoid:
            for avoid_term in test_case.should_avoid:
                if avoid_term.lower() in response.answer.lower():
                    avoided_content = False
                    break
        
        # Scoring heuristics
        if confidence_match and content_present and avoided_content:
            scores["accuracy"] = EvaluationScore.EXCELLENT
            scores["grounding"] = EvaluationScore.EXCELLENT
            scores["no_hallucination"] = EvaluationScore.EXCELLENT
        elif confidence_match:
            scores["accuracy"] = EvaluationScore.GOOD
            scores["grounding"] = EvaluationScore.GOOD
            scores["no_hallucination"] = EvaluationScore.GOOD if avoided_content else EvaluationScore.PARTIAL
        else:
            scores["accuracy"] = EvaluationScore.PARTIAL
            scores["grounding"] = EvaluationScore.PARTIAL
            scores["no_hallucination"] = EvaluationScore.PARTIAL
        
        # Check completeness
        if len(response.sources) > 0:
            scores["completeness"] = EvaluationScore.GOOD
        else:
            scores["completeness"] = EvaluationScore.PARTIAL
        
        # Check clarity (basic length check)
        if len(response.answer) > 50 and response.answer.count('\n') > 2:
            scores["clarity"] = EvaluationScore.GOOD
        else:
            scores["clarity"] = EvaluationScore.PARTIAL
        
        return scores
    
    def evaluate_suite(
        self,
        test_cases: List[TestCase],
        auto_score: bool = False,
        save_results: bool = True
    ) -> EvaluationResults:
        
        print("\n" + "="*80)
        print("[*] RAG SYSTEM EVALUATION SUITE")
        print("="*80)
        print(f"Total test cases: {len(test_cases)}\n")
        
        evaluated_cases = []
        
        for i, test_case in enumerate(test_cases, 1):
            print(f"\n{'#'*80}")
            print(f"TEST CASE {i}/{len(test_cases)}")
            print(f"{'#'*80}")
            
            evaluated_case = self.evaluate_single(test_case, auto_score=auto_score)
            evaluated_cases.append(evaluated_case)
            
            if i < len(test_cases):
                print("\n" + "─"*80)
                input("Press Enter to continue to next test case...")
        
        # Create results
        results = EvaluationResults(
            test_cases=evaluated_cases,
            timestamp=datetime.now().isoformat()
        )
        results.calculate_summary()
        
        # Display summary
        self._display_summary(results)
        
        # Save results
        if save_results:
            self._save_results(results)
        
        return results
    
    def _display_summary(self, results: EvaluationResults):
        """Display evaluation summary"""
        print("\n\n" + "="*80)
        print("[*] EVALUATION SUMMARY")
        print("="*80)
        
        categories = ["accuracy", "grounding", "completeness", "no_hallucination", "clarity"]
        
        for category in categories:
            if category in results.overall_scores:
                scores = results.overall_scores[category]
                total = scores["total"]
                
                if total == 0:
                    continue
                
                excellent_pct = (scores["excellent"] / total) * 100
                good_pct = (scores["good"] / total) * 100
                partial_pct = (scores["partial"] / total) * 100
                poor_pct = (scores["poor"] / total) * 100
                
                print(f"\n{category.upper().replace('_', ' ')}:")
                print(f"  [EXCELLENT] Excellent: {scores['excellent']}/{total} ({excellent_pct:.0f}%)")
                print(f"  [GOOD] Good:           {scores['good']}/{total} ({good_pct:.0f}%)")
                print(f"  [PARTIAL] Partial:     {scores['partial']}/{total} ({partial_pct:.0f}%)")
                print(f"  [POOR] Poor:           {scores['poor']}/{total} ({poor_pct:.0f}%)")
        
        # Category breakdown
        print("\n" + "─"*80)
        print("BY CATEGORY:")
        
        category_groups = {}
        for test_case in results.test_cases:
            if test_case.category not in category_groups:
                category_groups[test_case.category] = []
            category_groups[test_case.category].append(test_case)
        
        for category, cases in category_groups.items():
            print(f"\n{category.upper()} ({len(cases)} cases):")
            for test_case in cases:
                # Get average score
                score_values = {"excellent": 4, "good": 3, "partial": 2, "poor": 1}
                avg_score = 0
                count = 0
                for score in test_case.scores.values():
                    if score != EvaluationScore.NA:
                        if score == EvaluationScore.EXCELLENT:
                            avg_score += 4
                        elif score == EvaluationScore.GOOD:
                            avg_score += 3
                        elif score == EvaluationScore.PARTIAL:
                            avg_score += 2
                        elif score == EvaluationScore.POOR:
                            avg_score += 1
                        count += 1
                
                if count > 0:
                    avg_score /= count
                    if avg_score >= 3.5:
                        icon = "[EXCELLENT]"
                    elif avg_score >= 2.5:
                        icon = "[GOOD]"
                    elif avg_score >= 1.5:
                        icon = "[PARTIAL]"
                    else:
                        icon = "[POOR]"
                else:
                    icon = "[N/A]"
                
                print(f"  {icon} {test_case.question[:60]}...")
                if test_case.response:
                    print(f"     Confidence: {test_case.response.confidence}")
    
    def _save_results(self, results: EvaluationResults):
        """Save evaluation results to JSON"""
        output_dir = Path("evaluation_results")
        output_dir.mkdir(exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = output_dir / f"evaluation_{timestamp}.json"
        
        # Convert to serializable format
        data = {
            "timestamp": results.timestamp,
            "test_cases": [
                {
                    "question": tc.question,
                    "category": tc.category,
                    "expected_confidence": tc.expected_confidence,
                    "response": {
                        "answer": tc.response.answer if tc.response else None,
                        "confidence": tc.response.confidence if tc.response else None,
                        "sources": tc.response.sources if tc.response else []
                    },
                    "scores": {k: v.value for k, v in tc.scores.items()},
                    "notes": tc.evaluator_notes
                }
                for tc in results.test_cases
            ],
            "summary": results.overall_scores
        }
        
        with open(output_file, 'w') as f:
            json.dump(data, f, indent=2)
        
        print(f"\n[+] Results saved to: {output_file}")


# Comprehensive test suite
def create_test_suite() -> List[TestCase]:
    """Create comprehensive evaluation test suite"""
    
    return [
        # ========== ANSWERABLE QUESTIONS (High Confidence Expected) ==========
        TestCase(
            question="Who are the three founders of Nvidia?",
            category="answerable",
            expected_confidence="high",
            expected_content="Jensen Huang, Chris Malachowsky, and Curtis Priem",
            should_avoid=["guess", "speculate"],
            notes="should have clear answer"
        ),
        
        TestCase(
            question="What was Nvidia's original primary market focus before expanding into AI?",
            category="answerable",
            expected_confidence="high",
            expected_content="developing graphics processing units (GPUs) specifically for video gaming.",
            should_avoid=["general purpose", "broad market"],
            notes="should state gaming focus explicitly"
        ),
        
        TestCase(
            question="What is CUDA, and why was it strategically important for Nvidia?",
            category="answerable",
            expected_confidence="high",
            expected_content="software platform and API developed by Nvidia that allows developers to use Nvidia GPUs for general purpose processing (GPGPU)",
            should_avoid=["guess", "speculate"],
            notes="should explain both what and why"
        ),
        
        # ========== PARTIALLY ANSWERABLE (Medium Confidence Expected) ==========
        TestCase(
            question="What caused Nvidia's market cap loss in January 2025, and what was DeepSeek's model architecture?",
            category="partial",
            expected_confidence="medium",
            expected_content="Deepseek's model Launch",
            should_avoid=["speculate", "guess"],
            notes="May have partial info - should acknowledge gaps"
        ),
        
        TestCase(
            question="Who are the current board members of Nvidia and what are their backgrounds?",
            category="partial",
            expected_confidence="medium",
            expected_content="names of current board members",
            notes="May not have full bios"
        ),
        
        # ========== UNANSWERABLE (No Information Expected) ==========
        TestCase(
            question="What was Jensen Huang’s personal net worth in 1993?",
            category="unanswerable",
            expected_confidence="no_information",
            expected_content="net worth information not available",
            should_avoid=["estimate", "approximate"],
            notes="Should clearly state info not available"
        ),
        
        TestCase(
            question="What internal email led to the cancellation of the GeForce Partner Program?",
            category="unanswerable",
            expected_confidence="no_information",
            expected_content="don't have information",
            should_avoid=["leak", "rumor"],
            notes="Likely not in policy docs"
        ),
        
        TestCase(
            question="What was the profit margin of the RIVA 128?",
            category="unanswerable",
            expected_confidence="no_information",
            expected_content="don't have information",
            should_avoid=["guess", "assume"],
            notes="unlikely to be documented"
        ),
        
        # ========== EDGE CASES ==========
        TestCase(
            question="",
            category="edge_case",
            expected_confidence="no_information",
            notes="Empty query - should handle gracefully"
        ),
        
        TestCase(
            question="asdfghjkl qwerty",
            category="edge_case",
            expected_confidence="no_information",
            should_avoid=["keyboard", "typing"],
            notes="Nonsense query - should not hallucinate meaning"
        ),
        
        
    ]


# Main execution
if __name__ == "__main__":
    import sys
    from pathlib import Path
    import json
    
    # Handle imports for both module and script execution
    try:
        from .vector_store import ChromaVectorStore
        from .embeddings import EmbeddingGenerator
        from .retrieval import RetrievalPipeline
        from .rag_pipeline import RAGPipeline
    except ImportError:
        from vector_store import ChromaVectorStore
        from embeddings import EmbeddingGenerator
        from retrieval import RetrievalPipeline
        from rag_pipeline import RAGPipeline
    
    from langchain_community.retrievers import BM25Retriever
    from langchain_core.documents import Document
    
    print("="*80)
    print(" RAG SYSTEM EVALUATION FRAMEWORK")
    print("="*80)
    
    if len(sys.argv) > 1 and sys.argv[1] == "--run":
        try:
            # Initialize RAG pipeline
            print("\n1. Initializing RAG pipeline...")
            
            vector_store = ChromaVectorStore(
                persist_directory="data/chroma_db",
                collection_name="policy_documents"
            )
            
            metadata_path = Path("data/chroma_db/chunks_metadata.json")
            with open(metadata_path, 'r', encoding='utf-8') as f:
                chunks_metadata = json.load(f)
            
            # Convert to LangChain Documents for BM25
            from langchain_core.documents import Document
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
            
            retriever =RetrievalPipeline(
                vector_store=vector_store,
                bm25_retriever=bm25_retriever,
                embedding_generator=embedding_generator,
                #use_multi_query=True
            )
            
            rag_pipeline = RAGPipeline(retriever=retriever)
            
            # Create evaluator
            evaluator = RAGEvaluator(rag_pipeline)
            
            # Run evaluation
            print("\n2. Starting evaluation suite...")
            print("\nChoose evaluation mode:")
            print("  1. Manual scoring (recommended)")
            print("  2. Automated scoring (experimental)")
            
            mode = input("\nEnter choice [1/2]: ").strip()
            auto_score = (mode == "2")
            
            test_cases = create_test_suite()
            results = evaluator.evaluate_suite(
                test_cases,
                auto_score=auto_score,
                save_results=True
            )
            
            print("\n[+] Evaluation complete!")
        
        except FileNotFoundError as e:
            print(f"\n[ERROR] {e}")
            print("\nMake sure to run indexing first:")
            print("  python src/indexer.py")
            sys.exit(1)
        
        except Exception as e:
            print(f"\n[ERROR] Evaluation failed: {e}")
            import traceback
            traceback.print_exc()
            sys.exit(1)
    
    else:
        print("\nRAG System Evaluation Framework")
        print("\nFeatures:")
        print("   Comprehensive test suite (10+ test cases)")
        print("   Multiple categories: answerable, partial, unanswerable, edge cases")
        print("   5 evaluation criteria: accuracy, grounding, completeness, hallucination, clarity")
        print("   Manual and automated scoring")
        print("   Detailed reporting and JSON export")
        print("\nTo run evaluation:")
        print("  python src/evaluation.py --run")