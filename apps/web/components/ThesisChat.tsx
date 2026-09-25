"use client";

import { FormEvent, useMemo, useState } from "react";
import { Bot, Loader2, Send, Sparkles } from "lucide-react";
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
  const userMessages = useMemo(() => messages.filter((message) => message.role === "user").map((message) => message.text), [messages]);

  async function send(event: FormEvent) {
    event.preventDefault();
    const message = text.trim();
    if (!message || busy) return;
    const history = [...messages, { role: "user" as const, text: message }];
    setMessages(history); setText(""); setBusy(true); setError("");
    try {
      const response = await api<ChatResponse>("/v1/research/chat", { method: "POST", body: JSON.stringify({ history, messages: [...userMessages, message], sector: "", max_holdings: 8, max_weight: 0.25, weighting: "theme" }) });
      setMessages((current) => [...current, { role: "assistant", text: response.message }]);
      setProposal(response.proposal); setWarnings(response.warnings ?? []);
    } catch (reason) { setError(reason instanceof Error ? reason.message : "The research assistant could not respond."); }
    finally { setBusy(false); }
  }
  async function create() { if (!proposal || applying) return; setApplying(true); setError(""); try { await onCreate(proposal); } catch (reason) { setError(reason instanceof Error ? reason.message : "Could not create this custom ETF."); } finally { setApplying(false); } }

  return <section className="thesis-chat" aria-label="Custom basket thesis assistant">
    <header><div className="chat-icon"><Sparkles size={16} /></div><div><span>AI BASKET COPILOT</span><h3>Turn an idea into a custom basket</h3></div><small>Draft only</small></header>
    <div className="chat-messages">{messages.map((message, index) => <div className={`chat-message ${message.role}`} key={`${message.role}-${index}`}><Bot size={14} /><p>{message.text}</p></div>)}{busy && <div className="chat-message assistant"><Loader2 className="spin" size={14} /><p>Researching your thesis…</p></div>}</div>
    {error && <p className="chat-error">{error}</p>}
    {proposal && <div className="chat-proposal"><div><span>PROPOSAL READY</span><strong>{proposal.name}</strong><small>{proposal.holdings.length} holdings · review every position before saving</small></div><button className="primary" onClick={create} disabled={applying}>{applying ? <Loader2 className="spin" size={15} /> : <Sparkles size={15} />} Create Custom ETF</button></div>}
    {warnings.length > 0 && <p className="chat-warning">{warnings[0]}</p>}
    <form onSubmit={send}><input value={text} onChange={(event) => setText(event.target.value)} placeholder="Describe a theme, assets to include, or constraints…" aria-label="Describe your investment theme" /><button aria-label="Send message" disabled={!text.trim() || busy}><Send size={16} /></button></form>
    <footer>Uses grounded research and listed proxies for cross-asset exposure. Historical results are not predictions.</footer>
  </section>;
}
