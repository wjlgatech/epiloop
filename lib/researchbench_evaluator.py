"""
ResearchBench Evaluator

This module provides evaluation functions for assessing research agent performance
on the ResearchBench dataset. It includes evaluation of:
- Question decomposition quality
- Source coverage and retrieval
- Synthesis and answer quality
- Full benchmark runs

Usage:
    from lib.researchbench_evaluator import ResearchBenchEvaluator

    evaluator = ResearchBenchEvaluator()
    score = evaluator.evaluate_decomposition("AIML-001", generated_sub_questions)
"""

import json
import os
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from collections import defaultdict
import difflib


@dataclass
class EvaluationResult:
    """Container for evaluation results."""
    score: float
    max_score: float
    details: Dict[str, Any]
    feedback: List[str]

    @property
    def normalized_score(self) -> float:
        """Return score normalized to 0-100 scale."""
        if self.max_score == 0:
            return 0.0
        return (self.score / self.max_score) * 100


@dataclass
class BenchmarkReport:
    """Full benchmark evaluation report."""
    total_questions: int
    evaluated_questions: int
    average_decomposition_score: float
    average_source_coverage: float
    average_synthesis_score: float
    overall_score: float
    domain_scores: Dict[str, float]
    difficulty_scores: Dict[str, float]
    per_question_results: Dict[str, Dict[str, Any]]

    def to_dict(self) -> Dict:
        """Convert report to dictionary for JSON serialization."""
        return {
            "total_questions": self.total_questions,
            "evaluated_questions": self.evaluated_questions,
            "average_decomposition_score": self.average_decomposition_score,
            "average_source_coverage": self.average_source_coverage,
            "average_synthesis_score": self.average_synthesis_score,
            "overall_score": self.overall_score,
            "domain_scores": self.domain_scores,
            "difficulty_scores": self.difficulty_scores,
            "per_question_results": self.per_question_results
        }


class ResearchBenchEvaluator:
    """
    Evaluator for ResearchBench research agent assessments.

    This class loads the ResearchBench dataset and provides methods for
    evaluating different aspects of research agent performance.
    """

    def __init__(self, data_dir: Optional[str] = None):
        """
        Initialize the evaluator with the ResearchBench dataset.

        Args:
            data_dir: Path to the researchbench data directory.
                     Defaults to ../data/researchbench relative to this file.
        """
        if data_dir is None:
            # Default to sibling data directory
            module_dir = Path(__file__).parent
            data_dir = module_dir.parent / "data" / "researchbench"

        self.data_dir = Path(data_dir)
        self.questions_file = self.data_dir / "questions.json"
        self.ground_truth_dir = self.data_dir / "ground_truth"

        # Load questions
        self.questions = self._load_questions()
        self.questions_by_id = {q["id"]: q for q in self.questions}

        # Load ground truth where available
        self.ground_truth = self._load_ground_truth()

    def _load_questions(self) -> List[Dict]:
        """Load all questions from the dataset."""
        if not self.questions_file.exists():
            raise FileNotFoundError(f"Questions file not found: {self.questions_file}")

        with open(self.questions_file, 'r') as f:
            return json.load(f)

    def _load_ground_truth(self) -> Dict[str, Dict]:
        """Load all available ground truth files."""
        ground_truth = {}

        if not self.ground_truth_dir.exists():
            return ground_truth

        for gt_file in self.ground_truth_dir.glob("*.json"):
            question_id = gt_file.stem
            with open(gt_file, 'r') as f:
                ground_truth[question_id] = json.load(f)

        return ground_truth

    def get_question(self, question_id: str) -> Optional[Dict]:
        """Get a question by its ID."""
        return self.questions_by_id.get(question_id)

    def get_ground_truth(self, question_id: str) -> Optional[Dict]:
        """Get ground truth for a question if available."""
        return self.ground_truth.get(question_id)

    def has_ground_truth(self, question_id: str) -> bool:
        """Check if ground truth exists for a question."""
        return question_id in self.ground_truth

    def evaluate_decomposition(
        self,
        question_id: str,
        generated_sub_questions: List[str]
    ) -> EvaluationResult:
        """
        Evaluate the quality of question decomposition.

        Compares generated sub-questions against expected sub-questions
        from the dataset, measuring coverage and relevance.

        Args:
            question_id: The ID of the research question.
            generated_sub_questions: List of sub-questions generated by the agent.

        Returns:
            EvaluationResult with score (0-100) and detailed feedback.
        """
        question = self.get_question(question_id)
        if question is None:
            return EvaluationResult(
                score=0,
                max_score=100,
                details={"error": f"Question {question_id} not found"},
                feedback=[f"Question {question_id} not found in dataset"]
            )

        expected_sub_questions = question.get("sub_questions", [])
        if not expected_sub_questions:
            return EvaluationResult(
                score=50,
                max_score=100,
                details={"warning": "No expected sub-questions for comparison"},
                feedback=["No expected sub-questions available for this question"]
            )

        # Scoring components
        coverage_score = 0
        relevance_score = 0
        detail_score = 0
        feedback = []
        details = {
            "expected_count": len(expected_sub_questions),
            "generated_count": len(generated_sub_questions),
            "matched_topics": [],
            "missing_topics": [],
            "extra_topics": []
        }

        # Normalize questions for comparison
        def normalize(text: str) -> str:
            return re.sub(r'[^\w\s]', '', text.lower())

        expected_normalized = [normalize(q) for q in expected_sub_questions]
        generated_normalized = [normalize(q) for q in generated_sub_questions]

        # Check coverage of expected topics
        matched_expected = set()
        for i, exp in enumerate(expected_normalized):
            exp_words = set(exp.split())
            best_match_score = 0
            best_match_idx = -1

            for j, gen in enumerate(generated_normalized):
                gen_words = set(gen.split())
                # Calculate Jaccard-like similarity
                if exp_words or gen_words:
                    overlap = len(exp_words & gen_words)
                    union = len(exp_words | gen_words)
                    similarity = overlap / union if union > 0 else 0

                    if similarity > best_match_score:
                        best_match_score = similarity
                        best_match_idx = j

            if best_match_score >= 0.3:  # Threshold for considering a match
                matched_expected.add(i)
                details["matched_topics"].append({
                    "expected": expected_sub_questions[i],
                    "matched": generated_sub_questions[best_match_idx] if best_match_idx >= 0 else None,
                    "similarity": best_match_score
                })
            else:
                details["missing_topics"].append(expected_sub_questions[i])

        # Calculate coverage score (how many expected topics were covered)
        coverage_score = (len(matched_expected) / len(expected_sub_questions)) * 40

        # Calculate relevance score (penalize too few or too many sub-questions)
        count_ratio = len(generated_sub_questions) / len(expected_sub_questions)
        if 0.5 <= count_ratio <= 2.0:
            relevance_score = 30
        elif 0.25 <= count_ratio <= 3.0:
            relevance_score = 20
        else:
            relevance_score = 10

        # Calculate detail score (reward well-formed questions)
        well_formed_count = sum(
            1 for q in generated_sub_questions
            if len(q.split()) >= 5 and q.strip().endswith('?')
        )
        detail_score = (well_formed_count / max(len(generated_sub_questions), 1)) * 30

        # Generate feedback
        if len(matched_expected) == len(expected_sub_questions):
            feedback.append("Excellent coverage of all expected topics")
        elif len(matched_expected) >= len(expected_sub_questions) * 0.7:
            feedback.append("Good coverage of most expected topics")
        else:
            feedback.append(f"Missing coverage of {len(expected_sub_questions) - len(matched_expected)} expected topics")

        if details["missing_topics"]:
            feedback.append(f"Consider adding questions about: {', '.join(details['missing_topics'][:3])}")

        if len(generated_sub_questions) > len(expected_sub_questions) * 2:
            feedback.append("Consider consolidating sub-questions - may be too granular")
        elif len(generated_sub_questions) < len(expected_sub_questions) * 0.5:
            feedback.append("Consider adding more sub-questions for comprehensive coverage")

        total_score = coverage_score + relevance_score + detail_score

        return EvaluationResult(
            score=total_score,
            max_score=100,
            details=details,
            feedback=feedback
        )

    def evaluate_source_coverage(
        self,
        question_id: str,
        found_sources: List[Dict[str, str]]
    ) -> EvaluationResult:
        """
        Evaluate source coverage against ground truth or expected minimum.

        For questions with ground truth, compares against expert-curated sources.
        For others, evaluates based on expected_sources count.

        Args:
            question_id: The ID of the research question.
            found_sources: List of sources found, each with at least 'title' or 'url'.

        Returns:
            EvaluationResult with recall score (0-100) and detailed feedback.
        """
        question = self.get_question(question_id)
        if question is None:
            return EvaluationResult(
                score=0,
                max_score=100,
                details={"error": f"Question {question_id} not found"},
                feedback=[f"Question {question_id} not found in dataset"]
            )

        ground_truth = self.get_ground_truth(question_id)
        feedback = []
        details = {
            "found_count": len(found_sources),
            "expected_min": question.get("expected_sources", 3)
        }

        # If we have ground truth, compare against expert sources
        if ground_truth and "expert_sources" in ground_truth:
            expert_sources = ground_truth["expert_sources"]
            details["expert_count"] = len(expert_sources)

            # Match sources by title similarity
            matched_sources = []
            for expert in expert_sources:
                expert_title = expert.get("title", "").lower()
                for found in found_sources:
                    found_title = found.get("title", "").lower()
                    # Use sequence matcher for fuzzy matching
                    similarity = difflib.SequenceMatcher(
                        None, expert_title, found_title
                    ).ratio()
                    if similarity >= 0.5:
                        matched_sources.append({
                            "expert": expert["title"],
                            "found": found.get("title"),
                            "similarity": similarity
                        })
                        break

            details["matched_sources"] = matched_sources

            # Calculate recall against expert sources
            recall = len(matched_sources) / len(expert_sources) * 100

            if recall >= 80:
                feedback.append("Excellent source coverage matching expert recommendations")
            elif recall >= 50:
                feedback.append("Good source coverage with several expert-recommended sources")
            else:
                feedback.append("Consider finding more authoritative sources on this topic")

            return EvaluationResult(
                score=recall,
                max_score=100,
                details=details,
                feedback=feedback
            )

        # Without ground truth, evaluate based on quantity and expected minimum
        expected_min = question.get("expected_sources", 3)

        if len(found_sources) >= expected_min * 1.5:
            score = 100
            feedback.append("Comprehensive source coverage exceeding expectations")
        elif len(found_sources) >= expected_min:
            score = 80
            feedback.append("Adequate source coverage meeting expectations")
        elif len(found_sources) >= expected_min * 0.5:
            score = 50
            feedback.append("Partial source coverage - consider finding additional sources")
        else:
            score = 20
            feedback.append(f"Insufficient sources - expected at least {expected_min}")

        return EvaluationResult(
            score=score,
            max_score=100,
            details=details,
            feedback=feedback
        )

    def evaluate_synthesis(
        self,
        question_id: str,
        synthesis_text: str
    ) -> EvaluationResult:
        """
        Evaluate the quality of synthesized research answer.

        Assesses coherence, completeness, and accuracy against evaluation criteria.
        For questions with ground truth, checks for key findings coverage.

        Args:
            question_id: The ID of the research question.
            synthesis_text: The synthesized answer text.

        Returns:
            EvaluationResult with coherence score (0-100) and detailed feedback.
        """
        question = self.get_question(question_id)
        if question is None:
            return EvaluationResult(
                score=0,
                max_score=100,
                details={"error": f"Question {question_id} not found"},
                feedback=[f"Question {question_id} not found in dataset"]
            )

        ground_truth = self.get_ground_truth(question_id)
        feedback = []
        details = {
            "word_count": len(synthesis_text.split()),
            "paragraph_count": len([p for p in synthesis_text.split('\n\n') if p.strip()])
        }

        synthesis_lower = synthesis_text.lower()

        # Base coherence metrics
        coherence_score = 0

        # Length assessment (expect substantial answer)
        word_count = details["word_count"]
        if word_count >= 500:
            coherence_score += 20
        elif word_count >= 200:
            coherence_score += 15
        elif word_count >= 100:
            coherence_score += 10
        else:
            coherence_score += 5
            feedback.append("Answer may be too brief for comprehensive research synthesis")

        # Structure assessment
        if details["paragraph_count"] >= 3:
            coherence_score += 15
        elif details["paragraph_count"] >= 2:
            coherence_score += 10
        else:
            coherence_score += 5
            feedback.append("Consider organizing answer into more paragraphs")

        # Check for evaluation criteria coverage
        eval_criteria = question.get("evaluation_criteria", "")
        if eval_criteria:
            # Extract key terms from criteria
            criteria_terms = set(re.findall(r'\b\w{4,}\b', eval_criteria.lower()))
            # Check how many appear in synthesis
            matched_terms = sum(1 for term in criteria_terms if term in synthesis_lower)
            criteria_coverage = matched_terms / len(criteria_terms) if criteria_terms else 0
            coherence_score += criteria_coverage * 25
            details["criteria_coverage"] = criteria_coverage
        else:
            coherence_score += 15  # Default if no criteria

        # If ground truth available, check key findings
        if ground_truth and "key_findings" in ground_truth:
            key_findings = ground_truth["key_findings"]
            findings_matched = 0

            for finding in key_findings:
                finding_text = finding.get("finding", "").lower()
                # Extract key terms from finding
                finding_terms = set(re.findall(r'\b\w{4,}\b', finding_text))
                # Check if majority of terms appear
                if finding_terms:
                    matches = sum(1 for term in finding_terms if term in synthesis_lower)
                    if matches / len(finding_terms) >= 0.5:
                        findings_matched += 1

            findings_coverage = findings_matched / len(key_findings)
            coherence_score += findings_coverage * 30
            details["key_findings_coverage"] = findings_coverage
            details["findings_matched"] = findings_matched
            details["findings_total"] = len(key_findings)

            if findings_coverage >= 0.7:
                feedback.append("Good coverage of key findings from expert analysis")
            elif findings_coverage >= 0.4:
                feedback.append("Partial coverage of key findings - some important points may be missing")
            else:
                feedback.append("Consider incorporating more key findings on this topic")
        else:
            coherence_score += 20  # Default if no ground truth

        # Check for balanced perspective (if counterarguments available)
        if ground_truth and "known_counterarguments" in ground_truth:
            counterargs = ground_truth["known_counterarguments"]
            balance_terms = ["however", "although", "but", "limitation", "challenge",
                          "criticism", "debate", "counterargument", "alternatively"]
            balance_indicators = sum(1 for term in balance_terms if term in synthesis_lower)

            if balance_indicators >= 2:
                coherence_score += 10
                feedback.append("Good balance considering multiple perspectives")
            elif balance_indicators >= 1:
                coherence_score += 5
            else:
                feedback.append("Consider addressing counterarguments or limitations")

        # Ensure score doesn't exceed 100
        coherence_score = min(coherence_score, 100)

        return EvaluationResult(
            score=coherence_score,
            max_score=100,
            details=details,
            feedback=feedback
        )

    def run_benchmark(
        self,
        agent_output_dir: str,
        questions_subset: Optional[List[str]] = None
    ) -> BenchmarkReport:
        """
        Run full benchmark evaluation on agent outputs.

        Expects agent output directory to contain JSON files named by question_id,
        each with:
        - sub_questions: List of decomposed sub-questions
        - sources: List of sources found
        - synthesis: Final answer text

        Args:
            agent_output_dir: Directory containing agent output JSON files.
            questions_subset: Optional list of question IDs to evaluate.
                            If None, evaluates all questions with outputs.

        Returns:
            BenchmarkReport with comprehensive evaluation results.
        """
        output_dir = Path(agent_output_dir)
        if not output_dir.exists():
            raise FileNotFoundError(f"Agent output directory not found: {output_dir}")

        # Determine which questions to evaluate
        if questions_subset:
            question_ids = questions_subset
        else:
            # Find all output files
            question_ids = [f.stem for f in output_dir.glob("*.json")]

        # Collect results
        decomposition_scores = []
        source_scores = []
        synthesis_scores = []
        domain_results = defaultdict(list)
        difficulty_results = defaultdict(list)
        per_question_results = {}

        evaluated_count = 0

        for q_id in question_ids:
            output_file = output_dir / f"{q_id}.json"
            question = self.get_question(q_id)

            if not output_file.exists() or question is None:
                continue

            with open(output_file, 'r') as f:
                agent_output = json.load(f)

            evaluated_count += 1

            # Evaluate decomposition
            sub_questions = agent_output.get("sub_questions", [])
            decomp_result = self.evaluate_decomposition(q_id, sub_questions)
            decomposition_scores.append(decomp_result.normalized_score)

            # Evaluate source coverage
            sources = agent_output.get("sources", [])
            source_result = self.evaluate_source_coverage(q_id, sources)
            source_scores.append(source_result.normalized_score)

            # Evaluate synthesis
            synthesis = agent_output.get("synthesis", "")
            synth_result = self.evaluate_synthesis(q_id, synthesis)
            synthesis_scores.append(synth_result.normalized_score)

            # Aggregate by domain and difficulty
            domain = question.get("domain", "Unknown")
            difficulty = question.get("difficulty", "medium")

            overall_q_score = (
                decomp_result.normalized_score * 0.25 +
                source_result.normalized_score * 0.35 +
                synth_result.normalized_score * 0.40
            )

            domain_results[domain].append(overall_q_score)
            difficulty_results[difficulty].append(overall_q_score)

            per_question_results[q_id] = {
                "decomposition_score": decomp_result.normalized_score,
                "source_coverage_score": source_result.normalized_score,
                "synthesis_score": synth_result.normalized_score,
                "overall_score": overall_q_score,
                "decomposition_feedback": decomp_result.feedback,
                "source_feedback": source_result.feedback,
                "synthesis_feedback": synth_result.feedback
            }

        # Calculate averages
        def safe_avg(scores):
            return sum(scores) / len(scores) if scores else 0.0

        avg_decomp = safe_avg(decomposition_scores)
        avg_source = safe_avg(source_scores)
        avg_synth = safe_avg(synthesis_scores)

        overall = (avg_decomp * 0.25 + avg_source * 0.35 + avg_synth * 0.40)

        domain_scores = {d: safe_avg(s) for d, s in domain_results.items()}
        difficulty_scores = {d: safe_avg(s) for d, s in difficulty_results.items()}

        return BenchmarkReport(
            total_questions=len(self.questions),
            evaluated_questions=evaluated_count,
            average_decomposition_score=avg_decomp,
            average_source_coverage=avg_source,
            average_synthesis_score=avg_synth,
            overall_score=overall,
            domain_scores=domain_scores,
            difficulty_scores=difficulty_scores,
            per_question_results=per_question_results
        )

    def get_questions_by_domain(self, domain: str) -> List[Dict]:
        """Get all questions for a specific domain."""
        return [q for q in self.questions if q.get("domain") == domain]

    def get_questions_by_difficulty(self, difficulty: str) -> List[Dict]:
        """Get all questions for a specific difficulty level."""
        return [q for q in self.questions if q.get("difficulty") == difficulty]

    def get_questions_with_ground_truth(self) -> List[Dict]:
        """Get all questions that have ground truth available."""
        return [q for q in self.questions if q["id"] in self.ground_truth]

    def get_dataset_statistics(self) -> Dict:
        """Get statistics about the dataset."""
        domains = defaultdict(int)
        difficulties = defaultdict(int)

        for q in self.questions:
            domains[q.get("domain", "Unknown")] += 1
            difficulties[q.get("difficulty", "medium")] += 1

        return {
            "total_questions": len(self.questions),
            "questions_with_ground_truth": len(self.ground_truth),
            "questions_by_domain": dict(domains),
            "questions_by_difficulty": dict(difficulties),
            "domains": list(domains.keys()),
            "difficulty_levels": list(difficulties.keys())
        }


# Convenience functions for direct use
def evaluate_decomposition(question_id: str, generated_sub_questions: List[str]) -> float:
    """Convenience function to evaluate decomposition, returning score 0-100."""
    evaluator = ResearchBenchEvaluator()
    result = evaluator.evaluate_decomposition(question_id, generated_sub_questions)
    return result.normalized_score


def evaluate_source_coverage(question_id: str, found_sources: List[Dict[str, str]]) -> float:
    """Convenience function to evaluate source coverage, returning recall score 0-100."""
    evaluator = ResearchBenchEvaluator()
    result = evaluator.evaluate_source_coverage(question_id, found_sources)
    return result.normalized_score


def evaluate_synthesis(question_id: str, synthesis_text: str) -> float:
    """Convenience function to evaluate synthesis, returning coherence score 0-100."""
    evaluator = ResearchBenchEvaluator()
    result = evaluator.evaluate_synthesis(question_id, synthesis_text)
    return result.normalized_score


def run_benchmark(agent_output_dir: str) -> Dict:
    """Convenience function to run full benchmark, returning report as dict."""
    evaluator = ResearchBenchEvaluator()
    report = evaluator.run_benchmark(agent_output_dir)
    return report.to_dict()


if __name__ == "__main__":
    # Example usage and dataset statistics
    evaluator = ResearchBenchEvaluator()
    stats = evaluator.get_dataset_statistics()

    print("ResearchBench Dataset Statistics")
    print("=" * 40)
    print(f"Total questions: {stats['total_questions']}")
    print(f"Questions with ground truth: {stats['questions_with_ground_truth']}")
    print("\nQuestions by domain:")
    for domain, count in stats['questions_by_domain'].items():
        print(f"  {domain}: {count}")
    print("\nQuestions by difficulty:")
    for diff, count in stats['questions_by_difficulty'].items():
        print(f"  {diff}: {count}")
