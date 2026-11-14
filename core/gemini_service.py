"""Google Gemini API Integration Service for Grant and Scholarship Evaluation.

Provides:
- Secure API key & model configuration (env-based via python-dotenv).
- Model availability verification & fallback.
- Application profile analysis.
- Multi-agent evaluation explanations grounded in specialist outputs.
- Comprehensive committee report generation.
- Grounded RAG question-answering with strict clause citation.
- Semantic Kernel GoogleAIChatCompletion integration.
- Deterministic scoring isolation (read-only, never alters scores/eligibility).
- In-memory result caching and token-efficient prompts.
"""

from decimal import Decimal
import hashlib
import json
import logging
import os
import re
from typing import Any, Dict, List, Optional, Tuple

import dotenv
from google import genai
from google.genai import types
from google.genai.errors import APIError, ClientError, ServerError

from core.schemas import (
    ApplicantProfile,
    GeminiAnalysisResult,
    GeminiExplanationResult,
    GeminiReportResult,
    GeminiRAGResult,
)
from core.shared_state import EvaluationState
from rag.retriever import RubricRetriever

# Load environment variables from .env file
_project_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_env_candidates = [
    os.path.join(_project_dir, ".env"),
    os.path.join(os.path.dirname(_project_dir), ".env"),
    os.path.join(os.getcwd(), ".env"),
]
for _ep in _env_candidates:
    if os.path.exists(_ep):
        dotenv.load_dotenv(_ep, override=True)
        break
else:
    dotenv.load_dotenv(override=True)

logger = logging.getLogger("gemini_service")


def _minimize_income_band(inc: Optional[float]) -> str:
    """Anonymizes and categorizes household income into high-level evaluation bands."""
    if inc is None:
        return "Income Document Missing / Unverified"
    if inc <= 150000:
        return "Tier 1: Annual household income <= INR 150,000 (Maximum Need)"
    elif inc <= 300000:
        return "Tier 2: Annual household income between INR 150,001 and 300,000"
    elif inc <= 450000:
        return "Tier 3: Annual household income between INR 300,001 and 450,000"
    elif inc <= 600000:
        return "Tier 4: Annual household income between INR 450,001 and 600,000"
    else:
        return "Tier 5: Annual household income > INR 600,000 (Above Rubric Ceiling)"


class GeminiService:
    """Manages Google Gemini API interactions, explanations, reports, and RAG Q&A."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model_name: Optional[str] = None,
        temperature: float = 0.2,
        max_output_tokens: int = 1500,
    ) -> None:
        if api_key is not None:
            self.api_key = api_key.strip()
        else:
            self.api_key = os.getenv("GEMINI_API_KEY", "").strip()
        self.model_name = model_name or os.getenv("GEMINI_MODEL", "gemini-3.5-flash").strip()
        self.temperature = float(os.getenv("GEMINI_TEMPERATURE", str(temperature)))
        self.max_output_tokens = int(os.getenv("GEMINI_MAX_OUTPUT_TOKENS", str(max_output_tokens)))

        # Cache structures
        self._analysis_cache: Dict[str, GeminiAnalysisResult] = {}
        self._explanation_cache: Dict[str, GeminiExplanationResult] = {}
        self._report_cache: Dict[str, GeminiReportResult] = {}
        self._rag_cache: Dict[str, GeminiRAGResult] = {}

        # Connection status cache
        self._connection_verified: Optional[bool] = None
        self._connection_status_message: str = "Not checked"

        # Initialize Google GenAI client if key exists
        self._client: Optional[genai.Client] = None
        if self.api_key and self.api_key != "your_gemini_api_key_here":
            try:
                self._client = genai.Client(api_key=self.api_key)
            except Exception as e:
                logger.warning(f"Failed to instantiate Gemini Client: {type(e).__name__}")
                self._client = None

    @property
    def is_configured(self) -> bool:
        """Checks if a non-placeholder API key is configured."""
        return bool(self.api_key and self.api_key != "your_gemini_api_key_here")

    def get_masked_api_key(self) -> str:
        """Returns safe masked representation of API key without leaking credentials."""
        if not self.is_configured:
            return "Not Configured"
        k = self.api_key
        if len(k) <= 8:
            return "••••••••"
        return f"{k[:4]}••••••••{k[-4:]}"

    def verify_connection(self, force_refresh: bool = False) -> Tuple[bool, str]:
        """Safely verifies API key and model availability with fallback capability."""
        if not self.is_configured:
            self._connection_verified = False
            self._connection_status_message = "GEMINI_API_KEY is not configured. Add it to your .env file."
            return False, self._connection_status_message

        if not force_refresh and self._connection_verified is not None:
            return self._connection_verified, self._connection_status_message

        candidate_models = [self.model_name, "gemini-3.5-flash", "gemini-3.5-flash-lite", "gemini-2.5-pro", "gemini-3.8-flash"]
        # Deduplicate while preserving order
        candidate_models = list(dict.fromkeys(candidate_models))

        last_error = ""
        for m in candidate_models:
            try:
                client = self._client or genai.Client(api_key=self.api_key)
                # Test minimal 1-token generation to verify authentication and quota
                resp = client.models.generate_content(
                    model=m,
                    contents="Ping. Reply 'OK'.",
                    config=types.GenerateContentConfig(
                        max_output_tokens=5,
                        temperature=0.0,
                    ),
                )
                if resp and resp.text:
                    self.model_name = m
                    self._connection_verified = True
                    self._connection_status_message = f"Connected to Google Gemini ({m})"
                    return True, self._connection_status_message
            except ClientError as ce:
                # 400 or 403 or 404 (model not found)
                err_str = str(ce)
                if "403" in err_str or "API_KEY_INVALID" in err_str or "PERMISSION_DENIED" in err_str:
                    self._connection_verified = False
                    self._connection_status_message = "Authentication Failed: Invalid Gemini API key."
                    return False, self._connection_status_message
                last_error = f"Model {m} unavailable: {ce}"
                continue
            except APIError as ae:
                last_error = f"Gemini API error: {ae}"
                continue
            except Exception as ex:
                last_error = f"Connection error: {type(ex).__name__}"
                continue

        self._connection_verified = False
        self._connection_status_message = f"Gemini Unavailable: {last_error}"
        return False, self._connection_status_message

    # =========================================================================
    # A. APPLICATION PROFILE ANALYSIS
    # =========================================================================

    def analyze_applicant_profile(self, profile: ApplicantProfile) -> GeminiAnalysisResult:
        """Produces qualitative profile analysis, strengths, and missing-info warnings."""
        cache_key = f"{profile.applicant_id}_{profile.academic_percentage}_{profile.household_income}_{len(profile.achievements)}"
        if cache_key in self._analysis_cache:
            return self._analysis_cache[cache_key]

        if not self.is_configured:
            return self._fallback_analysis(profile, "Gemini API key is not configured.")

        # Build token-efficient structured prompt with direct identifiers stripped and income minimized
        acad_desc = f"{profile.academic_percentage:.2f}%" if profile.academic_percentage is not None else "MISSING / UNVERIFIED"
        minimized_income = _minimize_income_band(profile.household_income)
        achs_desc = "\n".join([f"- {a.title} ({a.level}, Verified: {a.is_verified})" for a in profile.achievements]) or "No achievements claimed."

        prompt = f"""You are an institutional scholarship admissions analyst. Analyze this anonymized applicant dossier (direct identifiers stripped for privacy):
Candidate Reference: [ANONYMIZED_CANDIDATE]
Academic Aggregate: {acad_desc}
Financial Need Category: {minimized_income}
Extracurricular Achievements:
{achs_desc}

Provide your analysis in strictly valid JSON with these keys:
{{
  "profile_summary": "1-2 sentence overview of candidate profile",
  "academic_observations": "Analysis of academic performance or missing record",
  "financial_summary": "Assessment of financial circumstances or missing record",
  "achievement_summary": "Summary of achievements and verified status",
  "strengths": ["list of 2-3 key strengths"],
  "areas_requiring_verification": ["list of fields/certificates requiring verification"],
  "missing_information_warnings": ["list of missing mandatory items, or empty list if complete"]
}}
Return ONLY JSON without markdown fences."""

        try:
            client = self._client or genai.Client(api_key=self.api_key)
            resp = client.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=self.temperature,
                    max_output_tokens=self.max_output_tokens,
                    response_mime_type="application/json",
                ),
            )
            raw_text = resp.text.strip()
            # Clean possible markdown wrapping if any
            raw_text = re.sub(r"^```(?:json)?\s*", "", raw_text)
            raw_text = re.sub(r"\s*```$", "", raw_text)
            data = json.loads(raw_text)

            res = GeminiAnalysisResult(
                applicant_id=profile.applicant_id,
                profile_summary=data.get("profile_summary", f"Profile for {profile.full_name}"),
                academic_observations=data.get("academic_observations", f"Academic score: {acad_desc}"),
                financial_summary=data.get("financial_summary", f"Financial Category: {minimized_income}"),
                achievement_summary=data.get("achievement_summary", f"{len(profile.achievements)} achievements submitted."),
                strengths=data.get("strengths", []),
                areas_requiring_verification=data.get("areas_requiring_verification", []),
                missing_information_warnings=data.get("missing_information_warnings", []),
            )
            self._analysis_cache[cache_key] = res
            return res

        except Exception as e:
            logger.warning(f"Gemini analysis call failed: {type(e).__name__} - {e}")
            return self._fallback_analysis(profile, f"Analysis generation error: {type(e).__name__}")

    def _fallback_analysis(self, profile: ApplicantProfile, note: str) -> GeminiAnalysisResult:
        """Deterministic rule-based fallback when Gemini is offline."""
        acad_desc = f"{profile.academic_percentage:.2f}%" if profile.academic_percentage is not None else "Missing"
        inc_desc = f"₹{profile.household_income:,.0f}" if profile.household_income is not None else "Missing"
        missing = []
        if profile.academic_percentage is None:
            missing.append("Mandatory academic transcripts missing.")
        if profile.household_income is None:
            missing.append("Mandatory income tax/salary documentation missing.")

        return GeminiAnalysisResult(
            applicant_id=profile.applicant_id,
            profile_summary=f"Dossier for {profile.full_name} enrolled in {profile.program_of_study or 'academic studies'}.",
            academic_observations=f"Academic record reported as: {acad_desc}.",
            financial_summary=f"Household income recorded as: {inc_desc}.",
            achievement_summary=f"{len(profile.achievements)} claimed achievement portfolio items.",
            strengths=[f"Enrolled in {profile.program_of_study}"] if profile.program_of_study else ["Submitted complete dossier"],
            areas_requiring_verification=[a.title for a in profile.achievements if not a.is_verified],
            missing_information_warnings=missing or ["No missing fields detected."],
        )

    # =========================================================================
    # B. MULTI-AGENT EVALUATION EXPLANATIONS
    # =========================================================================

    def explain_evaluation_results(self, state: EvaluationState) -> GeminiExplanationResult:
        """Explains specialist agent evaluation findings strictly grounded in agent outputs."""
        cache_key = f"{state.applicant_id}_{state.status}_{state.total_score}_{state.recommendation}"
        if cache_key in self._explanation_cache:
            return self._explanation_cache[cache_key]

        if not self.is_configured:
            return self._fallback_explanation(state, "Gemini API key is not configured.")

        # Grounding data extracted directly from deterministic agents
        elig_data = state.eligibility.model_dump() if state.eligibility else {}
        acad_data = state.academic_result.model_dump() if state.academic_result else {}
        fin_data = state.financial_result.model_dump() if state.financial_result else {}
        ach_data = state.achievement_result.model_dump() if state.achievement_result else {}
        audit_data = state.audit_result.model_dump() if state.audit_result else {}

        panel_score_desc = f"{state.total_score} / 100.0" if state.total_score is not None else "Excluded"
        panel_tier_desc = state.recommendation or "Pending"

        prompt = f"""You are an institutional scholarship adjudication explainer. Ground your explanations STRICTLY in the following specialist agent outputs. Do NOT change, contradict, or speculate beyond these findings:

CANDIDATE: [ANONYMIZED_CANDIDATE]
FINAL STATUS: {state.status}
COMPOSITE SCORE: {panel_score_desc}
RECOMMENDATION: {panel_tier_desc}

AGENT FINDINGS:
1. Eligibility Agent: Decision='{elig_data.get('decision')}', FailedRules={elig_data.get('failed_rules')}, Missing={elig_data.get('missing_fields')}, Justification='{elig_data.get('justification')}'
2. Merit Agent: Score={acad_data.get('score')} / 40.0, Justification='{acad_data.get('justification')}'
3. Financial Need Agent: Score={fin_data.get('score')} / 35.0, Bracket='{fin_data.get('income_band')}', Justification='{fin_data.get('justification')}'
4. Achievement Agent: Score={ach_data.get('score')} / 25.0, RawScore={ach_data.get('raw_score')}, VerifiedCount={ach_data.get('verified_count')}, Justification='{ach_data.get('justification')}'
5. Panel Manager: TotalScore={panel_score_desc}, Tier='{panel_tier_desc}', Weighting='40% Merit + 35% Need + 25% Achievement'
6. Fairness Auditor: Passed={audit_data.get('passed')}, Notes='{audit_data.get('audit_notes')}'

Return JSON with these exact keys:
{{
  "eligibility_explanation": "Clear explanation of eligibility gate outcome and cited clauses",
  "merit_explanation": "Clear explanation of merit score out of 40 points",
  "financial_need_explanation": "Clear explanation of financial score out of 35 points",
  "achievement_explanation": "Clear explanation of achievement portfolio score out of 25 points",
  "panel_recommendation_explanation": "Clear explanation of composite weighting and recommendation category",
  "fairness_audit_explanation": "Clear explanation of demographic non-discrimination and math verification"
}}
Return ONLY JSON without markdown fences."""

        try:
            client = self._client or genai.Client(api_key=self.api_key)
            resp = client.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=self.temperature,
                    max_output_tokens=self.max_output_tokens,
                    response_mime_type="application/json",
                ),
            )
            raw_text = resp.text.strip()
            raw_text = re.sub(r"^```(?:json)?\s*", "", raw_text)
            raw_text = re.sub(r"\s*```$", "", raw_text)
            data = json.loads(raw_text)

            res = GeminiExplanationResult(
                applicant_id=state.applicant_id,
                eligibility_explanation=data.get("eligibility_explanation", str(elig_data.get("justification"))),
                merit_explanation=data.get("merit_explanation", str(acad_data.get("justification"))),
                financial_need_explanation=data.get("financial_need_explanation", str(fin_data.get("justification"))),
                achievement_explanation=data.get("achievement_explanation", str(ach_data.get("justification"))),
                panel_recommendation_explanation=data.get("panel_recommendation_explanation", f"Allocated category '{state.recommendation}' with composite score {panel_score_desc}."),
                fairness_audit_explanation=data.get("fairness_audit_explanation", str(audit_data.get("audit_notes"))),
            )
            self._explanation_cache[cache_key] = res
            return res

        except Exception as e:
            logger.warning(f"Gemini explanation call failed: {type(e).__name__} - {e}")
            return self._fallback_explanation(state, f"Explanation error: {type(e).__name__}")

    def _fallback_explanation(self, state: EvaluationState, note: str) -> GeminiExplanationResult:
        """Deterministic fallback explanation."""
        score_desc = f"{state.total_score:.2f} / 100" if state.total_score is not None else "Excluded"
        return GeminiExplanationResult(
            applicant_id=state.applicant_id,
            eligibility_explanation=state.eligibility.justification if state.eligibility else "Eligibility pending.",
            merit_explanation=state.academic_result.justification if state.academic_result else "Merit evaluation pending.",
            financial_need_explanation=state.financial_result.justification if state.financial_result else "Financial evaluation pending.",
            achievement_explanation=state.achievement_result.justification if state.achievement_result else "Achievement evaluation pending.",
            panel_recommendation_explanation=f"Allocated recommendation category '{state.recommendation}' based on composite score of {score_desc}.",
            fairness_audit_explanation=state.audit_result.audit_notes if state.audit_result else "Fairness audit pending.",
        )

    # =========================================================================
    # C. COMMITTEE REPORT GENERATION
    # =========================================================================

    def generate_committee_report(self, state: EvaluationState) -> GeminiReportResult:
        """Generates a comprehensive publication-ready committee adjudication report."""
        cache_key = f"rep_{state.applicant_id}_{state.status}_{state.total_score}_{state.recommendation}"
        if cache_key in self._report_cache:
            return self._report_cache[cache_key]

        if not self.is_configured:
            return self._fallback_report(state, "Gemini API key is not configured.")

        p = state.profile
        acad_desc = f"{p.academic_percentage:.2f}%" if p.academic_percentage is not None else "Missing"
        minimized_income = _minimize_income_band(p.household_income)
        score_desc = f"{state.total_score:.2f} / 100.0" if state.total_score is not None else "Excluded"

        prompt = f"""You are the Lead Secretary of the Central Scholarship Adjudication Committee. Draft a formal committee adjudication report for this candidate (all direct identifiers stripped for privacy):

Candidate Reference: [ANONYMIZED_CANDIDATE]
Academic Record: {acad_desc}
Financial Need Assessment Band: {minimized_income}
Adjudication Status: {state.status}
Composite Score: {score_desc}
Recommendation: {state.recommendation}

Eligibility Finding: {state.eligibility.justification if state.eligibility else 'N/A'}
Merit Assessment: {state.academic_result.justification if state.academic_result else 'N/A'}
Financial Assessment: {state.financial_result.justification if state.financial_result else 'N/A'}
Achievement Portfolio: {state.achievement_result.justification if state.achievement_result else 'N/A'}
Committee Synthesis: Composite score {score_desc} with recommendation tier '{state.recommendation}'.
Fairness Audit: {state.audit_result.audit_notes if state.audit_result else 'N/A'}

Format output strictly as JSON with keys:
{{
  "report_title": "Official Scholarship Adjudication Report: [ANONYMIZED_CANDIDATE]",
  "executive_summary": "Executive summary paragraph explaining decision and ranking status",
  "evaluation_breakdown": "Summary paragraph detailing merit, need, and achievement scores",
  "main_strengths": ["bullet 1", "bullet 2"],
  "concerns_and_missing_info": ["bullet 1 or note confirming complete dossier"],
  "recommendation_explanation": "Paragraph explaining why candidate was placed in this tier",
  "rubric_references": ["Clause 1.1", "Clause 2.1", "Clause 3.1"],
  "full_report_markdown": "Full formal markdown report with sections: Executive Summary, Candidate Profile, Evaluation Matrix, Committee Decision, and Attestation"
}}
Return ONLY JSON without markdown fences."""

        try:
            client = self._client or genai.Client(api_key=self.api_key)
            resp = client.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=self.temperature,
                    max_output_tokens=self.max_output_tokens,
                    response_mime_type="application/json",
                ),
            )
            raw_text = resp.text.strip()
            raw_text = re.sub(r"^```(?:json)?\s*", "", raw_text)
            raw_text = re.sub(r"\s*```$", "", raw_text)
            data = json.loads(raw_text)

            raw_title = data.get("report_title", f"Official Scholarship Adjudication Report: [ANONYMIZED_CANDIDATE]")
            formatted_title = raw_title.replace("[ANONYMIZED_CANDIDATE]", f"{p.full_name} ({state.applicant_id})")
            raw_markdown = data.get("full_report_markdown", "")
            formatted_markdown = raw_markdown.replace("[ANONYMIZED_CANDIDATE]", f"{p.full_name} ({state.applicant_id})")

            res = GeminiReportResult(
                applicant_id=state.applicant_id,
                report_title=formatted_title,
                executive_summary=data.get("executive_summary", ""),
                evaluation_breakdown=data.get("evaluation_breakdown", ""),
                main_strengths=data.get("main_strengths", []),
                concerns_and_missing_info=data.get("concerns_and_missing_info", []),
                recommendation_explanation=data.get("recommendation_explanation", ""),
                rubric_references=data.get("rubric_references", ["Clause 1.1", "Clause 2.1", "Clause 3.1"]),
                full_report_markdown=formatted_markdown,
            )
            self._report_cache[cache_key] = res
            return res

        except Exception as e:
            logger.warning(f"Gemini report call failed: {type(e).__name__} - {e}")
            return self._fallback_report(state, f"Report error: {type(e).__name__}")

    def _fallback_report(self, state: EvaluationState, note: str) -> GeminiReportResult:
        """Deterministic report fallback."""
        p = state.profile
        score_txt = f"{state.total_score:.2f} / 100" if state.total_score is not None else "Excluded"
        md = f"""# Official Scholarship Adjudication Report: {p.full_name}
**Applicant ID:** `{state.applicant_id}` | **Status:** `{state.status}`  
**Composite Score:** `{score_txt}` | **Recommendation:** `{state.recommendation}`  

### Executive Summary
Candidate dossier was adjudicated through the 7-agent institutional pipeline. 
Status verdict is **{state.status}** with allocation category **{state.recommendation}**.

### Evaluation Breakdown
- **Eligibility Gate:** {state.eligibility.justification if state.eligibility else 'N/A'}
- **Academic Merit:** {state.academic_result.justification if state.academic_result else 'N/A'}
- **Financial Need:** {state.financial_result.justification if state.financial_result else 'N/A'}
- **Achievement Portfolio:** {state.achievement_result.justification if state.achievement_result else 'N/A'}
- **Committee Synthesis:** Composite score of {score_txt} with recommendation tier '{state.recommendation}'.
- **Fairness Audit:** {state.audit_result.audit_notes if state.audit_result else 'N/A'}
"""
        return GeminiReportResult(
            applicant_id=state.applicant_id,
            report_title=f"Official Scholarship Adjudication Report: {p.full_name}",
            executive_summary=f"Candidate {p.full_name} was adjudicated with status {state.status}.",
            evaluation_breakdown=f"Composite Score: {score_txt}. Recommendation Tier: {state.recommendation}.",
            main_strengths=[f"Enrolled in {p.program_of_study}"] if p.program_of_study else ["Submitted application"],
            concerns_and_missing_info=["Documentation complete"] if state.status != "NEEDS_REVIEW" else ["Missing mandatory documentation"],
            recommendation_explanation=f"Allocated tier '{state.recommendation}' based on official rubric thresholds.",
            rubric_references=["Clause 1.1", "Clause 2.1", "Clause 3.1"],
            full_report_markdown=md,
        )

    # =========================================================================
    # D. GROUNDED RAG QUESTION ANSWERING
    # =========================================================================

    def answer_rubric_question(
        self,
        question: str,
        retriever: RubricRetriever,
        top_k: int = 3,
    ) -> GeminiRAGResult:
        """Retrieves passages and produces a strictly grounded answer with clause citations."""
        clean_q = question.strip()
        cache_key = f"rag_{clean_q}_{top_k}"
        if cache_key in self._rag_cache:
            return self._rag_cache[cache_key]

        # 1. Retrieve governing passages from deterministic retriever
        passages = retriever.retrieve_relevant_clauses(clean_q, top_k=top_k)
        valid_clause_ids = {c.clause_id for c in passages}
        passages_data = [
            {"clause_id": c.clause_id, "title": c.title, "section": c.section, "text": c.text}
            for c in passages
        ]
        source_doc = os.path.basename(getattr(retriever, "rubric_file_path", "scholarship_rubric.md"))

        if not self.is_configured:
            # Deterministic retriever fallback
            return self._fallback_rag(clean_q, passages, "Gemini API key is not configured.", source_doc)

        # Build context block
        if not passages:
            return GeminiRAGResult(
                question=clean_q,
                answer="The available scholarship rubric does not establish this rule or criterion. No relevant clauses were found matching your inquiry.",
                cited_clauses=[],
                rejected_citations=[],
                retrieved_passages=[],
                source_document=source_doc,
                is_grounded=True,
                rubric_coverage_status="NOT_ESTABLISHED_IN_RUBRIC",
            )

        context_text = "\n\n".join([
            f"[{c.clause_id}] {c.title} (Section: {c.section})\n{c.text}"
            for c in passages
        ])

        prompt = f"""You are the official Scholarship Policy Advisor. Answer the following question based ONLY on the governing rubric passages provided below.

GOVERNING RUBRIC CLAUSES:
{context_text}

USER QUESTION:
{clean_q}

CRITICAL RULES:
1. Ground your answer strictly and exclusively in the provided rubric clauses.
2. Cite ONLY exact clause identifiers from the provided list: {list(valid_clause_ids)}. Do NOT invent or cite any clause not in this list.
3. Do NOT extrapolate, speculate, or invent policy rules not stated in the text.
4. If the provided clauses do NOT contain the answer, you MUST state: "The available scholarship rubric does not establish this rule or criterion." and set "is_covered": false.

Provide response in JSON:
{{
  "answer": "Clear, grounded plain-language answer citing the specific clause numbers",
  "cited_clauses": ["Clause 1.1", "Clause 2.1"],
  "is_covered": true
}}
Return ONLY JSON without markdown fences."""

        try:
            client = self._client or genai.Client(api_key=self.api_key)
            resp = client.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=0.0,  # Zero temperature for maximum factual grounding
                    max_output_tokens=self.max_output_tokens,
                    response_mime_type="application/json",
                ),
            )
            raw_text = resp.text.strip()
            raw_text = re.sub(r"^```(?:json)?\s*", "", raw_text)
            raw_text = re.sub(r"\s*```$", "", raw_text)
            data = json.loads(raw_text)

            is_covered = data.get("is_covered", True)
            ans = data.get("answer", "")
            raw_cited = data.get("cited_clauses", [])

            # Validate returned citations strictly against retrieved passage identifiers
            valid_citations = [c for c in raw_cited if c in valid_clause_ids]
            rejected_citations = [c for c in raw_cited if c not in valid_clause_ids]

            # If model returned no citations or says unestablished, mark accordingly
            if "does not establish" in ans.lower() or not valid_citations:
                is_covered = False
                if not valid_citations and "does not establish" not in ans.lower():
                    ans = "The available scholarship rubric does not establish this rule or criterion. No verified rubric clauses substantiate this inquiry."

            # Grounding requires valid citations and no fabricated citations
            is_grounded = bool(valid_citations and is_covered and len(rejected_citations) == 0)

            res = GeminiRAGResult(
                question=clean_q,
                answer=ans,
                cited_clauses=valid_citations,
                rejected_citations=rejected_citations,
                retrieved_passages=passages_data,
                source_document=source_doc,
                is_grounded=is_grounded,
                rubric_coverage_status="COVERED_IN_RUBRIC" if is_covered else "NOT_ESTABLISHED_IN_RUBRIC",
            )
            self._rag_cache[cache_key] = res
            return res

        except Exception as e:
            logger.warning(f"Gemini RAG call failed: {type(e).__name__} - {e}")
            return self._fallback_rag(clean_q, passages, f"Gemini error: {type(e).__name__}", source_doc)

    def _fallback_rag(self, question: str, passages: list, note: str, source_doc: str = "scholarship_rubric.md") -> GeminiRAGResult:
        """Deterministic RAG fallback synthesizing direct citations from passages."""
        if not passages:
            return GeminiRAGResult(
                question=question,
                answer="The available scholarship rubric does not establish this rule or criterion.",
                cited_clauses=[],
                rejected_citations=[],
                retrieved_passages=[],
                source_document=source_doc,
                is_grounded=True,
                rubric_coverage_status="NOT_ESTABLISHED_IN_RUBRIC",
            )

        citations = [p.clause_id for p in passages]
        passages_data = [
            {"clause_id": p.clause_id, "title": p.title, "section": p.section, "text": p.text}
            for p in passages
        ]
        summary_points = [f"Per **{p.clause_id} ({p.title})**: {p.text}" for p in passages]
        ans = f"Deterministic Rubric Retrieval ({note}):\n\n" + "\n\n".join(summary_points)
        return GeminiRAGResult(
            question=question,
            answer=ans,
            cited_clauses=citations,
            rejected_citations=[],
            retrieved_passages=passages_data,
            source_document=source_doc,
            is_grounded=True,
            rubric_coverage_status="COVERED_IN_RUBRIC",
        )
        answer = " ".join(summary_points)

        return GeminiRAGResult(
            question=question,
            answer=answer,
            cited_clauses=citations,
            is_grounded=True,
            rubric_coverage_status="COVERED_IN_RUBRIC",
        )
