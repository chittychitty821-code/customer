/* ==========================================================================
   OMNIDESK AI - SUPPORT HUB APPLICATION PORTAL CONTROLLER (SPA)
   Phase 3: Smart Human Escalation & Support Ticket Management
   ========================================================================== */

// Global Application State
const AppState = {
  currentView: 'chat',
  backendUrl: localStorage.getItem('omni_backend_url') || 'http://localhost:8000',
  adminApiKey: localStorage.getItem('omni_admin_key') || '',
  guardrailThreshold: parseFloat(localStorage.getItem('omni_threshold')) || 1.2,
  model: localStorage.getItem('omni_model') || 'gemini-3.6-flash',
  topK: parseInt(localStorage.getItem('omni_top_k')) || 2,
  isBackendOnline: false,
  isStreaming: false,
  activeTicketFilter: 'all',
  messages: [
    {
      role: 'assistant',
      content: 'Hello! I am your AI Customer Support Assistant, grounded exclusively in your verified store policies. Ask me about returns, international shipping rates, warranty repairs, price matching, or order cancellations.',
      sources: [],
      latency: null
    }
  ],
  knowledgeChunks: [
    {
      id: 'chunk_0',
      title: 'Section 1: Return and Exchange Policy',
      content: '30-Day Return Window: Customers may return eligible products within 30 calendar days of delivery for a full refund to original payment method. Items must be unused in original packaging. Open-box electronics incur a 15% restocking fee. Return shipping is free in USA & Canada.',
      tokens: 72,
      source: 'company_faq.txt'
    },
    {
      id: 'chunk_1',
      title: 'Section 2: Shipping and Delivery Options',
      content: 'Domestic Shipping: Standard (3-5 days) free over $50, flat $4.99 under $50. Expedited 2-Day: $14.99. Overnight: $29.99 for orders before 1 PM EST. International: 85+ countries via DHL Express (7-14 days), shipped DDP (Delivered Duty Paid with duties calculated at checkout).',
      tokens: 84,
      source: 'company_faq.txt'
    },
    {
      id: 'chunk_2',
      title: 'Section 3: Order Modification & Cancellation',
      content: 'Cancellation Window: Orders can be cancelled or modified within 60 minutes of placement directly from account dashboard or via support. After 60 minutes, orders enter automated warehouse picking and cannot be cancelled.',
      tokens: 58,
      source: 'company_faq.txt'
    },
    {
      id: 'chunk_3',
      title: 'Section 4: Warranty & Repair Coverage',
      content: '1-Year Limited Manufacturer Warranty: Covers defects in materials and manufacturing workmanship. Does NOT cover cosmetic wear, accidental drops, or unauthorized repairs. Claims require serial number and photos sent to support@company.com.',
      tokens: 65,
      source: 'company_faq.txt'
    },
    {
      id: 'chunk_4',
      title: 'Section 5: Payment Methods & Price Match',
      content: 'Accepted Payments: Visa, MasterCard, Amex, Discover, PayPal, Apple Pay, Google Pay, and Klarna/Affirm (0% APR). 14-Day Price Match Guarantee if an item is sold cheaper on an authorized retailer within 14 days.',
      tokens: 60,
      source: 'company_faq.txt'
    },
    {
      id: 'chunk_5',
      title: 'Section 6: Support Escalation & Hours',
      content: 'AI Support Hub available 24/7/365. Live Agent Hours: Mon-Fri 8 AM - 8 PM EST, Sat-Sun 10 AM - 6 PM EST. Escalation Email: support@company.com (under 2 hour response time). Priority phone: +1 (800) 555-APEX.',
      tokens: 55,
      source: 'company_faq.txt'
    }
  ],
  tickets: [
    {
      id: 'TCK-1042',
      customer_name: 'Elena Rostova',
      customer_email: 'elena.r@techcorp.io',
      subject: 'Custom enterprise bulk discount inquiry',
      query: 'We are looking to order 250 units for our corporate team. Are custom volume pricing tiers available?',
      priority: 'High',
      status: 'Open',
      created_at: 'Today, 10:14',
      assigned_agent: 'Unassigned',
      transcript_snippet: 'Customer asked for bulk volume tier pricing outside standard retail catalog.'
    },
    {
      id: 'TCK-1039',
      customer_name: 'Marcus Vance',
      customer_email: 'm.vance@vertex.com',
      subject: 'Missing commercial tax exemption invoice',
      query: 'Where can I upload our state resale tax exemption certificate for order #88412?',
      priority: 'Urgent',
      status: 'In Progress',
      created_at: 'Today, 09:30',
      assigned_agent: 'Sarah Jenkins',
      transcript_snippet: 'Deflected tax exemption form request.'
    },
    {
      id: 'TCK-1031',
      customer_name: 'David Kim',
      customer_email: 'dkim@ventures.com',
      subject: 'Freight shipping to Antarctica research station',
      query: 'Do you offer specialized freight shipping to McMurdo Station?',
      priority: 'Low',
      status: 'Resolved',
      created_at: 'Yesterday, 14:15',
      assigned_agent: 'Alex Morgan',
      transcript_snippet: 'Inquiry on non-standard remote geography delivery.'
    }
  ]
};

// Helper: Build headers with optional Admin API Key
function getAuthHeaders(baseHeaders = {}) {
  const headers = { ...baseHeaders };
  if (AppState.adminApiKey) {
    headers['X-API-Key'] = AppState.adminApiKey;
  }
  return headers;
}

// Toast Notification
function showToast(message, type = 'info') {
  const container = document.getElementById('toast-container');
  if (!container) return;

  const toast = document.createElement('div');
  toast.className = `toast ${type}`;
  
  let icon = 'fa-circle-info';
  if (type === 'success') icon = 'fa-circle-check';
  if (type === 'error') icon = 'fa-triangle-exclamation';
  if (type === 'warning') icon = 'fa-triangle-exclamation';

  toast.innerHTML = `<i class="fa-solid ${icon}"></i> <span>${message}</span>`;
  container.appendChild(toast);

  setTimeout(() => {
    toast.style.opacity = '0';
    toast.style.transform = 'translateX(100%)';
    toast.style.transition = 'all 0.3s ease';
    setTimeout(() => toast.remove(), 300);
  }, 4000);
}

// 1. Navigation View Switcher
function switchAppView(viewName) {
  AppState.currentView = viewName;

  const navMap = {
    chat: { btn: 'btn-nav-chat', title: 'Live AI Support Chat', view: 'view-chat' },
    kb: { btn: 'btn-nav-kb', title: 'Knowledge Base Studio', view: 'view-kb' },
    tickets: { btn: 'btn-nav-tickets', title: 'Escalation & Support Tickets Inbox', view: 'view-tickets' },
    analytics: { btn: 'btn-nav-analytics', title: 'Deflection & Analytics Dashboard', view: 'view-analytics' },
    settings: { btn: 'btn-nav-settings', title: 'RAG Pipeline Settings', view: 'view-settings' }
  };

  Object.keys(navMap).forEach(key => {
    const config = navMap[key];
    const btn = document.getElementById(config.btn);
    const viewEl = document.getElementById(config.view);
    if (btn) btn.classList.toggle('active', key === viewName);
    if (viewEl) viewEl.classList.toggle('active-view', key === viewName);
  });

  const titleEl = document.getElementById('current-view-title');
  if (titleEl && navMap[viewName]) {
    titleEl.textContent = navMap[viewName].title;
  }

  if (viewName === 'kb') {
    fetchKbChunksFromBackend();
  } else if (viewName === 'tickets') {
    fetchTicketsFromBackend();
  } else if (viewName === 'analytics') {
    fetchAnalyticsFromBackend();
  } else if (viewName === 'settings') {
    populateSettingsView();
  }
}

// Mobile sidebar toggle
function toggleAppSidebar() {
  const sidebar = document.getElementById('app-sidebar');
  if (sidebar) {
    sidebar.classList.toggle('mobile-open');
  }
}

// 2. Backend Health & Connectivity Checker
async function checkBackendHealth() {
  const statusDot = document.getElementById('sidebar-status-dot');
  const statusText = document.getElementById('sidebar-status-text');

  try {
    const res = await fetch(`${AppState.backendUrl}/health`, {
      signal: AbortSignal.timeout(2500)
    });

    if (res.ok) {
      const hData = await res.json();
      AppState.isBackendOnline = true;
      if (statusDot) {
        statusDot.className = 'pulse-dot';
      }
      if (statusText) {
        const modeDesc = hData.has_gemini_api_key ? 'Gemini Live' : 'Fallback Mode';
        statusText.textContent = `API Online (${modeDesc})`;
        statusText.style.color = '#34d399';
      }
      
      // Update sidebar ticket count badge
      if (hData.open_tickets !== undefined) {
        const badge = document.getElementById('sidebar-ticket-count');
        if (badge) badge.textContent = hData.open_tickets;
      }
      
      // Fetch pipeline info
      try {
        const infoRes = await fetch(`${AppState.backendUrl}/api/info`);
        if (infoRes.ok) {
          const info = await infoRes.json();
          const chunkCountEl = document.getElementById('info-chunk-count');
          if (chunkCountEl) {
            chunkCountEl.textContent = `${info.document_chunks} Chunks`;
          }
          const thresholdEl = document.getElementById('info-guardrail-threshold');
          if (thresholdEl) {
            thresholdEl.textContent = Number(info.guardrail_threshold).toFixed(2);
          }
          const modelBadge = document.getElementById('model-indicator-badge');
          if (modelBadge && info.generation_model) {
            const authTag = info.admin_auth_enabled ? ' • Protected' : '';
            modelBadge.innerHTML = `<i class="fa-solid fa-microchip"></i> ${info.generation_model}${authTag}`;
          }
        }
      } catch (e) {}

      return true;
    }
  } catch (err) {
    AppState.isBackendOnline = false;
  }

  // Offline / simulation mode
  if (statusDot) {
    statusDot.className = 'pulse-dot-red';
  }
  if (statusText) {
    statusText.textContent = 'Local Simulation Mode';
    statusText.style.color = '#f59e0b';
  }
  return false;
}

// 3. Live Support Chat with Real-Time SSE Streaming
function handleChatKeyDown(e) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault();
    handleSendChat();
  }
}

function sendAppQuickQuery(query) {
  const input = document.getElementById('app-chat-input');
  if (input) {
    input.value = query;
    handleSendChat();
  }
}

async function handleSendChat() {
  const input = document.getElementById('app-chat-input');
  const chatFeed = document.getElementById('chat-feed');
  const sendBtn = document.getElementById('btn-send-message');
  if (!input || !chatFeed || AppState.isStreaming) return;

  const query = input.value.trim();
  if (!query) return;

  // Add user message
  AppState.messages.push({ role: 'user', content: query });
  renderUserMessage(chatFeed, query);
  input.value = '';
  chatFeed.scrollTop = chatFeed.scrollHeight;

  // Create streaming assistant message bubble
  const msgRowId = 'msg-row-' + Date.now();
  const msgBubbleId = 'msg-bubble-' + Date.now();
  const actionsId = 'msg-actions-' + Date.now();
  
  createAssistantPlaceholder(chatFeed, msgRowId, msgBubbleId, actionsId);
  chatFeed.scrollTop = chatFeed.scrollHeight;

  const bubbleEl = document.getElementById(msgBubbleId);
  const actionsEl = document.getElementById(actionsId);
  AppState.isStreaming = true;
  if (sendBtn) sendBtn.disabled = true;

  let accumulatedText = '';
  let retrievedSources = [];
  let isDeflected = false;
  let latencyMs = 0;
  let modelUsed = AppState.model;

  if (AppState.isBackendOnline) {
    try {
      const response = await fetch(`${AppState.backendUrl}/ask/stream`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: query })
      });

      if (response.status === 429) {
        const retryAfter = response.headers.get('Retry-After') || '5';
        showToast(`Rate limit reached. Please wait ${retryAfter}s before sending more questions.`, 'warning');
        throw new Error(`Rate limit exceeded (${response.status})`);
      }

      if (!response.ok) {
        throw new Error(`Server returned ${response.status}`);
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder('utf-8');
      let buffer = '';

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const events = buffer.split('\n\n');
        buffer = events.pop();

        for (const rawEvent of events) {
          if (!rawEvent.trim()) continue;
          
          let eventType = 'message';
          let dataStr = '';

          const lines = rawEvent.split('\n');
          for (const line of lines) {
            if (line.startsWith('event: ')) {
              eventType = line.replace('event: ', '').trim();
            } else if (line.startsWith('data: ')) {
              dataStr = line.replace('data: ', '').trim();
            }
          }

          if (dataStr) {
            try {
              const data = JSON.parse(dataStr);
              if (eventType === 'sources') {
                retrievedSources = data.sources || [];
                isDeflected = !!data.deflected;
              } else if (eventType === 'token') {
                accumulatedText += data.token;
                updateStreamingMessage(bubbleEl, accumulatedText);
                chatFeed.scrollTop = chatFeed.scrollHeight;
              } else if (eventType === 'done') {
                latencyMs = data.latency_ms || 0;
                modelUsed = data.model || modelUsed;
                isDeflected = !!data.deflected;
              }
            } catch (err) {
              console.warn('SSE Parse error:', err);
            }
          }
        }
      }
    } catch (e) {
      console.warn('Backend stream failed, using offline fallback engine:', e);
      accumulatedText = await runSimulatedStreaming(query, bubbleEl, chatFeed, (srcs, defl, lat) => {
        retrievedSources = srcs;
        isDeflected = defl;
        latencyMs = lat;
      });
    }
  } else {
    // Offline simulation mode
    accumulatedText = await runSimulatedStreaming(query, bubbleEl, chatFeed, (srcs, defl, lat) => {
      retrievedSources = srcs;
      isDeflected = defl;
      latencyMs = lat;
    });
  }

  // Finalize assistant message
  finalizeAssistantMessage(bubbleEl, actionsEl, accumulatedText, retrievedSources, latencyMs, isDeflected, query);
  AppState.messages.push({
    role: 'assistant',
    content: accumulatedText,
    sources: retrievedSources,
    latency: latencyMs
  });

  AppState.isStreaming = false;
  if (sendBtn) sendBtn.disabled = false;
  chatFeed.scrollTop = chatFeed.scrollHeight;

  if (AppState.currentView === 'analytics') {
    fetchAnalyticsFromBackend();
  }
}

// Helper: simulated streaming when backend is offline
async function runSimulatedStreaming(query, bubbleEl, chatFeed, metaCallback) {
  let sources = [];
  const fullText = runLocalSimulatedRag(query, (outSources) => { sources = outSources; });
  const isDeflected = sources.length === 0;
  const startTime = Date.now();

  const words = fullText.split(' ');
  let currentText = '';

  for (let i = 0; i < words.length; i++) {
    currentText += (i === 0 ? '' : ' ') + words[i];
    updateStreamingMessage(bubbleEl, currentText);
    chatFeed.scrollTop = chatFeed.scrollHeight;
    await new Promise(r => setTimeout(r, 22));
  }

  const latency = Date.now() - startTime;
  if (metaCallback) metaCallback(sources, isDeflected, latency);
  return fullText;
}

function createAssistantPlaceholder(container, rowId, bubbleId, actionsId) {
  const row = document.createElement('div');
  row.className = 'chat-msg-row assistant-msg';
  row.id = rowId;
  row.innerHTML = `
    <div class="avatar-badge avatar-assistant">
      <i class="fa-solid fa-robot"></i>
    </div>
    <div style="flex: 1;">
      <div class="msg-bubble-content" id="${bubbleId}">
        <span class="typing-cursor"></span>
      </div>
      <div class="msg-actions-bar" id="${actionsId}" style="display: none;">
        <button type="button" class="msg-btn-action" onclick="copyMessageText(this)">
          <i class="fa-solid fa-copy"></i> Copy
        </button>
        <button type="button" class="msg-btn-action" onclick="speakMessageText(this)">
          <i class="fa-solid fa-volume-high"></i> Read Aloud
        </button>
        <button type="button" class="msg-btn-action" onclick="rateMessage(this, 'helpful')">
          <i class="fa-solid fa-thumbs-up"></i> Helpful
        </button>
        <button type="button" class="msg-btn-action" onclick="rateMessage(this, 'unhelpful')">
          <i class="fa-solid fa-thumbs-down"></i>
        </button>
      </div>
    </div>
  `;
  container.appendChild(row);
}

function updateStreamingMessage(bubbleEl, text) {
  if (!bubbleEl) return;
  bubbleEl.innerHTML = formatMarkdownText(text) + '<span class="typing-cursor"></span>';
}

function finalizeAssistantMessage(bubbleEl, actionsEl, text, sources, latencyMs, isDeflected, originalQuery = '') {
  if (!bubbleEl) return;

  let sourcesHtml = '';
  if (sources && sources.length > 0) {
    const sourcesList = sources.map((s, idx) => `
      <div style="margin-top: 4px; padding: 6px 8px; background: rgba(0,0,0,0.3); border-radius: 4px; line-height: 1.4; font-size: 0.82rem; border-left: 3px solid var(--secondary);">
        <strong>[Clause ${idx + 1}]</strong> ${escapeHtml(s)}
      </div>
    `).join('');

    sourcesHtml = `
      <div class="msg-sources-drawer" style="margin-top: 0.75rem; border-top: 1px solid var(--border-subtle); padding-top: 0.5rem;">
        <div class="sources-header" style="font-size: 0.78rem; color: var(--secondary-light); display: flex; align-items: center; gap: 6px; margin-bottom: 4px;">
          <i class="fa-solid fa-shield-check"></i>
          <span><strong>Verified Policy Citations</strong> (${sources.length} chunk${sources.length > 1 ? 's' : ''})</span>
        </div>
        ${sourcesList}
      </div>
    `;
  }

  let escalationButtonHtml = '';
  if (isDeflected) {
    const safeQuery = escapeHtml(originalQuery || text).replace(/'/g, "\\'");
    escalationButtonHtml = `
      <div>
        <button type="button" class="btn-escalate-ticket" onclick="openCreateTicketModal('${safeQuery}')">
          <i class="fa-solid fa-headset"></i> Escalate &amp; Create Support Ticket
        </button>
      </div>
    `;
  }

  let latencyBadge = '';
  if (latencyMs > 0) {
    latencyBadge = `
      <span class="latency-pill ${isDeflected ? 'deflected' : ''}">
        <i class="fa-solid fa-bolt"></i> ${latencyMs}ms
      </span>
    `;
  }

  bubbleEl.innerHTML = `
    <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 4px;">
      <div style="flex: 1;">${formatMarkdownText(text)}</div>
      ${latencyBadge}
    </div>
    ${escalationButtonHtml}
    ${sourcesHtml}
  `;

  if (actionsEl) {
    actionsEl.style.display = 'flex';
  }
}

function renderUserMessage(container, text) {
  const row = document.createElement('div');
  row.className = 'chat-msg-row user-msg';
  row.innerHTML = `
    <div class="avatar-badge avatar-user">
      <i class="fa-solid fa-user"></i>
    </div>
    <div style="flex: 1; text-align: right;">
      <div class="msg-bubble-content" style="text-align: left; display: inline-block;">
        ${escapeHtml(text)}
      </div>
    </div>
  `;
  container.appendChild(row);
}

// Local Grounded RAG Simulation for Offline Mode
function runLocalSimulatedRag(query, setSourcesCallback) {
  const q = query.toLowerCase();
  let matched = [];

  AppState.knowledgeChunks.forEach(chunk => {
    const text = (chunk.title + ' ' + chunk.content).toLowerCase();
    let score = 0;
    
    if (q.includes('return') || q.includes('refund') || q.includes('restock') || q.includes('30-day')) {
      if (text.includes('return')) score += 3;
    }
    if (q.includes('ship') || q.includes('international') || q.includes('canada') || q.includes('duties') || q.includes('overnight') || q.includes('delivery')) {
      if (text.includes('shipping') || text.includes('international')) score += 3;
    }
    if (q.includes('warranty') || q.includes('repair') || q.includes('defect') || q.includes('replace') || q.includes('broken')) {
      if (text.includes('warranty')) score += 3;
    }
    if (q.includes('cancel') || q.includes('modify') || q.includes('change address') || q.includes('60 minute')) {
      if (text.includes('cancellation')) score += 3;
    }
    if (q.includes('pay') || q.includes('card') || q.includes('paypal') || q.includes('apple') || q.includes('price match') || q.includes('klarna')) {
      if (text.includes('payment') || text.includes('price match')) score += 3;
    }
    if (q.includes('hour') || q.includes('contact') || q.includes('agent') || q.includes('support@') || q.includes('phone') || q.includes('escalat')) {
      if (text.includes('escalation') || text.includes('support hub')) score += 3;
    }

    if (score > 0) {
      matched.push({ chunk, score });
    }
  });

  if (matched.length === 0) {
    if (setSourcesCallback) setSourcesCallback([]);
    return "I am sorry, but our verified policy database does not contain information regarding that request. Would you like me to connect you with our live support team at support@company.com?";
  }

  matched.sort((a, b) => b.score - a.score);
  const topMatches = matched.slice(0, 2);
  const sources = topMatches.map(m => m.chunk.content);
  if (setSourcesCallback) setSourcesCallback(sources);

  if (q.includes('return') || q.includes('refund') || q.includes('30-day')) {
    return "Under our verified **Return and Exchange Policy**, you may return eligible products within **30 calendar days of delivery** for a full refund to your original payment method. Items must be unused and in original packaging. Note that open-box electronics may be subject to a 15% restocking fee unless defective. Return shipping is free for US and Canada orders.";
  }
  if (q.includes('ship') || q.includes('canada') || q.includes('international') || q.includes('duties')) {
    return "We offer Standard US shipping (3-5 business days, free over $50), Expedited 2-Day ($14.99), and Overnight Delivery ($29.99). We also ship to over 85 international countries (including Canada) via DHL Express. All international orders are shipped **DDP (Delivered Duty Paid)**, so all customs duties and import taxes are calculated and collected at checkout with no surprise fees upon delivery.";
  }
  if (q.includes('warranty') || q.includes('defect') || q.includes('claim')) {
    return "All hardware products come with a **1-Year Limited Manufacturer Warranty** covering defects in materials and workmanship. It does not cover accidental drops or water damage. To file a warranty claim, email your order number, serial number, and photos to **support@company.com**.";
  }
  if (q.includes('cancel') || q.includes('modify')) {
    return "Orders can be cancelled or modified within a strict **60-minute window** of order placement directly from your account dashboard or by reaching support. After 60 minutes, orders enter automated warehouse picking and cannot be stopped; you may initiate a standard return once received.";
  }
  if (q.includes('pay') || q.includes('price match') || q.includes('klarna') || q.includes('installment')) {
    return "We accept Visa, MasterCard, American Express, Discover, PayPal, Apple Pay, Google Pay, and Klarna / Affirm installments (0% APR available). Additionally, we offer a **14-Day Price Match Guarantee** if an item goes on sale or is listed cheaper at an authorized retailer within 14 days of purchase.";
  }

  return `Based on our verified store policy (${topMatches[0].chunk.title}):\n\n${topMatches[0].chunk.content}`;
}

// 4. Knowledge Base Studio Management
async function fetchKbChunksFromBackend() {
  if (AppState.isBackendOnline) {
    try {
      const res = await fetch(`${AppState.backendUrl}/api/kb/chunks`, {
        headers: getAuthHeaders()
      });
      if (res.ok) {
        const data = await res.json();
        if (data.chunks && data.chunks.length > 0) {
          AppState.knowledgeChunks = data.chunks;
        }
      }
    } catch (e) {
      console.warn('Failed to fetch KB chunks from API:', e);
    }
  }
  renderKbChunks();
  
  const chunkCountEl = document.getElementById('info-chunk-count');
  if (chunkCountEl) {
    chunkCountEl.textContent = `${AppState.knowledgeChunks.length} Chunks`;
  }
}

function renderKbChunks(filterText = '') {
  const container = document.getElementById('kb-chunks-list');
  if (!container) return;

  const chunks = AppState.knowledgeChunks.filter(c => {
    if (!filterText) return true;
    const s = filterText.toLowerCase();
    return c.title.toLowerCase().includes(s) || c.content.toLowerCase().includes(s);
  });

  if (chunks.length === 0) {
    container.innerHTML = `<div style="grid-column: 1/-1; text-align: center; color: var(--text-muted); padding: 3rem;">No policy chunks found matching "${filterText}".</div>`;
    return;
  }

  container.innerHTML = chunks.map(chunk => `
    <div class="chunk-card" id="card-${chunk.id}">
      <div class="chunk-header">
        <span><i class="fa-solid fa-hashtag"></i> ${chunk.id}</span>
        <div class="chunk-actions">
          <span class="badge badge-cyan" style="font-size: 0.72rem; padding: 0.15rem 0.5rem;">${chunk.tokens || 60} tokens</span>
          <button type="button" class="chunk-btn-delete" onclick="handleDeletePolicyClause('${chunk.id}')" title="Delete chunk">
            <i class="fa-solid fa-trash"></i>
          </button>
        </div>
      </div>
      <h4 style="font-size: 1.05rem;">${escapeHtml(chunk.title)}</h4>
      <div class="chunk-text">${escapeHtml(chunk.content)}</div>
      <div style="font-size: 0.75rem; color: var(--text-dim); display: flex; justify-content: space-between; margin-top: auto; padding-top: 0.5rem; border-top: 1px solid var(--border-subtle);">
        <span>Source: <code>${escapeHtml(chunk.source || 'company_faq.txt')}</code></span>
        <span style="color: #34d399;"><i class="fa-solid fa-circle-check"></i> Vector Indexed</span>
      </div>
    </div>
  `).join('');
}

function filterKbChunks() {
  const input = document.getElementById('kb-search-input');
  renderKbChunks(input ? input.value : '');
}

function openAddPolicyModal() {
  const modal = document.getElementById('add-policy-modal');
  if (modal) modal.classList.add('open');
}

function closeAddPolicyModal() {
  const modal = document.getElementById('add-policy-modal');
  if (modal) modal.classList.remove('open');
}

async function handleAddPolicyClause(e) {
  e.preventDefault();
  const title = document.getElementById('policy-title').value.trim();
  const content = document.getElementById('policy-content').value.trim();
  if (!title || !content) return;

  if (AppState.isBackendOnline) {
    try {
      const res = await fetch(`${AppState.backendUrl}/api/kb/add`, {
        method: 'POST',
        headers: getAuthHeaders({ 'Content-Type': 'application/json' }),
        body: JSON.stringify({ title, content, source: 'custom_policy.txt' })
      });

      if (res.status === 401) {
        showToast('Admin Authentication required. Please configure your Admin API Key in Settings.', 'error');
        return;
      }

      if (res.ok) {
        const data = await res.json();
        showToast(data.message || `Clause "${title}" indexed into ChromaDB!`, 'success');
        await fetchKbChunksFromBackend();
        closeAddPolicyModal();
        e.target.reset();
        return;
      }
    } catch (err) {
      console.warn('Add policy API failed, falling back to local list:', err);
    }
  }

  const newChunk = {
    id: `chunk_${AppState.knowledgeChunks.length}`,
    title: title,
    content: content,
    tokens: Math.round(content.length / 4),
    source: 'custom_policy.txt'
  };

  AppState.knowledgeChunks.push(newChunk);
  closeAddPolicyModal();
  renderKbChunks();
  showToast(`Clause "${title}" vectorized and added!`, 'success');
  e.target.reset();
}

async function handleDeletePolicyClause(chunkId) {
  if (!confirm(`Are you sure you want to remove chunk ${chunkId} from the vector index?`)) {
    return;
  }

  if (AppState.isBackendOnline) {
    try {
      const res = await fetch(`${AppState.backendUrl}/api/kb/chunks/${chunkId}`, {
        method: 'DELETE',
        headers: getAuthHeaders()
      });

      if (res.status === 401) {
        showToast('Admin Authentication required to delete chunks. Set Admin API Key in Settings.', 'error');
        return;
      }

      if (res.ok) {
        showToast(`Chunk ${chunkId} removed from ChromaDB`, 'success');
        await fetchKbChunksFromBackend();
        return;
      }
    } catch (e) {
      console.warn('Delete API call error:', e);
    }
  }

  AppState.knowledgeChunks = AppState.knowledgeChunks.filter(c => c.id !== chunkId);
  renderKbChunks();
  showToast(`Chunk ${chunkId} removed`, 'info');
}

async function handleResetKb() {
  if (!confirm("Reset knowledge base back to default company policies?")) return;

  if (AppState.isBackendOnline) {
    try {
      const res = await fetch(`${AppState.backendUrl}/api/kb/reset`, {
        method: 'POST',
        headers: getAuthHeaders()
      });

      if (res.status === 401) {
        showToast('Admin Authentication required to reset database. Set Admin API Key in Settings.', 'error');
        return;
      }

      if (res.ok) {
        const data = await res.json();
        showToast(data.message, 'success');
        await fetchKbChunksFromBackend();
        return;
      }
    } catch (e) {
      console.warn('Reset KB API error:', e);
    }
  }
  showToast('Reset completed', 'info');
}

// ==============================================================================
// 5. ESCALATION & TICKETS MANAGEMENT
// ==============================================================================

async function fetchTicketsFromBackend(showNotification = false) {
  if (AppState.isBackendOnline) {
    try {
      const res = await fetch(`${AppState.backendUrl}/api/tickets`);
      if (res.ok) {
        const data = await res.json();
        AppState.tickets = data.tickets || [];
      }

      const statsRes = await fetch(`${AppState.backendUrl}/api/tickets/stats`);
      if (statsRes.ok) {
        const stats = await statsRes.json();
        const openEl = document.getElementById('ticket-kpi-open');
        const inProgEl = document.getElementById('ticket-kpi-in-progress');
        const resEl = document.getElementById('ticket-kpi-resolved');
        const rateEl = document.getElementById('ticket-kpi-rate');
        const badgeEl = document.getElementById('sidebar-ticket-count');

        if (openEl) openEl.textContent = stats.open_tickets;
        if (inProgEl) inProgEl.textContent = stats.in_progress_tickets;
        if (resEl) resEl.textContent = stats.resolved_tickets;
        if (rateEl) rateEl.textContent = `${stats.resolution_rate_percent}%`;
        if (badgeEl) badgeEl.textContent = stats.open_tickets;
      }

      if (showNotification) {
        showToast('Tickets inbox synchronized', 'success');
      }
    } catch (e) {
      console.warn('Failed to fetch tickets from API:', e);
    }
  }
  renderTicketsList();
}

function renderTicketsList() {
  const container = document.getElementById('tickets-list-container');
  if (!container) return;

  const filtered = AppState.tickets.filter(t => {
    if (AppState.activeTicketFilter === 'all') return true;
    return t.status.toLowerCase() === AppState.activeTicketFilter.toLowerCase();
  });

  if (filtered.length === 0) {
    container.innerHTML = `<div style="grid-column: 1/-1; text-align: center; color: var(--text-muted); padding: 3rem;">No tickets found matching "${AppState.activeTicketFilter}".</div>`;
    return;
  }

  container.innerHTML = filtered.map(t => {
    const priorityClass = (t.priority || 'medium').toLowerCase();
    const statusClass = (t.status || 'open').toLowerCase().replace(' ', '-');

    return `
      <div class="ticket-card" id="card-${t.id}">
        <div class="ticket-card-header">
          <span class="ticket-id-tag"><i class="fa-solid fa-ticket"></i> ${t.id}</span>
          <div style="display: flex; gap: 0.4rem; align-items: center;">
            <span class="priority-pill ${priorityClass}">${t.priority}</span>
            <span class="status-pill ${statusClass}">${t.status}</span>
          </div>
        </div>

        <h4 style="font-size: 1.05rem; line-height: 1.35;">${escapeHtml(t.subject)}</h4>
        
        <div style="font-size: 0.86rem; color: var(--text-muted); background: rgba(0,0,0,0.25); padding: 0.5rem 0.75rem; border-radius: 6px;">
          ${escapeHtml(t.query)}
        </div>

        <div class="ticket-meta-info">
          <div><i class="fa-solid fa-user" style="margin-right: 4px;"></i> <strong>${escapeHtml(t.customer_name)}</strong> &bull; <code>${escapeHtml(t.customer_email)}</code></div>
          <div><i class="fa-solid fa-user-shield" style="margin-right: 4px;"></i> Assigned: <strong>${escapeHtml(t.assigned_agent || 'Unassigned')}</strong> &bull; ${t.created_at}</div>
        </div>

        <div class="ticket-card-actions">
          ${t.status !== 'In Progress' && t.status !== 'Resolved' ? `
            <button type="button" class="btn btn-secondary btn-sm" onclick="handleUpdateTicketStatus('${t.id}', 'In Progress')">
              <i class="fa-solid fa-spinner"></i> Claim &amp; Work
            </button>
          ` : ''}

          ${t.status !== 'Resolved' ? `
            <button type="button" class="btn btn-primary btn-sm" onclick="handleUpdateTicketStatus('${t.id}', 'Resolved')">
              <i class="fa-solid fa-check"></i> Mark Resolved
            </button>
          ` : `
            <button type="button" class="btn btn-secondary btn-sm" onclick="handleUpdateTicketStatus('${t.id}', 'Open')">
              <i class="fa-solid fa-envelope-open"></i> Reopen
            </button>
          `}

          <button type="button" class="chunk-btn-delete" onclick="handleDeleteTicket('${t.id}')" title="Delete ticket" style="margin-left: auto;">
            <i class="fa-solid fa-trash"></i>
          </button>
        </div>
      </div>
    `;
  }).join('');
}

function filterTicketsList(filter) {
  AppState.activeTicketFilter = filter;
  ['all', 'open', 'progress', 'resolved'].forEach(tab => {
    const btn = document.getElementById(`tab-ticket-${tab}`);
    if (btn) btn.classList.remove('active');
  });

  const activeBtn = document.getElementById(`tab-ticket-${filter.toLowerCase().replace(' ', '')}`);
  if (activeBtn) activeBtn.classList.add('active');
  renderTicketsList();
}

function openCreateTicketModal(queryText = '') {
  const modal = document.getElementById('create-ticket-modal');
  const queryField = document.getElementById('ticket-details');
  const subjectField = document.getElementById('ticket-subject');

  if (queryField && queryText) {
    queryField.value = queryText;
  }
  if (subjectField && queryText) {
    subjectField.value = queryText.length > 50 ? queryText.substring(0, 50) + '...' : queryText;
  }
  if (modal) modal.classList.add('open');
}

function closeCreateTicketModal() {
  const modal = document.getElementById('create-ticket-modal');
  if (modal) modal.classList.remove('open');
}

async function handleCreateTicketSubmit(e) {
  e.preventDefault();
  const name = document.getElementById('ticket-customer-name').value.trim();
  const email = document.getElementById('ticket-customer-email').value.trim();
  const priority = document.getElementById('ticket-priority').value;
  const subject = document.getElementById('ticket-subject').value.trim();
  const details = document.getElementById('ticket-details').value.trim();

  if (!name || !email || !subject || !details) return;

  if (AppState.isBackendOnline) {
    try {
      const res = await fetch(`${AppState.backendUrl}/api/tickets`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          customer_name: name,
          customer_email: email,
          priority: priority,
          subject: subject,
          query: details,
          transcript_snippet: details.substring(0, 150)
        })
      });

      if (res.ok) {
        const data = await res.json();
        showToast(data.message || 'Escalation ticket created successfully!', 'success');
        closeCreateTicketModal();
        e.target.reset();
        await fetchTicketsFromBackend();
        switchAppView('tickets');
        return;
      }
    } catch (err) {
      console.warn('Ticket API failed, adding locally:', err);
    }
  }

  // Local fallback ticket
  const localTicket = {
    id: `TCK-${Math.floor(1000 + Math.random() * 9000)}`,
    customer_name: name,
    customer_email: email,
    subject: subject,
    query: details,
    priority: priority,
    status: 'Open',
    created_at: 'Just now',
    assigned_agent: 'Unassigned',
    transcript_snippet: details.substring(0, 120)
  };

  AppState.tickets.unshift(localTicket);
  closeCreateTicketModal();
  e.target.reset();
  renderTicketsList();
  showToast(`Ticket ${localTicket.id} created!`, 'success');
  switchAppView('tickets');
}

async function handleUpdateTicketStatus(ticketId, newStatus) {
  if (AppState.isBackendOnline) {
    try {
      const res = await fetch(`${AppState.backendUrl}/api/tickets/${ticketId}`, {
        method: 'PATCH',
        headers: getAuthHeaders({ 'Content-Type': 'application/json' }),
        body: JSON.stringify({ status: newStatus })
      });

      if (res.ok) {
        showToast(`Ticket ${ticketId} updated to ${newStatus}`, 'success');
        await fetchTicketsFromBackend();
        return;
      }
    } catch (e) {
      console.warn('Update ticket error:', e);
    }
  }

  const t = AppState.tickets.find(x => x.id === ticketId);
  if (t) {
    t.status = newStatus;
    renderTicketsList();
    showToast(`Ticket ${ticketId} updated to ${newStatus}`, 'info');
  }
}

async function handleDeleteTicket(ticketId) {
  if (!confirm(`Are you sure you want to delete ticket ${ticketId}?`)) return;

  if (AppState.isBackendOnline) {
    try {
      const res = await fetch(`${AppState.backendUrl}/api/tickets/${ticketId}`, {
        method: 'DELETE',
        headers: getAuthHeaders()
      });

      if (res.status === 401) {
        showToast('Admin Authentication required to delete tickets.', 'error');
        return;
      }

      if (res.ok) {
        showToast(`Ticket ${ticketId} deleted`, 'success');
        await fetchTicketsFromBackend();
        return;
      }
    } catch (e) {
      console.warn('Delete ticket error:', e);
    }
  }

  AppState.tickets = AppState.tickets.filter(x => x.id !== ticketId);
  renderTicketsList();
  showToast(`Ticket ${ticketId} removed`, 'info');
}

// 6. Deflection & Analytics Dashboard
async function fetchAnalyticsFromBackend(showNotification = false) {
  if (AppState.isBackendOnline) {
    try {
      const res = await fetch(`${AppState.backendUrl}/api/analytics`, {
        headers: getAuthHeaders()
      });
      if (res.ok) {
        const data = await res.json();
        
        const rateEl = document.getElementById('kpi-deflection-rate');
        if (rateEl && data.deflection_rate !== undefined) {
          rateEl.textContent = `${data.deflection_rate}%`;
        }
        const latEl = document.getElementById('kpi-avg-latency');
        if (latEl && data.avg_latency_s !== undefined) {
          latEl.textContent = `${data.avg_latency_s}s`;
        }
        const inqEl = document.getElementById('kpi-total-inquiries');
        if (inqEl && data.total_inquiries !== undefined) {
          inqEl.textContent = data.total_inquiries.toLocaleString();
        }

        const auditContainer = document.getElementById('audit-list-container');
        if (auditContainer && data.audit_logs && data.audit_logs.length > 0) {
          auditContainer.innerHTML = data.audit_logs.map(log => `
            <div class="audit-row">
              <div>
                <strong>&quot;${escapeHtml(log.query)}&quot;</strong>
                <div class="audit-subtext">Matched: ${escapeHtml(log.matched)} &bull; ${log.latency_ms || 240}ms &bull; ${log.timestamp || ''}</div>
              </div>
              <span class="badge ${log.status.includes('Deflected') ? 'badge-amber' : 'badge-emerald'} chart-badge">
                ${escapeHtml(log.status)}
              </span>
            </div>
          `).join('');
        }

        if (showNotification) {
          showToast('Analytics & audit telemetry updated', 'success');
        }
        return;
      }
    } catch (e) {
      console.warn('Analytics fetch error:', e);
    }
  }

  if (showNotification) {
    showToast('Audit stream refreshed', 'info');
  }
}

// 7. Pipeline Settings Management
function populateSettingsView() {
  const backendInput = document.getElementById('setting-backend-url');
  const adminKeyInput = document.getElementById('setting-admin-key');
  const guardrailInput = document.getElementById('setting-guardrail');
  const topkInput = document.getElementById('setting-topk');
  const modelInput = document.getElementById('setting-model');

  if (backendInput) backendInput.value = AppState.backendUrl;
  if (adminKeyInput) adminKeyInput.value = AppState.adminApiKey;
  if (guardrailInput) {
    guardrailInput.value = AppState.guardrailThreshold;
    const disp = document.getElementById('val-guardrail-threshold');
    if (disp) disp.textContent = AppState.guardrailThreshold.toFixed(2);
  }
  if (topkInput) topkInput.value = AppState.topK;
  if (modelInput) modelInput.value = AppState.model;
}

function testBackendConnection() {
  const input = document.getElementById('setting-backend-url');
  if (input) {
    AppState.backendUrl = input.value.trim();
  }
  showToast('Testing connection to ' + AppState.backendUrl + '...', 'info');
  checkBackendHealth().then(online => {
    if (online) {
      showToast('Successfully connected to FastAPI Backend!', 'success');
      fetchKbChunksFromBackend();
      fetchTicketsFromBackend();
    } else {
      showToast('Could not reach backend. Running in offline simulation mode.', 'error');
    }
  });
}

async function savePipelineSettings() {
  const backendInput = document.getElementById('setting-backend-url');
  const adminKeyInput = document.getElementById('setting-admin-key');
  const guardrailInput = document.getElementById('setting-guardrail');
  const topkInput = document.getElementById('setting-topk');
  const modelInput = document.getElementById('setting-model');
  const promptInput = document.getElementById('setting-system-prompt');

  if (backendInput) {
    AppState.backendUrl = backendInput.value.trim();
    localStorage.setItem('omni_backend_url', AppState.backendUrl);
  }
  if (adminKeyInput) {
    AppState.adminApiKey = adminKeyInput.value.trim();
    localStorage.setItem('omni_admin_key', AppState.adminApiKey);
  }
  if (guardrailInput) {
    AppState.guardrailThreshold = parseFloat(guardrailInput.value);
    localStorage.setItem('omni_threshold', AppState.guardrailThreshold);
    const thresholdDisplay = document.getElementById('info-guardrail-threshold');
    if (thresholdDisplay) thresholdDisplay.textContent = AppState.guardrailThreshold.toFixed(2);
  }
  if (topkInput) {
    AppState.topK = parseInt(topkInput.value, 10);
    localStorage.setItem('omni_top_k', AppState.topK);
  }
  if (modelInput) {
    AppState.model = modelInput.value;
    localStorage.setItem('omni_model', AppState.model);
    const modelBadge = document.getElementById('model-indicator-badge');
    if (modelBadge) {
      modelBadge.innerHTML = `<i class="fa-solid fa-microchip"></i> ${AppState.model}`;
    }
  }

  // Push updates to backend if online
  if (AppState.isBackendOnline) {
    try {
      const payload = {
        guardrail_threshold: AppState.guardrailThreshold,
        top_k_chunks: AppState.topK,
        generation_model: AppState.model,
        system_instruction: promptInput ? promptInput.value : undefined
      };
      const res = await fetch(`${AppState.backendUrl}/api/settings`, {
        method: 'POST',
        headers: getAuthHeaders({ 'Content-Type': 'application/json' }),
        body: JSON.stringify(payload)
      });

      if (res.status === 401) {
        showToast('Local settings saved, but server rejected update: Invalid Admin API Key.', 'warning');
        return;
      }
    } catch (e) {
      console.warn('Failed to sync settings to API:', e);
    }
  }

  showToast('Pipeline settings saved successfully!', 'success');
}

// 8. TTS, Copy, and History Operations
function speakMessageText(btn) {
  const row = btn.closest('.chat-msg-row');
  if (!row) return;
  const bubble = row.querySelector('.msg-bubble-content');
  if (!bubble) return;

  const text = bubble.innerText.replace(/\[Clause \d+\][\s\S]*/g, '').trim();
  if (!text) return;

  if ('speechSynthesis' in window) {
    window.speechSynthesis.cancel();
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.rate = 1.05;
    utterance.pitch = 1.0;
    window.speechSynthesis.speak(utterance);
    showToast('Reading response aloud...', 'info');
  } else {
    showToast('Speech synthesis not supported in this browser.', 'error');
  }
}

function copyMessageText(btn) {
  const row = btn.closest('.chat-msg-row');
  if (!row) return;
  const bubble = row.querySelector('.msg-bubble-content');
  if (!bubble) return;

  const text = bubble.innerText.trim();
  navigator.clipboard.writeText(text).then(() => {
    showToast('Copied to clipboard!', 'success');
  }).catch(() => {
    showToast('Failed to copy', 'error');
  });
}

function rateMessage(btn, type) {
  showToast(type === 'helpful' ? 'Marked as helpful 👍' : 'Feedback recorded 👎', 'success');
}

function clearChatFeed() {
  const chatFeed = document.getElementById('chat-feed');
  if (!chatFeed) return;
  chatFeed.innerHTML = `
    <div class="chat-msg-row assistant-msg">
      <div class="avatar-badge avatar-assistant">
        <i class="fa-solid fa-robot"></i>
      </div>
      <div style="flex: 1;">
        <div class="msg-bubble-content">
          Session cleared. What would you like to know about our verified store policies?
        </div>
      </div>
    </div>
  `;
  AppState.messages = [];
  showToast('Chat history cleared', 'info');
}

function exportChatTranscript() {
  const dataStr = "data:text/json;charset=utf-8," + encodeURIComponent(JSON.stringify(AppState.messages, null, 2));
  const downloadAnchor = document.createElement('a');
  downloadAnchor.setAttribute("href", dataStr);
  downloadAnchor.setAttribute("download", `OmniDesk_Support_Transcript_${Date.now()}.json`);
  document.body.appendChild(downloadAnchor);
  downloadAnchor.click();
  downloadAnchor.remove();
  showToast('Transcript exported as JSON', 'success');
}

// Utility formatting
function escapeHtml(str) {
  if (!str) return '';
  return str.replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;');
}

function formatMarkdownText(text) {
  if (!text) return '';
  let html = escapeHtml(text);
  html = html.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
  html = html.replace(/\*(.*?)\*/g, '<em>$1</em>');
  html = html.replace(/^[-*]\s+(.*)$/gm, '<li>$1</li>');
  html = html.replace(/(<li>.*<\/li>)/s, '<ul>$1</ul>');
  html = html.replace(/\n\n/g, '<br><br>').replace(/\n/g, '<br>');
  return html;
}

// Initialize on DOM Ready
document.addEventListener('DOMContentLoaded', () => {
  populateSettingsView();
  checkBackendHealth().then(() => {
    fetchKbChunksFromBackend();
    fetchTicketsFromBackend();
  });
  renderKbChunks();
  renderTicketsList();
  setInterval(checkBackendHealth, 15000);
});
