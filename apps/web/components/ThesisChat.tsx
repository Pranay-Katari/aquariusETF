"use client";

import { FormEvent, useMemo, useState } from "react";
import { ArrowUp, Bot, Check, Loader2, RotateCcw, Sparkles } from "lucide-react";
import { api } from "@/lib/api";
import type { Holding } from "@/lib/types";

type ChatMessage = { role: "user" | "assistant"; text: string };
type Proposal = { name: string; description: string; symbol?: string; holdings: Holding[] };
type ChatResponse = { message: string; proposal: Proposal | null; warnings?: string[] };

export default function ThesisChat({ onCreate }: { onCreate: (proposal: Proposal) => void | Promise<void> }) {
  const [messages, setMessages] = useState<ChatMessage[]>([{ role: "assistant", text: "What investment theme do you want to explore? I can help shape a basket across stocks and listed funds for bonds, commodities, or crypto exposure." }]);
  const [text, setText] = useState("");
  const [proposal, setProposal] = useState<Proposal | null>(null);
  const [warnings, setWarnings] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [applying, setApplying] = useState(false);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const userMessages = useMemo(() => messages.filter((message) => message.role === "user").map((message) => message.text), [messages]);

  async function send(event: FormEvent) {
    event.preventDefault();
    const message = text.trim();
    if (!message || busy) return;
    const history = [...messages, { role: "user" as const, text: message }];
    setMessages(history); setText(""); setBusy(true); setError("");
    try {
      const response = await api<ChatResponse & { conversation_id?: string }>("/v1/research/chat", { method: "POST", body: JSON.stringify({ conversation_id: conversationId, history, messages: [...userMessages, message], current_proposal: proposal, sector: "", max_holdings: 8, max_weight: 0.25, weighting: "theme" }) });
      setMessages((current) => [...current, { role: "assistant", text: response.message }]);
      setProposal(response.proposal); setWarnings(response.warnings ?? []);
      if (response.conversation_id) setConversationId(response.conversation_id);
    } catch (reason) { setError(reason instanceof Error ? reason.message : "The research assistant could not respond."); }
    finally { setBusy(false); }
  }
  async function create() { if (!proposal || applying) return; setApplying(true); setError(""); try { await onCreate(proposal); } catch (reason) { setError(reason instanceof Error ? reason.message : "Could not create this custom ETF."); } finally { setApplying(false); } }
  function reset() { setMessages([{ role: "assistant", text: "Tell me the investment view you want to test. I’ll clarify the theme, asset mix, and constraints before proposing a basket." }]); setProposal(null); setWarnings([]); setError(""); setConversationId(null); }

  return <section className="thesis-chat" aria-label="Custom basket thesis assistant">
    <header><div className="chat-icon"><Sparkles size={17} /></div><div><h3>Basket Copilot</h3><span>Grounded portfolio research</span></div><button className="chat-reset" onClick={reset} type="button"><RotateCcw size={14}/> New chat</button></header>
    <div className="chat-intro"><h2>What would you like to invest in?</h2><p>Describe a theme, a macro view, or assets you want included. I’ll ask only what is needed to build a testable basket.</p><div>{["AI infrastructure", "Rate-cut beneficiaries", "Gold and bitcoin hedge"].map(prompt => <button type="button" key={prompt} onClick={()=>setText(prompt)}>{prompt}</button>)}</div></div>
    <div className="chat-messages">{messages.map((message, index) => <div className={`chat-message ${message.role}`} key={`${message.role}-${index}`}>{message.role === "assistant" && <Bot size={15} />}<p>{message.text}</p></div>)}{busy && <div className="chat-message assistant"><Loader2 className="spin" size={15} /><p>Checking context and shaping your brief…</p></div>}</div>
    {error && <p className="chat-error">{error}</p>}
    {proposal && <div className="chat-proposal"><div><span>Ready to review</span><strong>{proposal.name}</strong><small>{proposal.holdings.length} holdings · weights are editable</small></div><button className="primary" onClick={create} disabled={applying}>{applying ? <Loader2 className="spin" size={15} /> : <Check size={15} />} Open basket</button></div>}
    {warnings.length > 0 && <p className="chat-warning">{warnings[0]}</p>}
    <form onSubmit={send}><textarea value={text} onChange={(event) => setText(event.target.value)} placeholder="Message Basket Copilot…" aria-label="Describe your investment theme" rows={1}/><button aria-label="Send message" disabled={!text.trim() || busy}><ArrowUp size={18} /></button></form>
    <footer>Retrieval-grounded context · Listed instruments only · Not investment advice</footer>
  </section>;
}
