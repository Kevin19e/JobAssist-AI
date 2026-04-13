from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse, FileResponse
import uvicorn
import os

from backend.pdf_handler import extract_text_from_pdf
from backend.llm_assistant import (
    analyze_job_and_cv,
    analyze_multiple_jobs_for_cv,
    split_job_listings,
)

app = FastAPI(title="AI Job Assistant MVP")

# POST endpoint for analysis
@app.post("/api/analyze")
async def analyze_application(
    cv_file: UploadFile = File(...),
    job_description: str = Form(...),
    api_key: str = Form(None)
):
    if not cv_file.filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="CV must be a PDF file.")
    
    if not job_description.strip():
        raise HTTPException(status_code=400, detail="Job description cannot be empty.")
        
    try:
        # Read the uploaded PDF file
        pdf_bytes = await cv_file.read()
        
        # Extract text from PDF
        cv_text = extract_text_from_pdf(pdf_bytes)
        
        # Call LLM logic
        result = analyze_job_and_cv(cv_text, job_description, api_key)
        
        return JSONResponse(content=result)
        
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except RuntimeError as re:
        raise HTTPException(status_code=500, detail=str(re))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")


@app.post("/api/filter-jobs")
async def filter_jobs_by_cv(
    cv_file: UploadFile = File(...),
    jobs_bulk: str = Form(...),
    api_key: str = Form(None),
):
    """Compare many pasted job ads to one CV; returns ranked fit scores."""
    if not cv_file.filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="CV must be a PDF file.")

    listings = split_job_listings(jobs_bulk)
    if not listings:
        raise HTTPException(
            status_code=400,
            detail="Add at least one job posting. Between posts, put a line containing only: ---NEXT JOB---",
        )

    try:
        pdf_bytes = await cv_file.read()
        cv_text = extract_text_from_pdf(pdf_bytes)
        result = analyze_multiple_jobs_for_cv(cv_text, listings, api_key)
        return JSONResponse(content=result)
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except RuntimeError as re:
        raise HTTPException(status_code=500, detail=str(re))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")


# Mount frontend static files last, so it doesn't shadow API routes
# We'll serve index.html at root explicitly
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
frontend_path = os.path.join(BASE_DIR, 'frontend')

@app.get("/")
async def index():
    return FileResponse(os.path.join(frontend_path, "index.html"))

app.mount("/", StaticFiles(directory=frontend_path, html=True), name="frontend")

if __name__ == "__main__":
    uvicorn.run("backend.main:app", host="127.0.0.1", port=8000, reload=True)
