import os
import re
import time
import json
import uuid
import hashlib
from typing import Optional
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

def classify_intent_and_sentiment(query: str) -> dict:
    """
    Analyzes customer query text to determine the core intent category and sentiment urgency.
    """
    q = query.lower()
    
    # 1. Intent Classification
    intent = "General Inquiry"
    if any(k in q for k in ["return", "refund", "restock", "money back", "30-day", "exchange"]):
        intent = "Return & Refund"
    elif any(k in q for k in ["ship", "delivery", "track", "customs", "duties", "overnight", "canada", "dhl", "fedex", "freight"]):
        intent = "Shipping & Logistics"
    elif any(k in q for k in ["warranty", "repair", "defect", "broken", "replace", "hardware", "malfunction", "damaged"]):
        intent = "Warranty & Claims"
    elif any(k in q for k in ["pay", "price match", "charge", "invoice", "tax", "discount", "klarna", "affirm", "paypal", "credit", "bitcoin", "crypto"]):
        intent = "Billing & Payment"
    elif any(k in q for k in ["cancel", "modify", "change address", "change order", "stop order", "60 minute"]):
        intent = "Order Modification"
    elif any(k in q for k in ["account", "password", "login", "auth", "sign in"]):
        intent = "Account & Security"

    # 2. Sentiment & Urgency Classification
    sentiment = "Standard"
    if any(k in q for k in ["urgent", "asap", "immediately", "broken", "wrong", "terrible", "worst", "angry", "disappointed", "complaint", "unacceptable", "dispute", "lawyer", "fraud"]):
        sentiment = "High Urgency"
    elif any(k in q for k in ["vip", "enterprise", "bulk", "corporate", "commercial", "wholesale", "volume", "procurement", "sla"]):
        sentiment = "VIP / Commercial"
    elif any(k in q for k in ["please", "thank", "helpful", "appreciate", "wondering", "curious"]):
        sentiment = "Positive Inquiry"

    return {
        "intent": intent,
        "sentiment": sentiment
    }

def detect_language(text: str) -> str:
    """
    Detects the primary language of the customer query.
    Supported: English, Spanish, French, German, Japanese, Portuguese, Hindi.
    """
    if not text:
        return "English"
    
    # 1. Unicode script checks
    if any('\u3040' <= char <= '\u309f' or '\u30a0' <= char <= '\u30ff' for char in text):
        return "Japanese"
    if any('\u0900' <= char <= '\u097f' for char in text):
        return "Hindi"

    # 2. Keyword heuristic checks with scoring
    t = text.lower()
    
    scores = {
        "Spanish": 0,
        "Portuguese": 0,
        "French": 0,
        "German": 0,
        "English": 0
    }
    
    # Portuguese indicators
    pt_unique = ["qual", "olá", "ola", "obrigado", "obrigada", "você", "voce", "não", "nao", "troca", "prazo", "rastreamento", "entregue", "devolução", "devolucao", "reembolso"]
    # Spanish indicators
    es_unique = ["cuál", "cual", "hola", "gracias", "cómo", "como", "envío", "envio", "garantía", "garantia", "días", "cancelar", "precio", "cuánto", "tiempo", "devolución", "devolucion", "reembolso"]
    # French indicators
    fr_unique = ["bonjour", "remboursement", "retour", "livraison", "combien", "garantie", "délai", "annuler", "merci", "payer", "carte", "quelle", "quel", "est-ce"]
    # German indicators
    de_unique = ["hallo", "rückgabe", "ruckgabe", "versand", "erstattung", "garantie", "bestellung", "stornieren", "danke", "lieferung", "dauer", "wie", "ist", "das"]

    if "qual" in t or "obrigado" in t or "você" in t or "troca" in t or "prazo" in t:
        scores["Portuguese"] += 3
    if "cuál" in t or "¿" in t or "¡" in t or "gracias" in t or "días" in t or "cuánto" in t:
        scores["Spanish"] += 3
        
    for w in pt_unique:
        if w in t:
            scores["Portuguese"] += 1
    for w in es_unique:
        if w in t:
            scores["Spanish"] += 1
    for w in fr_unique:
        if w in t:
            scores["French"] += 2
    for w in de_unique:
        if w in t:
            scores["German"] += 2
            
    best_lang = max(scores, key=scores.get)
    if scores[best_lang] > 0:
        return best_lang
        
    return "English"

LOCAL_TRANSLATIONS = {
    "Spanish": {
        "return": "Bajo nuestra **Política de Devoluciones y Cambios**, los clientes pueden devolver productos elegibles dentro de los **30 días calendario posteriores a la entrega** para un reembolso completo al método de pago original. Los artículos deben estar sin usar y en su embalaje original. Los productos electrónicos de caja abierta tienen una tarifa de reposición del 15%. El envío de devolución es gratuito en EE. UU. y Canadá.",
        "ship": "Ofrecemos Envío Nacional Estándar (3-5 días, gratis en compras mayores a $50; $4.99 si es menor), Express de 2 Días ($14.99) y Entrega Nocturna ($29.99). Realizamos envíos internacionales a más de 85 países mediante DHL Express (7-14 días). Todos los pedidos internacionales se envían como **DDP (Delivered Duty Paid)**, con los aranceles e impuestos de importación cobrados en el proceso de pago.",
        "warranty": "Todos los productos de hardware incluyen una **Garantía Limitada del Fabricante de 1 Año** que cubre defectos en materiales y mano de obra. La garantía estándar no cubre desgaste cosmético o caídas accidentales. Para enviar un reclamo, proporcione su número de serie y fotos a **support@company.com**.",
        "cancel": "Los pedidos pueden cancelarse o modificarse dentro de una estricta **ventana de 60 minutos** desde su realización, directamente desde su panel de control o contactando a soporte.",
        "pay": "Aceptamos Visa, MasterCard, Amex, Discover, PayPal, Apple Pay, Google Pay y cuotas de Klarna / Affirm (0% TAE). También ofrecemos una **Garantía de Igualación de Precios de 14 Días** si un distribuidor autorizado ofrece un precio más bajo.",
        "deflected": "No dispongo de información suficiente en nuestra base de datos de políticas para responder a esto con precisión. ¿Le gustaría comunicarse con nuestro equipo de soporte en vivo en support@company.com?"
    },
    "French": {
        "return": "Conformément à notre **Politique de Retour et d'Échange**, les clients peuvent retourner les produits éligibles dans un délai de **30 jours calendaires suivant la livraison** pour un remboursement intégral sur le mode de paiement d'origine. Les articles doivent être inutilisés et dans leur emballage d'origine. Les produits électroniques en boîte ouverte entraînent des frais de réapprovisionnement de 15%. Les frais de retour sont gratuits aux États-Unis et au Canada.",
        "ship": "Nous proposons la Livraison Standard (3-5 jours, gratuite dès $50; $4.99 en dessous), Express 2 Jours ($14.99) et Livraison Lendemain ($29.99). Nous livrons à l'international dans plus de 85 pays via DHL Express (7-14 jours). Toutes les commandes internationales sont expédiées en **DDP (Delivered Duty Paid)**, avec tous les droits de douane et taxes inclus à la commande.",
        "warranty": "Tous les produits matériels bénéficient d'une **Garantie Constructeur Limitée de 1 An** couvrant les défauts de fabrication et de matériaux. Pour déposer une réclamation, envoyez votre numéro de série et des photos à **support@company.com**.",
        "cancel": "Les commandes peuvent être annulées ou modifiées dans un délai strict de **60 minutes** après leur enregistrement.",
        "pay": "Nous acceptons Visa, MasterCard, Amex, PayPal, Apple Pay, Google Pay et les paiements échelonnés Klarna / Affirm. Nous offrons également une **Garantie d'Alignement de Prix de 14 Jours**.",
        "deflected": "Je ne dispose pas de suffisamment d'informations dans notre base de données pour répondre avec précision. Souhaitez-vous contacter notre équipe d'assistance à support@company.com ?"
    },
    "German": {
        "return": "Gemäß unserer **Rückgabe- und Umtauschrichtlinie** können berechtigte Artikel innerhalb von **30 Kalendertagen nach Lieferung** gegen volle Rückerstattung zurückgegeben werden. Artikel müssen unbenutzt und in Originalverpackung sein. Für geöffnete Elektronikartikel fällt eine Wiedereinlagerungsgebühr von 15% an. Der Rückversand ist in den USA und Kanada kostenlos.",
        "ship": "Wir bieten Standardversand (3-5 Werktage, kostenlos ab $50), 2-Tage-Express ($14.99) und Übernachtzustellung ($29.99). Internationaler Versand in über 85 Länder erfolgt per DHL Express (7-14 Tage) via **DDP (Delivered Duty Paid)** inklusive aller Zollgebühren und Steuern.",
        "warranty": "Auf alle Hardwareprodukte gewähren wir eine **1-jährige eingeschränkte Herstellergarantie** auf Material- und Verarbeitungsfehler. Schadensmeldungen richten Sie bitte mit Seriennummer und Fotos an **support@company.com**.",
        "cancel": "Bestellungen können innerhalb eines strikten Zeitfensters von **60 Minuten** nach Aufgabe storniert oder geändert werden.",
        "pay": "Wir akzeptieren Visa, MasterCard, Amex, Discover, PayPal, Apple Pay, Google Pay sowie Klarna / Affirm Ratenzahlung (0% eff. Jahreszins). Zudem bieten wir eine **14-tägige Bestpreisgarantie**.",
        "deflected": "In unserer Richtliniendatenbank liegen nicht genügend Informationen vor, um dies präzise zu beantworten. Möchten Sie unseren Live-Support unter support@company.com kontaktieren?"
    },
    "Japanese": {
        "return": "当社の**返品・交換ポリシー**に基づき、商品お届けから**30日以内**であれば、元の支払い方法への全額返金にて返品が可能です。商品は未使用かつ元のパッケージに入っている必要があります。開封済みの電子機器には15%の再補充手数料が適用されます。米国およびカナダへの返送は無料です。",
        "ship": "国内標準配送（3〜5日、50ドル以上無料）、2日間速達（14.99ドル）、翌日配送（29.99ドル）を提供しています。DHL Expressを通じて85か国以上に配送可能です（7〜14日）。すべての国際注文は**DDP（関税元払）**で発送され、チェックアウト時に関税が決済されます。",
        "warranty": "すべてのハードウェア製品には、材質および製造上の欠陥を保証する**1年間の限定メーカー保証**が付帯します。保証請求を行うには、シリアル番号と写真を **support@company.com** まで送信してください。",
        "cancel": "ご注文のキャンセルまたは変更は、注文確定後**60分以内**に限り受け付けております。",
        "pay": "Visa、MasterCard、Amex、Discover、PayPal、Apple Pay、Google Pay、Klarna / Affirmに対応しています。また、**14日間の価格マッチ保証**も提供しております。",
        "deflected": "ポリシーデータベースに正確な情報がありません。担当サポートチーム（support@company.com）にお問い合わせください。"
    },
    "Portuguese": {
        "return": "De acordo com nossa **Política de Devolução e Troca**, produtos elegíveis podem ser devolvidos em até **30 dias corridos após a entrega** com reembolso integral. Os itens devem estar sem uso e na embalagem original. Eletrônicos com caixa aberta possuem taxa de reabastecimento de 15%.",
        "ship": "Oferecemos Envio Padrão (3-5 dias, grátis acima de $50), Expresso 2 Dias ($14.99) e Entrega Noturna ($29.99). Enviamos internacionalmente para mais de 85 países via DHL Express (7-14 dias) na modalidade **DDP (Delivered Duty Paid)**.",
        "warranty": "Todos os produtos de hardware possuem **Garantia Limitada do Fabricante de 1 Ano** contra defeitos de fabricação e material. Para acionar a garantia, envie número de série e fotos para **support@company.com**.",
        "cancel": "Pedidos podem ser cancelados ou alterados dentro de um prazo rigoroso de **60 minutos** após a compra.",
        "pay": "Aceitamos Visa, MasterCard, Amex, PayPal, Apple Pay, Google Pay e parcelamento Klarna/Affirm. Oferecemos **Garantia de Cobrimento de Preço de 14 Dias**.",
        "deflected": "Não encontramos informações suficientes na base de políticas. Deseja falar com o suporte em support@company.com?"
    },
    "Hindi": {
        "return": "हमारी **वापसी और विनिमय नीति** के तहत, ग्राहक डिलीवरी के **30 कैलेंडर दिनों** के भीतर मूल भुगतान विधि पर पूर्ण धनवापसी के लिए पात्र उत्पादों को वापस कर सकते हैं। वस्तुएं अप्रयुक्त और मूल पैकेजिंग में होनी चाहिए। ओपन-बॉक्स इलेक्ट्रॉनिक्स पर 15% रीस्टॉकिंग शुल्क लागू होता है।",
        "ship": "हम मानक घरेलू शिपिंग (3-5 दिन, $50 से अधिक पर मुफ़्त), 2-दिवसीय एक्सप्रेस ($14.99), और रातोंरात डिलीवरी ($29.99) प्रदान करते हैं। हम DHL एक्सप्रेस (7-14 दिन) के माध्यम से 85+ देशों में अंतरराष्ट्रीय स्तर पर **DDP (Delivered Duty Paid)** शिप करते हैं।",
        "warranty": "सभी हार्डवेयर उत्पादों में सामग्री और विनिर्माण दोषों को कवर करने वाली **1-वर्ष की सीमित निर्माता वारंटी** शामिल है। दावा दर्ज करने के लिए, अपना सीरियल नंबर और फोटो **support@company.com** पर भेजें।",
        "cancel": "ऑर्डर देने के **60 मिनट की सख्त समय सीमा** के भीतर ही ऑर्डर रद्द या संशोधित किए जा सकते हैं।",
        "pay": "हम वीज़ा, मास्टरकार्ड, एमेक्स, पेपैल, ऐप्पल पे, गूगल पे और क्लार्ना स्वीकार करते हैं। हम **14-दिवसीय मूल्य मिलान गारंटी** भी प्रदान करते हैं।",
        "deflected": "सटीक उत्तर देने के लिए हमारी नीति डेटाबेस में पर्याप्त जानकारी नहीं है। क्या आप हमारी सहायता टीम support@company.com से संपर्क करना चाहते हैं?"
    }
}

def translate_grounded_response(answer: str, target_lang: str, query: str = "") -> str:
    """Translates a grounded English answer into target language."""
    if not target_lang or target_lang == "English":
        return answer
    
    lang_dict = LOCAL_TRANSLATIONS.get(target_lang)
    if not lang_dict:
        return answer
    
    combined = (query + " " + answer).lower()
    if any(k in combined for k in ["return", "refund", "30-day", "devoluc", "rückgabe", "retour", "वापसी", "返品"]):
        return lang_dict.get("return", answer)
    if any(k in combined for k in ["ship", "delivery", "canada", "dhl", "duties", "envio", "versand", "livraison", "शिपिंग", "配送"]):
        return lang_dict.get("ship", answer)
    if any(k in combined for k in ["warranty", "defect", "repair", "garant", "वारंटी", "保証"]):
        return lang_dict.get("warranty", answer)
    if any(k in combined for k in ["cancel", "modify", "60 minute", "annuler", "stornier", "रद्द"]):
        return lang_dict.get("cancel", answer)
    if any(k in combined for k in ["pay", "price match", "klarna", "payer", "preismatch", "मूल्य"]):
        return lang_dict.get("pay", answer)
    if "not have sufficient information" in answer.lower():
        return lang_dict.get("deflected", answer)

    return answer

def query_rag_pipeline(user_query: str, target_language: Optional[str] = None) -> dict:
    """
    Complete end-to-end RAG query execution pipeline with multi-language support.
    """
    start_time = time.time()
    classification = classify_intent_and_sentiment(user_query)
    lang = target_language if (target_language and target_language != "Auto Detect") else detect_language(user_query)
    
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
        base_deflected = "I do not have sufficient information in our policy database to answer this accurately. Would you like to reach our live support team at support@company.com?"
        final_answer = translate_grounded_response(base_deflected, lang, user_query) if lang != "English" else base_deflected
        return {
            "answer": final_answer,
            "sources": [],
            "distances": [float(d) for d in distances] if distances else [],
            "deflected": True,
            "latency_ms": latency,
            "intent": classification["intent"],
            "sentiment": classification["sentiment"],
            "language": lang,
            "model": CURRENT_SETTINGS["generation_model"]
        }

    context = "\n---\n".join(documents)
    client = get_genai_client()

    if client:
        try:
            from google.genai import types
            lang_instruction = f" Respond in {lang}." if lang != "English" else ""
            prompt = f"<context>\n{context}\n</context>\n\nCustomer Query: {user_query}\n{lang_instruction}"
            response = client.models.generate_content(
                model=CURRENT_SETTINGS["generation_model"],
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=CURRENT_SETTINGS["system_instruction"] + lang_instruction,
                    temperature=CURRENT_SETTINGS["temperature"],
                )
            )
            answer = response.text.strip()
        except Exception as e:
            print(f"[Gemini Generate Warning] {e}. Using grounded fallback generator.")
            raw_answer = generate_local_grounded_answer(user_query, documents)
            answer = translate_grounded_response(raw_answer, lang, user_query)
    else:
        raw_answer = generate_local_grounded_answer(user_query, documents)
        answer = translate_grounded_response(raw_answer, lang, user_query)

    latency = int((time.time() - start_time) * 1000)
    return {
        "answer": answer,
        "sources": documents,
        "distances": [float(d) for d in distances] if distances else [],
        "deflected": False,
        "latency_ms": latency,
        "intent": classification["intent"],
        "sentiment": classification["sentiment"],
        "language": lang,
        "model": CURRENT_SETTINGS["generation_model"]
    }

# Alias for backwards compatibility
run_rag_pipeline = query_rag_pipeline

def stream_rag_pipeline(user_query: str, target_language: Optional[str] = None):
    """
    Generator yielding Server-Sent Events (SSE) chunks formatted as:
    event: <event_type>\ndata: <json_data>\n\n
    """
    start_time = time.time()
    classification = classify_intent_and_sentiment(user_query)
    lang = target_language if (target_language and target_language != "Auto Detect") else detect_language(user_query)
    
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
        "threshold": CURRENT_SETTINGS["guardrail_threshold"],
        "intent": classification["intent"],
        "sentiment": classification["sentiment"],
        "language": lang
    }
    yield f"event: sources\ndata: {json.dumps(sources_payload)}\n\n"

    if is_deflected:
        fallback_msg = "I do not have sufficient information in our policy database to answer this accurately. Would you like to reach our live support team at support@company.com?"
        if lang != "English":
            fallback_msg = translate_grounded_response(fallback_msg, lang, user_query)
            
        for word in fallback_msg.split(" "):
            yield f"event: token\ndata: {json.dumps({'token': word + ' '})}\n\n"
            time.sleep(0.02)
        latency = int((time.time() - start_time) * 1000)
        yield f"event: done\ndata: {json.dumps({'latency_ms': latency, 'model': CURRENT_SETTINGS['generation_model'], 'deflected': True, 'intent': classification['intent'], 'sentiment': classification['sentiment'], 'language': lang})}\n\n"
        return

    context = "\n---\n".join(documents)
    client = get_genai_client()

    if client:
        try:
            from google.genai import types
            lang_instruction = f" Answer in {lang}." if lang != "English" else ""
            prompt = f"<context>\n{context}\n</context>\n\nCustomer Query: {user_query}\n{lang_instruction}"
            stream = client.models.generate_content_stream(
                model=CURRENT_SETTINGS["generation_model"],
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=CURRENT_SETTINGS["system_instruction"] + lang_instruction,
                    temperature=CURRENT_SETTINGS["temperature"],
                )
            )
            for chunk in stream:
                if chunk.text:
                    yield f"event: token\ndata: {json.dumps({'token': chunk.text})}\n\n"
        except Exception as e:
            print(f"[Gemini Stream Warning] {e}. Streaming via grounded fallback.")
            raw_answer = generate_local_grounded_answer(user_query, documents)
            answer = translate_grounded_response(raw_answer, lang, user_query)
            for word in answer.split(" "):
                yield f"event: token\ndata: {json.dumps({'token': word + ' '})}\n\n"
                time.sleep(0.025)
    else:
        raw_answer = generate_local_grounded_answer(user_query, documents)
        answer = translate_grounded_response(raw_answer, lang, user_query)
        for word in answer.split(" "):
            yield f"event: token\ndata: {json.dumps({'token': word + ' '})}\n\n"
            time.sleep(0.025)

    latency = int((time.time() - start_time) * 1000)
    yield f"event: done\ndata: {json.dumps({'latency_ms': latency, 'model': CURRENT_SETTINGS['generation_model'], 'deflected': False, 'intent': classification['intent'], 'sentiment': classification['sentiment'], 'language': lang})}\n\n"

def generate_local_copilot_draft(ticket_query: str, customer_name: str, customer_tier: str, documents: list[str]) -> str:
    first_name = customer_name.split()[0] if customer_name else "there"
    vip_greeting = " As one of our priority account members, your inquiry has been fast-tracked." if ("VIP" in customer_tier or "Pro" in customer_tier) else ""
    
    grounded_info = documents[0] if documents else "our team is actively looking into the details of your request."
    
    return (
        f"Hi {first_name},\n\n"
        f"Thank you for contacting OmniDesk Support!{vip_greeting}\n\n"
        f"Regarding your inquiry:\n\"{ticket_query}\"\n\n"
        f"Based on our verified store policies:\n{grounded_info}\n\n"
        "Please let us know if you need any additional assistance or if we can help finalize this for you.\n\n"
        "Warm regards,\n"
        "The OmniDesk Support Team"
    )

def generate_agent_reply_draft(ticket_query: str, customer_name: str, customer_tier: str = "Standard Retail", intent: str = "General Inquiry") -> dict:
    """
    AI Copilot Generator: Creates a personalized, grounded response draft for a human support agent.
    """
    start_time = time.time()
    query_emb = generate_embedding(ticket_query)
    results = collection.query(
        query_embeddings=[query_emb],
        n_results=min(3, max(1, collection.count()))
    )
    documents = results.get("documents", [[]])[0]
    context = "\n---\n".join(documents) if documents else "No specific policy clause found."

    client = get_genai_client()
    tier_note = f" (Account Tier: {customer_tier})" if customer_tier else ""

    copilot_system_prompt = (
        "You are OmniDesk AI Copilot assisting a human customer support specialist. "
        "Draft a warm, polite, professional, and definitive resolution email to the customer based on verified store policies. "
        "Include clear next steps, address the customer by first name, cite relevant policy conditions (e.g. 30-day window, DDP customs, 1-year warranty), "
        "and sign off as 'The OmniDesk Support Team'."
    )

    if client:
        try:
            from google.genai import types
            prompt = (
                f"<verified_policies>\n{context}\n</verified_policies>\n\n"
                f"Customer Name: {customer_name}{tier_note}\n"
                f"Inquiry Category: {intent}\n"
                f"Customer Message: {ticket_query}\n\n"
                "Please generate a complete, ready-to-send agent reply draft:"
            )
            res = client.models.generate_content(
                model=CURRENT_SETTINGS["generation_model"],
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=copilot_system_prompt,
                    temperature=0.3
                )
            )
            draft = res.text.strip()
        except Exception as e:
            print(f"[Copilot Draft Warning] {e}. Using deterministic copilot draft generator.")
            draft = generate_local_copilot_draft(ticket_query, customer_name, customer_tier, documents)
    else:
        draft = generate_local_copilot_draft(ticket_query, customer_name, customer_tier, documents)

    latency = int((time.time() - start_time) * 1000)
    return {
        "suggested_reply": draft,
        "sources": documents,
        "latency_ms": latency
    }

def run_synthetic_benchmark(num_queries: int = 8) -> dict:
    """
    Executes a standardized synthetic load & accuracy benchmark across
    diverse customer intent categories, guardrails, and multilingual scenarios.
    """
    test_battery = [
        {"q": "What is the return window for open-box electronics?", "expected_intent": "Return & Refund", "should_deflect": False, "lang": "English"},
        {"q": "Do you ship to Canada and how are customs duties handled?", "expected_intent": "Shipping & Logistics", "should_deflect": False, "lang": "English"},
        {"q": "What is covered under the hardware manufacturer warranty?", "expected_intent": "Warranty & Claims", "should_deflect": False, "lang": "English"},
        {"q": "Can I cancel an order I placed 20 minutes ago?", "expected_intent": "Order Modification", "should_deflect": False, "lang": "English"},
        {"q": "¿Cuál es la política de devoluciones y reembolsos?", "expected_intent": "Return & Refund", "should_deflect": False, "lang": "Spanish"},
        {"q": "Wie lautet das Rückgaberecht für Einkäufe?", "expected_intent": "Return & Refund", "should_deflect": False, "lang": "German"},
        {"q": "返品ポリシーと返金条件は何ですか？", "expected_intent": "Return & Refund", "should_deflect": False, "lang": "Japanese"},
        {"q": "What is the stock price of Apple on NASDAQ?", "expected_intent": "General Inquiry", "should_deflect": True, "lang": "English"}
    ]
    
    battery = test_battery[:min(num_queries, len(test_battery))]
    results = []
    latencies = []
    bench_start = time.time()
    
    for item in battery:
        q_res = query_rag_pipeline(item["q"], target_language=item["lang"])
        lat = q_res.get("latency_ms", 50)
        latencies.append(lat)
        
        is_deflected = q_res.get("deflected", False)
        deflection_correct = (is_deflected == item["should_deflect"])
        intent_match = (q_res.get("intent") == item["expected_intent"])
        
        results.append({
            "query": item["q"],
            "language": q_res.get("language", item["lang"]),
            "intent": q_res.get("intent"),
            "latency_ms": lat,
            "deflected": is_deflected,
            "deflection_accurate": deflection_correct,
            "intent_accurate": intent_match
        })
        
    total_time_s = max(0.001, time.time() - bench_start)
    latencies.sort()
    
    p50 = latencies[len(latencies) // 2] if latencies else 0
    p90 = latencies[int(len(latencies) * 0.9)] if latencies else 0
    p99 = latencies[-1] if latencies else 0
    qps = round(len(battery) / total_time_s, 2)
    deflection_accuracy = round(sum(1 for r in results if r["deflection_accurate"]) / len(results) * 100, 1)
    intent_accuracy = round(sum(1 for r in results if r["intent_accurate"]) / len(results) * 100, 1)
    
    return {
        "status": "success",
        "benchmark_id": f"bench_{uuid.uuid4().hex[:8]}",
        "total_queries": len(battery),
        "total_duration_s": round(total_time_s, 3),
        "qps": qps,
        "latency_p50_ms": p50,
        "latency_p90_ms": p90,
        "latency_p99_ms": p99,
        "avg_latency_ms": round(sum(latencies) / len(latencies), 1) if latencies else 0,
        "guardrail_accuracy_percent": deflection_accuracy,
        "intent_accuracy_percent": intent_accuracy,
        "detailed_results": results
    }