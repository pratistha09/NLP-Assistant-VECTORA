# 🚀 VECTORA AI Procurement Assistant - Setup & Usage Guide

## Quick Start

### 1. **Backend Connection Status**

**Status Bar Location:** Top-right of the sidebar  
**What it shows:**
- 🟢 **Connected**: Backend is running on `http://127.0.0.1:8000`
- 🔴 **Disconnected**: Backend is not responding

**How to Control It:**
```bash
# Start Backend (from project root)
python -m uvicorn app:app --host 127.0.0.1 --port 8000 --reload

# Or if you have uvicorn installed globally:
uvicorn app:app --reload --port 8000
```

The backend automatically checks for connection every time you:
- Load the page
- Switch between tabs
- Save settings

---

## 2. **Developer Unlock Procedure**

### What is Developer Unlock?
Developer Unlock gives you access to:
- API Integration Code Snippets
- Endpoint documentation
- JavaScript examples for your frontend team

### Step-by-Step:

**Step 1: Find Your Dev Secret**
```bash
# Open your .env file at project root
cat .env
# Look for this line:
# DEV_SECRET=your_dev_secret_key
```

**Step 2: Go to Settings Tab**
- Click on **"Developer & Settings"** in the left sidebar

**Step 3: Enter the Secret**
- Copy the value from `DEV_SECRET=` in your `.env` file
- Paste it in the "Developer Secret" input field
- Click **"Unlock"** button

**Step 4: View API Guide**
- If successful, you'll see ✓ message
- The **"API Integration Guide"** section will appear below
- Browse through code snippets for each endpoint

### Troubleshooting:
| Problem | Solution |
|---------|----------|
| ✗ Invalid secret | Check that the secret in `.env` matches exactly (case-sensitive) |
| ✗ Backend unreachable | Ensure FastAPI server is running on port 8000 |
| Status stays blank | Try refreshing the page |

---

## 3. **API Configuration**

### Google Gemini API Key (Optional)

**Location:** Settings Tab → Google Gemini API Key

**Why Add It:**
- Enables advanced AI features with Google's Gemini model
- Better summarization and entity extraction
- OCR for invoice images
- Optional: Works without it using local models

**How to Get It:**
1. Visit https://makersuite.google.com/app/apikey
2. Create new API key
3. Copy the key (starts with `AIzaSy...`)
4. Paste in the input field in Settings
5. Click **"Save & Update"**

**Privacy:** Your key is stored only in your browser's local storage, not on the server.

---

## 4. **Backend Setup**

### Prerequisites
```bash
# Install dependencies
pip install -r requirements.txt

# If FastAPI/Uvicorn missing:
pip install fastapi uvicorn python-multipart
```

### Environment Variables (.env)
```bash
# Required
DEV_SECRET=your-dev-secret-here  # Your developer secret (change this in production!)

# Optional (only if using Gemini)
GOOGLE_API_KEY=your-api-key-here
```

### Running the Backend
```bash
# Development mode with auto-reload
uvicorn app:app --reload --port 8000

# Or using Python module
python -m uvicorn app:app --reload --port 8000
```

**Backend URL:** `http://127.0.0.1:8000`

---

## 5. **API Endpoints**

All endpoints support optional `X-Gemini-API-Key` header for advanced features.

### Email Analyzer
```
POST /api/analyze-email
Content-Type: application/json

{
  "text": "your email content here"
}

Response:
{
  "category": "procurement",
  "priority": "high",
  "sentiment": "positive",
  "confidence": 85,
  "action_items": [...],
  "key_dates": [...]
}
```

### Invoice Extractor
```
POST /api/extract-invoice
Content-Type: multipart/form-data

file: <PDF or text file> OR text: <invoice text>

Response:
{
  "invoice_number": "INV-123",
  "date": "2026-06-08",
  "total_amount": "₹50,000",
  "vendor": "ABC Corp",
  "client": "XYZ Ltd",
  "line_items": [...]
}
```

### Contract Summarizer
```
POST /api/summarize-contract
Content-Type: multipart/form-data

file: <PDF or text file> OR text: <contract text>

Response:
{
  "summary": "This is a 24-month...",
  "clauses": [
    {"name": "Liability", "content": "..."},
    {"name": "Payment", "content": "..."}
  ]
}
```

### RAG Chatbot
```
# 1. Index Contract
POST /api/index-contract
file: <PDF or text> OR text: <content>

# 2. Query Contract
POST /api/chat-contract
Content-Type: application/json

{
  "question": "What are the payment terms?"
}

Response:
{
  "answer": "The payment terms are...",
  "sources": ["clause 3.2", "section 4"]
}
```

### Health Check
```
GET /api/health

Response:
{
  "status": "healthy",
  "message": "Backend is running"
}
```

---

## 6. **UI Features & Tips**

### 📧 Email Analyzer
- **Templates:** Pre-fill with sample emails for testing
- **Sentiment:** Color-coded gauge (red=negative, yellow=neutral, green=positive)
- **Action Items:** Automatically extracted from email content

### 📄 Invoice Extractor
- **Drag & Drop:** Supported for PDF files
- **Automatic Parsing:** Extracts vendor, client, amounts, dates
- **Line Items:** Table format for itemized charges

### 📋 Contract Summarizer
- **Multi-page Support:** Works with long PDFs
- **Key Clauses:** Auto-extracted legal sections
- **Clause Detection:** Identifies liability, payment, duration, penalties

### 💬 RAG Chatbot
- **Vector Index:** FAISS-based semantic search
- **Context Aware:** References relevant contract sections
- **Templates:** Quick questions for common queries

---

## 7. **Troubleshooting**

| Issue | Solution |
|-------|----------|
| Backend shows "Disconnected" | Run `uvicorn app:app --reload --port 8000` |
| "File too large" error | Keep PDFs under 50MB |
| Gemini not working | Check API key format and validity |
| "Invalid secret" on unlock | Ensure .env has correct DEV_SECRET value |
| No GPU available | App uses CPU by default (slower but works) |

---

## 8. **Project Structure**

```
AI_Procurement_Assistant/
├── app.py                 # FastAPI backend
├── .env                   # Environment variables (DEV_SECRET, etc)
├── requirements.txt       # Python dependencies
├── static/               # Frontend files
│   ├── index.html        # Main UI
│   ├── app.js            # Frontend logic
│   └── styles.css        # Styling
└── utils/                # NLP modules
    ├── email_analyzer.py
    ├── invoice_extractor.py
    ├── summarizer.py
    └── rag_chatbot.py
```

---

## 9. **Tips for Best Results**

### Email Analysis
✓ Use complete email threads  
✓ Include subject line for better categorization  
✓ Works best with business emails  

### Invoice Parsing
✓ High-quality PDFs work better than scans  
✓ Clear formatting improves extraction  
✓ Supports multiple currencies  

### Contract Summarization
✓ Minimum 500 words for better summary  
✓ Standard legal language works best  
✓ Single-page contracts load faster  

### RAG Chatbot
✓ Index contracts before asking questions  
✓ Ask specific questions for better answers  
✓ Use natural language (e.g., "What are the payment terms?")  

---

## 🎯 Next Steps

1. ✓ Ensure backend is running
2. ✓ Check connection status (green dot)
3. ✓ Add Gemini API key (optional)
4. ✓ Unlock developer features if needed
5. ✓ Start using the tools!

---

**For Issues or Questions:** Check the browser console (F12) for error logs.
