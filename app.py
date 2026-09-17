import os
import streamlit as st
import requests
import json
import time
from dotenv import load_dotenv

load_dotenv()
if os.path.exists("doc/.env"):
    load_dotenv("doc/.env")

st.set_page_config(
    page_title="OmniDesk AI — Enterprise Support Hub",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for glassmorphic styling
st.markdown("""
<style>
    .metric-card {
        background: rgba(30, 41, 59, 0.6);
        border: 1px solid rgba(99, 102, 241, 0.25);
        border-radius: 12px;
        padding: 1rem 1.25rem;
        margin-bottom: 1rem;
    }
    .ticket-badge-vip {
        background-color: rgba(245, 158, 11, 0.2);
        color: #fbbf24;
        padding: 2px 8px;
        border-radius: 4px;
        font-size: 0.8rem;
        font-weight: 600;
    }
    .ticket-badge-pro {
        background-color: rgba(168, 85, 247, 0.2);
        color: #c084fc;
        padding: 2px 8px;
        border-radius: 4px;
        font-size: 0.8rem;
        font-weight: 600;
    }
    .ticket-badge-std {
        background-color: rgba(148, 163, 184, 0.2);
        color: #94a3b8;
        padding: 2px 8px;
        border-radius: 4px;
        font-size: 0.8rem;
    }
    .intent-pill {
        background: rgba(6, 182, 212, 0.15);
        color: #38bdf8;
        border: 1px solid rgba(6, 182, 212, 0.3);
        padding: 2px 8px;
        border-radius: 12px;
        font-size: 0.75rem;
        font-weight: 600;
    }
    .sentiment-urgent {
        background: rgba(244, 63, 94, 0.2);
        color: #fb7185;
        border: 1px solid rgba(244, 63, 94, 0.4);
        padding: 2px 8px;
        border-radius: 12px;
        font-size: 0.75rem;
        font-weight: 600;
    }
</style>
""", unsafe_allow_html=True)

# Helper function for auth headers
def get_headers(admin_key=""):
    headers = {"Content-Type": "application/json"}
    if admin_key:
        headers["X-API-Key"] = admin_key
    return headers

# Initialize session states
if "messages" not in st.session_state:
    st.session_state.messages = [
        {"role": "assistant", "content": "Hello! I am your AI Support Assistant grounded in verified store documentation. How can I assist you today?", "language": "English"}
    ]
if "admin_api_key" not in st.session_state:
    st.session_state.admin_api_key = ""
if "selected_language" not in st.session_state:
    st.session_state.selected_language = "Auto Detect"

# Sidebar Configuration
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/4712/4712035.png", width=48)
    st.title("OmniDesk AI")
    st.caption("Enterprise RAG Support Portal")
    
    st.markdown("---")
    st.subheader("⚙️ System Connection")
    default_backend = os.getenv("RAILWAY_URL") or os.getenv("BACKEND_URL") or "http://127.0.0.1:8000"
    backend_url = st.text_input("Backend API URL", value=default_backend, help="Enter your Railway backend URL (e.g. https://your-app.up.railway.app) or localhost:8000")
    admin_key = st.text_input("Admin API Key", value=st.session_state.admin_api_key, type="password", help="Required for protected KB mutations and settings sync.")
    st.session_state.admin_api_key = admin_key

    # Check connection health
    is_online = False
    health_info = {}
    try:
        r = requests.get(f"{backend_url.rstrip('/')}/health", timeout=3)
        if r.status_code == 200:
            is_online = True
            health_info = r.json()
            st.success(f"🟢 API Online ({health_info.get('vector_count', 0)} vectors)")
        else:
            st.warning(f"🟠 API Warning: {r.status_code}")
    except Exception:
        st.error("🔴 Backend Offline\nEnter your live Railway URL or start local server.")

    st.markdown("---")
    st.subheader("🎛️ Pipeline Settings")
    model_choice = st.selectbox("Generation Model", ["gemini-3.6-flash", "gemini-1.5-flash", "gemini-1.5-pro"], index=0)
    threshold = st.slider("Guardrail Deflection Threshold", min_value=0.2, max_value=2.0, value=0.90, step=0.05, help="Vector distance beyond which queries are deflected to human support.")
    top_k = st.slider("Retrieved Chunks (Top-K)", min_value=1, max_value=8, value=3)

    if st.button("Sync Settings to Backend", use_container_width=True) and is_online:
        try:
            res = requests.post(
                f"{backend_url}/api/settings",
                headers=get_headers(admin_key),
                json={"generation_model": model_choice, "guardrail_threshold": threshold, "top_k_chunks": top_k},
                timeout=3
            )
            if res.status_code == 200:
                st.toast("Settings synchronized successfully!", icon="✅")
            elif res.status_code == 401:
                st.error("Unauthorized: Invalid Admin API Key")
            else:
                st.error(f"Failed to sync: {res.text}")
        except Exception as e:
            st.error(f"Error: {e}")

# Main Tabs Navigation
tab_chat, tab_kb, tab_tickets, tab_analytics = st.tabs([
    "💬 Live AI Assistant",
    "📚 Knowledge Base Studio",
    "🎫 Escalations & Tickets Queue",
    "📊 Deflection & Analytics"
])

# ==============================================================================
# TAB 1: LIVE AI ASSISTANT CHAT
# ==============================================================================
with tab_chat:
    c_head1, c_head2 = st.columns([3, 2])
    with c_head1:
        st.subheader("Grounded Customer Support Agent")
        st.caption("Sub-second answers verified against company store policies with automatic human escalation.")
    with c_head2:
        lang_options = ["Auto Detect", "English", "Spanish", "French", "German", "Japanese", "Portuguese", "Hindi"]
        curr_idx = lang_options.index(st.session_state.selected_language) if st.session_state.selected_language in lang_options else 0
        sel_lang = st.selectbox("🌐 Target Language Localization", lang_options, index=curr_idx, key="lang_selector")
        st.session_state.selected_language = sel_lang

    # Render chat history
    for idx, msg in enumerate(st.session_state.messages):
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            
            # Show metadata chips
            chips = []
            if msg.get("intent"):
                chips.append(f"<span class='intent-pill'>{msg['intent']}</span>")
            if msg.get("sentiment") and "Urgent" in msg.get("sentiment", ""):
                chips.append(f"<span class='sentiment-urgent'>{msg['sentiment']}</span>")
            if msg.get("language") and msg.get("language") != "English":
                chips.append(f"<span class='intent-pill' style='background:rgba(16,185,129,0.15);color:#34d399;border-color:rgba(16,185,129,0.3);'>🌐 {msg['language']}</span>")
            
            if chips or msg.get("latency_ms"):
                cols = st.columns([max(len(chips), 1), 1, 3])
                if chips:
                    cols[0].markdown(" ".join(chips), unsafe_allow_html=True)
                if msg.get("latency_ms"):
                    cols[1].caption(f"⚡ {msg['latency_ms']}ms")

            # Show citations expander
            if msg.get("sources"):
                with st.expander(f"Verified Reference Context ({len(msg['sources'])} clauses)"):
                    for i, src in enumerate(msg["sources"]):
                        st.markdown(f"**[Clause {i+1}]** {src}")

            # CSAT Feedback Buttons for Assistant Responses
            if msg["role"] == "assistant" and idx > 0:
                fb_c1, fb_c2, fb_c3 = st.columns([1, 1, 6])
                if fb_c1.button("👍 Helpful", key=f"csat_pos_{idx}"):
                    if is_online:
                        requests.post(
                            f"{backend_url}/api/feedback",
                            json={
                                "is_positive": True,
                                "rating": 5,
                                "query": msg.get("original_query", ""),
                                "response": msg.get("content", ""),
                                "language": msg.get("language", "English")
                            },
                            timeout=3
                        )
                        st.toast("Thank you for your feedback! (5/5)", icon="⭐")
                if fb_c2.button("👎 Needs Work", key=f"csat_neg_{idx}"):
                    if is_online:
                        requests.post(
                            f"{backend_url}/api/feedback",
                            json={
                                "is_positive": False,
                                "rating": 2,
                                "query": msg.get("original_query", ""),
                                "response": msg.get("content", ""),
                                "language": msg.get("language", "English")
                            },
                            timeout=3
                        )
                        st.toast("Feedback recorded. We'll improve our documentation.", icon="📝")

            # Inline Escalation button if deflected
            if msg.get("deflected") and msg["role"] == "assistant":
                with st.expander("⚡ Escalate Inquiry & Create Support Ticket", expanded=False):
                    with st.form(key=f"escalate_form_{idx}"):
                        esc_name = st.text_input("Customer Name", value="Elena Rostova", key=f"esc_name_{idx}")
                        esc_email = st.text_input("Customer Email", value="elena@example.com", key=f"esc_email_{idx}")
                        esc_prio = st.selectbox("Priority Level", ["Urgent", "High", "Medium", "Low"], index=1, key=f"esc_prio_{idx}")
                        esc_subj = st.text_input("Subject", value=msg.get("original_query", "Customer Assistance Required")[:60], key=f"esc_subj_{idx}")
                        esc_query = st.text_area("Context Details", value=msg.get("original_query", ""), key=f"esc_query_{idx}")
                        
                        if st.form_submit_button("Submit Escalation Ticket", use_container_width=True):
                            if is_online:
                                try:
                                    t_res = requests.post(
                                        f"{backend_url}/api/tickets",
                                        json={
                                            "customer_name": esc_name,
                                            "customer_email": esc_email,
                                            "priority": esc_prio,
                                            "subject": esc_subj,
                                            "query": esc_query
                                        },
                                        timeout=4
                                    )
                                    if t_res.status_code == 200:
                                        t_data = t_res.json()
                                        st.success(f"✅ Ticket {t_data['ticket']['id']} created and routed to Tier 2 Support!")
                                    else:
                                        st.error(f"Failed: {t_res.text}")
                                except Exception as e:
                                    st.error(f"Error creating ticket: {e}")
                            else:
                                st.info("Created local ticket simulation (Backend offline).")

    # Chat user input
    if prompt := st.chat_input("Ask about returns, international shipping, warranties, or payment..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            with st.spinner("Retrieving verified policies..."):
                if is_online:
                    try:
                        req_payload = {"query": prompt}
                        if st.session_state.selected_language != "Auto Detect":
                            req_payload["language"] = st.session_state.selected_language

                        res = requests.post(
                            f"{backend_url}/ask",
                            json=req_payload,
                            timeout=15
                        )
                        if res.status_code == 200:
                            data = res.json()
                            answer = data.get("answer", "")
                            sources = data.get("sources", [])
                            latency = data.get("latency_ms", 0)
                            deflected = data.get("deflected", False)
                            intent = data.get("intent", "General Inquiry")
                            sentiment = data.get("sentiment", "Standard")
                            resp_lang = data.get("language", "English")

                            st.markdown(answer)
                            if sources:
                                with st.expander(f"Verified Reference Context ({len(sources)} clauses)"):
                                    for i, s in enumerate(sources):
                                        st.markdown(f"**[Clause {i+1}]** {s}")

                            st.session_state.messages.append({
                                "role": "assistant",
                                "content": answer,
                                "sources": sources,
                                "latency_ms": latency,
                                "deflected": deflected,
                                "intent": intent,
                                "sentiment": sentiment,
                                "language": resp_lang,
                                "original_query": prompt
                            })
                            st.rerun()
                        else:
                            st.error(f"Service Error ({res.status_code}): {res.text}")
                    except Exception as e:
                        st.error(f"Connection error: {e}")
                else:
                    st.warning("Backend server offline. Please start `python server.py`.")

# ==============================================================================
# TAB 2: KNOWLEDGE BASE STUDIO
# ==============================================================================
with tab_kb:
    st.subheader("ChromaDB Policy Vector Management")
    st.caption("Inspect, add, vectorized, and backup customer store policy clauses.")

    if is_online:
        try:
            kb_res = requests.get(f"{backend_url}/api/kb/chunks", headers=get_headers(admin_key), timeout=3)
            chunks = kb_res.json().get("chunks", []) if kb_res.status_code == 200 else []
        except Exception:
            chunks = []
    else:
        chunks = []

    kb_col1, kb_col2, kb_col3 = st.columns([2, 1, 1])
    kb_col1.metric("Indexed Policy Clauses", f"{len(chunks)} Vectors", "ChromaDB Persistent")
    kb_col2.metric("Embedding Dimension", "768-D", "gemini-embedding-001")
    
    # Download JSON Backup
    if is_online and chunks:
        kb_col3.download_button(
            label="📥 Export KB Backup (JSON)",
            data=json.dumps(chunks, indent=2),
            file_name="omnidesk_kb_backup.json",
            mime="application/json",
            use_container_width=True
        )

    st.markdown("---")
    
    # Add new policy clause expander
    with st.expander("➕ Ingest New Policy Clause to Vector Index", expanded=False):
        with st.form("add_chunk_form"):
            clause_title = st.text_input("Clause Title / Header", placeholder="e.g. Section 9: VIP Concierge Benefits")
            clause_content = st.text_area("Policy Clause Text", placeholder="Detailed policy wording for vector embedding...")
            clause_source = st.text_input("Source Document", value="custom_policy.txt")
            
            if st.form_submit_button("Vectorize & Ingest Clause", use_container_width=True):
                if not clause_title or not clause_content:
                    st.error("Title and Content are required.")
                elif is_online:
                    try:
                        add_r = requests.post(
                            f"{backend_url}/api/kb/add",
                            headers=get_headers(admin_key),
                            json={"title": clause_title, "content": clause_content, "source": clause_source},
                            timeout=6
                        )
                        if add_r.status_code == 200:
                            st.success(f"Clause '{clause_title}' successfully indexed into ChromaDB!")
                            st.rerun()
                        elif add_r.status_code == 401:
                            st.error("Unauthorized: Please enter a valid Admin API Key in the sidebar.")
                        else:
                            st.error(f"Error: {add_r.text}")
                    except Exception as e:
                        st.error(f"Failed to add clause: {e}")
                else:
                    st.error("Backend offline.")

    # Search and list chunks
    search_kb = st.text_input("🔍 Search Indexed Policy Vectors", placeholder="Filter by title or keywords...")
    filtered_chunks = [c for c in chunks if not search_kb or search_kb.lower() in (c.get("title","") + " " + c.get("content","")).lower()]

    for chunk in filtered_chunks:
        with st.container():
            st.markdown(f"#### 📄 {chunk.get('title', 'Policy Clause')} `{chunk.get('id')}`")
            st.write(chunk.get("content"))
            c_cols = st.columns([2, 1, 1])
            c_cols[0].caption(f"Source: `{chunk.get('source', 'company_faq.txt')}` • {chunk.get('tokens', 60)} tokens")
            
            if c_cols[2].button(f"🗑️ Delete", key=f"del_{chunk.get('id')}"):
                if is_online:
                    del_r = requests.delete(f"{backend_url}/api/kb/chunks/{chunk.get('id')}", headers=get_headers(admin_key))
                    if del_r.status_code == 200:
                        st.toast(f"Deleted chunk {chunk.get('id')}")
                        st.rerun()
                    elif del_r.status_code == 401:
                        st.error("Admin API Key required to delete chunks.")
                st.markdown("---")

# ==============================================================================
# TAB 3: ESCALATIONS & TICKETS QUEUE
# ==============================================================================
with tab_tickets:
    st.subheader("Support Tickets & Agent Escalations")
    st.caption("Track, route, and resolve customer issues requiring human agent review.")

    tickets = []
    stats = {"open_tickets": 0, "in_progress_tickets": 0, "resolved_tickets": 0, "resolution_rate_percent": 100.0}
    macros = []
    if is_online:
        try:
            t_res = requests.get(f"{backend_url}/api/tickets", timeout=3)
            if t_res.status_code == 200:
                tickets = t_res.json().get("tickets", [])
            s_res = requests.get(f"{backend_url}/api/tickets/stats", timeout=3)
            if s_res.status_code == 200:
                stats = s_res.json()
            m_res = requests.get(f"{backend_url}/api/macros", timeout=3)
            if m_res.status_code == 200:
                macros = m_res.json().get("macros", [])
        except Exception:
            pass

    # Ticket KPIs
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Open Tickets", stats.get("open_tickets", 0), "Pending Agent")
    k2.metric("In Progress", stats.get("in_progress_tickets", 0), "Being Handled")
    k3.metric("Resolved Tickets", stats.get("resolved_tickets", 0), "Closed")
    k4.metric("Resolution Rate", f"{stats.get('resolution_rate_percent', 100.0)}%", "SLA < 2h")

    st.markdown("---")

    # Filters and Export Row
    f_col1, f_col2, f_col3, f_col4 = st.columns([2, 1, 1, 1])
    search_ticket = f_col1.text_input("🔎 Search Tickets", placeholder="Search Customer ID, Name, Email, or Issue...")
    status_filter = f_col2.selectbox("Status Filter", ["All", "Open", "In Progress", "Resolved"])
    
    # Download CSV export
    if is_online and tickets:
        try:
            csv_res = requests.get(f"{backend_url}/api/tickets/export?format=csv", timeout=3)
            if csv_res.status_code == 200:
                f_col3.download_button(
                    label="📥 Export CSV",
                    data=csv_res.content,
                    file_name="omnidesk_tickets_export.csv",
                    mime="text/csv",
                    use_container_width=True
                )
        except Exception:
            pass

    # Filtered Tickets
    filtered_tickets = []
    for t in tickets:
        if status_filter != "All" and t.get("status", "").lower() != status_filter.lower():
            continue
        if search_ticket:
            sterm = search_ticket.lower()
            combined = (t.get("customer_id", "") + " " + t.get("customer_name", "") + " " + t.get("customer_email", "") + " " + t.get("subject", "") + " " + t.get("query", "")).lower()
            if sterm not in combined:
                continue
        filtered_tickets.append(t)

    if not filtered_tickets:
        st.info("No tickets found matching current filters.")

    for t in filtered_tickets:
        tier = t.get("customer_tier", "Standard Retail")
        tier_class = "ticket-badge-vip" if "VIP" in tier else ("ticket-badge-pro" if "Pro" in tier else "ticket-badge-std")
        
        sla = t.get("sla_details", {})
        sla_label = sla.get("label", "SLA Active")
        sla_badge = f"⏱️ {sla_label}"

        with st.expander(f"🎫 [{t.get('id')}] {t.get('subject')} — {t.get('customer_name')} ({t.get('status')} • {sla_badge})", expanded=(t.get("status") == "Open")):
            t_col1, t_col2 = st.columns([3, 2])
            with t_col1:
                st.markdown(f"**Customer:** {t.get('customer_name')} • `ID: {t.get('customer_id', 'CUST-XXXX')}` • <span class='{tier_class}'>{tier}</span>", unsafe_allow_html=True)
                st.caption(f"Email: {t.get('customer_email')} • Created: {t.get('created_at')} • SLA Status: **{sla_label}**")
                st.info(f"**Inquiry Query:**\n{t.get('query')}")
                
                # Badges
                b_cols = st.columns(3)
                b_cols[0].markdown(f"**Priority:** `{t.get('priority', 'Medium')}`")
                b_cols[1].markdown(f"**Intent:** <span class='intent-pill'>{t.get('intent', 'General Inquiry')}</span>", unsafe_allow_html=True)
                b_cols[2].markdown(f"**Sentiment:** `{t.get('sentiment', 'Standard')}`")

                # AI Copilot Draft & Macro Rules Generator
                with st.expander("🤖 OmniDesk AI Copilot & Macro Rules", expanded=False):
                    # Macro Pills / Selection
                    if macros:
                        st.caption("⚡ Quick Macro Automation Templates:")
                        m_cols = st.columns(min(len(macros), 4))
                        for m_idx, m_item in enumerate(macros[:4]):
                            if m_cols[m_idx].button(f"{m_item.get('icon', '⚡')} {m_item.get('name')}", key=f"mbtn_{t.get('id')}_{m_item.get('id')}"):
                                try:
                                    app_res = requests.post(
                                        f"{backend_url}/api/tickets/{t.get('id')}/apply-macro",
                                        json={"macro_id": m_item.get("id")}
                                    )
                                    if app_res.status_code == 200:
                                        applied_text = app_res.json().get("applied_text", "")
                                        st.session_state[f"draft_{t.get('id')}"] = applied_text
                                        st.toast(f"Applied Macro: {m_item.get('name')}!")
                                        st.rerun()
                                except Exception as e:
                                    st.error(f"Macro error: {e}")

                    st.markdown("---")
                    if st.button("💡 Generate Grounded AI Resolution Draft", key=f"copilot_btn_{t.get('id')}"):
                        try:
                            sug_r = requests.post(f"{backend_url}/api/tickets/{t.get('id')}/suggest-reply", timeout=10)
                            if sug_r.status_code == 200:
                                st.session_state[f"draft_{t.get('id')}"] = sug_r.json().get("suggested_reply", "")
                                st.toast("Grounded draft generated!")
                        except Exception as e:
                            st.error(f"Draft error: {e}")

                    draft_text = st.session_state.get(f"draft_{t.get('id')}", "")
                    edit_draft = st.text_area("Agent Reply Draft / Macro Editor", value=draft_text, height=120, key=f"draft_area_{t.get('id')}")
                    
                    c_send1, c_send2 = st.columns(2)
                    if c_send1.button("📨 Send Reply to Customer", key=f"send_draft_{t.get('id')}", use_container_width=True):
                        if edit_draft.strip():
                            requests.post(
                                f"{backend_url}/api/tickets/{t.get('id')}/messages",
                                json={"sender": "Support Agent", "text": edit_draft.strip(), "is_internal_note": False}
                            )
                            st.toast("Reply sent to customer!")
                            st.rerun()

                # Conversation Thread
                messages = t.get("messages", [])
                if messages:
                    st.markdown("**💬 Conversation Thread:**")
                    for m in messages:
                        is_int = m.get("is_internal_note", False)
                        sender = m.get("sender", "User")
                        ts = m.get("timestamp", "")
                        prefix = "🔒 [Internal Staff Note]" if is_int else f"👤 [{sender}]"
                        if is_int:
                            st.warning(f"**{prefix}** ({ts}):\n{m.get('text')}")
                        else:
                            st.chat_message("user" if sender == t.get("customer_name") else "assistant").write(f"**{sender}** ({ts}):\n{m.get('text')}")

                # Quick Message / Note Input
                with st.form(f"msg_form_{t.get('id')}"):
                    new_msg_text = st.text_input("Post Message or Staff Note", placeholder="Add response or internal note...")
                    is_note = st.checkbox("Internal Note Only (Private)", key=f"chk_note_{t.get('id')}")
                    if st.form_submit_button("Post Message", use_container_width=True):
                        if new_msg_text.strip():
                            requests.post(
                                f"{backend_url}/api/tickets/{t.get('id')}/messages",
                                json={"sender": "Staff Note" if is_note else "Support Agent", "text": new_msg_text.strip(), "is_internal_note": is_note}
                            )
                            st.toast("Message logged to thread!")
                            st.rerun()

            with t_col2:
                st.markdown(f"**Current Status:** `{t.get('status')}`")
                
                # Agent Assignment
                agents = ["Unassigned", "Alex Morgan (Tier 2 Lead)", "Sarah Chen (Logistics)", "David Miller (Billing)", "Emma Watson (Warranty)"]
                curr_agent = t.get("assigned_agent", "Unassigned")
                curr_idx = 0
                for i, a in enumerate(agents):
                    if curr_agent in a:
                        curr_idx = i
                        break
                
                new_agent = st.selectbox("Assign Agent", agents, index=curr_idx, key=f"agent_sel_{t.get('id')}")
                if new_agent != agents[curr_idx]:
                    assigned_name = new_agent.split(" (")[0]
                    requests.patch(
                        f"{backend_url}/api/tickets/{t.get('id')}",
                        headers=get_headers(admin_key),
                        json={"assigned_agent": assigned_name, "status": "In Progress"}
                    )
                    st.toast(f"Assigned to {assigned_name}")
                    st.rerun()

                act1, act2 = st.columns(2)
                if t.get("status") != "Resolved":
                    if act1.button("✅ Mark Resolved", key=f"res_{t.get('id')}", use_container_width=True):
                        requests.patch(f"{backend_url}/api/tickets/{t.get('id')}", headers=get_headers(admin_key), json={"status": "Resolved"})
                        st.toast("Ticket marked as Resolved!")
                        st.rerun()
                else:
                    if act1.button("🔄 Reopen", key=f"reopen_{t.get('id')}", use_container_width=True):
                        requests.patch(f"{backend_url}/api/tickets/{t.get('id')}", headers=get_headers(admin_key), json={"status": "Open"})
                        st.toast("Ticket Reopened!")
                        st.rerun()

                if act2.button("🗑️ Delete", key=f"deltck_{t.get('id')}", use_container_width=True):
                    requests.delete(f"{backend_url}/api/tickets/{t.get('id')}", headers=get_headers(admin_key))
                    st.toast("Ticket deleted!")
                    st.rerun()

# ==============================================================================
# TAB 4: DEFLECTION & ANALYTICS
# ==============================================================================
with tab_analytics:
    st.subheader("Resolution & Deflection Telemetry")
    st.caption("Live AI deflection rate, CSAT customer feedback, and grounded audit trail log.")

    analytics_data = {"deflection_rate": 88.4, "avg_latency_s": 0.42, "total_inquiries": 1284, "csat_score": 4.92, "csat_positive_percent": 99.1, "audit_logs": []}
    if is_online:
        try:
            an_res = requests.get(f"{backend_url}/api/analytics", headers=get_headers(admin_key), timeout=3)
            if an_res.status_code == 200:
                analytics_data = an_res.json()
        except Exception:
            pass

    a1, a2, a3, a4 = st.columns(4)
    a1.metric("Autonomous Deflection", f"{analytics_data.get('deflection_rate', 88.4)}%", "+4.2% vs human tier")
    a2.metric("Average Response Latency", f"{analytics_data.get('avg_latency_s', 0.42)}s", "Sub-second SSE")
    a3.metric("Total Inquiries Handled", f"{analytics_data.get('total_inquiries', 1284):,}", "24/7 Availability")
    a4.metric("Customer CSAT Score", f"{analytics_data.get('csat_score', 4.92)} / 5.0", f"{analytics_data.get('csat_positive_percent', 99.1)}% Positive")

    st.markdown("---")
    st.subheader("📋 Live Grounded Audit Stream")
    
    logs = analytics_data.get("audit_logs", [])
    if logs:
        st.dataframe(
            logs,
            column_config={
                "id": "Log ID",
                "query": "Customer Query",
                "matched": "Matched Policy Section",
                "status": "Resolution Status",
                "latency_ms": "Latency (ms)",
                "timestamp": "Timestamp"
            },
            use_container_width=True,
            hide_index=True
        )
    else:
        st.info("No audit entries recorded yet in current session.")

    st.markdown("---")
    b_col1, b_col2 = st.columns([3, 1])
    with b_col1:
        st.subheader("⚡ Synthetic Load & Accuracy Benchmark Studio")
        st.caption("Multi-scenario load test evaluating throughput (QPS), latency percentiles, and guardrail precision.")
    with b_col2:
        if st.button("🚀 Run Synthetic Benchmark", use_container_width=True) and is_online:
            try:
                b_res = requests.post(f"{backend_url}/api/benchmark/simulate", json={"num_queries": 8}, timeout=15)
                if b_res.status_code == 200:
                    st.session_state["bench_results"] = b_res.json()
                    st.toast("Synthetic Benchmark Completed!", icon="⚡")
            except Exception as e:
                st.error(f"Benchmark error: {e}")

    bench = st.session_state.get("bench_results")
    if bench:
        bm1, bm2, bm3, bm4 = st.columns(4)
        bm1.metric("Throughput", f"{bench.get('qps', 18.4)} QPS", "Concurrent Load")
        bm2.metric("P50 Latency", f"{bench.get('latency_p50_ms', 48)}ms", "Sub-second")
        bm3.metric("Guardrail Precision", f"{bench.get('guardrail_accuracy_percent', 100.0)}%", "Policy Grounded")
        bm4.metric("Intent Accuracy", f"{bench.get('intent_accuracy_percent', 100.0)}%", "Auto Classification")

        with st.expander("📊 Detailed Battery Results (8 Test Scenarios)", expanded=True):
            st.dataframe(bench.get("detailed_results", []), use_container_width=True, hide_index=True)

    st.markdown("---")
    st.subheader("🔔 Outbound Incident Webhooks Feed")
    w_col1, w_col2 = st.columns([3, 1])
    with w_col1:
        st.caption("Automated dispatch to Slack, PagerDuty, and SIEM on SLA risk thresholds and low CSAT scores.")
    with w_col2:
        if st.button("📡 Dispatch Test Alert", use_container_width=True) and is_online:
            try:
                w_res = requests.post(f"{backend_url}/api/webhooks/test", timeout=3)
                if w_res.status_code == 200:
                    st.toast("Test Webhook Alert Dispatched to Slack!", icon="🔔")
            except Exception as e:
                st.error(f"Webhook error: {e}")

    wh_logs = analytics_data.get("recent_webhooks", [])
    if wh_logs:
        for w in wh_logs:
            st.info(f"**{w.get('title')}** • Target: `{w.get('destination')}` • Status: **{w.get('status')}** (⏱️ {w.get('timestamp')})")