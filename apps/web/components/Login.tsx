"use client";

import { ArrowLeft, ArrowRight, Chrome, Loader2, ShieldCheck } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { supabase } from "@/lib/api";

export default function Login() {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  async function signInWithGoogle() {
    if (!supabase) { setError("Supabase is not configured yet. Add the public Supabase URL and anon key to apps/web/.env.local."); return; }
    setBusy(true); setError("");
    const { error: authError } = await supabase.auth.signInWithOAuth({ provider: "google", options: { redirectTo: `${window.location.origin}/dashboard` } });
    if (authError) { setError(authError.message); setBusy(false); }
  }
  return <main className="login-page"><button className="login-back" onClick={() => router.push("/")}><ArrowLeft size={16} /> Back to Aquarius Baskets</button><section className="login-card"><div className="login-mark">A</div><span className="login-eyebrow">AQUARIUS BASKETS</span><h1>Welcome to your<br />investment workspace.</h1><p>Sign in to build, test, and keep track of your basket ideas.</p><button className="google-button" onClick={signInWithGoogle} disabled={busy}>{busy ? <Loader2 className="spin" size={18} /> : <Chrome size={18} />} Continue with Google <ArrowRight size={16} /></button>{error && <p className="login-error">{error}</p>}<div className="login-security"><ShieldCheck size={15} /> Secure sign-in via Supabase</div></section><aside className="login-art"><div><span>THE INVESTING WORKSPACE</span><h2>Ideas deserve<br /><em>better evidence.</em></h2><p>Research the past, test the present, and shape your next move.</p></div></aside></main>;
}
