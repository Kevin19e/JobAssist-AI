import os
import json
import re
from pydantic import BaseModel, Field
from typing import List

MAX_JOB_LISTINGS_PER_REQUEST = 12
MODELS = ["gemini-2.5-flash", "gemini-2.0-flash", "gemini-1.5-flash"]

class JobAnalysisResult(BaseModel):
    category: str = Field(description="Role category, e.g., AI Consulting, Digital, etc.")
    languages: List[str] = Field(description="Detected language requirements")
    sponsorship_signals: str = Field(description="Any signals about work authorization or sponsorship")
    seniority: str = Field(description="Required seniority level")
    fit_score: int = Field(description="Fit score from 0 to 100 based on the user's constraints")
    recommendation: str = Field(description="Must be one of: 'Apply now', 'Apply with tailoring', 'Low chance', 'Do not apply'")
    red_flags: List[str] = Field(description="Red flags based on the user's constraints (e.g. requires strong French, Supply chain, Big 4)")
    missing_keywords: List[str] = Field(description="Important keywords missing from the CV")
    tailored_summary: str = Field(description="A short CV summary tailored to this specific job")
    cover_letter: str = Field(description="A short cover letter for this job")
    recruiter_message: str = Field(description="A short, direct LinkedIn message to send to a recruiter")


class BatchJobItem(BaseModel):
    batch_index: int = Field(description="Must match the listing number (1 for first === JOB 1 ===, etc.)")
    inferred_title: str = Field(description="Short job title or role name inferred from the posting")
    fit_score: int = Field(description="Fit score from 0 to 100 based on CV and user constraints")
    recommendation: str = Field(
        description="Must be one of: 'Apply now', 'Apply with tailoring', 'Low chance', 'Do not apply'"
    )
    quick_verdict: str = Field(description="2-4 sentences: why this role fits or does not fit this CV")
    red_flags: List[str] = Field(description="Deal-breakers or concerns for this candidate")


class BatchJobAnalysisResult(BaseModel):
    results: List[BatchJobItem]


def split_job_listings(bulk_text: str) -> List[str]:
    """Split pasted text into separate job ads (delimiter on its own line)."""
    text = bulk_text.replace("\r\n", "\n").strip()
    if not text:
        return []
    parts = re.split(r"(?m)^\s*---NEXT\s+JOB---\s*$", text, flags=re.IGNORECASE)
    cleaned = [p.strip() for p in parts if p.strip()]
    return cleaned


def analyze_multiple_jobs_for_cv(cv_text: str, listings: List[str], user_api_key: str = None) -> dict:
    """Score many job postings against one CV; returns ranked analyses."""
    api_key = user_api_key or os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError(
            "GEMINI_API_KEY environment variable not found. "
            "Please get a free key from https://aistudio.google.com/ and set it. "
            "On Windows run: set GEMINI_API_KEY=your_key"
        )
    if not listings:
        raise ValueError("No job listings found. Separate each posting with a line containing only: ---NEXT JOB---")
    if len(listings) > MAX_JOB_LISTINGS_PER_REQUEST:
        raise ValueError(
            f"Too many listings ({len(listings)}). Paste at most {MAX_JOB_LISTINGS_PER_REQUEST} per run."
        )

    from google import genai
    from google.genai import types

    client = genai.Client(api_key=api_key)

    numbered_blocks = []
    for i, block in enumerate(listings, start=1):
        numbered_blocks.append(f"=== JOB {i} ===\n{block}")
    listings_blob = "\n\n".join(numbered_blocks)

    system_prompt = """
You are an AI Job Assistant that helps candidates evaluate job fit.

YOUR TASK:
The user uploaded their CV and pasted several separate job listings, each marked === JOB N ===.
For EACH listing, compare it to the CV and assign fit_score and recommendation.
Infer the candidate's profile (location, languages, experience, target roles) from their CV.
Penalize listings that clearly mismatch the candidate's profile (wrong seniority, missing languages, unpaid, etc.).
Do NOT invent CV experience. Be consistent: batch_index must equal the JOB number.
"""

    prompt = f"""
--- USER CV START ---
{cv_text}
--- USER CV END ---

--- JOB LISTINGS START ---
{listings_blob}
--- JOB LISTINGS END ---

Return one result object per listing (same count as jobs above), with batch_index matching N in === JOB N ===.
"""

    last_error = None
    for model_name in MODELS:
        try:
            response = client.models.generate_content(
                model=model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=system_prompt,
                    response_mime_type="application/json",
                    response_schema=BatchJobAnalysisResult,
                    temperature=0.2,
                ),
            )
            data = json.loads(response.text)
            items = data.get("results", [])
            items.sort(key=lambda x: (-int(x.get("fit_score", 0)), x.get("batch_index", 0)))
            return {"results": items, "listing_count": len(listings)}
        except Exception as e:
            last_error = e
            continue
    raise RuntimeError(f"All models failed. Last error: {str(last_error)}")


def analyze_job_and_cv(cv_text: str, job_text: str, user_api_key: str = None) -> dict:
    """Uses Google Gemini API to analyze the CV against the Job Description."""
    # To keep it free, we use the google-genai SDK 
    # It requires the GEMINI_API_KEY environment variable or a passed key.
    api_key = user_api_key or os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError(
            "GEMINI_API_KEY environment variable not found. "
            "Please get a free key from https://aistudio.google.com/ and set it. "
            "On Windows run: set GEMINI_API_KEY=your_key"
        )
    
    # Import locally to avoid crashing immediately if not installed
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=api_key)

    system_prompt = """
You are an AI Job Assistant that helps candidates evaluate job fit.

YOUR TASK:
Analyze the provided Job Description and the User's CV.
Infer the candidate's profile (location, languages, experience level, target roles) directly from their CV.
If the job strongly mismatches the candidate's profile (e.g., requires languages not on the CV, wrong seniority, or is unpaid), the fit score should be heavily penalized, and 'Do not apply' should probably be recommended.
Do NOT invent any experience not present in the CV. Keep the generated texts (summary, cover letter, recruiter message) short, human, and straight to the point.
"""

    prompt = f"""
--- USER CV START ---
{cv_text}
--- USER CV END ---

--- JOB DESCRIPTION START ---
{job_text}
--- JOB DESCRIPTION END ---

Based on the System instructions and the CV/Job pairs above, perform the job analysis and return JSON.
"""

    last_error = None
    for model_name in MODELS:
        try:
            response = client.models.generate_content(
                model=model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=system_prompt,
                    response_mime_type="application/json",
                    response_schema=JobAnalysisResult,
                    temperature=0.2,
                ),
            )
            return json.loads(response.text)
        except Exception as e:
            last_error = e
            continue
    raise RuntimeError(f"All models failed. Last error: {str(last_error)}")
