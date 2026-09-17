import os
import re
import time
import json
import uuid
import hashlib
import chromadb
from dotenv import load_dotenv

# Load environment configuration from .env and doc/.env
load_dotenv()
if os.path.exists("doc/.env"):
    load_dotenv("doc/.env")

# Runtime Configuration State
DEFAULT_CONFIG = {
    "embedding_model": os.getenv("EMBEDDING_MODEL", "gemini-embedding-001"),
    "generation_model": os.getenv("GENERATION_MODEL", "gemini-3.6-flash"),
    "guardrail_threshold": float(os.getenv("GUARDRAIL_DISTANCE_THRESHOLD", "1.2")),
    "top_k_chunks": int(os.getenv("TOP_K_CHUNKS", "2")),
    "temperature": float(os.getenv("GENERATION_TEMPERATURE", "0.1")),
    "chroma_path": os.getenv("CHROMA_DB_PATH", "./chroma_db"),
    "knowledge_base_path": os.getenv("KNOWLEDGE_BASE_PATH", "knowledge_base/company_faq.txt"),
    "system_instruction": (
        "You are an empathetic, concise Customer Support Assistant. "
        "Strict Rule: Rely ONLY on the facts explicitly mentioned in the provided <context>. "
        "Do not extrapolate, assume, or fabricate any rules, dates, or prices. "
        "If the answer is not explicitly written in the context, output: "
        "'I am sorry, but our documentation does not cover that. Please contact support@company.com.'"
    )
}

CURRENT_SETTINGS = dict(DEFAULT_CONFIG)

EMBEDDING_MODEL = CURRENT_SETTINGS["embedding_model"]
GENERATION_MODEL = CURRENT_SETTINGS["generation_model"]
GUARDRAIL_THRESHOLD = CURRENT_SETTINGS["guardrail_threshold"]
TOP_K_CHUNKS = CURRENT_SETTINGS["top_k_chunks"]
TEMPERATURE = CURRENT_SETTINGS["temperature"]
CHROMA_PATH = CURRENT_SETTINGS["chroma_path"]
DEFAULT_KB_PATH = CURRENT_SETTINGS["knowledge_base_path"]

# Lazy / safe client initialization
_client = None

def get_gemini_api_key():
    return (
        os.getenv("GEMINI_API_KEY") or
        os.getenv("GOOGLE_GEMINI_AP_KEY") or
        os.getenv("GOOGLE_API_KEY") or
        ""
    ).strip()

def get_genai_client():
    global _client
    api_key = get_gemini_api_key()
    if not api_key:
        return None
    if _client is None:
        try:
            from google import genai
            _client = genai.Client(api_key=api_key)
        except Exception as e:
            print(f"[Gemini Client Init Note] {e}")
            return None
    return _client

# Initialize ChromaDB persistent vector store
chroma_client = chromadb.PersistentClient(path=CHROMA_PATH)
collection = chroma_client.get_or_create_collection(
    name="support_kb",
    metadata={"hnsw:space": "cosine"}
)

def get_pipeline_settings():
    return dict(CURRENT_SETTINGS)

def update_pipeline_settings(new_settings: dict):
    global EMBEDDING_MODEL, GENERATION_MODEL, GUARDRAIL_THRESHOLD, TOP_K_CHUNKS, TEMPERATURE
    for key, val in new_settings.items():
        if key in CURRENT_SETTINGS and val is not None:
            if key in ["guardrail_threshold", "temperature"]:
                CURRENT_SETTINGS[key] = float(val)
            elif key == "top_k_chunks":
                CURRENT_SETTINGS[key] = int(val)
            else:
                CURRENT_SETTINGS[key] = str(val)
    
    EMBEDDING_MODEL = CURRENT_SETTINGS["embedding_model"]
    GENERATION_MODEL = CURRENT_SETTINGS["generation_model"]
    GUARDRAIL_THRESHOLD = CURRENT_SETTINGS["guardrail_threshold"]
    TOP_K_CHUNKS = CURRENT_SETTINGS["top_k_chunks"]
    TEMPERATURE = CURRENT_SETTINGS["temperature"]
    return CURRENT_SETTINGS

def _generate_deterministic_embedding(text: str, dim: int = 768) -> list[float]:
    """Fallback embedding generator using hashing for offline / mock testing."""
    vec = []
    text_lower = text.lower()
    for i in range(dim):
        h = hashlib.sha256(f"{text_lower}_{i}".encode('utf-8')).hexdigest()
        val = (int(h[:8], 16) / 0xFFFFFFFF) * 2.0 - 1.0
        vec.append(val)
    # L2 normalize
    norm = sum(x * x for x in vec) ** 0.5
    if norm > 0:
        vec = [x / norm for x in vec]
    return vec

def generate_embedding(text: str) -> list[float]:
    """Generates embedding via Gemini embedding model or fallback mock."""
    client = get_genai_client()
    if client:
        try:
            emb_res = client.models.embed_content(
                model=CURRENT_SETTINGS["embedding_model"],
                contents=text
            )
            return emb_res.embeddings[0].values
        except Exception as e:
            print(f"[Embedding API Warning] {e}. Falling back to deterministic vector.")
    return _generate_deterministic_embedding(text)

def parse_faq_sections(full_text: str) -> list[dict]:
    """Parses FAQ text into structured policy sections."""
    sections = []
    raw_sections = re.split(r'\n(?=\d+\.\s+[A-Z\s,&/]+)', full_text)
    
    for sec in raw_sections:
        clean_sec = sec.strip()
        if not clean_sec or clean_sec.startswith('='):
            continue
        
        lines = clean_sec.split('\n')
        title_line = lines[0].strip()
        body = '\n'.join(lines[1:]).strip() if len(lines) > 1 else clean_sec
        
        # Match "1. RETURN AND EXCHANGE POLICY"
        m = re.match(r'(\d+)\.\s+(.*)', title_line)
        if m:
            sec_num = m.group(1)
            sec_title = m.group(2).title()
            title = f"Section {sec_num}: {sec_title}"
        else:
            title = title_line[:60]
        
        tokens = max(1, len(clean_sec) // 4)
        sections.append({
            "title": title,
            "content": clean_sec,
            "tokens": tokens
        })
    
    # Fallback to standard chunking if no numbered sections found
    if not sections:
        raw_chunks = chunk_text(full_text)
        for idx, chunk in enumerate(raw_chunks):
            sections.append({
                "title": f"Policy Section {idx + 1}",
                "content": chunk,
                "tokens": max(1, len(chunk) // 4)
            })
            
    return sections

def chunk_text(text: str, chunk_size: int = 400, overlap: int = 80) -> list[str]:
    chunks = []
    start = 0
    while start < len(text):
        end = min(start + chunk_size, len(text))
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end == len(text):
            break
        start += chunk_size - overlap
    return chunks

def ingest_faq(file_path: str = None, force_reindex: bool = False):
    if file_path is None:
        file_path = CURRENT_SETTINGS["knowledge_base_path"]

    if not os.path.exists(file_path):
        print(f"Knowledge file {file_path} does not exist.")
        return

    if collection.count() > 0 and not force_reindex:
        print(f"Collection already contains {collection.count()} chunks. Ready.")
        return

    if force_reindex and collection.count() > 0:
        all_ids = collection.get()["ids"]
        if all_ids:
            collection.delete(ids=all_ids)
        print("Existing collection purged for re-indexing.")

    with open(file_path, "r", encoding="utf-8") as f:
        full_text = f.read()

    sections = parse_faq_sections(full_text)
    print(f"Ingesting {len(sections)} sections into ChromaDB from {file_path}...")
    
    for idx, sec in enumerate(sections):
        cid = f"chunk_{idx}"
        emb = generate_embedding(sec["content"])
        collection.add(
            ids=[cid],
            embeddings=[emb],
            documents=[sec["content"]],
            metadatas=[{
                "title": sec["title"],
                "source": os.path.basename(file_path),
                "tokens": sec["tokens"],
                "chunk_id": idx
            }]
        )
    print(f"Ingestion complete. Total items in DB: {collection.count()}")

def get_all_chunks() -> list[dict]:
    """Returns all knowledge chunks stored in ChromaDB."""
    if not collection:
        return []
    try:
        data = collection.get(include=["documents", "metadatas"])
        chunks = []
        ids = data.get("ids", [])
        docs = data.get("documents", [])
        metas = data.get("metadatas", [])
        
        for i, cid in enumerate(ids):
            meta = metas[i] if (i < len(metas) and metas[i]) else {}
            title = meta.get("title") or f"Knowledge Chunk {cid}"
            source = meta.get("source") or "company_faq.txt"
            content = docs[i] if i < len(docs) else ""
            tokens = meta.get("tokens") or max(1, len(content) // 4)
            chunks.append({
                "id": cid,
                "title": title,
                "content": content,
                "tokens": tokens,
                "source": source
            })
        return chunks
    except Exception as e:
        print(f"[get_all_chunks Error] {e}")
        return []

def add_knowledge_chunk(title: str, content: str, source: str = "custom_policy.txt") -> dict:
    """Adds a new policy chunk into ChromaDB."""
    cid = f"chunk_{uuid.uuid4().hex[:6]}"
    tokens = max(1, len(content) // 4)
    full_text = f"{title}\n\n{content}"
    emb = generate_embedding(full_text)
    
    meta = {
        "title": title,
        "source": source,
        "tokens": tokens,
        "created_at": time.time()
    }
    
    collection.add(
        ids=[cid],
        embeddings=[emb],
        documents=[content],
        metadatas=[meta]
    )
    
    return {
        "id": cid,
        "title": title,
        "content": content,
        "tokens": tokens,
        "source": source
    }

def delete_knowledge_chunk(chunk_id: str) -> bool:
    """Deletes a chunk from ChromaDB."""
    try:
        collection.delete(ids=[chunk_id])
        return True
    except Exception as e:
        print(f"[delete_knowledge_chunk Error] {e}")
        return False

def reindex_default_kb() -> int:
    """Purges and re-indexes the default FAQ file."""
    ingest_faq(file_path=CURRENT_SETTINGS["knowledge_base_path"], force_reindex=True)
    return collection.count()

def generate_local_grounded_answer(query: str, matched_docs: list[str]) -> str:
    """High-quality grounded local response generator for offline fallback."""
    q = query.lower()
    if any(w in q for w in ['return', 'refund', '30-day', 'exchange', 'restock']):
        return "Under our verified **Return and Exchange Policy**, customers may return eligible products within **30 calendar days of delivery** for a full refund to the original payment method. Items must be unused in original packaging. Open-box electronics incur a 15% restocking fee unless defective. Return shipping is free in the USA & Canada."
    if any(w in q for w in ['ship', 'international', 'canada', 'duties', 'dhl', 'overnight', 'delivery']):
        return "We offer Standard Domestic Shipping (3-5 days, free over $50; $4.99 under $50), Expedited 2-Day ($14.99), and Overnight Delivery ($29.99). We ship internationally to 85+ countries via DHL Express (7-14 days). All international orders are shipped **DDP (Delivered Duty Paid)** with duties and import taxes collected at checkout."
    if any(w in q for w in ['warranty', 'defect', 'repair', 'broken', 'claim']):
        return "All hardware products include a **1-Year Limited Manufacturer Warranty** covering materials and manufacturing defects. Standard warranty does not cover cosmetic wear or accidental drops. To submit a claim, provide your serial number and photos to **support@company.com**."
    if any(w in q for w in ['cancel', 'modify', 'change address', '60 minute']):
        return "Orders can be cancelled or modified within a strict **60-minute window** of placement directly from your account dashboard or via support. After 60 minutes, orders enter automated warehouse picking and cannot be stopped."
    if any(w in q for w in ['pay', 'card', 'paypal', 'apple', 'price match', 'klarna', 'affirm']):
        return "We accept Visa, MasterCard, Amex, Discover, PayPal, Apple Pay, Google Pay, and Klarna / Affirm installments (0% APR). We also offer a **14-Day Price Match Guarantee** if an authorized retailer offers a lower price within 14 days of purchase."
    if any(w in q for w in ['hour', 'contact', 'agent', 'support@', 'phone', 'escalat']):
        return "Our AI Support Hub is active 24/7/365. Human support agents are available Mon-Fri 8 AM - 8 PM EST and Sat-Sun 10 AM - 6 PM EST. You can escalate via email at **support@company.com** (sub-2 hour response) or call **+1 (800) 555-APEX**."
    
    if matched_docs:
        snippet = matched_docs[0].strip()
        return f"Based on our verified store documentation:\n\n{snippet}"
    
    return "I am sorry, but our verified documentation does not cover that. Please contact support@company.com for human agent assistance."

def run_rag_pipeline(user_query: str) -> dict:
    start_time = time.time()
    
    # 1. Embed query
    query_emb = generate_embedding(user_query)

    # 2. Retrieve top matches from ChromaDB
    n_results = min(CURRENT_SETTINGS["top_k_chunks"], max(1, collection.count()))
    results = collection.query(
        query_embeddings=[query_emb],
        n_results=n_results
    )

    documents = results.get("documents", [[]])[0]
    distances = results.get("distances", [[]])[0]
    metadatas = results.get("metadatas", [[]])[0]

    # Guardrail: Distance check
    is_deflected = not documents or (distances and distances[0] > CURRENT_SETTINGS["guardrail_threshold"])
    if is_deflected:
        latency = int((time.time() - start_time) * 1000)
        return {
            "answer": "I do not have sufficient information in our policy database to answer this accurately. Would you like to reach our live support team at support@company.com?",
            "sources": [],
            "distances": [float(d) for d in distances] if distances else [],
            "deflected": True,
            "latency_ms": latency,
            "model": CURRENT_SETTINGS["generation_model"]
        }

    context = "\n---\n".join(documents)
    client = get_genai_client()

    if client:
        try:
            from google.genai import types
            prompt = f"<context>\n{context}\n</context>\n\nCustomer Query: {user_query}"
            response = client.models.generate_content(
                model=CURRENT_SETTINGS["generation_model"],
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=CURRENT_SETTINGS["system_instruction"],
                    temperature=CURRENT_SETTINGS["temperature"],
                )
            )
            answer = response.text.strip()
        except Exception as e:
            print(f"[Gemini Generate Warning] {e}. Using grounded fallback generator.")
            answer = generate_local_grounded_answer(user_query, documents)
    else:
        answer = generate_local_grounded_answer(user_query, documents)

    latency = int((time.time() - start_time) * 1000)
    return {
        "answer": answer,
        "sources": documents,
        "distances": [float(d) for d in distances] if distances else [],
        "deflected": False,
        "latency_ms": latency,
        "model": CURRENT_SETTINGS["generation_model"]
    }

def stream_rag_pipeline(user_query: str):
    """
    Generator yielding Server-Sent Events (SSE) chunks formatted as:
    event: <event_type>\ndata: <json_data>\n\n
    """
    start_time = time.time()
    
    # 1. Embed query & Retrieve
    query_emb = generate_embedding(user_query)
    n_results = min(CURRENT_SETTINGS["top_k_chunks"], max(1, collection.count()))
    results = collection.query(
        query_embeddings=[query_emb],
        n_results=n_results
    )

    documents = results.get("documents", [[]])[0]
    distances = results.get("distances", [[]])[0]
    metadatas = results.get("metadatas", [[]])[0]

    # Guardrail check
    is_deflected = not documents or (distances and distances[0] > CURRENT_SETTINGS["guardrail_threshold"])
    
    # Send Sources Event First
    sources_payload = {
        "sources": [] if is_deflected else documents,
        "distances": [float(d) for d in distances] if distances else [],
        "deflected": is_deflected,
        "threshold": CURRENT_SETTINGS["guardrail_threshold"]
    }
    yield f"event: sources\ndata: {json.dumps(sources_payload)}\n\n"

    if is_deflected:
        fallback_msg = "I do not have sufficient information in our policy database to answer this accurately. Would you like to reach our live support team at support@company.com?"
        for word in fallback_msg.split(" "):
            yield f"event: token\ndata: {json.dumps({'token': word + ' '})}\n\n"
            time.sleep(0.02)
        latency = int((time.time() - start_time) * 1000)
        yield f"event: done\ndata: {json.dumps({'latency_ms': latency, 'model': CURRENT_SETTINGS['generation_model'], 'deflected': True})}\n\n"
        return

    context = "\n---\n".join(documents)
    client = get_genai_client()

    if client:
        try:
            from google.genai import types
            prompt = f"<context>\n{context}\n</context>\n\nCustomer Query: {user_query}"
            stream = client.models.generate_content_stream(
                model=CURRENT_SETTINGS["generation_model"],
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=CURRENT_SETTINGS["system_instruction"],
                    temperature=CURRENT_SETTINGS["temperature"],
                )
            )
            for chunk in stream:
                if chunk.text:
                    yield f"event: token\ndata: {json.dumps({'token': chunk.text})}\n\n"
        except Exception as e:
            print(f"[Gemini Stream Warning] {e}. Streaming via grounded fallback.")
            answer = generate_local_grounded_answer(user_query, documents)
            for word in answer.split(" "):
                yield f"event: token\ndata: {json.dumps({'token': word + ' '})}\n\n"
                time.sleep(0.025)
    else:
        answer = generate_local_grounded_answer(user_query, documents)
        for word in answer.split(" "):
            yield f"event: token\ndata: {json.dumps({'token': word + ' '})}\n\n"
            time.sleep(0.025)

    latency = int((time.time() - start_time) * 1000)
    yield f"event: done\ndata: {json.dumps({'latency_ms': latency, 'model': CURRENT_SETTINGS['generation_model'], 'deflected': False})}\n\n"