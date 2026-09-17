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
  openCopilotDrawers: new Set(),
  selectedLanguage: localStorage.getItem('omni_language') || 'Auto Detect',
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

  let appliedLanguage = AppState.selectedLanguage || 'English';

  if (AppState.isBackendOnline) {
    try {
      const response = await fetch(`${AppState.backendUrl}/ask/stream`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: query, language: AppState.selectedLanguage })
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
                if (data.language) appliedLanguage = data.language;
              } else if (eventType === 'token') {
                accumulatedText += data.token;
                updateStreamingMessage(bubbleEl, accumulatedText);
                chatFeed.scrollTop = chatFeed.scrollHeight;
              } else if (eventType === 'done') {
                latencyMs = data.latency_ms || 0;
                modelUsed = data.model || modelUsed;
                isDeflected = !!data.deflected;
                if (data.language) appliedLanguage = data.language;
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

  // Finalize assistant message with multi-language and CSAT
  finalizeAssistantMessage(bubbleEl, actionsEl, accumulatedText, retrievedSources, latencyMs, isDeflected, query, appliedLanguage);
  AppState.messages.push({
    role: 'assistant',
    content: accumulatedText,
    sources: retrievedSources,
    latency: latencyMs,
    language: appliedLanguage
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
      </div>
    </div>
  `;
  container.appendChild(row);
}

function updateStreamingMessage(bubbleEl, text) {
  if (!bubbleEl) return;
  bubbleEl.innerHTML = formatMarkdownText(text) + '<span class="typing-cursor"></span>';
}

function finalizeAssistantMessage(bubbleEl, actionsEl, text, sources, latencyMs, isDeflected, originalQuery = '', appliedLanguage = 'English') {
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

  let badgeRowHtml = '';
  const badges = [];
  if (appliedLanguage && appliedLanguage !== 'English') {
    badges.push(`<span class="lang-badge"><i class="fa-solid fa-language"></i> ${appliedLanguage}</span>`);
  }
  if (latencyMs > 0) {
    badges.push(`<span class="latency-pill ${isDeflected ? 'deflected' : ''}"><i class="fa-solid fa-bolt"></i> ${latencyMs}ms</span>`);
  }
  if (badges.length > 0) {
    badgeRowHtml = `<div style="display: flex; gap: 0.35rem; align-items: center;">${badges.join('')}</div>`;
  }

  // CSAT rating container
  const safeOriginalQ = escapeHtml(originalQuery || text).replace(/'/g, "\\'");
  const csatHtml = `
    <div class="csat-container">
      <span>Was this answer helpful?</span>
      <div class="csat-btn-group">
        <button type="button" class="csat-btn thumb-up" onclick="handleRateAssistantResponse(this, true, 5, '${safeOriginalQ}')" title="Helpful answer">
          <i class="fa-solid fa-thumbs-up"></i> Helpful
        </button>
        <button type="button" class="csat-btn thumb-down" onclick="handleRateAssistantResponse(this, false, 1, '${safeOriginalQ}')" title="Needs improvement">
          <i class="fa-solid fa-thumbs-down"></i> Needs Work
        </button>
      </div>
    </div>
  `;

  bubbleEl.innerHTML = `
    <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 4px; gap: 0.5rem;">
      <div style="flex: 1;">${formatMarkdownText(text)}</div>
      ${badgeRowHtml}
    </div>
    ${escalationButtonHtml}
    ${sourcesHtml}
    ${csatHtml}
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

function exportKnowledgeBaseBackup() {
  const dataStr = "data:text/json;charset=utf-8," + encodeURIComponent(JSON.stringify({
    export_date: new Date().toISOString(),
    total_chunks: AppState.knowledgeChunks.length,
    chunks: AppState.knowledgeChunks
  }, null, 2));
  const downloadAnchor = document.createElement('a');
  downloadAnchor.setAttribute("href", dataStr);
  downloadAnchor.setAttribute("download", "omnidesk_kb_backup.json");
  document.body.appendChild(downloadAnchor);
  downloadAnchor.click();
  downloadAnchor.remove();
  showToast('Knowledge base backup downloaded!', 'success');
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

function getCustomerInitials(name) {
  if (!name) return 'CU';
  const parts = name.trim().split(/\s+/);
  if (parts.length >= 2) {
    return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
  }
  return name.substring(0, 2).toUpperCase();
}

function renderTicketsList(searchQuery = '') {
  const container = document.getElementById('tickets-list-container');
  if (!container) return;

  const searchInput = document.getElementById('tickets-search-input');
  const term = (searchQuery || (searchInput ? searchInput.value : '')).toLowerCase().trim();

  const filtered = AppState.tickets.filter(t => {
    // Status tab filter
    const matchesStatus = AppState.activeTicketFilter === 'all' || 
      t.status.toLowerCase() === AppState.activeTicketFilter.toLowerCase();
    
    if (!matchesStatus) return false;

    // Search query filter
    if (!term) return true;

    const custId = (t.customer_id || '').toLowerCase();
    const custName = (t.customer_name || '').toLowerCase();
    const custEmail = (t.customer_email || '').toLowerCase();
    const tckId = (t.id || '').toLowerCase();
    const subject = (t.subject || '').toLowerCase();
    const query = (t.query || '').toLowerCase();
    const agent = (t.assigned_agent || '').toLowerCase();

    return custId.includes(term) || custName.includes(term) || custEmail.includes(term) ||
           tckId.includes(term) || subject.includes(term) || query.includes(term) || agent.includes(term);
  });

  if (filtered.length === 0) {
    container.innerHTML = `<div style="grid-column: 1/-1; text-align: center; color: var(--text-muted); padding: 3rem;">No tickets found matching your criteria.</div>`;
    return;
  }

  const agentsList = [
    { name: 'Unassigned', label: 'Unassigned' },
    { name: 'Alex Morgan', label: 'Alex Morgan (Tier 2 Lead)' },
    { name: 'Sarah Chen', label: 'Sarah Chen (Logistics)' },
    { name: 'David Miller', label: 'David Miller (Billing)' },
    { name: 'Emma Watson', label: 'Emma Watson (Warranty)' }
  ];

  container.innerHTML = filtered.map(t => {
    const priorityClass = (t.priority || 'medium').toLowerCase();
    const statusClass = (t.status || 'open').toLowerCase().replace(' ', '-');
    const initials = getCustomerInitials(t.customer_name);
    const custId = t.customer_id || 'CUST-' + t.id.replace('TCK-', '');
    const tier = t.customer_tier || 'Standard Retail';
    const tierClass = tier.toLowerCase().includes('vip') ? 'vip' : (tier.toLowerCase().includes('pro') ? 'pro' : 'standard');
    
    const intent = t.intent || 'General Inquiry';
    const sentiment = t.sentiment || 'Standard';
    const sentimentClass = sentiment.toLowerCase().includes('urgent') ? 'urgent' : (sentiment.toLowerCase().includes('vip') ? 'vip' : '');

    const agentOptions = agentsList.map(a => `
      <option value="${a.name}" ${t.assigned_agent === a.name ? 'selected' : ''}>${a.label}</option>
    `).join('');

    return `
      <div class="ticket-card" id="card-${t.id}">
        <!-- Customer Identity Header -->
        <div class="ticket-customer-header">
          <div class="customer-avatar-initials" title="Customer: ${escapeHtml(t.customer_name)}">
            ${initials}
          </div>
          <div class="customer-info-col">
            <div class="customer-name-row">
              <span class="customer-name-text">${escapeHtml(t.customer_name)}</span>
              <span class="customer-id-pill"><i class="fa-solid fa-id-badge"></i> ${custId}</span>
              <span class="customer-tier-badge ${tierClass}">${tier}</span>
            </div>
            <div style="font-size: 0.78rem; color: var(--text-muted); margin-top: 2px;">
              <a href="mailto:${escapeHtml(t.customer_email)}" style="color: var(--secondary-light); text-decoration: none;">
                <i class="fa-regular fa-envelope"></i> ${escapeHtml(t.customer_email)}
              </a>
            </div>
          </div>
        </div>

        <!-- Ticket Card Meta Header -->
        <div class="ticket-card-header">
          <span class="ticket-id-tag"><i class="fa-solid fa-ticket"></i> ${t.id}</span>
          <div style="display: flex; gap: 0.4rem; align-items: center;">
            <span class="priority-pill ${priorityClass}">${t.priority}</span>
            <span class="status-pill ${statusClass}">${t.status}</span>
          </div>
        </div>

        <div style="display: flex; gap: 0.4rem; align-items: center; flex-wrap: wrap; margin-top: 2px;">
          <span class="intent-pill"><i class="fa-solid fa-tag"></i> ${escapeHtml(intent)}</span>
          <span class="sentiment-pill ${sentimentClass}">${escapeHtml(sentiment)}</span>
          <span class="sla-badge ${t.sla_details ? t.sla_details.badge_status : 'normal'}">
            <i class="fa-solid fa-stopwatch"></i> ${escapeHtml(t.sla_details ? t.sla_details.label : 'SLA Active')}
          </span>
        </div>

        <h4 style="font-size: 1.02rem; line-height: 1.35; margin: 0.2rem 0;">${escapeHtml(t.subject)}</h4>
        
        <div style="font-size: 0.86rem; color: var(--text-muted); background: rgba(0,0,0,0.25); padding: 0.5rem 0.75rem; border-radius: 6px; line-height: 1.45;">
          ${escapeHtml(t.query)}
        </div>

        <div class="ticket-meta-info">
          <div class="ticket-agent-assign-row">
            <label for="agent-select-${t.id}" style="color: var(--text-muted); font-size: 0.78rem; display: flex; align-items: center; gap: 4px;">
              <i class="fa-solid fa-user-shield"></i> Fast Route Agent:
            </label>
            <select id="agent-select-${t.id}" class="ticket-agent-select" onchange="handleAssignTicketAgent('${t.id}', this.value)">
              ${agentOptions}
            </select>
          </div>
          <div style="font-size: 0.76rem; color: var(--text-dim); display: flex; justify-content: space-between;">
            <span><i class="fa-regular fa-clock"></i> Created: ${t.created_at}</span>
            <span><i class="fa-solid fa-bolt"></i> Target: ${t.sla_details ? Math.round(t.sla_details.sla_target_minutes / 60) + 'h window' : '< 2h'}</span>
          </div>
        </div>

        <div class="ticket-card-actions">
          <button type="button" class="btn btn-copilot btn-sm" onclick="toggleCopilotDrawer('${t.id}')">
            <i class="fa-solid fa-wand-magic-sparkles"></i> AI Copilot
          </button>

          ${t.status !== 'In Progress' && t.status !== 'Resolved' ? `
            <button type="button" class="btn btn-secondary btn-sm" onclick="handleClaimTicket('${t.id}')">
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

        <!-- AI Copilot & Conversation Thread Drawer -->
        <div id="copilot-drawer-${t.id}" class="ticket-copilot-drawer" style="display: ${AppState.openCopilotDrawers.has(t.id) ? 'flex' : 'none'};">
          <div class="copilot-section-header">
            <span><i class="fa-solid fa-robot"></i> OmniDesk AI Grounded Draft Assistant</span>
            <button type="button" class="btn btn-secondary btn-sm" onclick="handleGenerateCopilotDraft('${t.id}')">
              <i class="fa-solid fa-sparkles"></i> 💡 Generate Draft
            </button>
          </div>

          <!-- Quick Macros Bar -->
          <div class="macro-pills-row">
            <span style="font-size: 0.76rem; color: var(--text-muted); font-weight: 600;"><i class="fa-solid fa-bolt"></i> Macros:</span>
            <button type="button" class="macro-pill-btn" onclick="handleApplyMacroDraft('${t.id}', 'macro_return_rma')" title="Apply 30-Day RMA Return template">
              📦 30-Day RMA
            </button>
            <button type="button" class="macro-pill-btn" onclick="handleApplyMacroDraft('${t.id}', 'macro_warranty_claim')" title="Apply 1-Year Warranty replacement intake">
              🛡️ 1-Yr Warranty
            </button>
            <button type="button" class="macro-pill-btn" onclick="handleApplyMacroDraft('${t.id}', 'macro_price_match')" title="Apply 14-Day Price Match adjustment">
              💳 Price Match
            </button>
            <button type="button" class="macro-pill-btn" onclick="handleApplyMacroDraft('${t.id}', 'macro_intl_ddp')" title="Apply DHL International DDP details">
              ✈️ DHL DDP
            </button>
          </div>

          <textarea id="copilot-draft-${t.id}" class="copilot-draft-textarea" rows="4" placeholder="Click 'Generate Draft' or select a Macro above to auto-fill verified policy resolution..."></textarea>
          <div class="copilot-actions-row">
            <button type="button" class="btn btn-primary btn-sm" onclick="handleSendCopilotDraft('${t.id}')">
              <i class="fa-solid fa-paper-plane"></i> Send Reply to Customer
            </button>
            <button type="button" class="btn btn-secondary btn-sm" onclick="handleCopyCopilotDraft('${t.id}')">
              <i class="fa-regular fa-copy"></i> Copy Draft
            </button>
          </div>

          <!-- Thread & Staff Notes Box -->
          <div class="ticket-thread-box">
            <div class="thread-title">
              <i class="fa-solid fa-comments"></i> Conversation Thread &amp; Audit Trail (${(t.messages || []).length})
            </div>
            <div class="thread-messages-list">
              ${(t.messages && t.messages.length > 0 ? t.messages : [
                { id: 'msg_1', sender: t.customer_name, text: t.query, is_internal_note: false, timestamp: t.created_at }
              ]).map(m => {
                const isInternal = m.is_internal_note;
                const bubbleClass = isInternal ? 'internal' : (m.sender === t.customer_name ? 'customer' : 'agent');
                const roleBadge = isInternal 
                  ? '<span style="color: #f59e0b;"><i class="fa-solid fa-lock"></i> Staff Note</span>' 
                  : (bubbleClass === 'agent' ? '<span style="color: #818cf8;"><i class="fa-solid fa-headset"></i> Agent</span>' : '<span style="color: #38bdf8;"><i class="fa-solid fa-user"></i> Customer</span>');
                return `
                  <div class="thread-msg-bubble ${bubbleClass}">
                    <div class="thread-msg-meta">
                      <span><strong>${escapeHtml(m.sender)}</strong> (${roleBadge})</span>
                      <span>${escapeHtml(m.timestamp || '')}</span>
                    </div>
                    <div>${escapeHtml(m.text)}</div>
                  </div>
                `;
              }).join('')}
            </div>
            <div class="thread-input-box">
              <textarea id="thread-input-${t.id}" class="thread-input-textarea" rows="2" placeholder="Write message to customer or staff note..."></textarea>
              <div class="thread-controls-row">
                <label class="thread-internal-toggle">
                  <input type="checkbox" id="thread-internal-${t.id}">
                  <span style="color: #f59e0b;"><i class="fa-solid fa-lock"></i> Internal Staff Note</span>
                </label>
                <button type="button" class="btn btn-secondary btn-sm" onclick="handleSendThreadMessage('${t.id}')">
                  <i class="fa-solid fa-reply"></i> Post Message
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    `;
  }).join('');
}

function toggleCopilotDrawer(ticketId) {
  if (AppState.openCopilotDrawers.has(ticketId)) {
    AppState.openCopilotDrawers.delete(ticketId);
  } else {
    AppState.openCopilotDrawers.add(ticketId);
  }
  const drawer = document.getElementById(`copilot-drawer-${ticketId}`);
  if (drawer) {
    drawer.style.display = AppState.openCopilotDrawers.has(ticketId) ? 'flex' : 'none';
  }
}

async function handleGenerateCopilotDraft(ticketId) {
  const draftEl = document.getElementById(`copilot-draft-${ticketId}`);
  if (draftEl) {
    draftEl.value = 'Synthesizing verified policy grounding and drafting response...';
  }
  
  if (AppState.isBackendOnline) {
    try {
      const res = await fetch(`${AppState.backendUrl}/api/tickets/${ticketId}/suggest-reply`, {
        method: 'POST',
        headers: getAuthHeaders()
      });
      if (res.ok) {
        const data = await res.json();
        if (draftEl) draftEl.value = data.suggested_reply || '';
        showToast(`💡 AI Grounded Draft generated (${data.latency_ms || 120}ms)`, 'success');
        return;
      }
    } catch (e) {
      console.warn('Copilot draft API failed:', e);
    }
  }
  
  // Local fallback draft generator
  const t = AppState.tickets.find(x => x.id === ticketId);
  if (t && draftEl) {
    const first = t.customer_name ? t.customer_name.split(' ')[0] : 'there';
    draftEl.value = `Hi ${first},\n\nThank you for contacting OmniDesk Support!\n\nRegarding your inquiry:\n"${t.query}"\n\nBased on our verified store policies, our team has reviewed your case and can confirm that all claims and requests are processed within our official 30-day / 1-year coverage guidelines.\n\nPlease let us know if we can assist you with any additional details.\n\nWarm regards,\nThe OmniDesk Support Team`;
    showToast('💡 AI Grounded Draft generated (Local fallback)', 'info');
  }
}

async function handleSendCopilotDraft(ticketId) {
  const draftEl = document.getElementById(`copilot-draft-${ticketId}`);
  const text = draftEl ? draftEl.value.trim() : '';
  if (!text) {
    showToast('Please generate or type a reply before sending.', 'warning');
    return;
  }
  
  await submitTicketMessage(ticketId, 'Alex Morgan (Support Agent)', text, false);
  if (draftEl) draftEl.value = '';
  showToast('Reply sent to customer & ticket marked In Progress!', 'success');
}

function handleLanguageChange(selectedLang) {
  AppState.selectedLanguage = selectedLang;
  localStorage.setItem('omni_language', selectedLang);
  showToast(`Language set to ${selectedLang}`, 'info');
}

async function handleRateAssistantResponse(btnEl, isPositive, rating, queryText = '') {
  const container = btnEl.closest('.csat-container');
  if (container) {
    const btns = container.querySelectorAll('.csat-btn');
    btns.forEach(b => b.classList.remove('active'));
    btnEl.classList.add('active');
  }

  const payload = {
    query: queryText,
    rating: rating,
    is_positive: isPositive,
    language: AppState.selectedLanguage
  };

  if (AppState.isBackendOnline) {
    try {
      await fetch(`${AppState.backendUrl}/api/feedback`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
    } catch (e) {
      console.warn('Feedback sync error:', e);
    }
  }
  showToast(isPositive ? '⭐ Thank you! Positive rating recorded.' : '📝 Feedback logged for quality review.', 'success');
}

function handleApplyMacroDraft(ticketId, macroId) {
  const t = AppState.tickets.find(x => x.id === ticketId);
  const custName = t ? t.customer_name : 'Valued Customer';
  const agent = t && t.assigned_agent !== 'Unassigned' ? t.assigned_agent : 'OmniDesk Support';
  
  const macroTemplates = {
    'macro_return_rma': `Hi ${custName},\n\nThank you for contacting OmniDesk Support. We have authorized your return request for Ticket #${ticketId} under our 30-Day Policy.\n\nNext Steps:\n1. Affix the prepaid return shipping label to the original packaging.\n2. Drop off at any authorized courier depot within 14 days.\n3. Your full refund will process within 3-5 business days upon arrival.\n\nWarm regards,\n${agent} — OmniDesk Support`,
    'macro_warranty_claim': `Hi ${custName},\n\nWe have received your warranty inquiry for Ticket #${ticketId}. To process your 1-Year Limited Manufacturer Warranty replacement:\n\n1. Reply with your hardware serial number (on barcode label).\n2. Attach 1-2 clear photos/video of the issue.\n\nOnce received, our warranty desk will expedite your replacement dispatch.\n\nBest regards,\n${agent} — Warranty Desk`,
    'macro_price_match': `Hi ${custName},\n\nGreat news! We have verified the promotional pricing under our 14-Day Price Match Guarantee for Ticket #${ticketId}.\n\nA price adjustment credit has been applied to your original payment method and will reflect on your statement in 2-3 business days.\n\nThank you for choosing OmniDesk,\n${agent}`,
    'macro_intl_ddp': `Hi ${custName},\n\nRegarding your international delivery inquiry for Ticket #${ticketId}:\n\nAll international shipments are dispatched via DHL Express under Delivered Duty Paid (DDP) terms. All customs duties, VAT, and brokerage fees were pre-cleared at checkout. No additional fees will be requested upon arrival.\n\nTracking updates are active in your account dashboard.\n\nSafe travels & regards,\n${agent}`
  };

  const template = macroTemplates[macroId];
  if (template) {
    const draftEl = document.getElementById(`copilot-draft-${ticketId}`);
    if (draftEl) {
      draftEl.value = template;
      showToast('⚡ Macro template applied to draft area!', 'success');
    }
  }
}

function handleCopyCopilotDraft(ticketId) {
  const draftEl = document.getElementById(`copilot-draft-${ticketId}`);
  if (draftEl && draftEl.value) {
    navigator.clipboard.writeText(draftEl.value).then(() => {
      showToast('Draft copied to clipboard!', 'success');
    }).catch(() => {
      draftEl.select();
      showToast('Draft text selected', 'info');
    });
  }
}

async function handleSendThreadMessage(ticketId) {
  const inputEl = document.getElementById(`thread-input-${ticketId}`);
  const isInternalEl = document.getElementById(`thread-internal-${ticketId}`);
  const text = inputEl ? inputEl.value.trim() : '';
  const isInternal = isInternalEl ? isInternalEl.checked : false;
  
  if (!text) {
    showToast('Message text cannot be empty.', 'warning');
    return;
  }
  
  await submitTicketMessage(ticketId, isInternal ? 'Staff Note' : 'Support Specialist', text, isInternal);
  if (inputEl) inputEl.value = '';
  showToast(isInternal ? 'Internal staff note logged' : 'Message posted to ticket thread', 'success');
}

async function submitTicketMessage(ticketId, sender, text, isInternal) {
  const payload = {
    sender: sender,
    text: text,
    is_internal_note: isInternal
  };
  
  if (AppState.isBackendOnline) {
    try {
      const res = await fetch(`${AppState.backendUrl}/api/tickets/${ticketId}/messages`, {
        method: 'POST',
        headers: getAuthHeaders({ 'Content-Type': 'application/json' }),
        body: JSON.stringify(payload)
      });
      if (res.ok) {
        await fetchTicketsFromBackend();
        return;
      }
    } catch (e) {
      console.warn('Post message API error:', e);
    }
  }
  
  // Local fallback
  const t = AppState.tickets.find(x => x.id === ticketId);
  if (t) {
    if (!t.messages) t.messages = [];
    t.messages.push({
      id: `msg_${t.messages.length + 1}`,
      sender: sender,
      text: text,
      is_internal_note: isInternal,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    });
    if (!isInternal && t.status === 'Open') {
      t.status = 'In Progress';
    }
    renderTicketsList();
  }
}

function handleSearchTickets() {
  const input = document.getElementById('tickets-search-input');
  renderTicketsList(input ? input.value : '');
}

async function handleClaimTicket(ticketId) {
  // Claim assigns Alex Morgan (Tier 2 Lead) and sets status to In Progress
  await handleAssignTicketAgent(ticketId, 'Alex Morgan', 'In Progress');
}

async function handleAssignTicketAgent(ticketId, agentName, targetStatus = null) {
  const payload = {
    assigned_agent: agentName
  };
  if (targetStatus) {
    payload.status = targetStatus;
  } else if (agentName !== 'Unassigned') {
    // If transitioning from unassigned to a specific agent, automatically mark In Progress
    const curr = AppState.tickets.find(x => x.id === ticketId);
    if (curr && curr.status === 'Open') {
      payload.status = 'In Progress';
    }
  }

  if (AppState.isBackendOnline) {
    try {
      const res = await fetch(`${AppState.backendUrl}/api/tickets/${ticketId}`, {
        method: 'PATCH',
        headers: getAuthHeaders({ 'Content-Type': 'application/json' }),
        body: JSON.stringify(payload)
      });

      if (res.ok) {
        showToast(`Ticket ${ticketId} assigned to ${agentName}`, 'success');
        await fetchTicketsFromBackend();
        return;
      }
    } catch (e) {
      console.warn('Assign agent error:', e);
    }
  }

  const t = AppState.tickets.find(x => x.id === ticketId);
  if (t) {
    t.assigned_agent = agentName;
    if (payload.status) t.status = payload.status;
    renderTicketsList();
    showToast(`Ticket ${ticketId} assigned to ${agentName}`, 'info');
  }
}

function filterTicketsList(filter = null) {
  if (filter) {
    AppState.activeTicketFilter = filter;
    ['all', 'open', 'progress', 'resolved'].forEach(tab => {
      const btn = document.getElementById(`tab-ticket-${tab}`);
      if (btn) btn.classList.remove('active');
    });

    const activeBtn = document.getElementById(`tab-ticket-${filter.toLowerCase().replace(' ', '')}`);
    if (activeBtn) activeBtn.classList.add('active');
  }
  renderTicketsList();
}

function exportTicketsData(format = 'csv') {
  if (AppState.isBackendOnline) {
    const url = `${AppState.backendUrl}/api/tickets/export?format=${format}`;
    const downloadAnchor = document.createElement('a');
    downloadAnchor.setAttribute("href", url);
    downloadAnchor.setAttribute("download", `omnidesk_tickets_export.${format}`);
    document.body.appendChild(downloadAnchor);
    downloadAnchor.click();
    downloadAnchor.remove();
    showToast(`Exporting tickets as ${format.toUpperCase()}...`, 'success');
    return;
  }

  // Local fallback export
  if (format === 'json') {
    const dataStr = "data:text/json;charset=utf-8," + encodeURIComponent(JSON.stringify(AppState.tickets, null, 2));
    const a = document.createElement('a');
    a.setAttribute("href", dataStr);
    a.setAttribute("download", "omnidesk_tickets_export.json");
    document.body.appendChild(a);
    a.click();
    a.remove();
  } else {
    let csv = "Ticket ID,Customer ID,Customer Name,Customer Email,Customer Tier,Priority,Status,Intent,Sentiment,Assigned Agent,Created At,Subject,Query Context\n";
    AppState.tickets.forEach(t => {
      csv += `"${t.id}","${t.customer_id || ''}","${t.customer_name || ''}","${t.customer_email || ''}","${t.customer_tier || ''}","${t.priority || ''}","${t.status || ''}","${t.intent || 'General Inquiry'}","${t.sentiment || 'Standard'}","${t.assigned_agent || 'Unassigned'}","${t.created_at || ''}","${(t.subject || '').replace(/"/g, '""')}","${(t.query || '').replace(/"/g, '""')}"\n`;
    });
    const dataStr = "data:text/csv;charset=utf-8," + encodeURIComponent(csv);
    const a = document.createElement('a');
    a.setAttribute("href", dataStr);
    a.setAttribute("download", "omnidesk_tickets_export.csv");
    document.body.appendChild(a);
    a.click();
    a.remove();
  }
  showToast(`Exported ${AppState.tickets.length} tickets as ${format.toUpperCase()}!`, 'success');
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

  const custId = `CUST-${Math.floor(1000 + Math.random() * 9000)}`;
  const tier = priority === 'Urgent' ? 'VIP Enterprise' : (priority === 'High' ? 'Pro Business' : 'Standard Retail');

  if (AppState.isBackendOnline) {
    try {
      const res = await fetch(`${AppState.backendUrl}/api/tickets`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          customer_id: custId,
          customer_name: name,
          customer_email: email,
          customer_tier: tier,
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
    customer_id: custId,
    customer_name: name,
    customer_email: email,
    customer_tier: tier,
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

// Phase 7: Synthetic Benchmark Runner
async function handleRunSyntheticBenchmark() {
  const btn = document.getElementById('btn-run-benchmark');
  const resultsContainer = document.getElementById('bench-results-container');
  const tbody = document.getElementById('bench-results-tbody');
  
  if (btn) {
    btn.disabled = true;
    btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Executing Benchmark...';
  }
  showToast('Running autonomous synthetic benchmark battery (8 scenarios)...', 'info');

  try {
    const res = await fetch(`${AppState.backendUrl}/api/benchmark/simulate`, {
      method: 'POST',
      headers: getAuthHeaders(),
      body: JSON.stringify({ num_queries: 8 })
    });

    if (res.ok) {
      const data = await res.json();
      
      // Update KPI metrics
      const qpsEl = document.getElementById('bench-qps');
      const p50El = document.getElementById('bench-p50');
      const precEl = document.getElementById('bench-precision');
      const intentEl = document.getElementById('bench-intent-acc');
      
      if (qpsEl) qpsEl.textContent = `${data.qps} QPS`;
      if (p50El) p50El.textContent = `${data.latency_p50_ms}ms`;
      if (precEl) precEl.textContent = `${data.guardrail_accuracy_percent}%`;
      if (intentEl) intentEl.textContent = `${data.intent_accuracy_percent}%`;

      // Render table rows
      if (tbody && data.detailed_results) {
        tbody.innerHTML = data.detailed_results.map(r => `
          <tr>
            <td style="font-weight: 500;">${escapeHtml(r.query)}</td>
            <td><span class="lang-badge">🌐 ${escapeHtml(r.language)}</span></td>
            <td><span class="intent-pill">${escapeHtml(r.intent)}</span></td>
            <td>⚡ ${r.latency_ms}ms</td>
            <td>${r.deflected ? '<span class="badge badge-amber">Deflected</span>' : '<span class="badge badge-emerald">Grounded</span>'}</td>
            <td>${r.deflection_accurate ? '✅ Accurate' : '⚠️ Review'}</td>
          </tr>
        `).join('');
      }

      if (resultsContainer) {
        resultsContainer.style.display = 'block';
      }
      showToast(`Benchmark completed! ${data.qps} QPS | P50: ${data.latency_p50_ms}ms | Precision: ${data.guardrail_accuracy_percent}%`, 'success');
    } else {
      showToast('Benchmark run error: ' + res.statusText, 'error');
    }
  } catch (err) {
    console.error('Benchmark error:', err);
    showToast('Failed to connect to backend for benchmark', 'error');
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.innerHTML = '<i class="fa-solid fa-play"></i> Run Synthetic Benchmark';
    }
  }
}

// Phase 7: Webhook Dispatcher
async function handleTriggerTestWebhook() {
  const btn = document.getElementById('btn-test-webhook');
  if (btn) {
    btn.disabled = true;
    btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Dispatching...';
  }

  try {
    const res = await fetch(`${AppState.backendUrl}/api/webhooks/test`, {
      method: 'POST',
      headers: getAuthHeaders(),
      body: JSON.stringify({
        event_type: "sla_alert_test",
        channel: "Slack #support-alerts",
        message: "Simulated high-priority incident alert from OmniDesk AI Support Hub."
      })
    });

    if (res.ok) {
      const data = await res.json();
      showToast('Webhook alert dispatched to Slack #support-alerts!', 'success');
      fetchWebhookLogsFromBackend();
    } else {
      showToast('Webhook dispatch failed', 'error');
    }
  } catch (err) {
    console.error('Webhook error:', err);
    showToast('Failed to dispatch webhook', 'error');
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.innerHTML = '<i class="fa-solid fa-paper-plane"></i> Test Alert Webhook';
    }
  }
}

async function fetchWebhookLogsFromBackend() {
  try {
    const res = await fetch(`${AppState.backendUrl}/api/webhooks/logs`);
    if (res.ok) {
      const data = await res.json();
      renderWebhookLogs(data.logs || []);
    }
  } catch (err) {
    console.error('Failed to fetch webhook logs:', err);
  }
}

function renderWebhookLogs(logs) {
  const container = document.getElementById('webhook-logs-container');
  if (!container) return;
  
  if (!logs || logs.length === 0) {
    container.innerHTML = '<div class="text-dim text-xs py-2">No webhook incidents dispatched in current session.</div>';
    return;
  }

  container.innerHTML = logs.slice(0, 5).map(log => `
    <div class="webhook-log-item">
      <div>
        <div class="webhook-log-title">
          <span>${escapeHtml(log.title)}</span>
          <span class="badge ${log.severity === 'high' ? 'badge-rose' : 'badge-cyan'}" style="font-size: 0.68rem; padding: 2px 6px;">${escapeHtml(log.severity).toUpperCase()}</span>
        </div>
        <div class="webhook-log-dest">Destination: <code>${escapeHtml(log.destination)}</code> &bull; Status: <span class="text-emerald font-semibold">${escapeHtml(log.status)}</span></div>
      </div>
      <div class="text-xs text-muted">⏱️ ${escapeHtml(log.timestamp)}</div>
    </div>
  `).join('');
}

// Initialize on DOM Ready
document.addEventListener('DOMContentLoaded', () => {
  populateSettingsView();
  checkBackendHealth().then(() => {
    fetchKbChunksFromBackend();
    fetchTicketsFromBackend();
    fetchWebhookLogsFromBackend();
  });
  renderKbChunks();
  renderTicketsList();
  setInterval(checkBackendHealth, 15000);
});
