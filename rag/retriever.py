"""Grounded RAG retrieval module over official scholarship evaluation rubric.

Provides deterministic, reproducible clause extraction and retrieval without requiring
external third-party API keys or remote vector services.
"""

from dataclasses import dataclass, field
import os
import re
from typing import Dict, List, Optional


@dataclass
class RubricClause:
    clause_id: str
    section: str
    title: str
    text: str
    keywords: List[str] = field(default_factory=list)

    @property
    def citation(self) -> str:
        return f"{self.clause_id}: {self.title}"


class RubricRetriever:
    """Extracts, indexes, and retrieves grounded clauses from the scholarship rubric."""

    def __init__(self, rubric_file_path: Optional[str] = None) -> None:
        if rubric_file_path is None:
            # Default relative to this module
            base_dir = os.path.dirname(os.path.abspath(__file__))
            rubric_file_path = os.path.join(base_dir, "scholarship_rubric.md")
        
        self.rubric_file_path = os.path.abspath(rubric_file_path)
        self.clauses: Dict[str, RubricClause] = {}
        self._load_and_index_rubric()

    def _load_and_index_rubric(self) -> None:
        """Parse markdown rubric into structured indexed clauses."""
        if not os.path.exists(self.rubric_file_path):
            raise FileNotFoundError(f"Rubric file not found at: {self.rubric_file_path}")

        with open(self.rubric_file_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Split on section/clause headers
        current_section = "General Overview"
        # Regex to capture "### Clause X.Y: Title" followed by body
        clause_pattern = re.compile(
            r"###\s+(Clause\s+(\d+\.\d+)):\s*([^\n]+)\n(.*?)(?=(?:###|\Z))",
            re.DOTALL
        )

        section_pattern = re.compile(r"##\s+SECTION\s+\d+:\s*([^\n]+)")

        lines = content.splitlines()
        current_section = "Overview"

        # Extract clauses with section tracking
        raw_sections = content.split("## SECTION ")
        for sec in raw_sections[1:]:
            lines = sec.splitlines()
            sec_header = lines[0].split(":", 1)
            sec_name = sec_header[1].strip() if len(sec_header) > 1 else sec_header[0].strip()

            for match in clause_pattern.finditer(sec):
                clause_label = match.group(1).strip()  # e.g. "Clause 1.1"
                clause_num = match.group(2).strip()    # e.g. "1.1"
                title = match.group(3).strip()         # e.g. "Academic Minimum Threshold"
                body = match.group(4).strip()

                # Generate search tokens
                tokens = re.findall(r"\w+", (title + " " + body).lower())
                stop_words = {"the", "a", "an", "and", "or", "in", "of", "to", "for", "is", "are", "be", "with", "by", "from"}
                filtered_keywords = list({t for t in tokens if t not in stop_words and len(t) > 2})

                clause_id = f"Clause {clause_num}"
                self.clauses[clause_id] = RubricClause(
                    clause_id=clause_id,
                    section=sec_name,
                    title=title,
                    text=body,
                    keywords=filtered_keywords,
                )

    def get_clause_by_id(self, clause_id: str) -> Optional[RubricClause]:
        """Fetch a specific clause directly (e.g. 'Clause 1.1' or '1.1')."""
        normalized_id = clause_id if clause_id.startswith("Clause ") else f"Clause {clause_id}"
        return self.clauses.get(normalized_id)

    def retrieve_relevant_clauses(self, query: str, top_k: int = 2) -> List[RubricClause]:
        """Rank and return top_k most relevant rubric clauses using grounded keyword relevance."""
        query_tokens = set(re.findall(r"\w+", query.lower()))
        scored_clauses = []

        for clause in self.clauses.values():
            score = 0
            # Higher weight for title overlap
            title_tokens = set(re.findall(r"\w+", clause.title.lower()))
            score += len(query_tokens.intersection(title_tokens)) * 3

            # Body keyword overlap
            body_tokens = set(clause.keywords)
            score += len(query_tokens.intersection(body_tokens)) * 1

            # Exact query phrase boost
            if query.lower() in clause.text.lower():
                score += 5

            scored_clauses.append((score, clause))

        scored_clauses.sort(key=lambda x: x[0], reverse=True)
        return [clause for score, clause in scored_clauses[:top_k] if score > 0]

    def format_grounding_citations(self, clauses: List[RubricClause]) -> str:
        """Format a human-readable grounding reference block for justifications."""
        if not clauses:
            return "No matching rubric clause cited."
        citations = [f"[{c.clause_id} - {c.title}] {c.text}" for c in clauses]
        return "\n".join(citations)

