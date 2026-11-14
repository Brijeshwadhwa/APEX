"""Unit tests for grounded RAG rubric retrieval module."""

import pytest
from rag.retriever import RubricRetriever, RubricClause


@pytest.fixture
def retriever():
    return RubricRetriever()


def test_rubric_indexing(retriever):
    assert len(retriever.clauses) >= 7
    assert "Clause 1.1" in retriever.clauses
    assert "Clause 1.2" in retriever.clauses
    assert "Clause 2.1" in retriever.clauses
    assert "Clause 2.2" in retriever.clauses
    assert "Clause 2.3" in retriever.clauses
    assert "Clause 3.1" in retriever.clauses
    assert "Clause 3.2" in retriever.clauses


def test_get_clause_by_id(retriever):
    c1 = retriever.get_clause_by_id("Clause 1.1")
    assert c1 is not None
    assert "Academic Minimum Threshold" in c1.title
    assert "60.0%" in c1.text

    c2 = retriever.get_clause_by_id("2.2")
    assert c2 is not None
    assert "Financial Need Dimension" in c2.title


def test_retrieve_relevant_clauses_query(retriever):
    results = retriever.retrieve_relevant_clauses("academic minimum threshold percentage", top_k=2)
    assert len(results) > 0
    top_clause = results[0]
    assert top_clause.clause_id == "Clause 1.1"

    need_results = retriever.retrieve_relevant_clauses("household income brackets need", top_k=2)
    assert len(need_results) > 0
    assert any("Financial Need" in c.title or "Household Income" in c.title for c in need_results)


def test_citation_formatting(retriever):
    clauses = [retriever.get_clause_by_id("Clause 1.1"), retriever.get_clause_by_id("Clause 1.2")]
    formatted = retriever.format_grounding_citations(clauses)
    assert "[Clause 1.1 - Academic Minimum Threshold]" in formatted
    assert "[Clause 1.2 - Household Income Ceiling]" in formatted

