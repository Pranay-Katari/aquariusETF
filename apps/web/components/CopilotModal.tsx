"use client";

import { X } from "lucide-react";
import ThesisChat from "./ThesisChat";
import type { Holding } from "@/lib/types";

type Proposal = { name: string; description: string; symbol?: string; holdings: Holding[] };

export default function CopilotModal({ open, onClose, onApply }: { open: boolean; onClose: () => void; onApply: (proposal: Proposal) => Promise<void> }) {
  if (!open) return null;
  return <div className="copilot-overlay" role="dialog" aria-modal="true" aria-label="AI Basket Copilot">
    <div className="copilot-modal"><button className="copilot-close" onClick={onClose} aria-label="Close AI Basket Copilot"><X size={18} /></button><ThesisChat onCreate={onApply} /></div>
    <style jsx global>{`
      .copilot-overlay{position:fixed;inset:0;z-index:50;display:grid;place-items:center;padding:22px;background:rgba(3,12,27,.76);backdrop-filter:blur(9px)}.copilot-modal{position:relative;width:min(680px,100%);max-height:min(760px,calc(100dvh - 44px));overflow:auto;border:1px solid #31557b;border-radius:16px;background:#0b1a30;box-shadow:0 28px 90px rgba(0,0,0,.48)}.copilot-close{position:absolute;z-index:2;top:15px;right:15px;display:grid;width:34px;height:34px;place-items:center;border:1px solid #355477;border-radius:9px;background:#10213a;color:#e8f1ff}.thesis-chat header{display:flex;align-items:center;gap:12px;padding:24px 62px 20px 24px;border-bottom:1px solid #254663}.chat-icon{display:grid;width:38px;height:38px;place-items:center;border-radius:11px;background:#124a4b;color:#57e1d2}.thesis-chat header span,.chat-proposal span{color:#64ddd3;font:700 10px "DM Mono",monospace;letter-spacing:.1em}.thesis-chat header h3{margin:5px 0 0;font-size:18px}.thesis-chat header small{margin-left:auto;color:#9db2cb}.chat-messages{display:grid;gap:13px;max-height:290px;overflow:auto;padding:22px 24px}.chat-message{display:flex;gap:9px;align-items:flex-start}.chat-message svg{flex:0 0 auto;margin-top:5px;color:#55d9d1}.chat-message p{max-width:88%;margin:0;padding:12px 14px;border-radius:11px;background:#132a47;color:#dce8fa;line-height:1.5}.chat-message.user{justify-content:flex-end}.chat-message.user p{background:#214861}.chat-proposal{display:flex;align-items:center;justify-content:space-between;gap:15px;margin:0 24px 15px;padding:14px;border:1px solid #276568;border-radius:11px;background:#0d2a35}.chat-proposal strong,.chat-proposal small{display:block;margin-top:5px}.chat-proposal small,.chat-warning,.chat-error,.thesis-chat footer{color:#9bb1c9;font-size:11px}.chat-proposal .primary{display:flex;align-items:center;gap:7px;border:0;border-radius:9px;padding:11px 13px;background:#4fd5c6;color:#061629;font-weight:800}.chat-error,.chat-warning{margin:0 24px 14px}.chat-error{color:#ffbdc7}.thesis-chat form{display:flex;gap:10px;padding:0 24px 13px}.thesis-chat form input{min-width:0;flex:1;border:1px solid #355779;border-radius:10px;background:#09172a;color:#edf4ff;padding:13px;outline:0}.thesis-chat form button{display:grid;width:46px;place-items:center;border:0;border-radius:10px;background:#48cfc1;color:#062035}.thesis-chat footer{display:block;padding:0 24px 20px;line-height:1.5}@media(max-width:520px){.copilot-overlay{padding:12px}.chat-proposal{align-items:stretch;flex-direction:column}.chat-proposal .primary{justify-content:center}}
    `}</style>
  </div>;
}
