// Global State
let currentTab = 'overview';
let selectedInvoiceFile = null;
let selectedContractFile = null;
let selectedChatFile = null;
let isContractIndexed = false;
let currentEndpointCode = 'email';
const API_BASE_URL = (() => {
    try {
        const origin = window.location.origin;
        // If the page is already served from backend (port 8000), use that origin.
        if (origin && origin !== 'null' && origin.includes(':8000')) return origin;
    } catch (e) {}
    // Default to backend running locally on port 8000 (uvicorn)
    return 'http://127.0.0.1:8000';
})();

// Page Title Mapping
const PAGE_TITLES = {
    overview: { title: "Procurement Intelligence Overview", subtitle: "Interactive NLP Hub and developer playground for procurement operations." },
    email: { title: "Procurement Email Analyzer", subtitle: "Analyze email sentiments, categories, priorities, and extract actions." },
    invoice: { title: "Invoice Entity Extractor", subtitle: "Automatically extract amounts, dates, vendors, and line item tables." },
    contract: { title: "Contract Summarizer & Clause Parser", subtitle: "Condense long agreements and extract legal terms." },
    chatbot: { title: "Contract Q&A Chatbot (RAG)", subtitle: "Index contract text and ask questions with sources." },
    "api-settings": { title: "Settings & API Integration Guide", subtitle: "Manage API Keys and copy integration snippets for your teammates." }
};

// Ready-to-copy code snippets
const CODE_SNIPPETS = {
    email: `// Integrate Email Analyzer Endpoint
const analyzeEmail = async (emailText, geminiKey = "") => {
  const response = await fetch("http://127.0.0.1:8000/api/analyze-email", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-Gemini-API-Key": geminiKey // optional
    },
    body: JSON.stringify({ text: emailText })
  });
  
  const data = await response.json();
  console.log("Analysis Results:", data);
  return data;
};`,
    invoice: `// Integrate Invoice Extractor Endpoint (supports PDF File or Text)
const extractInvoice = async (invoiceFileOrText, geminiKey = "") => {
  const formData = new FormData();
  
  if (invoiceFileOrText instanceof File) {
    formData.append("file", invoiceFileOrText);
  } else {
    formData.append("text", invoiceFileOrText);
  }
  
  const response = await fetch("http://127.0.0.1:8000/api/extract-invoice", {
    method: "POST",
    headers: {
      "X-Gemini-API-Key": geminiKey // optional
    },
    body: formData
  });
  
  const data = await response.json();
  console.log("Invoice Data:", data);
  return data;
};`,
    summarize: `// Integrate Contract Summarizer Endpoint (supports PDF File or Text)
const summarizeContract = async (contractFileOrText, geminiKey = "") => {
  const formData = new FormData();
  
  if (contractFileOrText instanceof File) {
    formData.append("file", contractFileOrText);
  } else {
    formData.append("text", contractFileOrText);
  }
  
  const response = await fetch("http://127.0.0.1:8000/api/summarize-contract", {
    method: "POST",
    headers: {
      "X-Gemini-API-Key": geminiKey // optional
    },
    body: formData
  });
  
  const data = await response.json();
  console.log("Contract Summary:", data);
  return data;
};`,
    chat: `// Integrate RAG Chatbot Endpoint
// 1. Index document text or file first:
const indexContract = async (fileOrText) => {
  const formData = new FormData();
  if (fileOrText instanceof File) {
    formData.append("file", fileOrText);
  } else {
    formData.append("text", fileOrText);
  }
  const res = await fetch("http://127.0.0.1:8000/api/index-contract", {
    method: "POST",
    body: formData
  });
  return await res.json();
};

// 2. Query chatbot against indexed document:
const queryChatbot = async (question, geminiKey = "") => {
  const response = await fetch("http://127.0.0.1:8000/api/chat-contract", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-Gemini-API-Key": geminiKey // optional
    },
    body: JSON.stringify({ question: question })
  });
  
  const data = await response.json();
  console.log("Chatbot Answer:", data.answer);
  return data;
};`
};

// Initialize Application on load
document.addEventListener('DOMContentLoaded', () => {
    // 1. Load key from LocalStorage
    const savedKey = localStorage.getItem('gemini_api_key');
    if (savedKey) {
        document.getElementById('gemini-key-input').value = savedKey;
        updateAPIBadge(true);
    } else {
        updateAPIBadge(false);
    }
    
    // 2. Setup Sidebar click handlers
    document.querySelectorAll('.nav-item').forEach(item => {
        item.addEventListener('click', (e) => {
            e.preventDefault();
            const tabId = item.getAttribute('data-tab');
            switchTab(tabId);
        });
    });

    // 3. Setup Invoice upload handlers
    setupDragAndDrop('invoice-upload-zone', 'invoice-file', 'invoice-file-info', 'invoice-filename', (file) => {
        selectedInvoiceFile = file;
    });

    // 4. Setup Contract upload handlers
    setupDragAndDrop('contract-upload-zone', 'contract-file', 'contract-file-info', 'contract-filename', (file) => {
        selectedContractFile = file;
    });

    // 5. Setup Chat file upload handlers
    setupDragAndDrop('chat-upload-zone', 'chat-file', 'chat-file-info', 'chat-filename', (file) => {
        selectedChatFile = file;
    });
    
    // 6. Display code snippet on init
    showEndpointCode('email');
    
    // Check backend connection health
    checkBackendHealth();
});

// Toggle password visibility
function togglePassVisibility(id) {
    const input = document.getElementById(id);
    const btn = input.nextElementSibling;
    if (input.type === 'password') {
        input.type = 'text';
        btn.innerHTML = '<i class="fa-solid fa-eye-slash"></i>';
    } else {
        input.type = 'password';
        btn.innerHTML = '<i class="fa-solid fa-eye"></i>';
    }
}

// Check if FastAPI is running
async function checkBackendHealth() {
    try {
        const response = await fetch(`${API_BASE_URL}/api/health`, {
            method: 'GET',
            headers: { 'Content-Type': 'application/json' },
            timeout: 3000
        });
        if (response.ok) {
            const data = await response.json();
            document.getElementById('connection-status').innerHTML = `
                <span class="status-indicator online"></span>
                <span class="status-text">Backend Connected</span>
            `;
        } else {
            throw new Error('Backend returned error');
        }
    } catch (e) {
        document.getElementById('connection-status').innerHTML = `
            <span class="status-indicator offline"></span>
            <span class="status-text">Backend Disconnected</span>
        `;
    }
}

// Tab Switching
function switchTab(tabId) {
    currentTab = tabId;
    
    // Active sidebar menu item
    document.querySelectorAll('.nav-item').forEach(item => {
        if (item.getAttribute('data-tab') === tabId) {
            item.classList.add('active');
        } else {
            item.classList.remove('active');
        }
    });

    // Active tab panel view
    document.querySelectorAll('.tab-panel').forEach(panel => {
        if (panel.id === `tab-${tabId}`) {
            panel.classList.add('active');
        } else {
            panel.classList.remove('active');
        }
    });

    // Change Header titles
    if (PAGE_TITLES[tabId]) {
        document.getElementById('page-title').innerText = PAGE_TITLES[tabId].title;
        document.getElementById('page-subtitle').innerText = PAGE_TITLES[tabId].subtitle;
    }
}

// Setup Upload Zone drag and drop
function setupDragAndDrop(zoneId, inputId, infoId, filenameId, fileSetterCallback) {
    const zone = document.getElementById(zoneId);
    const input = document.getElementById(inputId);
    const info = document.getElementById(infoId);
    const fname = document.getElementById(filenameId);

    zone.addEventListener('click', () => input.click());

    zone.addEventListener('dragover', (e) => {
        e.preventDefault();
        zone.style.borderColor = 'var(--accent-blue)';
    });

    zone.addEventListener('dragleave', () => {
        zone.style.borderColor = 'var(--border-glass)';
    });

    zone.addEventListener('drop', (e) => {
        e.preventDefault();
        zone.style.borderColor = 'var(--border-glass)';
        if (e.dataTransfer.files.length > 0) {
            const file = e.dataTransfer.files[0];
            handleFileSelection(file, zone, info, fname, fileSetterCallback);
        }
    });

    input.addEventListener('change', () => {
        if (input.files.length > 0) {
            const file = input.files[0];
            handleFileSelection(file, zone, info, fname, fileSetterCallback);
        }
    });
}

function handleFileSelection(file, zone, info, fname, callback) {
    callback(file);
    zone.classList.add('hidden');
    info.classList.remove('hidden');
    fname.innerText = file.name;
}

// Clear Files
function clearInvoiceFile() {
    selectedInvoiceFile = null;
    document.getElementById('invoice-file').value = '';
    document.getElementById('invoice-file-info').classList.add('hidden');
    document.getElementById('invoice-upload-zone').classList.remove('hidden');
}

function clearContractFile() {
    selectedContractFile = null;
    document.getElementById('contract-file').value = '';
    document.getElementById('contract-file-info').classList.add('hidden');
    document.getElementById('contract-upload-zone').classList.remove('hidden');
}

function clearChatFile() {
    selectedChatFile = null;
    document.getElementById('chat-file').value = '';
    document.getElementById('chat-file-info').classList.add('hidden');
    document.getElementById('chat-upload-zone').classList.remove('hidden');
}

// Settings Handlers
function getGeminiKey() {
    return localStorage.getItem('gemini_api_key') || "";
}

function updateAPIBadge(hasKey) {
    const badge = document.getElementById('api-mode-badge');
    const modelStatus = document.getElementById('model-status');
    if (hasKey) {
        badge.className = "api-mode-badge gemini";
        badge.innerHTML = `<i class="fa-solid fa-sparkles"></i> <span>Gemini AI Connected</span>`;
        if (modelStatus) modelStatus.innerText = "Gemini Advanced AI";
    } else {
        badge.className = "api-mode-badge";
        badge.innerHTML = `<i class="fa-solid fa-bolt"></i> <span>Local Processing</span>`;
        if (modelStatus) modelStatus.innerText = "Hybrid CPU (Local)";
    }
}

function saveSettings() {
    const key = document.getElementById('gemini-key-input').value.trim();
    if (key) {
        localStorage.setItem('gemini_api_key', key);
        updateAPIBadge(true);
        alert('Configuration saved successfully! Running in advanced Gemini AI mode.');
    } else {
        localStorage.removeItem('gemini_api_key');
        updateAPIBadge(false);
        alert('Configuration cleared! Running in offline Local mode.');
    }
    checkBackendHealth();
}

// Quick pre-filled email templates
const EMAIL_TEMPLATES = {
    payment: `Subject: URGENT: Outstanding Payment for Invoice INV-2026-302
Dear Billing Team,

This is to follow up on the payment status for Invoice INV-2026-302, dated 15 May 2026, which was due on 30 May 2026.
The total outstanding amount is ₹4,50,000 for IT licensing support services.
Our operations are heavily affected by this outstanding payment. Please check with your finance director and update us on the transaction immediately.

Regards,
Rajesh Kumar, IT Operations Lead`,
    quote: `Subject: Purchase request: Supply of 50 ThinkPad laptops
Hello Procurement,

We would like to request a quote for the procurement of 50 Lenovo ThinkPad L14 Laptops. 
We need the shipment delivered to our Noida sector 62 head office by 15 July 2026.
Please submit the complete RFP quotation sheet and detailed warranty policies before 20 June 2026.

Thank you,
Pooja Sen, Operations Manager`,
    thanks: `Subject: Great Service - Technical support team feedback
Dear Vendor Support,

I wanted to send a quick note appreciating your team's prompt support in resolving our cloud servers maintenance issues yesterday. 
The team resolved the bug within 2 hours, which minimized our client downtime. Excellent performance! We are very satisfied with this collaboration.

Best regards,
Aman Sharma, XYZ Director`
};

function fillEmailTemplate(type) {
    if (EMAIL_TEMPLATES[type]) {
        document.getElementById('email-input').value = EMAIL_TEMPLATES[type];
    }
}

// Quick pre-filled invoice templates
const INVOICE_TEMPLATES = {
    sample1: `ABC Technologies\nInvoice Number: INV-2026-998\nDate: 05 June 2026\nTotal: ₹59,000\nVendor: ABC Technologies\nClient: XYZ Solutions`,
    sample2: `Vendor: Global Supplies Pvt Ltd\nInvoice: INV-4500\nDate: 2026-05-20\nAmount Due: $4,500.00\nNotes: Please remit within 30 days.`
};

function fillInvoiceTemplate(type) {
    if (INVOICE_TEMPLATES[type]) {
        document.getElementById('invoice-text').value = INVOICE_TEMPLATES[type];
    }
}

// Quick pre-filled contract templates
const CONTRACT_TEMPLATES = {
    short: `SERVICE AGREEMENT\nThis Agreement is made on 8 June 2026 between ABC Technologies (Vendor) and XYZ Solutions (Client). The Vendor shall provide Software Development services for a period of 24 months. Total contract value: ₹1,500,000. Payment terms: 3 installments.`,
    nda: `NON-DISCLOSURE AGREEMENT\nThis NDA is entered into between ABC Technologies and XYZ Solutions. Both parties agree to keep confidential information secure for a period of 3 years.`
};

function fillContractTemplate(type) {
    if (CONTRACT_TEMPLATES[type]) {
        document.getElementById('contract-text').value = CONTRACT_TEMPLATES[type];
    }
}

// Quick pre-filled chat/document templates
const CHAT_TEMPLATES = {
    paymentQ: `Please clarify payment terms and penalties for late payment in this contract. Are installments acceptable?`,
    scopeQ: `What services are included in the scope of work and which items are explicitly excluded?`
};

function fillChatTemplate(type) {
    if (CHAT_TEMPLATES[type]) {
        document.getElementById('chat-input').value = CHAT_TEMPLATES[type];
    }
}

// Developer unlock flow
async function unlockDeveloper() {
    const secret = document.getElementById('dev-secret-input').value.trim();
    const status = document.getElementById('dev-unlock-status');
    
    if (!secret) {
        status.innerHTML = '<span style="color: var(--accent-yellow);">⚠ Please enter the secret</span>';
        return;
    }
    
    status.innerHTML = '<span style="color: var(--accent-cyan);">🔄 Verifying...</span>';
    
    try {
        const res = await fetch(`${API_BASE_URL}/api/dev-auth`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ secret })
        });
        
        const data = await res.json();
        
        if (data.authorized) {
            localStorage.setItem('dev_authorized', '1');
            document.getElementById('dev-tools-section').style.display = 'block';
            status.innerHTML = '<span style="color: var(--accent-green);">✓ Unlocked! See API guide below.</span>';
            document.getElementById('dev-secret-input').value = '';
            setTimeout(() => {
                status.innerHTML = '<span style="color: var(--accent-green);">✓ Developer mode active</span>';
            }, 2000);
        } else {
            status.innerHTML = '<span style="color: var(--accent-red);">✗ Invalid secret. Access Denied.</span>';
        }
    } catch (e) {
        status.innerHTML = `<span style="color: var(--accent-red);">✗ Error: ${e.message || 'Backend unreachable'}</span>`;
    }
}

// Show dev tools if previously authorized locally (best-effort)
document.addEventListener('DOMContentLoaded', () => {
    if (localStorage.getItem('dev_authorized') === '1') {
        const el = document.getElementById('dev-tools-section');
        if (el) el.style.display = 'block';
    }
});

// 1. RUN EMAIL ANALYSIS
async function runEmailAnalysis() {
    const text = document.getElementById('email-input').value.trim();
    if (!text) {
        alert('Please write or paste email content.');
        return;
    }

    const btn = document.getElementById('btn-analyze-email');
    const placeholder = document.getElementById('email-output-placeholder');
    const results = document.getElementById('email-results');
    
    // Set Loading state
    btn.disabled = true;
    btn.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i> Analyzing...`;
    placeholder.classList.add('hidden');
    results.classList.add('hidden');

    try {
        const response = await fetch(`${API_BASE_URL}/api/analyze-email`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-Gemini-API-Key': getGeminiKey()
            },
            body: JSON.stringify({ text })
        });
        
        if (!response.ok) {
            const errorText = await response.text().catch(() => 'Backend failed to process.');
            throw new Error(errorText || 'Backend failed to process.');
        }
        
        const data = await response.json();
        
        // Render Output fields
        document.getElementById('email-category').innerText = data.category;
        
        const priorityPill = document.getElementById('email-priority');
        priorityPill.innerText = data.priority;
        priorityPill.className = `pill-value badge-priority ${data.priority.toLowerCase()}`;

        // Sentiment meter fill width (Positive ~ 90%, Neutral ~ 50%, Negative ~ 15%)
        const fill = document.getElementById('email-sentiment-bar');
        const sentimentVal = document.getElementById('email-sentiment-val');
        const sentimentConf = document.getElementById('email-sentiment-conf');
        
        sentimentVal.innerText = data.sentiment;
        sentimentConf.innerText = `${data.confidence}% confidence`;
        
        if (data.sentiment === 'Positive') {
            fill.style.width = '90%';
            fill.style.background = 'var(--accent-green)';
            sentimentVal.style.color = 'var(--accent-green)';
        } else if (data.sentiment === 'Negative') {
            fill.style.width = '20%';
            fill.style.background = 'var(--accent-red)';
            sentimentVal.style.color = 'var(--accent-red)';
        } else {
            fill.style.width = '50%';
            fill.style.background = 'var(--accent-yellow)';
            sentimentVal.style.color = 'var(--accent-yellow)';
        }

        // Render Action Items
        const actionsList = document.getElementById('email-action-items');
        actionsList.innerHTML = '';
        if (data.action_items && data.action_items.length > 0) {
            data.action_items.forEach(item => {
                actionsList.innerHTML += `<li>${item}</li>`;
            });
        } else {
            actionsList.innerHTML = `<li>No actionable items parsed.</li>`;
        }

        // Render Dates
        const datesList = document.getElementById('email-key-dates');
        datesList.innerHTML = '';
        if (data.key_dates && data.key_dates.length > 0) {
            data.key_dates.forEach(item => {
                datesList.innerHTML += `<li><i class="fa-regular fa-calendar-check"></i> ${item}</li>`;
            });
        } else {
            datesList.innerHTML = `<li>No key dates referenced.</li>`;
        }

        // Explanation / Pipeline mode
        document.getElementById('email-explanation').innerText = `${data.explanation} (Running via: ${data.mode})`;

        // Show result box
        results.classList.remove('hidden');

    } catch (e) {
        alert('Error: ' + e.message);
        placeholder.classList.remove('hidden');
    } finally {
        btn.disabled = false;
        btn.innerHTML = `<i class="fa-solid fa-magnifying-glass"></i> Analyze Email`;
    }
}

// 2. RUN INVOICE EXTRACTION
async function runInvoiceExtraction() {
    const text = document.getElementById('invoice-text').value.trim();
    if (!selectedInvoiceFile && !text) {
        alert('Please upload a PDF invoice or paste raw invoice text.');
        return;
    }

    const btn = document.getElementById('btn-extract-invoice');
    const placeholder = document.getElementById('invoice-output-placeholder');
    const results = document.getElementById('invoice-results');
    
    // Set Loading state
    btn.disabled = true;
    btn.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i> Parsing...`;
    placeholder.classList.add('hidden');
    results.classList.add('hidden');

    try {
        const formData = new FormData();
        if (selectedInvoiceFile) {
            formData.append('file', selectedInvoiceFile);
        } else {
            formData.append('text', text);
        }

        const response = await fetch(`${API_BASE_URL}/api/extract-invoice`, {
            method: 'POST',
            headers: {
                'X-Gemini-API-Key': getGeminiKey()
            },
            body: formData
        });
        
        if (!response.ok) throw new Error('Invoice extraction failed.');
        
        const data = await response.json();
        
        // Render general stats
        document.getElementById('inv-number').innerText = data.invoice_number;
        document.getElementById('inv-date').innerText = data.date;
        document.getElementById('inv-total').innerText = `${data.currency}${data.total_amount}`;
        document.getElementById('inv-vendor').innerText = data.vendor_name;
        document.getElementById('inv-client').innerText = data.client_name;

        // Render Table line items
        const tbody = document.querySelector('#inv-items-table tbody');
        tbody.innerHTML = '';
        if (data.line_items && data.line_items.length > 0) {
            data.line_items.forEach(item => {
                tbody.innerHTML += `
                    <tr>
                        <td style="font-weight: 600;">${item.description}</td>
                        <td>${item.quantity}</td>
                        <td>${data.currency}${item.unit_price}</td>
                        <td style="font-weight: 700; color: var(--text-primary);">${data.currency}${item.total}</td>
                    </tr>
                `;
            });
        } else {
            tbody.innerHTML = `<tr><td colspan="4" style="text-align: center;">No items found.</td></tr>`;
        }

        // Show results
        results.classList.remove('hidden');
    } catch (e) {
        alert('Error parsing invoice: ' + e.message);
        placeholder.classList.remove('hidden');
    } finally {
        btn.disabled = false;
        btn.innerHTML = `<i class="fa-solid fa-gear"></i> Parse Invoice`;
    }
}

// 3. RUN CONTRACT SUMMARIZATION
async function runContractSummarization() {
    const text = document.getElementById('contract-text').value.trim();
    if (!selectedContractFile && !text) {
        alert('Please upload a PDF contract or paste contract text.');
        return;
    }

    const btn = document.getElementById('btn-summarize-contract');
    const placeholder = document.getElementById('contract-output-placeholder');
    const results = document.getElementById('contract-results');
    
    btn.disabled = true;
    btn.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i> Summarizing...`;
    placeholder.classList.add('hidden');
    results.classList.add('hidden');

    try {
        const formData = new FormData();
        if (selectedContractFile) {
            formData.append('file', selectedContractFile);
        } else {
            formData.append('text', text);
        }

        const response = await fetch(`${API_BASE_URL}/api/summarize-contract`, {
            method: 'POST',
            headers: {
                'X-Gemini-API-Key': getGeminiKey()
            },
            body: formData
        });
        
        if (!response.ok) throw new Error('Contract summarization failed.');
        
        const data = await response.json();
        
        // Render Summary Paragraph
        document.getElementById('contract-summary-text').innerText = data.summary_text;

        // Render Legal Clauses Grid
        const clausesGrid = document.getElementById('contract-clauses');
        clausesGrid.innerHTML = '';
        
        const iconMapping = {
            "Parties Involved": "fa-building-shield",
            "Duration & Effective Date": "fa-clock",
            "Financial Obligations": "fa-coins",
            "Scope of Services": "fa-screwdriver-wrench",
            "Termination & Dispute Resolution": "fa-gavel"
        };
        
        if (data.clauses && Object.keys(data.clauses).length > 0) {
            for (const [title, points] of Object.entries(data.clauses)) {
                const iconClass = iconMapping[title] || "fa-file-text";
                const pointsList = points.map(p => `• ${p}`).join('<br>');
                clausesGrid.innerHTML += `
                    <div class="clause-item">
                        <div class="clause-header">
                            <i class="fa-solid ${iconClass}"></i>
                            <h5>${title}</h5>
                        </div>
                        <div class="clause-body">
                            ${pointsList}
                        </div>
                    </div>
                `;
            }
        }

        results.classList.remove('hidden');
    } catch (e) {
        alert('Error summarizing: ' + e.message);
        placeholder.classList.remove('hidden');
    } finally {
        btn.disabled = false;
        btn.innerHTML = `<i class="fa-solid fa-compress"></i> Summarize Contract`;
    }
}

// 4. RAG CHATBOT LOGIC
async function indexContractForChat() {
    const text = document.getElementById('chat-text').value.trim();
    if (!selectedChatFile && !text) {
        alert('Please upload a PDF/text file or paste contract text to index.');
        return;
    }

    const btn = document.getElementById('btn-index-contract');
    const statusBox = document.getElementById('index-status');
    const chatInput = document.getElementById('chat-input');
    const chatBtn = document.getElementById('btn-send-chat');
    
    btn.disabled = true;
    btn.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i> Indexing...`;
    statusBox.className = "index-status status-unindexed";
    statusBox.innerHTML = `<i class="fa-solid fa-hourglass-start"></i> Encoding vectors...`;

    try {
        const formData = new FormData();
        if (selectedChatFile) {
            formData.append('file', selectedChatFile);
        } else {
            formData.append('text', text);
        }

        const response = await fetch(`${API_BASE_URL}/api/index-contract`, {
            method: 'POST',
            body: formData
        });
        
        if (!response.ok) throw new Error('Contract indexing failed.');
        
        const data = await response.json();
        
        if (data.status === 'success') {
            isContractIndexed = true;
            statusBox.className = "index-status status-indexed";
            statusBox.innerHTML = `<i class="fa-solid fa-circle-check"></i> Vector Index Ready!`;
            
            document.getElementById('chat-status-indicator').innerText = `RAG Ready (${data.message})`;
            
            // Enable chat inputs
            chatInput.disabled = false;
            chatBtn.disabled = false;
            
            appendChatMessage('system', `Successfully indexed contract. Ask me questions like "What are the payment terms?" or "Who are the parties involved?"`);
        } else {
            throw new Error(data.message);
        }
    } catch (e) {
        alert('Error: ' + e.message);
        statusBox.className = "index-status status-unindexed";
        statusBox.innerHTML = `<i class="fa-solid fa-triangle-exclamation"></i> Index Failed`;
    } finally {
        btn.disabled = false;
        btn.innerHTML = `<i class="fa-solid fa-database"></i> Build Vector Index`;
    }
}

function checkChatEnter(e) {
    if (e.key === 'Enter') {
        sendChatMessage();
    }
}

async function sendChatMessage() {
    const input = document.getElementById('chat-input');
    const question = input.value.trim();
    if (!question || !isContractIndexed) return;

    // Display user message
    appendChatMessage('user', question);
    input.value = '';

    // Show bot typing loader
    const messagesArea = document.getElementById('chat-messages');
    const loaderId = `loader-${Date.now()}`;
    const loaderDiv = document.createElement('div');
    loaderDiv.id = loaderId;
    loaderDiv.className = 'message system-msg';
    loaderDiv.innerHTML = `
        <div class="avatar"><i class="fa-solid fa-robot"></i></div>
        <div class="msg-bubble">
            <p><span class="loading-dots">Searching vector spaces</span></p>
        </div>
    `;
    messagesArea.appendChild(loaderDiv);
    messagesArea.scrollTop = messagesArea.scrollHeight;

    try {
        const response = await fetch(`${API_BASE_URL}/api/chat-contract`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-Gemini-API-Key': getGeminiKey()
            },
            body: JSON.stringify({ question })
        });
        
        if (!response.ok) throw new Error('Failed to fetch chatbot answer.');
        
        const data = await response.json();
        
        // Remove typing loader
        document.getElementById(loaderId).remove();
        
        // Append response
        appendChatMessage('system', data.answer);
    } catch (e) {
        document.getElementById(loaderId).remove();
        appendChatMessage('system', `Error responding: ${e.message}`);
    }
}

function appendChatMessage(sender, text) {
    const messagesArea = document.getElementById('chat-messages');
    const msgDiv = document.createElement('div');
    msgDiv.className = `message ${sender === 'user' ? 'user-msg' : 'system-msg'}`;
    
    const icon = sender === 'user' ? 'fa-user' : 'fa-robot';
    
    msgDiv.innerHTML = `
        <div class="avatar"><i class="fa-solid ${icon}"></i></div>
        <div class="msg-bubble">
            <p>${text}</p>
        </div>
    `;
    
    messagesArea.appendChild(msgDiv);
    messagesArea.scrollTop = messagesArea.scrollHeight;
}

// 5. DEVELOPER INTEGRATION DISPLAY
function showEndpointCode(type) {
    currentEndpointCode = type;
    
    // Toggle active selector buttons
    document.querySelectorAll('.btn-endpoint').forEach(btn => {
        if (btn.getAttribute('onclick').includes(`'${type}'`)) {
            btn.classList.add('active');
        } else {
            btn.classList.remove('active');
        }
    });

    const display = document.getElementById('code-snippet-display');
    if (CODE_SNIPPETS[type]) {
        display.innerText = CODE_SNIPPETS[type];
    }
}

function copyCodeSnippet() {
    const code = CODE_SNIPPETS[currentEndpointCode];
    navigator.clipboard.writeText(code).then(() => {
        alert('API integration snippet copied to clipboard!');
    }).catch(err => {
        alert('Failed to copy code: ', err);
    });
}
