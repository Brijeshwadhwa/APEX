# CSE476 DEMONSTRATION SCHOLARSHIP AND MERIT GRANT EVALUATION RUBRIC
Document Version: 1.0.0 (Course Project Demonstration Specification)
Project: CSE476 Agentic AI & Intelligent Automation — CA2 (Grant & Scholarship Application Evaluator)
Provenance: Coursework Demonstration Specification (Synthetic Institutional Scenario)
Notice: This document is an illustrative, project-created demonstration rubric developed specifically for academic coursework and multi-agent system demonstration. It does not represent an official university policy, statutory regulation, or governmental authority. All thresholds, scoring curves, and criteria are illustrative parameters designed to evaluate agent orchestration, RAG retrieval, and policy compliance.

---

## SECTION 1: MANDATORY ELIGIBILITY REQUIREMENTS

### Clause 1.1: Academic Minimum Threshold
All candidates must possess a verified qualifying academic percentage of not less than 60.0% (sixty percent) or equivalent Grade Point Average. Candidates possessing an academic score below 60.0% are disqualified outright with status "INELIGIBLE". Academic performance cannot be waived or compensated by financial hardship or extracurricular achievements.

### Clause 1.2: Household Income Ceiling
The gross annual household income from all verified family sources must not exceed INR 6,00,000 (Indian Rupees Six Lakhs). Candidates whose family income exceeds INR 6,00,000 are ineligible for need-grounded financial assistance under this grant scheme.

### Clause 1.3: Completeness and Verification Standard
Every application must contain unambiguous documentation for academic qualifications and family income. If mandatory records are missing or unverified, the candidate cannot be confirmed as eligible and must be marked with status "NEEDS_REVIEW" for manual human review and follow-up. Incomplete applications must never be allocated a confirmed ranking slot.

---

## SECTION 2: MERIT AND SCORING FORMULATION (MAXIMUM 100 POINTS)

The total composite score is evaluated on a 100-point scale partitioned across three distinct dimensions:
Composite Score = Academic Score (Max 40) + Financial Need Score (Max 35) + Achievement Score (Max 25)

### Clause 2.1: Academic Performance Dimension (Weight: 40 Points)
Academic scores are proportionally scaled from the applicant's aggregate percentage P (where 60.0 <= P <= 100.0) according to the linear formula:
Academic Score = (Percentage / 100) * 40.0
The maximum attainable academic score is 40.0 points. Scores are rounded to two decimal places.

### Clause 2.2: Financial Need Dimension (Weight: 35 Points)
Financial assistance points are awarded on a progressive need-based scale divided into discrete income brackets:
- Band A (INR 0 to INR 1,50,000): 35.0 points (Maximum Need)
- Band B (INR 1,50,001 to INR 2,50,000): 28.0 points (High Need)
- Band C (INR 2,50,001 to INR 4,00,000): 20.0 points (Moderate Need)
- Band D (INR 4,00,001 to INR 6,00,000): 10.0 points (Low Need)
- Band E (Above INR 6,00,000): 0.0 points (Zero Need / Ineligible)

### Clause 2.3: Achievement Portfolio Dimension (Weight: 25 Points)
Recognizes validated co-curricular, athletic, technical, and leadership achievements. Points are awarded solely for verified achievements with valid documentation:
- International Level Recognition: 15.0 points per distinct achievement
- National Level Recognition: 10.0 points per distinct achievement
- State / Provincial Level Recognition: 6.0 points per distinct achievement
- District / Regional Level Recognition: 3.0 points per distinct achievement
- Institutional / College Level Recognition: 1.0 points per distinct achievement
Cumulative achievement points are capped at a maximum ceiling of 25.0 points. Duplicate claims for the same event or certificate number are disqualified.

---

## SECTION 3: RECOMMENDATION TIERS AND QUOTA ADJUDICATION

### Clause 3.1: Recommendation Classification Thresholds
Following aggregation of the three specialist scores, candidates are assigned a formal committee recommendation based on the total composite score:
- Composite Score >= 80.0 points: "High Priority" (Direct Scholarship Award Nominee)
- Composite Score >= 65.0 and < 80.0 points: "Recommended" (Merit Grant Award Nominee)
- Composite Score >= 50.0 and < 65.0 points: "Consider" (Waitlist / Secondary Allocation Pool)
- Composite Score < 50.0 points: "Low Priority" (Rejected / Non-competitive)

### Clause 3.2: Exclusion of Disqualified and Pending Records
Applicants designated as "INELIGIBLE" or "NEEDS_REVIEW" are strictly barred from appearing on the confirmed scholarship award roster.

### Clause 3.3: Deterministic Ranking and Tie-Breaking Rules
Eligible candidates who successfully pass the automated fairness audit are ranked on the confirmed award roster using a strict multi-tier deterministic tie-breaking policy:
1. Primary Criterion: Total Composite Score out of 100.0 (descending order).
2. First Tie-Breaker: Qualifying Academic Percentage (descending order).
3. Second Tie-Breaker: Gross Annual Household Income (ascending order — lower household income receives priority for financial assistance).
4. Third Tie-Breaker: Cumulative Verified Achievement Score out of 25.0 (descending order).
5. Final Arbiter: Applicant ID (lexicographical ascending order to guarantee stable, reproducible rankings).

Candidates who fail the automated fairness audit or display mathematical calculation discrepancies are quarantined from the confirmed award roster pending manual human committee review.

---

## SECTION 4: FAIRNESS, ETHICS AND DEMOGRAPHIC NON-DISCRIMINATION

### Clause 4.1: Prohibited Scoring Attributes
Evaluation must be blind to candidate demographic characteristics. Gender, religion, social caste/category, race, ethnicity, marital status, and political affiliations are strictly prohibited from exerting any influence, weight, or penalty on scoring or eligibility determinations.

### Clause 4.2: Audit and Consistency Verification
Every evaluation trace is subjected to automated fairness auditing. If any specialist agent cites or correlates demographic attributes to awarded scores, the decision is flagged as biased and referred to human adjustment. Furthermore, mathematical summation across individual scores must be verified for exact consistency.

