"use client";

import { ArrowRight, ChevronRight } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect } from "react";
import { supabase } from "@/lib/api";

export default function Landing() {
  const router = useRouter();

  // Supabase can fall back to the configured site URL after OAuth.  If that
  // URL is the landing page, continue an authenticated user into the studio
  // instead of presenting a second sign-in button.
  useEffect(() => {
    if (!supabase) return;
    let active = true;
    supabase.auth.getSession().then(({ data: { session } }) => {
      if (active && session) router.replace("/dashboard");
    });
    return () => {
      active = false;
    };
  }, [router]);

  return (
    <main
      className="gradient-home"
      style={{ width: "100%", margin: 0, minHeight: "100dvh" }}
    >
      <div className="orb orb-a" />
      <div className="orb orb-b" />
      <div className="ray ray-a" />
      <div className="ray ray-b" />

      <nav>
        <button className="brand" onClick={() => router.push("/")}>
          aquarius<span>baskets</span>
        </button>
        <div className="nav-actions">
          <button className="link-button" onClick={() => router.push("/dashboard")}>
            Explore
          </button>
          <button className="start-button" onClick={() => router.push("/dashboard")}>
            Start building <ChevronRight size={16} />
          </button>
        </div>
      </nav>

      <section className="gradient-hero">
        <div className="copy">
          <p>MAKE YOUR THESIS TESTABLE</p>
          <h1>
            Build the view
            <br />
            before the <i>market</i> moves.
          </h1>
          <span>
            Turn an investment idea into a balanced basket, test it against history,
            and understand the risk in a few focused steps.
          </span>
          <div className="hero-actions">
            <button className="primary" onClick={() => router.push("/dashboard")}>
              Create a basket <ArrowRight size={17} />
            </button>
            <button className="secondary" onClick={() => router.push("/dashboard")}>
              Explore the studio
            </button>
          </div>
        </div>

        <div className="stack" aria-hidden="true">
          <div className="floating-card thesis-card">
            <small>01 · THESIS</small>
            <strong>AI power demand</strong>
            <p>Data centers need more energy.</p>
            <div className="card-line"><b /></div>
          </div>
          <div className="floating-card test-card">
            <small>BACKTEST · 5 YEARS</small>
            <div className="metric"><span>+18.4%</span><em>CAGR</em></div>
            <div className="spark"><i /><i /><i /><i /><i /><i /><i /></div>
            <p>vs SPY&nbsp; +12.1%</p>
          </div>
          <div className="floating-card risk-card">
            <small>RISK SIGNAL</small>
            <strong><b /> Balanced</strong>
            <p>Drawdown within target range</p>
          </div>
        </div>
      </section>

      <footer>
        <span>Build a focused basket</span>
        <i />
        <span>Test it against history</span>
        <i />
        <span>Make the next decision clearer</span>
      </footer>

      <style jsx>{`
        .gradient-home {
          box-sizing: border-box;
          overflow: hidden;
          position: relative;
          isolation: isolate;
          padding: 0 clamp(22px, 6vw, 82px) 42px;
          color: #07152c;
          background: linear-gradient(118deg, #63cbd5 0%, #70badf 44%, #8576e8 100%);
        }
        .orb, .ray { position: absolute; pointer-events: none; z-index: -1; }
        .orb { border-radius: 999px; filter: blur(1px); opacity: .42; }
        .orb-a { width: 42vw; height: 42vw; right: -12vw; top: -18vw; background: #b7a3ff; animation: orbit 12s ease-in-out infinite alternate; }
        .orb-b { width: 32vw; height: 32vw; left: -15vw; bottom: -14vw; background: #8ce4d9; animation: orbit 15s ease-in-out infinite alternate-reverse; }
        .ray { width: 65vw; height: 1px; background: rgba(255,255,255,.42); transform: rotate(-28deg); }
        .ray-a { right: -18vw; top: 26%; animation: ray 9s ease-in-out infinite; }
        .ray-b { left: -28vw; bottom: 11%; opacity: .5; animation: ray 12s ease-in-out infinite reverse; }
        nav { height: 84px; display: flex; align-items: center; justify-content: space-between; }
        button { font: inherit; cursor: pointer; }
        .brand { border: 0; background: transparent; padding: 0; font: 800 22px/1 "Manrope", sans-serif; letter-spacing: -.08em; color: #07152c; }
        .brand span { color: #fff; }
        .nav-actions, .hero-actions { display: flex; align-items: center; gap: 14px; }
        .link-button { border: 0; background: transparent; color: rgba(7,21,44,.73); font-weight: 700; }
        .start-button, .primary { display: inline-flex; align-items: center; gap: 8px; border: 0; border-radius: 999px; color: white; background: #081a35; box-shadow: 0 9px 22px rgba(6,18,42,.19); font-weight: 800; }
        .start-button { padding: 11px 16px; font-size: 13px; }
        .gradient-hero { min-height: calc(100dvh - 176px); display: flex; align-items: center; justify-content: space-between; gap: 48px; max-width: 1200px; margin: 0 auto; }
        .copy { max-width: 640px; padding: 44px 0; }
        .copy > p { margin: 0 0 18px; font: 700 11px/1 "DM Mono", monospace; letter-spacing: .15em; color: rgba(7,21,44,.68); }
        h1 { margin: 0; font: 800 clamp(47px, 6.2vw, 86px)/.98 "Manrope", sans-serif; letter-spacing: -.075em; }
        h1 i { color: #fff; font-style: normal; text-shadow: 0 4px 24px rgba(68,49,163,.22); }
        .copy > span { display: block; max-width: 500px; margin-top: 25px; color: rgba(7,21,44,.73); font: 500 16px/1.65 "Manrope", sans-serif; }
        .hero-actions { margin-top: 31px; }
        .primary { padding: 15px 21px; font-size: 14px; }
        .secondary { padding: 14px 8px; border: 0; background: transparent; color: #07152c; font-weight: 800; }
        .stack { position: relative; width: min(420px, 36vw); height: 350px; flex: 0 0 auto; }
        .floating-card { position: absolute; box-sizing: border-box; border: 1px solid rgba(255,255,255,.55); border-radius: 18px; padding: 20px; background: rgba(8,26,53,.88); color: #eff5ff; box-shadow: 0 25px 50px rgba(17,35,78,.24), inset 0 1px rgba(255,255,255,.08); backdrop-filter: blur(16px); }
        .floating-card small { display: block; font: 600 10px/1 "DM Mono", monospace; letter-spacing: .12em; color: #aebfe0; }
        .floating-card strong { display: block; margin-top: 12px; font: 800 18px/1.1 "Manrope", sans-serif; letter-spacing: -.04em; }
        .floating-card p { margin: 9px 0 0; color: #aebfe0; font: 500 11px/1.35 "Manrope", sans-serif; }
        .thesis-card { width: 270px; top: 15px; left: 16px; transform: rotate(-7deg); animation: drift-one 6s ease-in-out infinite; }
        .card-line { height: 5px; margin-top: 16px; overflow: hidden; border-radius: 10px; background: #263e69; }
        .card-line b { display: block; width: 72%; height: 100%; border-radius: inherit; background: linear-gradient(90deg, #53d4d5, #8376fb); }
        .test-card { width: 292px; right: 0; top: 100px; transform: rotate(7deg); animation: drift-two 7s ease-in-out infinite; }
        .metric { display: flex; align-items: baseline; gap: 8px; margin-top: 11px; }
        .metric span { color: #55e0d4; font: 800 29px/1 "DM Mono", monospace; letter-spacing: -.08em; }
        .metric em { color: #aebfe0; font: 600 9px/1 "DM Mono", monospace; font-style: normal; letter-spacing: .12em; }
        .spark { height: 26px; display: flex; align-items: end; gap: 5px; margin: 13px 0 0; }
        .spark i { display: block; flex: 1; border-radius: 4px 4px 0 0; background: linear-gradient(#786eff, #48d1d6); }
        .spark i:nth-child(1) { height: 25%; }.spark i:nth-child(2) { height: 40%; }.spark i:nth-child(3) { height: 31%; }.spark i:nth-child(4) { height: 56%; }.spark i:nth-child(5) { height: 52%; }.spark i:nth-child(6) { height: 76%; }.spark i:nth-child(7) { height: 100%; }
        .risk-card { width: 240px; bottom: 10px; left: 65px; transform: rotate(-2deg); animation: drift-three 5.5s ease-in-out infinite; }
        .risk-card strong b { display: inline-block; width: 9px; height: 9px; margin-right: 7px; border-radius: 50%; background: #5ce4c6; box-shadow: 0 0 0 5px rgba(92,228,198,.15); }
        footer { max-width: 1200px; margin: 0 auto; display: flex; align-items: center; gap: 16px; color: rgba(7,21,44,.72); font: 700 11px/1 "DM Mono", monospace; letter-spacing: .04em; }
        footer i { width: 4px; height: 4px; flex: 0 0 auto; border-radius: 50%; background: rgba(7,21,44,.5); }
        @keyframes drift-one { 50% { transform: translate(6px,-11px) rotate(-4deg); } }
        @keyframes drift-two { 50% { transform: translate(-8px,9px) rotate(4deg); } }
        @keyframes drift-three { 50% { transform: translate(4px,-8px) rotate(1deg); } }
        @keyframes orbit { to { transform: translate(4vw,3vw) scale(1.09); } }
        @keyframes ray { 50% { opacity: .1; transform: rotate(-28deg) translateX(8vw); } }
        @media (max-width: 760px) {
          .gradient-home { padding-inline: 24px; }
          .link-button { display: none; }
          .gradient-hero { min-height: auto; display: block; padding-top: 20px; }
          .copy { padding-bottom: 28px; }
          .stack { width: 100%; max-width: 390px; height: 305px; margin: 0 auto; }
          footer { flex-wrap: wrap; gap: 10px; margin-top: 26px; }
        }
        @media (max-width: 430px) {
          h1 { font-size: 46px; }
          .copy > span { font-size: 14px; }
          .start-button { padding: 10px 12px; }
          .thesis-card { left: 0; }.test-card { right: 0; }.risk-card { left: 28px; }
          footer i { display: none; }
        }
      `}</style>
    </main>
  );
}
