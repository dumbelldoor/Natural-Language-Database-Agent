import { useState, useEffect, useRef, useCallback } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import {
  Bot, User, Plus, Moon, Sun, Database,
  ChevronDown, ChevronRight, Loader2, ArrowUp,
  RefreshCw, CheckCircle, XCircle, BarChart2,
  Code2, Table2, AlertTriangle, MessageSquare,
} from 'lucide-react';
import {
  BarChart, Bar, LineChart, Line, ScatterChart, Scatter,
  XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
} from 'recharts';
import './index.css';

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
// ThinkingBlock — FIX: never unmounts, just hides steps
// ─────────────────────────────────────────────
const ThinkingBlock = ({ steps = [], isComplete }) => {
  const [open, setOpen] = useState(!isComplete);

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
            <div
              key={i}
              className={`thinking-step${!isComplete && i === steps.length - 1 ? ' active' : ''}`}
            >
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
// SQL Preview
// ─────────────────────────────────────────────
const SqlBlock = ({ sql }) => {
  const [open, setOpen] = useState(false);
  if (!sql) return null;
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
// Data Table
// ─────────────────────────────────────────────
const DataTable = ({ data, rowCount }) => {
  const [open, setOpen] = useState(false);
  if (!data?.length) return null;
  const cols = Object.keys(data[0]);
  return (
    <div className="detail-block">
      <button className="detail-toggle" onClick={() => setOpen(o => !o)}>
        <Table2 size={13} />
        {open ? 'Hide Data' : `View Raw Data  (${rowCount} row${rowCount !== 1 ? 's' : ''})`}
        {open ? <ChevronDown size={13} /> : <ChevronRight size={13} />}
      </button>
      {open && (
        <div className="table-scroll">
          <table className="result-table">
            <thead>
              <tr>{cols.map(c => <th key={c}>{c}</th>)}</tr>
            </thead>
            <tbody>
              {data.slice(0, 50).map((row, i) => (
                <tr key={i}>
                  {cols.map(c => <td key={c}>{row[c] == null ? '—' : String(row[c])}</td>)}
                </tr>
              ))}
            </tbody>
          </table>
          {data.length > 50 && (
            <p className="table-note">Showing first 50 of {rowCount} rows.</p>
          )}
        </div>
      )}
    </div>
  );
};

// ─────────────────────────────────────────────
// Chart
// ─────────────────────────────────────────────
const ChartBlock = ({ chartConfig, data }) => {
  if (!chartConfig || !data?.length) return null;
  const { chart_type, x, y } = chartConfig;
  if (!(x in data[0]) || !(y in data[0])) return null;

  const chartData = data.slice(0, 30).map(r => ({ ...r, [y]: safeNum(r[y]) }));
  const tick = { fontSize: 11, fill: 'var(--text-secondary)' };
  const grid = 'var(--border-color)';
  const tooltipStyle = {
    background: 'var(--bg-secondary)',
    border: '1px solid var(--border-color)',
    borderRadius: 8,
    fontSize: 12,
  };

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
            <Line type="monotone" dataKey={y} stroke="var(--accent-color)" dot={false} strokeWidth={2} />
          </LineChart>
        ) : chart_type === 'scatter' ? (
          <ScatterChart margin={{ top: 5, right: 16, left: 0, bottom: 36 }}>
            <CartesianGrid strokeDasharray="3 3" stroke={grid} />
            <XAxis dataKey={x} name={x} tick={tick} />
            <YAxis dataKey={y} name={y} tick={tick} />
            <Tooltip contentStyle={tooltipStyle} />
            <Scatter data={chartData} fill="var(--accent-color)" />
          </ScatterChart>
        ) : (
          <BarChart data={chartData} margin={{ top: 5, right: 16, left: 0, bottom: 36 }}>
            <CartesianGrid strokeDasharray="3 3" stroke={grid} />
            <XAxis dataKey={x} tick={tick} angle={-30} textAnchor="end" />
            <YAxis tick={tick} />
            <Tooltip contentStyle={tooltipStyle} />
            <Bar dataKey={y} fill="var(--accent-color)" radius={[4, 4, 0, 0]} />
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
    <pre className="sql-code">{sql}</pre>
    <div className="approval-buttons">
      <button className="btn-approve" onClick={onApprove}>
        <CheckCircle size={14} /> Approve &amp; Execute
      </button>
      <button className="btn-reject" onClick={onReject}>
        <XCircle size={14} /> Reject
      </button>
    </div>
  </div>
);

// ─────────────────────────────────────────────
// Single chat message
// ─────────────────────────────────────────────
const ChatMessage = ({ message, onRetry, onApprove, onReject }) => {
  const isUser = message.role === 'user';

  return (
    <div className={`msg-row ${isUser ? 'is-user' : 'is-agent'} fade-in`}>
      <div className="msg-avatar">{isUser ? <User size={15} /> : <Bot size={15} />}</div>

      <div className="msg-body">
        {/* Thinking block */}
        {(message.status === 'thinking' || message.steps?.length > 0) && (
          <ThinkingBlock steps={message.steps || []} isComplete={message.status === 'done'} />
        )}

        {/* HITL approval */}
        {message.requires_approval && (
          <ApprovalBanner
            sql={message.generated_sql}
            onApprove={onApprove}
            onReject={onReject}
          />
        )}

        {/* Main answer text */}
        {message.content && (
          <div className="markdown-body">
            <ReactMarkdown
              remarkPlugins={[remarkGfm]}
              components={{
                table: ({ children }) => (
                  <div className="md-table-wrap"><table>{children}</table></div>
                ),
              }}
            >
              {message.content}
            </ReactMarkdown>
          </div>
        )}

        {/* Extras (chart, data table, SQL) — only for completed non-approval messages */}
        {!message.requires_approval && message.status === 'done' && (
          <>
            <ChartBlock chartConfig={message.chart_config} data={message.data} />
            <DataTable data={message.data} rowCount={message.row_count ?? message.data?.length ?? 0} />
            <SqlBlock sql={message.generated_sql} />
          </>
        )}

        {/* Retry button — shown when content contains an error */}
        {message.status === 'done' && message.isError && (
          <button className="btn-retry" onClick={onRetry}>
            <RefreshCw size={13} /> Retry
          </button>
        )}
      </div>
    </div>
  );
};

// ─────────────────────────────────────────────
// Sidebar chat entry
// ─────────────────────────────────────────────
const ChatEntry = ({ chat, isActive, onClick }) => (
  <button
    className={`chat-entry ${isActive ? 'active' : ''}`}
    onClick={onClick}
    title={chat.title}
  >
    <MessageSquare size={13} />
    <span className="chat-entry-title">{chat.title}</span>
  </button>
);

// ─────────────────────────────────────────────
// Constants
// ─────────────────────────────────────────────
const WELCOME = {
  id: 'welcome',
  role: 'agent',
  status: 'done',
  content:
    "Hello! I'm your **Autonomous Data Agent**.\n\nAsk anything about your database in plain English — I'll write the SQL, execute it, and give you the results.\n\n**Try asking:**\n- Who are our top 10 customers by spending?\n- Show me monthly revenue trend for 2024\n- Best-selling products by category\n- Average order value by signup year",
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
  const [theme, setTheme] = useState('dark');
  const [chats, setChats] = useState([makeChat()]);
  const [activeChatId, setActiveChatId] = useState(chats[0].id);
  const [input, setInput] = useState('');
  const [isGenerating, setIsGenerating] = useState(false);
  const [pendingApproval, setPendingApproval] = useState(null); // { query }
  const bottomRef = useRef(null);
  const inputRef = useRef(null);

  const activeChat = chats.find(c => c.id === activeChatId) ?? chats[0];
  const messages = activeChat.messages;

  useEffect(() => {
    document.body.className = theme === 'dark' ? 'dark-theme' : '';
  }, [theme]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // ── Chat helpers ──────────────────────────────
  const updateChat = useCallback((chatId, updater) => {
    setChats(prev => prev.map(c => c.id === chatId ? updater(c) : c));
  }, []);

  const addMsg = useCallback((chatId, msg) => {
    setChats(prev => prev.map(c =>
      c.id === chatId ? { ...c, messages: [...c.messages, msg] } : c
    ));
  }, []);

  const updateMsg = useCallback((chatId, msgId, patch) => {
    setChats(prev => prev.map(c =>
      c.id === chatId
        ? { ...c, messages: c.messages.map(m => m.id === msgId ? { ...m, ...patch } : m) }
        : c
    ));
  }, []);

  const newChat = () => {
    const chat = makeChat();
    setChats(prev => [chat, ...prev]);
    setActiveChatId(chat.id);
    setPendingApproval(null);
    setInput('');
    inputRef.current?.focus();
  };

  // ── API call ──────────────────────────────────
  const callApi = useCallback(async (payload, chatId, agentMsgId, initialSteps) => {
    const MAX_RETRIES = 2;
    let lastError = null;

    for (let attempt = 0; attempt <= MAX_RETRIES; attempt++) {
      try {
        const res = await fetch('http://localhost:8000/api/chat', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload),
        });
        const data = await res.json();

        if (!res.ok) throw new Error(data.detail || `Server error ${res.status}`);

        if (data.requires_approval) {
          setPendingApproval({ query: payload.query });
          updateMsg(chatId, agentMsgId, {
            status: 'done',
            steps: data.steps ?? initialSteps,
            content: data.answer,
            requires_approval: true,
            generated_sql: data.generated_sql,
            isError: false,
          });
        } else {
          setPendingApproval(null);
          updateMsg(chatId, agentMsgId, {
            status: 'done',
            steps: data.steps ?? initialSteps,
            content: data.answer,
            requires_approval: false,
            chart_config: data.chart_config,
            data: data.data,
            row_count: data.row_count,
            generated_sql: data.generated_sql,
            isError: false,
          });
        }
        return; // success — exit
      } catch (err) {
        lastError = err;
        if (attempt < MAX_RETRIES) {
          // brief wait before retry (exponential: 1s, 2s)
          await new Promise(r => setTimeout(r, 1000 * (attempt + 1)));
          updateMsg(chatId, agentMsgId, {
            steps: [...initialSteps, `Retrying… (attempt ${attempt + 2}/${MAX_RETRIES + 1})`],
          });
        }
      }
    }

    // All retries exhausted
    updateMsg(chatId, agentMsgId, {
      status: 'done',
      steps: initialSteps,
      content: `**Error:** ${lastError?.message ?? 'Unknown error'}`,
      isError: true,
    });
  }, [updateMsg]);

  // ── Submit query ──────────────────────────────
  const handleSubmit = async (queryText) => {
    const q = (queryText ?? input).trim();
    if (!q || isGenerating) return;

    const chatId = activeChatId;
    const userMsgId = genId();
    const agentMsgId = genId();

    const userMsg = { id: userMsgId, role: 'user', content: q, status: 'done' };
    const initialSteps = [
      'Analyzing intent and selecting relevant tables…',
      'Generating PostgreSQL query from schema…',
    ];
    const agentMsg = { id: agentMsgId, role: 'agent', content: '', status: 'thinking', steps: initialSteps };

    // Auto-title the chat from first user message
    if (activeChat.messages.length === 1 && activeChat.title === 'New Chat') {
      updateChat(chatId, c => ({ ...c, title: autoTitle(q) }));
    }

    setChats(prev => prev.map(c =>
      c.id === chatId ? { ...c, messages: [...c.messages, userMsg, agentMsg] } : c
    ));
    setInput('');
    setIsGenerating(true);

    await callApi({ query: q, is_approved: false }, chatId, agentMsgId, initialSteps);
    setIsGenerating(false);
  };

  // ── Retry last query ──────────────────────────
  const handleRetry = () => {
    const lastUser = [...messages].reverse().find(m => m.role === 'user');
    if (lastUser) handleSubmit(lastUser.content);
  };

  // ── HITL approve / reject ─────────────────────
  const handleApprove = async () => {
    if (!pendingApproval) return;
    const chatId = activeChatId;
    const agentMsgId = genId();
    const steps = ['Executing approved modification…', 'Generating confirmation…'];
    addMsg(chatId, { id: agentMsgId, role: 'agent', content: '', status: 'thinking', steps });
    setIsGenerating(true);
    await callApi({ query: pendingApproval.query, is_approved: true }, chatId, agentMsgId, steps);
    setIsGenerating(false);
  };

  const handleReject = () => {
    setPendingApproval(null);
    const chatId = activeChatId;
    addMsg(chatId, {
      id: genId(), role: 'agent', status: 'done', steps: [],
      content: 'Action **rejected**. No data was modified.',
    });
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSubmit(); }
  };

  // ─────────────────────────────────────────────
  return (
    <div className="app">
      {/* ── Sidebar ── */}
      <aside className="sidebar">
        {/* Logo */}
        <div className="sidebar-logo">
          <div className="logo-icon"><Database size={20} color="white" /></div>
          <div>
            <p className="logo-title">NL-to-SQL</p>
            <p className="logo-sub">Powered by LangGraph</p>
          </div>
        </div>

        {/* New chat */}
        <div className="sidebar-actions">
          <button className="btn-new-chat" onClick={newChat}>
            <Plus size={15} /> New Chat
          </button>
          <button
            className="btn-theme"
            onClick={() => setTheme(t => t === 'dark' ? 'light' : 'dark')}
            title="Toggle theme"
          >
            {theme === 'dark' ? <Sun size={15} /> : <Moon size={15} />}
          </button>
        </div>

        {/* Chat history */}
        <div className="sidebar-section-label">Chats</div>
        <nav className="chat-list">
          {chats.map(chat => (
            <ChatEntry
              key={chat.id}
              chat={chat}
              isActive={chat.id === activeChatId}
              onClick={() => { setActiveChatId(chat.id); setPendingApproval(null); }}
            />
          ))}
        </nav>

        {/* Sample queries */}
        <div className="sidebar-section-label" style={{ marginTop: 'auto', paddingTop: '1rem' }}>
          Sample Queries
        </div>
        <div className="sample-list">
          {SAMPLE_QUERIES.map(q => (
            <button key={q} className="sample-query" onClick={() => setInput(q)}>
              {q}
            </button>
          ))}
        </div>
      </aside>

      {/* ── Main chat ── */}
      <main className="chat-main">
        {/* Messages */}
        <div className="chat-scroll">
          <div className="chat-feed">
            {messages.map((msg, idx) => (
              <ChatMessage
                key={msg.id}
                message={msg}
                onRetry={handleRetry}
                onApprove={handleApprove}
                onReject={handleReject}
              />
            ))}
            <div ref={bottomRef} />
          </div>
        </div>

        {/* Input */}
        <div className="input-wrap">
          <div className={`input-box ${isGenerating ? 'is-loading' : ''}`}>
            <textarea
              ref={inputRef}
              className="chat-textarea"
              placeholder="Ask anything about your database…"
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              disabled={isGenerating}
              rows={1}
            />
            <button
              className="btn-send"
              onClick={() => handleSubmit()}
              disabled={!input.trim() || isGenerating}
            >
              {isGenerating
                ? <Loader2 size={16} className="spin" style={{ color: 'white' }} />
                : <ArrowUp size={16} />}
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
