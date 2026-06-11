import os
import re
import json
import numpy as np

try:
    import google.generativeai as genai
except ImportError:
    genai = None

try:
    from sentence_transformers import SentenceTransformer
    import faiss
except ImportError:
    SentenceTransformer = None
    faiss = None

class ContractRAG:
    def __init__(self):
        self.model = None
        self.index = None
        self.chunks = []
        self.dimension = 384  # Default dimension for all-MiniLM-L6-v2
        
    def _lazy_load_model(self):
        """
        Loads SentenceTransformer lazily to speed up server start.
        """
        if self.model is None:
            if SentenceTransformer is None:
                raise ImportError("sentence-transformers is not installed.")
            # Run model on CPU
            self.model = SentenceTransformer("all-MiniLM-L6-v2", device="cpu")
            
    def chunk_text(self, text, chunk_size=500, overlap=100):
        """
        Splits text into chunks of roughly chunk_size characters with overlap.
        """
        # Remove extra whitespace
        text_clean = re.sub(r'\s+', ' ', text).strip()
        
        chunks = []
        start = 0
        text_len = len(text_clean)
        
        while start < text_len:
            end = min(start + chunk_size, text_len)
            chunk = text_clean[start:end]
            chunks.append(chunk)
            
            # Move start pointer forward by chunk_size - overlap
            start += chunk_size - overlap
            if start >= text_len or end == text_len:
                break
                
        return chunks
        
    def index_contract(self, text):
        """
        Splits the contract text, generates embeddings, and indexes them in FAISS.
        """
        if not text or not text.strip():
            return {"status": "error", "message": "Empty text provided."}
            
        try:
            self._lazy_load_model()
            
            # Split text into chunks
            paragraphs = [
                p.strip()
                for p in re.split(r'\n\s*\n', text)
                if p.strip()
                ]
            
            if len(paragraphs) >= 2:
                self.chunks = paragraphs
            else:
                self.chunks = self.chunk_text(text)
            if not self.chunks:
                return {"status": "error", "message": "Failed to extract chunks from text."}
                
            # Generate embeddings
            embeddings = self.model.encode(
                self.chunks,
                convert_to_numpy=True,
                normalize_embeddings=True
            )
            self.dimension = embeddings.shape[1]
            
            # Build FAISS index
            self.index = faiss.IndexFlatL2(self.dimension)
            self.index.add(np.array(embeddings).astype("float32"))
            
            return {
                "status": "success", 
                "message": f"Successfully indexed contract. Split into {len(self.chunks)} chunks."
            }
        except Exception as e:
            return {"status": "error", "message": f"Failed to index: {str(e)}"}
            
    def query(self, question, k=3, api_key=None):
        """
        Queries the indexed contract.
        If api_key is present, uses Gemini for generation.
        Otherwise, returns retrieved passages formatted as a response.
        """
        if not self.chunks or self.index is None:
            return {
                "answer": "No contract has been indexed yet. Please upload a contract first.",
                "sources": [],
                "mode": "Error"
            }
            
        try:
            self._lazy_load_model()
            
            # 1. Retrieve top-k chunks
            q_emb = self.model.encode(
                [question],
                convert_to_numpy=True,
                normalize_embeddings=True
            )
            distances, indices = self.index.search(np.array(q_emb).astype("float32"), min(k, len(self.chunks)))
            
            retrieved_chunks = []
            for idx in indices[0]:
                if idx != -1 and idx < len(self.chunks):
                    retrieved_chunks.append(self.chunks[idx])
                    
            if not retrieved_chunks:
                return {
                    "answer": "Could not find any relevant information in the contract.",
                    "sources": [],
                    "mode": "Offline Search"
                }
                
            # 2. Answer generation (Gemini AI vs Offline fallback)
            if api_key and genai is not None:
                try:
                    genai.configure(api_key=api_key)
                    model = genai.GenerativeModel("gemini-1.5-flash")
                    
                    context_text = "\n\n".join([f"--- Chunk {i+1} ---\n{chunk}" for i, chunk in enumerate(retrieved_chunks)])
                    
                    prompt = f"""
                    You are an expert AI Procurement Assistant. Answer the question based ONLY on the provided contract context chunks.
                    If the context doesn't contain the answer, say "I cannot find the answer to this question in the contract."
                    Cite the specific details from the contract context. Keep your response professional, precise, and clean.

                    Contract Context:
                    {context_text}

                    Question:
                    {question}

                    Answer:
                    """
                    response = model.generate_content(prompt)
                    return {
                        "answer": response.text.strip(),
                        "sources": retrieved_chunks,
                        "mode": "Gemini AI RAG"
                    }
                except Exception as e:
                    # Fallback to local if Gemini error
                    pass
                    
            # Local/Offline Response Formulation
            # We return the best retrieved passages cleanly
            best_chunk = retrieved_chunks[0]
            
            answer = (
                f"Answer based on the contract:\n\n"
                f"{best_chunk}"
            )
            for i, chunk in enumerate(retrieved_chunks):
                answer += f"**Relevant Clause {i+1}:** {chunk}\n\n"
                
            answer += "*Note: Running in offline local search mode. To generate natural language answers synthesis, please supply a Gemini API Key in Settings.*"
            
            question_lower = question.lower()
            
            if "duration" in question_lower or "term" in question_lower:
                keyword = ["month", "year", "duration", "effective"]
            elif "payment" in question_lower or "amount" in question_lower:
                keyword = ["payment", "fee", "price", "amount", "₹"]
            elif "penalty" in question_lower:
                keyword = ["penalty", "delay", "breach"]
            else:
                keyword = []
            filtered = []
                
            for chunk in retrieved_chunks:
                if any(k.lower() in chunk.lower() for k in keyword):
                    filtered.append(chunk)
                    
            if filtered:
                best_chunk = filtered[0]
            else:
                best_chunk = retrieved_chunks[0]

            return {
                "answer": answer,
                "sources": retrieved_chunks,
                "mode": "Local Semantic Search (Offline)"
            }
            
        except Exception as e:
            return {
                "answer": f"Error querying index: {str(e)}",
                "sources": [],
                "mode": "Error"
            }

# Global chatbot instance to persist index in server memory
rag_chatbot_instance = ContractRAG()

if __name__ == "__main__":
    # Test RAG
    sample_text = """
    This CONTRACT is signed on 5 June 2026.
    ABC Technologies shall build a custom CRM system. The price of services is set at ₹15,00,000.
    XYZ Solutions must clear payment in 10 monthly payments of ₹1,50,000 each.
    If work is delayed, a penalty of 1% per week is applicable.
    """
    
    bot = ContractRAG()
    res = bot.index_contract(sample_text)
    print(res)
    
    q_res = bot.query("What is the penalty for delay?")
    print(q_res["answer"])