"use client";

import { ArrowRight, BarChart3, CheckCircle2, LineChart, ShieldCheck, Sparkles } from "lucide-react";
import { useRouter } from "next/navigation";

const proof = ["Build a focused basket", "Test any historical entry date", "Compare against SPY or QQQ"];

export default function Landing() {
  const router = useRouter();
  return <main className="landing">
    <nav className="landing-nav"><button className="landing-brand" onClick={() => router.push("/")}>aquarius<span>BASKETS</span></button><div><button className="nav-login" onClick={() => router.push("/login")}>Log in</button><button className="nav-start" onClick={() => router.push("/login")}>Start building <ArrowRight size={15} /></button></div></nav>
    <section className="landing-hero">
      <div className="hero-copy"><div className="eyebrow"><Sparkles size={13} /> YOUR INVESTING THESIS, MADE TESTABLE</div><h1>Turn an idea into<br /><em>an investable view.</em></h1><p>Build a custom basket of stocks and listed ETFs, model when you would have entered, and see how your thesis held up against the market.</p><div className="hero-actions"><button className="hero-primary" onClick={() => router.push("/login")}>Create your basket <ArrowRight size={17} /></button><button className="hero-secondary" onClick={() => router.push("/dashboard")}>Explore the studio</button></div><div className="hero-proof">{proof.map((item) => <span key={item}><CheckCircle2 size={15} />{item}</span>)}</div></div>
      <div className="hero-terminal"><div className="terminal-top"><span /><span /><span /><p>aquarius / simulation</p><b>LIVE MODEL</b></div><div className="terminal-body"><div className="terminal-label">THEMATIC BASKET</div><div className="terminal-name">AI Infrastructure <span>• CUSTOM</span></div><div className="terminal-grid"><div><span>Starting value</span><strong>$10,000</strong></div><div><span>Selected entry</span><strong>5 years ago</strong></div></div><div className="terminal-chart"><svg viewBox="0 0 460 170" preserveAspectRatio="none" aria-hidden="true"><defs><linearGradient id="fill" x1="0" x2="0" y1="0" y2="1"><stop stopColor="#61f2d2" stopOpacity=".43" /><stop offset="1" stopColor="#61f2d2" stopOpacity="0" /></linearGradient></defs><path d="M0 146 L22 141 L48 143 L70 126 L94 130 L120 105 L145 112 L170 91 L193 101 L222 82 L245 94 L268 56 L295 74 L318 51 L342 58 L365 31 L390 47 L420 18 L460 27 V170 H0Z" fill="url(#fill)" /><path d="M0 146 L22 141 L48 143 L70 126 L94 130 L120 105 L145 112 L170 91 L193 101 L222 82 L245 94 L268 56 L295 74 L318 51 L342 58 L365 31 L390 47 L420 18 L460 27" fill="none" stroke="#61f2d2" strokeWidth="3" /></svg></div><div className="terminal-return"><span>Hypothetical return</span><strong>+182.4%</strong><small>vs. +96.8% benchmark</small></div></div></div>
    </section>
    <section className="landing-features"><article><span className="feature-icon"><Sparkles size={20} /></span><h2>Start with a thesis</h2><p>Choose the companies and allocations that reflect your point of view.</p></article><article><span className="feature-icon"><LineChart size={20} /></span><h2>Test the timing</h2><p>Model what would have happened had you entered one week or five years ago.</p></article><article><span className="feature-icon"><BarChart3 size={20} /></span><h2>Understand the outcome</h2><p>See returns, drawdowns, and benchmark context in one clear workspace.</p></article><article><span className="feature-icon"><ShieldCheck size={20} /></span><h2>Built for decisions</h2><p>Save portfolio versions and retain the assumptions behind every simulation.</p></article></section>
    <footer className="landing-footer"><span>© 2026 Aquarius Baskets</span><span>For research and simulation only. Not investment advice.</span></footer>
  </main>;
}
