import os
import importlib
import tempfile
from typing import Dict, Any, List, Optional

from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

# ResearchAssistantFlow is imported lazily inside initialize() so the server
# can start (and serve the frontend) even if heavy deps aren't installed yet.
def _load_flow_class():
    mod = importlib.import_module("src.workflows.flow")
    return mod.ResearchAssistantFlow

# ---------------------------------------------------------------------------
# Global in-memory state
# ---------------------------------------------------------------------------
_state: Dict[str, Any] = {
    "assistant": None,
    "initialized": False,
    "chat_history": [],          # list of {"query": str, "response": dict}
    "document_processed": False,
    "current_document": None,
}

# ---------------------------------------------------------------------------
# Research-assistant wrapper
# ---------------------------------------------------------------------------
class ResearchAssistant:
    def __init__(self, user_id: str = "web_user", thread_id: str = "web_session"):
        self.user_id = user_id
        self.thread_id = thread_id
        self.flow = None
        self.initialized = False
        
        # Check environment explicitly
        load_dotenv() 
        self.demo_mode = os.getenv("DEMO_MODE", "false").lower() == "true"
        print(f"[AUTH] App starting: DemoMode={self.demo_mode}")

    def initialize(self):
        """Initialize the assistant. Return (success, error_msg)"""
        # If explicitly in demo mode, skip heavy imports
        if self.demo_mode:
            print("[DEMO] Starting in Demo Mode (Mock results).")
            self.initialized = True
            return True, None
            
        try:
            FlowClass = _load_flow_class()
            self.flow = FlowClass(
                tensorlake_api_key=os.getenv("TENSORLAKE_API_KEY"),
                voyage_api_key=os.getenv("VOYAGE_API_KEY"),
                groq_api_key=os.getenv("GROQ_API_KEY"),
                zep_api_key=os.getenv("ZEP_API_KEY"),
                firecrawl_api_key=os.getenv("FIRECRAWL_API_KEY"),
                milvus_db_path="chroma_db",
            )
            self.initialized = True
            return True, None
        except Exception as e:
            # Do NOT silently fall back to demo mode — report the actual error
            import traceback
            traceback.print_exc()
            print(f"[ERROR] Initialization failed: {e}")
            return False, str(e)

    def query(self, user_query: str) -> Dict[str, Any]:
        if not self.initialized:
            return {"error": "Research Assistant not initialized"}
        
        if self.demo_mode:
            import time
            time.sleep(2)  # Simulate thinking
            return {
                "final_response": f"I analyzed your document regarding '{user_query}'. (DEMO MODE: Results are simulated because full dependencies are not yet installed.)",
                "context_sources": {
                    "rag_result": {"status": "OK", "answer": "Demo document context...", "citations": [{"label": "Paper.pdf", "locator": "page 1"}]},
                    "web_result": {"status": "OK", "answer": "Demo web results...", "citations": [{"label": "Web Article", "locator": "https://example.com"}]},
                },
                "evaluation_result": {
                    "relevant_sources": ["RAG", "Web"],
                    "relevance_scores": {"RAG": 0.9, "Web": 0.8},
                    "reasoning": "Both document and web sources contain information relevant to your demo query."
                }
            }
            
        try:
            result = self.flow.kickoff(
                inputs={
                    "query": user_query,
                    "user_id": self.user_id,
                    "thread_id": self.thread_id,
                }
            )
            return result
        except Exception as e:
            return {"error": str(e)}

    def process_documents(self, paths: List[str]) -> Dict[str, Any]:
        if self.demo_mode:
            return {"success": True, "message": "Demo mode: file tracked but not parsed."}
        return self.flow.process_documents(paths)


# ---------------------------------------------------------------------------
# FastAPI application
# ---------------------------------------------------------------------------
app = FastAPI(title="AI Research Assistant API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------
class QueryRequest(BaseModel):
    query: str


# ---------------------------------------------------------------------------
# API Endpoints
# ---------------------------------------------------------------------------

@app.get("/api/status")
def get_status():
    """Return current application state (initialization, document, API keys)."""
    return {
        "initialized": _state["initialized"],
        "document_processed": _state["document_processed"],
        "current_document": _state["current_document"],
        "chat_history_length": len(_state["chat_history"]),
        "api_keys": {
            "GROQ_API_KEY":       bool(os.getenv("GROQ_API_KEY")),
            "VOYAGE_API_KEY":     bool(os.getenv("VOYAGE_API_KEY")),
            "ZEP_API_KEY":        bool(os.getenv("ZEP_API_KEY")),
            "TENSORLAKE_API_KEY": bool(os.getenv("TENSORLAKE_API_KEY")),
            "FIRECRAWL_API_KEY":  bool(os.getenv("FIRECRAWL_API_KEY")),
        },
    }


@app.post("/api/initialize")
def initialize_assistant():
    """Initialize the ResearchAssistantFlow (loads models, connects to DBs)."""
    if _state["initialized"]:
        return {"success": True, "message": "Already initialized"}

    assistant = ResearchAssistant()
    ok, err = assistant.initialize()
    if ok:
        _state["assistant"] = assistant
        _state["initialized"] = True
        return {"success": True, "message": "Research Assistant initialized successfully"}

    raise HTTPException(
        status_code=503,
        detail=f"Failed to initialize: {err}. Ensure all dependencies are installed (run: pip install -r requirements.txt).",
    )


@app.post("/api/upload")
async def upload_document(file: UploadFile = File(...)):
    """Upload and process a PDF document into the RAG pipeline."""
    if not _state["initialized"]:
        raise HTTPException(status_code=400, detail="Initialize the assistant first.")

    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported.")

    tmp_path = None
    try:
        content = await file.read()
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            tmp.write(content)
            tmp_path = tmp.name

        assistant: ResearchAssistant = _state["assistant"]
        assistant.process_documents([tmp_path])

        _state["document_processed"] = True
        _state["current_document"] = file.filename

        return {
            "success": True,
            "message": f"Document '{file.filename}' processed successfully.",
            "document": file.filename,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)


@app.post("/api/query")
def query_assistant(request: QueryRequest):
    """Send a query to the multi-agent research pipeline."""
    if not _state["initialized"]:
        raise HTTPException(status_code=400, detail="Initialize the assistant first.")
    if not _state["document_processed"]:
        raise HTTPException(status_code=400, detail="Upload and process a document first.")

    assistant: ResearchAssistant = _state["assistant"]
    result = assistant.query(request.query)

    if isinstance(result, dict) and "error" in result:
        raise HTTPException(status_code=500, detail=result["error"])

    # Persist to history
    _state["chat_history"].append(
        {"query": request.query, "response": result}
    )
    return result


@app.get("/api/history")
def get_history():
    """Return the full chat history."""
    return {"history": _state["chat_history"]}


@app.post("/api/reset")
def reset_chat():
    """Clear the in-memory chat history."""
    _state["chat_history"] = []
    return {"success": True, "message": "Chat history cleared."}


# ---------------------------------------------------------------------------
# Static files + SPA catch-all
# ---------------------------------------------------------------------------
app.mount("/static", StaticFiles(directory="frontend"), name="static")


@app.get("/")
def serve_index():
    return FileResponse("frontend/index.html")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend:app", host="0.0.0.0", port=8000, reload=True)
