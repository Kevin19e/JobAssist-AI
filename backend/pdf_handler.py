import io
from pypdf import PdfReader

def extract_text_from_pdf(pdf_bytes: bytes) -> str:
    """Extracts text from a given PDF byte stream."""
    try:
        reader = PdfReader(io.BytesIO(pdf_bytes))
        text = ""
        for page in reader.pages:
            text += page.extract_text() + "\n"
        return text.strip()
    except Exception as e:
        raise ValueError(f"Failed to parse PDF: {str(e)}")
