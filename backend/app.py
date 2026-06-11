import os
import shutil
from typing import Optional
from fastapi import Body
from fastapi import FastAPI, File, UploadFile, Form, Header, HTTPException
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

import uuid

# Load .env file if present (simple parser) and auto-create a .env with DEV_SECRET if missing
ENV_PATH = os.path.join(os.path.dirname(__file__), '.env')
if os.path.exists(ENV_PATH):
    try:
        with open(ENV_PATH, 'r') as envf:
            for line in envf:
                line = line.strip()
                if not line or line.startswith('#') or '=' not in line:
                    continue
                k, v = line.split('=', 1)
                k = k.strip()
                v = v.strip().strip('"').strip("'")
                if k and k not in os.environ:
                    os.environ[k] = v
    except Exception:
        pass
else:
    # Auto-create .env with a random DEV_SECRET if not present and DEV_SECRET not set
    if not os.environ.get('DEV_SECRET'):
        gen = 'vectora-' + uuid.uuid4().hex[:12]
        try:
            with open(ENV_PATH, 'w') as envf:
                envf.write(f'DEV_SECRET={gen}\n')
            os.environ['DEV_SECRET'] = gen
        except Exception:
            # best-effort only
            os.environ['DEV_SECRET'] = gen

# Import NLP utilities
from utils.email_analyzer import analyze_email_procurement
from utils.invoice_extractor import extract_invoice_data
from utils.summarizer import summarize_contract
from utils.rag_chatbot import rag_chatbot_instance

app = FastAPI(
    title="AI Procurement Assistant NLP Hub",
    description="NLP Backend for Email Analysis, Invoice Extraction, Contract Summarization, and RAG Chatbot."
)

# Enable CORS for frontend flexibility
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Temp directory for saving uploaded files
TEMP_DIR = "temp_uploads"
os.makedirs(TEMP_DIR, exist_ok=True)

class EmailRequest(BaseModel):
    text: str

class ChatRequest(BaseModel):
    question: str

def save_upload_file(upload_file: UploadFile) -> str:
    """
    Saves an uploaded file to a temporary directory and returns its absolute path.
    """
    try:
        file_path = os.path.join(TEMP_DIR, upload_file.filename)
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(upload_file.file, buffer)
        return file_path
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Could not save file: {str(e)}")

@app.post("/api/analyze-email")
async def analyze_email_endpoint(
    request: EmailRequest,
    x_gemini_api_key: Optional[str] = Header(None)
):
    try:
        result = analyze_email_procurement(request.text, api_key=x_gemini_api_key)
        return JSONResponse(content=result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/extract-invoice")
async def extract_invoice_endpoint(
    file: Optional[UploadFile] = File(None),
    text: Optional[str] = Form(None),
    x_gemini_api_key: Optional[str] = Header(None)
):
    source = None
    if file:
        source = save_upload_file(file)
    elif text:
        source = text
    else:
        raise HTTPException(status_code=400, detail="Either 'file' or 'text' must be provided.")
        
    try:
        result = extract_invoice_data(source, api_key=x_gemini_api_key)
        # Clean up temp file if created
        if file and source and os.path.exists(source):
            os.remove(source)
        return JSONResponse(content=result)
    except Exception as e:
        # Ensure cleanup on failure
        if file and source and os.path.exists(source):
            os.remove(source)
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/summarize-contract")
async def summarize_contract_endpoint(
    file: Optional[UploadFile] = File(None),
    text: Optional[str] = Form(None),
    x_gemini_api_key: Optional[str] = Header(None)
):
    source = None
    if file:
        source = save_upload_file(file)
    elif text:
        source = text
    else:
        raise HTTPException(status_code=400, detail="Either 'file' or 'text' must be provided.")
        
    try:
        result = summarize_contract(source, api_key=x_gemini_api_key)
        if file and source and os.path.exists(source):
            os.remove(source)
        return JSONResponse(content=result)
    except Exception as e:
        if file and source and os.path.exists(source):
            os.remove(source)
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/index-contract")
async def index_contract_endpoint(
    file: Optional[UploadFile] = File(None),
    text: Optional[str] = Form(None)
):
    source = None
    if file:
        source = save_upload_file(file)
        # Read text from PDF or text file
        if file.filename.lower().endswith(".pdf"):
            from utils.invoice_extractor import extract_text_from_pdf
            contract_text = extract_text_from_pdf(source)
        else:
            try:
                with open(source, "r", encoding="utf-8") as f:
                    contract_text = f.read()
            except Exception as e:
                contract_text = f"[Error reading file: {str(e)}]"
        if source and os.path.exists(source):
            os.remove(source)
    elif text:
        contract_text = text
    else:
        raise HTTPException(status_code=400, detail="Either 'file' or 'text' must be provided.")
        
    if not contract_text or contract_text.startswith("[Error"):
        raise HTTPException(status_code=400, detail="Invalid text content for indexing.")
        
    try:
        import utils.rag_chatbot
        result = utils.rag_chatbot.rag_chatbot_instance.index_contract(contract_text)
        return JSONResponse(content=result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/chat-contract")
async def chat_contract_endpoint(
    request: ChatRequest,
    x_gemini_api_key: Optional[str] = Header(None)
):
    try:
        import utils.rag_chatbot
        result = utils.rag_chatbot.rag_chatbot_instance.query(request.question, api_key=x_gemini_api_key)
        return JSONResponse(content=result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/health")
async def health_check():
    """
    Health check endpoint to verify backend is running.
    """
    return JSONResponse(content={"status": "healthy", "message": "Backend is running"})

@app.post("/api/dev-auth")
async def dev_auth_endpoint(payload: dict = Body(...)):
    """
    Simple server-side developer unlock endpoint.
    Expects JSON: { "secret": "your-secret-here" }
    The server checks this against the DEV_SECRET environment variable.
    """
    try:
        secret = payload.get("secret") if isinstance(payload, dict) else None
        if not secret:
            raise HTTPException(status_code=400, detail="Missing secret")

        dev_secret = os.environ.get("DEV_SECRET", "")
        authorized = bool(dev_secret and secret == dev_secret)
        return JSONResponse(content={"authorized": authorized})
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Frontend is deployed separately

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="127.0.0.1", port=8000, reload=True)