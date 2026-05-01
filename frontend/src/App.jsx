import { useState, useEffect, useRef, useCallback } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import {
  Bot, User, Plus, Moon, Sun, Database,
  ChevronDown, ChevronRight, Loader2, ArrowUp,
  RefreshCw, CheckCircle, XCircle, BarChart2,
  Code2, Table2, AlertTriangle, MessageSquare,
  Upload, FileText, Shield, X,
} from 'lucide-react';
import {
  BarChart, Bar, LineChart, Line, ScatterChart, Scatter,
  XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
} from 'recharts';
import './index.css';

// ─────────────────────────────────────────────
// Config
// ─────────────────────────────────────────────
const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

// ─────────────────────────────────────────────
// Admin mode — set via ?admin=TOKEN in URL
// Token stored in sessionStorage; sent as header
// ─────────────────────────────────────────────
function initAdmin() {
  const params = new URLSearchParams(window.location.search);
  const token  = params.get('admin');
  if (token) {
    sessionStorage.setItem('nl2sql_admin', token);
    // Clean URL
    window.history.replaceState({}, '', window.location.pathname);
  }
  return sessionStorage.getItem('nl2sql_admin') || '';
}

const ADMIN_TOKEN = initAdmin();
const IS_ADMIN    = Boolean(ADMIN_TOKEN);

// ─────────────────────────────────────────────
// Utilities
// ─────────────────────────────────────────────
const genId = () => `${Date.now()}-${Math.random().toString(36).slice(2, 7)}`;

function safeNum(v) {
  const n = parseFloat(v);
  return isNaN(n) ? v : n;
}

function autoTitle(text) {
  return text.length > 42 ? text.slice(0, 42) + '…' : text;
}

// ─────────────────────────────────────────────
// ThinkingBlock — only visible to admin
// ─────────────────────────────────────────────
const ThinkingBlock = ({ steps = [], isComplete }) => {
  const [open, setOpen] = useState(!isComplete);
  if (!IS_ADMIN) return null;

  return (
    <div className={`thinking-block ${isComplete ? 'is-complete' : 'is-active'}`}>
      <button className="thinking-header" onClick={() => setOpen(o => !o)}>
        {open ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
        <span>{isComplete ? 'Thought Process' : 'Agent is thinking…'}</span>
        {!isComplete && <Loader2 size={13} className="spin" />}
      </button>
      {open && (
        <div className="thinking-steps">
          {steps.map((step, i) => (
            <div key={i} className={`thinking-step${!isComplete && i === steps.length - 1 ? ' active' : ''}`}>
              <span className="step-dot" />
              {step}
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

// ─────────────────────────────────────────────
// SQL Preview — admin only
// ─────────────────────────────────────────────
const SqlBlock = ({ sql }) => {
  const [open, setOpen] = useState(false);
  if (!sql || !IS_ADMIN) return null;
  return (
    <div className="detail-block">
      <button className="detail-toggle" onClick={() => setOpen(o => !o)}>
        <Code2 size={13} />
        {open ? 'Hide SQL' : 'View Generated SQL'}
        {open ? <ChevronDown size={13} /> : <ChevronRight size={13} />}
      </button>
      {open && <pre className="sql-code">{sql}</pre>}
    </div>
  );
};

// ─────────────────────────────────────────────
// Data Table — admin only
// ─────────────────────────────────────────────
const DataTable = ({ data, rowCount }) => {
  const [open, setOpen] = useState(false);
  if (!data?.length || !IS_ADMIN) return null;
  const cols = Object.keys(data[0]);
  return (
    <div className="detail-block">
      <button className="detail-toggle" onClick={() => setOpen(o => !o)}>
        <Table2 size={13} />
        {open ? 'Hide Data' : `View Raw Data (${rowCount} row${rowCount !== 1 ? 's' : ''})`}
        {open ? <ChevronDown size={13} /> : <ChevronRight size={13} />}
      </button>
      {open && (
        <div className="table-scroll">
          <table className="result-table">
            <thead><tr>{cols.map(c => <th key={c}>{c}</th>)}</tr></thead>
            <tbody>
              {data.slice(0, 50).map((row, i) => (
                <tr key={i}>{cols.map(c => <td key={c}>{row[c] == null ? '—' : String(row[c])}</td>)}</tr>
              ))}
            </tbody>
          </table>
          {data.length > 50 && <p className="table-note">Showing first 50 of {rowCount} rows.</p>}
        </div>
      )}
    </div>
  );
};

// ─────────────────────────────────────────────
// Chart — visible to everyone
// ─────────────────────────────────────────────
const ChartBlock = ({ chartConfig, data }) => {
  if (!chartConfig || !data?.length) return null;
  const { chart_type, x, y } = chartConfig;
  if (!(x in data[0]) || !(y in data[0])) return null;

  const chartData    = data.slice(0, 30).map(r => ({ ...r, [y]: safeNum(r[y]) }));
  const tick         = { fontSize: 11, fill: 'var(--text-muted)' };
  const grid         = 'var(--border)';
  const tooltipStyle = { background: 'var(--bg-secondary)', border: '1px solid var(--border)', borderRadius: 8, fontSize: 12 };

  return (
    <div className="chart-container fade-in">
      <p className="chart-label"><BarChart2 size={13} /> {y} by {x}</p>
      <ResponsiveContainer width="100%" height={220}>
        {chart_type === 'line' ? (
          <LineChart data={chartData} margin={{ top: 5, right: 16, left: 0, bottom: 36 }}>
            <CartesianGrid strokeDasharray="3 3" stroke={grid} />
            <XAxis dataKey={x} tick={tick} angle={-30} textAnchor="end" />
            <YAxis tick={tick} />
            <Tooltip contentStyle={tooltipStyle} />
            <Line type="monotone" dataKey={y} stroke="var(--accent)" dot={false} strokeWidth={2} />
          </LineChart>
        ) : chart_type === 'scatter' ? (
          <ScatterChart margin={{ top: 5, right: 16, left: 0, bottom: 36 }}>
            <CartesianGrid strokeDasharray="3 3" stroke={grid} />
            <XAxis dataKey={x} name={x} tick={tick} />
            <YAxis dataKey={y} name={y} tick={tick} />
            <Tooltip contentStyle={tooltipStyle} />
            <Scatter data={chartData} fill="var(--accent)" />
          </ScatterChart>
        ) : (
          <BarChart data={chartData} margin={{ top: 5, right: 16, left: 0, bottom: 36 }}>
            <CartesianGrid strokeDasharray="3 3" stroke={grid} />
            <XAxis dataKey={x} tick={tick} angle={-30} textAnchor="end" />
            <YAxis tick={tick} />
            <Tooltip contentStyle={tooltipStyle} />
            <Bar dataKey={y} fill="var(--accent)" radius={[4, 4, 0, 0]} />
          </BarChart>
        )}
      </ResponsiveContainer>
    </div>
  );
};

// ─────────────────────────────────────────────
// Approval Banner (HITL)
// ─────────────────────────────────────────────
const ApprovalBanner = ({ sql, onApprove, onReject }) => (
  <div className="approval-banner fade-in">
    <div className="approval-header">
      <AlertTriangle size={16} color="#f59e0b" />
      <strong>Database Modification — Review Required</strong>
    </div>
    <p className="approval-note">This query will write to the database. Approve to execute or reject to cancel.</p>
    {IS_ADMIN && <pre className="sql-code">{sql}</pre>}
    <div className="approval-buttons">
      <button className="btn-approve" onClick={onApprove}><CheckCircle size={14} /> Approve &amp; Execute</button>
      <button className="btn-reject" onClick={onReject}><XCircle size={14} /> Reject</button>
    </div>
  </div>
);

// ─────────────────────────────────────────────
// Chat message
// ─────────────────────────────────────────────
const ChatMessage = ({ message, onRetry, onApprove, onReject }) => {
  const isUser = message.role === 'user';
  return (
    <div className={`msg-row ${isUser ? 'is-user' : 'is-agent'} fade-in`}>
      <div className="msg-avatar">{isUser ? <User size={15} /> : <Bot size={15} />}</div>
      <div className="msg-body">
        {(message.status === 'thinking' || message.steps?.length > 0) && (
          <ThinkingBlock steps={message.steps || []} isComplete={message.status === 'done'} />
        )}
        {message.requires_approval && (
          <ApprovalBanner sql={message.generated_sql} onApprove={onApprove} onReject={onReject} />
        )}
        {message.content && (
          <div className="markdown-body">
            <ReactMarkdown
              remarkPlugins={[remarkGfm]}
              components={{ table: ({ children }) => <div className="md-table-wrap"><table>{children}</table></div> }}
            >
              {message.content}
            </ReactMarkdown>
          </div>
        )}
        {!message.requires_approval && message.status === 'done' && (
          <>
            <ChartBlock chartConfig={message.chart_config} data={message.data} />
            <DataTable data={message.data} rowCount={message.row_count ?? message.data?.length ?? 0} />
            <SqlBlock sql={message.generated_sql} />
          </>
        )}
        {message.status === 'done' && message.isError && (
          <button className="btn-retry" onClick={onRetry}><RefreshCw size={13} /> Retry</button>
        )}
      </div>
    </div>
  );
};

// ─────────────────────────────────────────────
// File Upload Component
// ─────────────────────────────────────────────
const FileUploadZone = ({ onUploaded, onClear, uploadedFile }) => {
  const [dragging, setDragging] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [error, setError]       = useState('');
  const fileRef = useRef(null);

  const handleFile = async (file) => {
    const allowed = ['.csv', '.xlsx', '.xls', '.sql'];
    const ext     = file.name.slice(file.name.lastIndexOf('.')).toLowerCase();
    if (!allowed.includes(ext)) { setError(`Unsupported type. Use: ${allowed.join(', ')}`); return; }
    if (file.size > 10 * 1024 * 1024) { setError('File too large (max 10 MB).'); return; }

    setError('');
    setUploading(true);
    try {
      const form = new FormData();
      form.append('file', file);
      const res  = await fetch(`${API_URL}/api/upload`, { method: 'POST', body: form });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Upload failed');
      onUploaded({ sessionId: data.session_id, filename: file.name, schema: data.schema, tableName: data.table_name, sample: data.sample });
    } catch (e) {
      setError(e.message);
    } finally {
      setUploading(false);
    }
  };

  const onDrop = (e) => {
    e.preventDefault(); setDragging(false);
    const file = e.dataTransfer.files[0];
    if (file) handleFile(file);
  };

  if (uploadedFile) {
    return (
      <div className="upload-active fade-in">
        <div className="upload-active-header">
          <FileText size={13} />
          <span className="upload-filename">{uploadedFile.filename}</span>
          <button className="upload-clear" onClick={onClear} title="Remove file"><X size={12} /></button>
        </div>
        <p className="upload-source-label">Querying your file</p>
      </div>
    );
  }

  return (
    <div
      className={`upload-zone ${dragging ? 'dragging' : ''} ${uploading ? 'uploading' : ''}`}
      onDragOver={e => { e.preventDefault(); setDragging(true); }}
      onDragLeave={() => setDragging(false)}
      onDrop={onDrop}
      onClick={() => fileRef.current?.click()}
    >
      <input ref={fileRef} type="file" accept=".csv,.xlsx,.xls,.sql" style={{ display: 'none' }}
        onChange={e => e.target.files[0] && handleFile(e.target.files[0])} />
      {uploading
        ? <><Loader2 size={16} className="spin" /><span>Parsing file…</span></>
        : <><Upload size={14} /><span>Drop CSV, XLSX, or SQL</span></>}
      {error && <p className="upload-error">{error}</p>}
    </div>
  );
};

// ─────────────────────────────────────────────
// Trial Banner
// ─────────────────────────────────────────────
const TrialBanner = ({ used, limit }) => {
  if (IS_ADMIN) return null;
  const remaining = limit - used;
  if (remaining > 0) {
    return (
      <div className="trial-badge">
        <Shield size={12} />
        <span>{remaining} free {remaining === 1 ? 'query' : 'queries'} left today</span>
      </div>
    );
  }
  return (
    <div className="trial-exhausted">
      <Shield size={14} />
      <strong>Free trial limit reached</strong>
      <p>You've used your {limit} free queries for today. Come back tomorrow!</p>
    </div>
  );
};

// ─────────────────────────────────────────────
// Sidebar chat entry
// ─────────────────────────────────────────────
const ChatEntry = ({ chat, isActive, onClick }) => (
  <button className={`chat-entry ${isActive ? 'active' : ''}`} onClick={onClick} title={chat.title}>
    <MessageSquare size={13} />
    <span className="chat-entry-title">{chat.title}</span>
  </button>
);

// ─────────────────────────────────────────────
// Constants
// ─────────────────────────────────────────────
const WELCOME = {
  id: 'welcome', role: 'agent', status: 'done',
  content:
    "Hello! I'm your **Autonomous Data Agent**.\n\nAsk anything about your database in plain English — " +
    "I'll write the SQL, execute it, and present the results.\n\n**Try asking:**\n" +
    "- Who are our top 10 customers by spending?\n- Show me monthly revenue trend for 2024\n" +
    "- Best-selling products by category\n- Average order value by signup year\n\n" +
    "Or **upload your own CSV / XLSX / SQL file** from the sidebar to query your own data.",
  steps: [],
};

const SAMPLE_QUERIES = [
  'Top 10 customers by lifetime value',
  'Monthly revenue trend 2024',
  'Best-selling products by category',
  'Orders by status breakdown',
  'Average salary by department',
];

function makeChat(title = 'New Chat') {
  return { id: genId(), title, messages: [WELCOME], createdAt: Date.now() };
}

// ─────────────────────────────────────────────
// Main App
// ─────────────────────────────────────────────
export default function App() {
  const [theme, setTheme]           = useState('dark');
  const [chats, setChats]           = useState([makeChat()]);
  const [activeChatId, setActive]   = useState(chats[0].id);
  const [input, setInput]           = useState('');
  const [isGenerating, setGen]      = useState(false);
  const [pendingApproval, setPA]    = useState(null);
  const [uploadedFile, setUpload]   = useState(null);  // { sessionId, filename, schema, tableName }
  const [trialInfo, setTrial]       = useState({ used: 0, limit: 2 });
  const bottomRef  = useRef(null);
  const inputRef   = useRef(null);

  const activeChat = chats.find(c => c.id === activeChatId) ?? chats[0];
  const messages   = activeChat.messages;
  const trialExhausted = !IS_ADMIN && trialInfo.used >= trialInfo.limit;

  useEffect(() => { document.body.className = theme === 'dark' ? 'dark-theme' : ''; }, [theme]);
  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: 'smooth' }); }, [messages]);

  // ── Chat helpers ──────────────────────────────
  const updateChat = useCallback((id, fn) =>
    setChats(p => p.map(c => c.id === id ? fn(c) : c)), []);

  const addMsg = useCallback((id, msg) =>
    setChats(p => p.map(c => c.id === id ? { ...c, messages: [...c.messages, msg] } : c)), []);

  const updateMsg = useCallback((chatId, msgId, patch) =>
    setChats(p => p.map(c =>
      c.id === chatId ? { ...c, messages: c.messages.map(m => m.id === msgId ? { ...m, ...patch } : m) } : c
    )), []);

  const newChat = () => {
    const chat = makeChat();
    setChats(p => [chat, ...p]);
    setActive(chat.id);
    setPA(null);
    setInput('');
    inputRef.current?.focus();
  };

  // ── API call ──────────────────────────────────
  const callApi = useCallback(async (payload, chatId, agentMsgId, initialSteps) => {
    const MAX_RETRIES = 2;
    let lastError = null;

    const headers = { 'Content-Type': 'application/json' };
    if (IS_ADMIN) headers['X-Admin-Token'] = ADMIN_TOKEN;

    for (let attempt = 0; attempt <= MAX_RETRIES; attempt++) {
      try {
        const res  = await fetch(`${API_URL}/api/chat`, { method: 'POST', headers, body: JSON.stringify(payload) });
        const data = await res.json();

        if (!res.ok) throw new Error(data.detail || `Server error ${res.status}`);

        // Update trial counter from server response
        setTrial({ used: data.trial_used, limit: data.trial_limit });

        if (data.requires_approval) {
          setPA({ query: payload.query });
          updateMsg(chatId, agentMsgId, {
            status: 'done', steps: data.steps ?? initialSteps,
            content: data.answer, requires_approval: true, generated_sql: data.generated_sql, isError: false,
          });
        } else {
          setPA(null);
          updateMsg(chatId, agentMsgId, {
            status: 'done', steps: data.steps ?? initialSteps,
            content: data.answer, requires_approval: false,
            chart_config: data.chart_config, data: data.data,
            row_count: data.row_count, generated_sql: data.generated_sql, isError: false,
          });
        }
        return;
      } catch (err) {
        lastError = err;
        if (attempt < MAX_RETRIES) {
          await new Promise(r => setTimeout(r, 1000 * (attempt + 1)));
          updateMsg(chatId, agentMsgId, {
            steps: [...initialSteps, `Retrying… (attempt ${attempt + 2}/${MAX_RETRIES + 1})`],
          });
        }
      }
    }

    updateMsg(chatId, agentMsgId, {
      status: 'done', steps: initialSteps,
      content: `**Error:** ${lastError?.message ?? 'Unknown error'}`, isError: true,
    });
  }, [updateMsg]);

  // ── Submit query ──────────────────────────────
  const handleSubmit = async (queryText) => {
    const q = (queryText ?? input).trim();
    if (!q || isGenerating || trialExhausted) return;

    const chatId      = activeChatId;
    const userMsgId   = genId();
    const agentMsgId  = genId();

    const initialSteps = [
      uploadedFile ? `Analyzing uploaded file: ${uploadedFile.filename}…` : 'Analyzing intent and selecting relevant tables…',
      'Generating SQL from schema context…',
    ];
    const userMsg  = { id: userMsgId, role: 'user', content: q, status: 'done' };
    const agentMsg = { id: agentMsgId, role: 'agent', content: '', status: 'thinking', steps: initialSteps };

    if (activeChat.messages.length === 1 && activeChat.title === 'New Chat') {
      updateChat(chatId, c => ({ ...c, title: autoTitle(q) }));
    }

    setChats(p => p.map(c => c.id === chatId ? { ...c, messages: [...c.messages, userMsg, agentMsg] } : c));
    setInput('');
    setGen(true);

    const payload = {
      query: q,
      is_approved: false,
      data_source: uploadedFile ? 'upload' : 'postgres',
      session_id:  uploadedFile?.sessionId ?? null,
    };
    await callApi(payload, chatId, agentMsgId, initialSteps);
    setGen(false);
  };

  const handleRetry = () => {
    const lastUser = [...messages].reverse().find(m => m.role === 'user');
    if (lastUser) handleSubmit(lastUser.content);
  };

  const handleApprove = async () => {
    if (!pendingApproval) return;
    const chatId     = activeChatId;
    const agentMsgId = genId();
    const steps      = ['Executing approved modification…', 'Generating confirmation…'];
    addMsg(chatId, { id: agentMsgId, role: 'agent', content: '', status: 'thinking', steps });
    setGen(true);
    await callApi({ query: pendingApproval.query, is_approved: true, data_source: 'postgres' }, chatId, agentMsgId, steps);
    setGen(false);
  };

  const handleReject = () => {
    setPA(null);
    addMsg(activeChatId, { id: genId(), role: 'agent', status: 'done', steps: [], content: 'Action **rejected**. No data was modified.' });
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSubmit(); }
  };

  // ─────────────────────────────────────────────
  return (
    <div className="app">
      {/* ── Sidebar ── */}
      <aside className="sidebar">
        <div className="sidebar-logo">
          <div className="logo-icon"><Database size={20} color="white" /></div>
          <div>
            <p className="logo-title">NL-to-SQL</p>
            <p className="logo-sub">Powered by LangGraph{IS_ADMIN ? ' · Admin' : ''}</p>
          </div>
        </div>

        <div className="sidebar-actions">
          <button className="btn-new-chat" onClick={newChat}><Plus size={15} /> New Chat</button>
          <button className="btn-theme" onClick={() => setTheme(t => t === 'dark' ? 'light' : 'dark')} title="Toggle theme">
            {theme === 'dark' ? <Sun size={15} /> : <Moon size={15} />}
          </button>
        </div>

        {/* Trial badge */}
        <TrialBanner used={trialInfo.used} limit={trialInfo.limit} />

        {/* File upload */}
        <div className="sidebar-section-label">Upload Your Data</div>
        <FileUploadZone
          uploadedFile={uploadedFile}
          onUploaded={setUpload}
          onClear={() => setUpload(null)}
        />

        {/* Chat history */}
        <div className="sidebar-section-label">Chats</div>
        <nav className="chat-list">
          {chats.map(chat => (
            <ChatEntry key={chat.id} chat={chat} isActive={chat.id === activeChatId}
              onClick={() => { setActive(chat.id); setPA(null); }} />
          ))}
        </nav>

        {/* Sample queries */}
        <div className="sidebar-section-label" style={{ marginTop: 'auto', paddingTop: '1rem' }}>
          Sample Queries
        </div>
        <div className="sample-list">
          {SAMPLE_QUERIES.map(q => (
            <button key={q} className="sample-query" onClick={() => setInput(q)}>{q}</button>
          ))}
        </div>
      </aside>

      {/* ── Main chat ── */}
      <main className="chat-main">
        <div className="chat-scroll">
          <div className="chat-feed">
            {messages.map(msg => (
              <ChatMessage key={msg.id} message={msg} onRetry={handleRetry} onApprove={handleApprove} onReject={handleReject} />
            ))}
            <div ref={bottomRef} />
          </div>
        </div>

        {/* Input */}
        <div className="input-wrap">
          {uploadedFile && (
            <div className="input-source-tag">
              <FileText size={11} /> Querying: <strong>{uploadedFile.filename}</strong>
            </div>
          )}
          <div className={`input-box ${isGenerating ? 'is-loading' : ''} ${trialExhausted ? 'is-disabled' : ''}`}>
            <textarea
              ref={inputRef}
              className="chat-textarea"
              placeholder={trialExhausted ? 'Trial limit reached for today. Come back tomorrow!' : 'Ask anything about your database…'}
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              disabled={isGenerating || trialExhausted}
              rows={1}
            />
            <button className="btn-send" onClick={() => handleSubmit()} disabled={!input.trim() || isGenerating || trialExhausted}>
              {isGenerating ? <Loader2 size={16} className="spin" style={{ color: 'white' }} /> : <ArrowUp size={16} />}
            </button>
          </div>
          <p className="input-footer">
            Agentic Text-to-SQL · LangGraph · PostgreSQL · GitHub Models
          </p>
        </div>
      </main>
    </div>
  );
}
