"use client";
import { useEffect, useState, useCallback } from "react";
import { usePathname, useRouter } from "next/navigation";
import {
  Activity,
  ArrowDown,
  ArrowRight,
  ArrowUpRight,
  Bookmark,
  Check,
  ChevronDown,
  ChevronRight,
  Copy,
  Download,
  FlaskConical,
  FolderOpen,
  HelpCircle,
  Layers3,
  LayoutDashboard,
  Loader2,
  LogOut,
  Plus,
  Search,
  Settings2,
  ShieldCheck,
  Sparkles,
  Trash2,
  Waves,
  X,
} from "lucide-react";
import { api, supabase, money, pct, defaultConfig } from "@/lib/api";
import type {
  ETF,
  Holding,
  Config,
  Backtest,
  Series,
  Attribution,
  Preview,
} from "@/lib/types";
import PerformanceChart from "./PerformanceChart";
import Diagnostics from "./Diagnostics";
import Compare from "./Compare";
const colors = [
  "#3c8268",
  "#719b88",
  "#a7c5b4",
  "#547d92",
  "#88a7b8",
  "#b5c6cf",
  "#b4a383",
  "#d2c4a9",
  "#9b91b4",
  "#c4b9d5",
];
const blank = (): Omit<
  ETF,
  "id" | "version" | "created_at" | "updated_at"
> => ({
  name: "Untitled portfolio",
  symbol: "CUSTOM",
  description: "",
  holdings: [],
});
const demoHoldings: Holding[] = [
  ["NVDA", "NVIDIA", "Accelerated computing", 0.18],
  ["AVGO", "Broadcom", "Semiconductors", 0.15],
  ["VRT", "Vertiv", "Power & cooling", 0.12],
  ["ANET", "Arista Networks", "Networking", 0.1],
  ["MSFT", "Microsoft", "Cloud platforms", 0.15],
  ["AMZN", "Amazon", "Cloud platforms", 0.1],
  ["GOOGL", "Alphabet", "Cloud platforms", 0.1],
  ["AMD", "Advanced Micro Devices", "Semiconductors", 0.1],
].map(([ticker, company_name, theme_tag, target_weight]) => ({
  ticker: String(ticker),
  company_name: String(company_name),
  theme_tag: String(theme_tag),
  target_weight: Number(target_weight),
  rationale: "",
  sources: [],
}));

export default function Workspace() {
  const router = useRouter(),
    pathname = usePathname();
  const [etfs, setEtfs] = useState<ETF[]>([]),
    [selected, setSelected] = useState<ETF | null>(null),
    [draft, setDraft] = useState(blank()),
    [config, setConfig] = useState<Config>(defaultConfig),
    [runs, setRuns] = useState<Backtest[]>([]),
    [result, setResult] = useState<Backtest | null>(null),
    [series, setSeries] = useState<Series | null>(null),
    [attribution, setAttribution] = useState<Attribution[]>([]);
  const [health, setHealth] = useState<{
      mode: string;
      market_provider: string;
      paper_enabled: boolean;
      research_mode: string;
    } | null>(null),
    [ready, setReady] = useState(false),
    [busy, setBusy] = useState(""),
    [error, setError] = useState(""),
    [notice, setNotice] = useState(""),
    [tab, setTab] = useState("Overview"),
    [range, setRange] = useState("5Y"),
    [normalized, setNormalized] = useState(false);
  const [modal, setModal] = useState<
      "research" | "stock" | "settings" | "trade" | "help" | "compare" | null
    >(null),
    [researchHolding, setResearchHolding] = useState<Holding | null>(null),
    [prompt, setPrompt] = useState(
      "Build a portfolio of AI data center infrastructure companies",
    ),
    [maxNames, setMaxNames] = useState(8),
    [maxWeight, setMaxWeight] = useState(25),
    [query, setQuery] = useState(""),
    [symbols, setSymbols] = useState<
      { ticker: string; company_name: string; theme_tag: string }[]
    >([]),
    [preview, setPreview] = useState<Preview | null>(null),
    [investment, setInvestment] = useState(10000),
    [tradeConfirmed, setTradeConfirmed] = useState(false),
    [email, setEmail] = useState(""),
    [password, setPassword] = useState(""),
    [authed, setAuthed] = useState(false);
  const isDashboard = pathname === "/dashboard";
  const dirty = selected
    ? JSON.stringify({
        name: selected.name,
        symbol: selected.symbol,
        description: selected.description,
        holdings: selected.holdings,
      }) !== JSON.stringify(draft)
    : true;
  const total = draft.holdings.reduce((a, h) => a + h.target_weight, 0),
    valid =
      draft.holdings.length > 0 &&
      Math.abs(total - 1) < 1e-6 &&
      draft.holdings.every(
        (h) =>
          Number.isFinite(h.target_weight) &&
          h.target_weight >= 0 &&
          h.target_weight <= 1,
      );
  const stale =
    !!result && (dirty || result.portfolio_version !== selected?.version);
  const activeJob = result?.status === "queued" || result?.status === "running";
  const loadList = useCallback(async () => {
    const list = await api<ETF[]>("/v1/etfs");
    setEtfs(list);
    return list;
  }, []);
  const openPortfolio = useCallback(async (etf: ETF) => {
    setSelected(etf);
    setDraft({
      name: etf.name,
      symbol: etf.symbol,
      description: etf.description,
      holdings: etf.holdings,
    });
    setSeries(null);
    setAttribution([]);
    const history = await api<Backtest[]>(`/v1/etfs/${etf.id}/backtests`);
    setRuns(history);
    setResult(history[0] || null);
    if (history[0]) setConfig(history[0].config);
    setTab("Overview");
  }, []);
  async function action(label: string, fn: () => Promise<void>) {
    setBusy(label);
    setError("");
    setNotice("");
    try {
      await fn();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong");
    } finally {
      setBusy("");
    }
  }
  useEffect(() => {
    api<typeof health>("/health")
      .then(setHealth)
      .catch((e) => setError(e.message));
    if (supabase) {
      supabase.auth.getSession().then(({ data }) => setAuthed(!!data.session));
      const { data } = supabase.auth.onAuthStateChange((_event, session) =>
        setAuthed(!!session),
      );
      return () => data.subscription.unsubscribe();
    } else setAuthed(true);
  }, []);
  useEffect(() => {
    if (!authed) return;
    let canceled = false;
    loadList()
      .then(async (list) => {
        if (canceled) return;
        const id = pathname.split("/")[2];
        const etf =
          id && id !== "new" ? list.find((e) => e.id === id) : list[0];
        if (id && id !== "new" && !etf)
          throw new Error("Portfolio not found in this workspace.");
        if (pathname === "/etf/new") {
          setSelected(null);
          setDraft(blank());
          setResult(null);
        } else if (etf) {
          await openPortfolio(etf);
          const section = pathname.split("/")[3],
            runId = pathname.split("/")[4];
          if (section === "research") setTab("Research");
          if (section === "backtests") {
            if (runId) {
              const r = await api<Backtest>(`/v1/backtests/${runId}`);
              if (r.etf_id !== etf.id)
                throw new Error("Backtest does not belong to this portfolio");
              setResult(r);
              setConfig(r.config);
            } else setTab("Backtest history");
          }
          if (section === "trade") {
            setPreview(null);
            setModal("trade");
          }
        } else {
          setDraft({
            name: "AI Infrastructure",
            symbol: "AICORE",
            description:
              "The building blocks of an AI-powered world. A focused basket spanning compute, connectivity, and cloud.",
            holdings: demoHoldings,
          });
          setSelected(null);
        }
        setReady(true);
      })
      .catch((e) => {
        setError(e.message);
        setReady(true);
      });
    return () => {
      canceled = true;
    };
  }, [authed, pathname, loadList, openPortfolio]);
  useEffect(() => {
    if (!result || !activeJob) return;
    const timer = setInterval(() => {
      api<Backtest>(`/v1/backtests/${result.id}`)
        .then((r) => {
          setResult(r);
          if (r.status === "failed") setError(r.error || "Backtest failed");
          if (!["queued", "running"].includes(r.status))
            setRuns((old) => [r, ...old.filter((x) => x.id !== r.id)]);
        })
        .catch((e) => setError(e.message));
    }, 900);
    return () => clearInterval(timer);
  }, [result?.id, activeJob]);
  useEffect(() => {
    if (result?.status !== "completed") {
      setSeries(null);
      return;
    }
    let canceled = false;
    Promise.all([
      api<Series>(`/v1/backtests/${result.id}/series?range=${range}`),
      api<Attribution[]>(`/v1/backtests/${result.id}/attribution`),
    ])
      .then(([s, a]) => {
        if (!canceled) {
          setSeries(s);
          setAttribution(a);
        }
      })
      .catch((e) => setError(e.message));
    return () => {
      canceled = true;
    };
  }, [result?.id, result?.status, range]);
  useEffect(() => {
    if (modal !== "stock") return;
    let canceled = false;
    api<typeof symbols>(`/v1/market/symbols?q=${encodeURIComponent(query)}`)
      .then((s) => {
        if (!canceled) setSymbols(s);
      })
      .catch((e) => setError(e.message));
    return () => {
      canceled = true;
    };
  }, [query, modal]);
  useEffect(() => {
    if (!modal && !researchHolding) return;
    const previous = document.activeElement as HTMLElement | null;
    const dialog = document.querySelector<HTMLElement>("[role=dialog]");
    const focusable = () =>
      Array.from(
        dialog?.querySelectorAll<HTMLElement>(
          'button:not(:disabled),a[href],input:not(:disabled),select,textarea,[tabindex="0"]',
        ) || [],
      ).filter((el) => el.getClientRects().length > 0);
    focusable()[0]?.focus();
    const trap = (e: KeyboardEvent) => {
      if (e.key !== "Tab") return;
      const items = focusable(),
        first = items[0],
        last = items.at(-1);
      if (e.shiftKey && document.activeElement === first) {
        e.preventDefault();
        last?.focus();
      } else if (!e.shiftKey && document.activeElement === last) {
        e.preventDefault();
        first?.focus();
      }
    };
    document.addEventListener("keydown", trap);
    const close = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        setModal(null);
        setResearchHolding(null);
      }
    };
    window.addEventListener("keydown", close);
    return () => {
      window.removeEventListener("keydown", close);
      document.removeEventListener("keydown", trap);
      previous?.focus();
    };
  }, [modal, researchHolding]);
  async function save(): Promise<ETF> {
    if (!valid)
      throw new Error(
        "Holdings must have non-negative weights that total 100%.",
      );
    const etf = selected
      ? await api<ETF>(`/v1/etfs/${selected.id}`, {
          method: "PATCH",
          body: JSON.stringify({
            ...draft,
            expected_version: selected.version,
          }),
        })
      : await api<ETF>("/v1/etfs", {
          method: "POST",
          body: JSON.stringify(draft),
        });
    setSelected(etf);
    setDraft({
      name: etf.name,
      symbol: etf.symbol,
      description: etf.description,
      holdings: etf.holdings,
    });
    await loadList();
    return etf;
  }
  async function run() {
    await action("Generating backtest", async () => {
      const saved = dirty || !selected ? await save() : selected;
      const r = await api<Backtest>("/v1/backtests", {
        method: "POST",
        body: JSON.stringify({
          ...config,
          etf_id: saved.id,
          portfolio_version: saved.version,
        }),
      });
      setResult(r);
      setSeries(null);
      setTab("Overview");
      setRuns((old) => [r, ...old]);
    });
  }
  function changeWeight(i: number, value: string) {
    setDraft((d) => ({
      ...d,
      holdings: d.holdings.map((h, j) =>
        j === i ? { ...h, target_weight: Number(value) / 100 } : h,
      ),
    }));
  }
  function distribute(normalize: boolean) {
    setDraft((d) => ({
      ...d,
      holdings: d.holdings.map((h) => ({
        ...h,
        target_weight:
          normalize && total > 0
            ? h.target_weight / total
            : 1 / d.holdings.length,
      })),
    }));
  }
  function addStock(s: (typeof symbols)[number]) {
    if (draft.holdings.some((h) => h.ticker === s.ticker)) return;
    setDraft((d) => ({
      ...d,
      holdings: [
        ...d.holdings,
        { ...s, target_weight: 0, rationale: "", sources: [] },
      ],
    }));
    setModal(null);
    setQuery("");
    setNotice("Stock added at 0%. Set its weight or choose Equal weight.");
  }
  async function exportResult() {
    if (!result) return;
    await action("Exporting", async () => {
      const data = await api<object>(`/v1/backtests/${result.id}/artifact`);
      const url = URL.createObjectURL(
        new Blob([JSON.stringify(data, null, 2)], { type: "application/json" }),
      );
      const a = document.createElement("a");
      a.href = url;
      a.download = `aquarius-backtest-${result.id}.json`;
      a.click();
      URL.revokeObjectURL(url);
    });
  }
  const m = result?.status === "completed" ? result.metrics : {};
  if (health?.mode === "production" && (!authed || !supabase))
    return (
      <div className="login">
        <div className="brand">
          <Waves /> aquarius<span>®</span>
        </div>
        <h1>Your next idea starts here.</h1>
        <p>Sign in to your portfolio research workspace.</p>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            action("Signing in", async () => {
              if (!supabase)
                throw new Error(
                  "Configure public Supabase environment variables.",
                );
              const { error } = await supabase.auth.signInWithPassword({
                email,
                password,
              });
              if (error) throw error;
            });
          }}
        >
          <label>
            Email
            <input
              required
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />
          </label>
          <label>
            Password
            <input
              required
              type="password"
              minLength={8}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
          </label>
          {error && <p className="error">{error}</p>}
          <button className="primary" disabled={!!busy}>
            Sign in
          </button>
          <button
            type="button"
            onClick={() =>
              action("Creating account", async () => {
                if (!supabase) throw new Error("Supabase is not configured");
                const { error } = await supabase.auth.signUp({
                  email,
                  password,
                });
                if (error) throw error;
                setNotice(
                  "Check your email to confirm your account, then sign in.",
                );
              })
            }
          >
            Create account
          </button>
          {notice && <p>{notice}</p>}
        </form>
      </div>
    );
  return (
    <div className="app-shell">
      <aside className="sidebar">
        <a className="brand" href="/dashboard">
          <Waves size={27} /> aquarius<span>®</span>
        </a>
        <div className="workspace-switch">
          <div className="avatar small">P</div>
          <span>
            Personal workspace<small>Research & simulation</small>
          </span>
          <ChevronDown size={14} />
        </div>
        <div className="nav-caption">WORKSPACE</div>
        <nav>
          <button
            className={isDashboard ? "nav-item active" : "nav-item"}
            onClick={() => router.push("/dashboard")}
          >
            <LayoutDashboard size={17} /> Dashboard
          </button>
          <button
            className={!isDashboard ? "nav-item active" : "nav-item"}
            onClick={() => router.push(etfs[0] ? `/etf/${etfs[0].id}` : "/")}
          >
            <Layers3 size={17} /> Portfolio studio{" "}
            <span className="count">{etfs.length || 1}</span>
          </button>
          <button className="nav-item" onClick={() => setModal("research")}>
            <Sparkles size={17} /> Research lab{" "}
            <span className="tiny-badge">BETA</span>
          </button>
        </nav>
        <div className="nav-caption portfolio-caption">
          YOUR PORTFOLIOS
          <button
            title="Create portfolio"
            aria-label="Create portfolio"
            onClick={() => router.push("/etf/new")}
          >
            <Plus size={15} />
          </button>
        </div>
        <div className="portfolio-nav">
          {etfs.map((e, i) => (
            <button
              key={e.id}
              className={selected?.id === e.id ? "selected" : ""}
              onClick={() => router.push(`/etf/${e.id}`)}
            >
              <span
                className="portfolio-dot"
                style={{ background: colors[i % colors.length] }}
              />
              {e.name}
            </button>
          ))}
          {etfs.length === 0 && (
            <div className="nav-empty">
              Your saved portfolios
              <br />
              will appear here.
            </div>
          )}
        </div>
        <div className="sidebar-bottom">
          <div className="tip-card">
            <FlaskConical size={18} />
            <strong>Ideas, meet evidence.</strong>
            <p>
              Build your thesis. Test the basket. Understand the trade-offs.
            </p>
            <button onClick={() => setModal("help")}>
              How it works <ArrowUpRight size={13} />
            </button>
          </div>
          <button className="nav-item" onClick={() => setModal("help")}>
            <HelpCircle size={17} /> Help & methodology
          </button>
          <div className="user-profile">
            <div className="avatar">P</div>
            <span>
              Personal account
              <small>
                {health?.mode === "demo"
                  ? "Local demo workspace"
                  : "Authenticated workspace"}
              </small>
            </span>
            {supabase && (
              <button
                aria-label="Sign out"
                onClick={() => supabase?.auth.signOut()}
              >
                <LogOut size={16} />
              </button>
            )}
          </div>
        </div>
      </aside>
      <div className="main-shell">
        <header className="topbar">
          <div>
            Workspace <ChevronRight size={13} />{" "}
            <strong>{isDashboard ? "Dashboard" : "Portfolio studio"}</strong>
          </div>
          <div>
            <span className="environment">
              <span />
              {health?.market_provider.startsWith("synthetic")
                ? "Synthetic data demo"
                : "Market data connected"}
            </span>
            <button
              className="icon-button"
              aria-label="Help"
              onClick={() => setModal("help")}
            >
              <HelpCircle size={18} />
            </button>
            <div className="avatar small">P</div>
          </div>
        </header>
        <nav className="mobile-nav" aria-label="Mobile workspace">
          <button onClick={() => router.push("/dashboard")}>
            <LayoutDashboard size={14} /> Dashboard
          </button>
          <button onClick={() => router.push("/etf/new")}>
            <Plus size={14} /> New portfolio
          </button>
          <button onClick={() => setModal("research")}>
            <Sparkles size={14} /> Research
          </button>
        </nav>
        <main aria-busy={!ready}>
          <div className="breadcrumb">
            {isDashboard ? (
              "Your workspace"
            ) : (
              <>
                Portfolios <ChevronRight size={12} /> <span>{draft.name}</span>
              </>
            )}
          </div>
          {error && (
            <div role="alert" className="alert error">
              <span>{error}</span>
              <button aria-label="Dismiss error" onClick={() => setError("")}>
                <X size={16} />
              </button>
            </div>
          )}
          {notice && (
            <div role="status" className="alert success">
              <span>
                <Check size={15} /> {notice}
              </span>
              <button
                aria-label="Dismiss notification"
                onClick={() => setNotice("")}
              >
                <X size={16} />
              </button>
            </div>
          )}
          {isDashboard ? (
            <>
              <div className="page-heading">
                <div>
                  <div className="eyebrow">
                    A LITTLE CURIOSITY. A CLEARER PICTURE.
                  </div>
                  <h1>Your portfolio workspace</h1>
                  <p>Turn an investment idea into something you can explore.</p>
                </div>
                <button
                  className="primary"
                  onClick={() => router.push("/etf/new")}
                >
                  <Plus size={16} /> Create portfolio
                </button>
              </div>
              <div className="dashboard-hero">
                <div>
                  <span className="pill">PORTFOLIO STUDIO</span>
                  <h2>
                    Follow a theme.
                    <br />
                    Understand the whole picture.
                  </h2>
                  <p>
                    Build your own basket, explore its history, and see what
                    drives its performance.
                  </p>
                  <button
                    className="primary"
                    onClick={() => setModal("research")}
                  >
                    <Sparkles size={16} /> Explore a theme{" "}
                    <ArrowRight size={16} />
                  </button>
                </div>
                <div className="hero-orbit">
                  <Waves size={90} />
                  <span className="orbit-label one">COMPUTE</span>
                  <span className="orbit-label two">CONNECTIVITY</span>
                  <span className="orbit-label three">CLOUD</span>
                </div>
              </div>
              <div className="section-title">
                <h2>
                  Saved portfolios <span>{etfs.length}</span>
                </h2>
                <span>Private to your workspace</span>
              </div>
              <div className="portfolio-cards">
                {etfs.map((e) => (
                  <button
                    className="portfolio-card"
                    key={e.id}
                    onClick={() => router.push(`/etf/${e.id}`)}
                  >
                    <div className="portfolio-icon">
                      <Layers3 />
                    </div>
                    <h3>{e.name}</h3>
                    <p>{e.description || "A custom thematic portfolio."}</p>
                    <footer>
                      <span>
                        {e.holdings.length} holdings · v{e.version}
                      </span>
                      <ArrowUpRight size={18} />
                    </footer>
                  </button>
                ))}
                <button
                  className="portfolio-card new-card"
                  onClick={() => router.push("/etf/new")}
                >
                  <Plus size={28} />
                  <h3>Start with your own idea</h3>
                  <p>Create a portfolio manually.</p>
                </button>
              </div>
            </>
          ) : (
            <>
              <div className="page-heading">
                <div>
                  <div className="title-line">
                    <div className="portfolio-icon">
                      <Layers3 size={24} />
                    </div>
                    <h1>{draft.name}</h1>
                    <span className="pill">{draft.symbol || "CUSTOM"}</span>
                  </div>
                  <p>
                    {draft.description ||
                      "Your ideas. Your allocation. A clearer view of the possibilities."}
                  </p>
                  <div className="portfolio-meta">
                    <span>
                      <span className="status-dot" />{" "}
                      {selected ? "Saved portfolio" : "Draft portfolio"}
                    </span>
                    <span>{draft.holdings.length} holdings</span>
                    <span>
                      {selected
                        ? `Version ${selected.version}`
                        : "Not saved yet"}
                    </span>
                    <span>USD</span>
                  </div>
                </div>
                <div className="heading-actions">
                  <button
                    disabled={!!busy || !valid}
                    onClick={() =>
                      action("Saving", async () => {
                        await save();
                        setNotice("Portfolio saved.");
                      })
                    }
                  >
                    {busy === "Saving" ? (
                      <Loader2 className="spin" size={15} />
                    ) : (
                      <Bookmark size={15} />
                    )}{" "}
                    {dirty ? "Save portfolio" : "Saved"}
                  </button>
                  <button
                    className="icon-button"
                    title="Duplicate as a new portfolio"
                    aria-label="Duplicate portfolio"
                    disabled={!valid || !!busy}
                    onClick={() =>
                      action("Duplicating", async () => {
                        const e = await api<ETF>("/v1/etfs", {
                          method: "POST",
                          body: JSON.stringify({
                            ...draft,
                            name: draft.name + " · Variant",
                          }),
                        });
                        await loadList();
                        router.push(`/etf/${e.id}`);
                      })
                    }
                  >
                    <Copy size={16} />
                  </button>
                </div>
              </div>
              <div className="tabs">
                <div>
                  {["Overview", "Holdings", "Research", "Backtest history"].map(
                    (t) => (
                      <button
                        className={tab === t ? "active" : ""}
                        key={t}
                        onClick={() => setTab(t)}
                      >
                        {t}
                        {t === "Holdings" && (
                          <span>{draft.holdings.length}</span>
                        )}
                      </button>
                    ),
                  )}
                </div>
                <span>
                  <ShieldCheck size={13} /> Retrospective basket
                </span>
              </div>
              {stale && (
                <div className="alert stale">
                  <span>
                    <Activity size={15} /> This analysis uses a previous
                    allocation. Generate an updated backtest to evaluate your
                    changes.
                  </span>
                </div>
              )}
              <div className="studio-grid">
                <div className="studio-main">
                  {(tab === "Overview" || tab === "Holdings") && (
                    <>
                      <div className="metrics-grid">
                        {[
                          {
                            label: "Portfolio value",
                            value: money(m.ending_value),
                            sub:
                              result?.status === "completed"
                                ? `From ${money(result.config.initial_capital)}`
                                : "Run a backtest to see results",
                          },
                          {
                            label: "Total return",
                            value: pct(m.total_return),
                            sub: "Over the full backtest period",
                            green: (m.total_return ?? 0) > 0,
                          },
                          {
                            label: "Annualized return",
                            value: pct(m.cagr),
                            sub: "Compound annual growth",
                            green: (m.cagr ?? 0) > 0,
                          },
                          {
                            label: "Maximum drawdown",
                            value: pct(m.max_drawdown),
                            sub: "Largest peak-to-trough decline",
                          },
                        ].map((item) => (
                          <div className="metric-card" key={item.label}>
                            <div>
                              {item.label}
                              <HelpCircle size={13} />
                            </div>
                            <strong className={item.green ? "positive" : ""}>
                              {item.value}
                            </strong>
                            <small>{item.sub}</small>
                          </div>
                        ))}
                      </div>
                      {tab === "Overview" && (
                        <section className="panel performance">
                          <div className="panel-heading">
                            <div>
                              <h2>Performance</h2>
                              <p>
                                {result?.status === "completed"
                                  ? `${result.config.start_date} — ${result.config.end_date}`
                                  : "See how your idea holds up over time"}
                              </p>
                            </div>
                            <button
                              className="subtle-button"
                              disabled={!series}
                              onClick={() => setNormalized((v) => !v)}
                            >
                              {normalized
                                ? "Indexed to 100"
                                : "Portfolio value"}
                              <ChevronDown size={13} />
                            </button>
                          </div>
                          <div className="chart-controls">
                            <div className="legend">
                              <span>
                                <i style={{ background: "#347961" }} />
                                {result && stale
                                  ? "Saved portfolio"
                                  : draft.symbol || "Portfolio"}
                              </span>
                              <span>
                                <i style={{ background: "#aab2c2" }} />
                                {result?.config.benchmark || config.benchmark}
                              </span>
                            </div>
                            <div className="range-buttons">
                              {["1M", "6M", "YTD", "1Y", "5Y", "MAX"].map(
                                (r) => (
                                  <button
                                    key={r}
                                    className={range === r ? "active" : ""}
                                    onClick={() => setRange(r)}
                                  >
                                    {r}
                                  </button>
                                ),
                              )}
                            </div>
                          </div>
                          {series ? (
                            <PerformanceChart
                              data={series}
                              normalized={normalized}
                            />
                          ) : (
                            <div className="chart-empty">
                              {activeJob ? (
                                <>
                                  <Loader2 size={34} className="spin" />
                                  <h3>Putting your portfolio to the test</h3>
                                  <p>
                                    Loading prices and calculating the exact
                                    saved allocation.
                                  </p>
                                  <button
                                    onClick={() =>
                                      action("Canceling", async () => {
                                        const r = await api<Backtest>(
                                          `/v1/backtests/${result!.id}/cancel`,
                                          { method: "POST" },
                                        );
                                        setResult(r);
                                      })
                                    }
                                  >
                                    Cancel backtest
                                  </button>
                                </>
                              ) : result?.status === "completed" ? (
                                <>
                                  <Loader2 size={30} className="spin" />
                                  <h3>Loading saved analysis…</h3>
                                </>
                              ) : result?.status === "failed" ||
                                result?.status === "canceled" ? (
                                <>
                                  <Activity size={30} />
                                  <h3>
                                    {result.status === "failed"
                                      ? "This backtest could not complete"
                                      : "Backtest canceled"}
                                  </h3>
                                  <p>
                                    {result.error ||
                                      "Your portfolio is saved. Generate a new backtest when ready."}
                                  </p>
                                  <button
                                    onClick={run}
                                    disabled={!valid || !!busy}
                                  >
                                    Generate a new backtest
                                  </button>
                                </>
                              ) : (
                                <>
                                  <div className="empty-chart-art">
                                    <span />
                                    <span />
                                    <span />
                                    <span />
                                    <Activity size={50} />
                                  </div>
                                  <h3>A thesis is just the beginning.</h3>
                                  <p>
                                    Set your holdings, then generate a backtest
                                    <br />
                                    to explore portfolio and benchmark
                                    performance.
                                  </p>
                                  <button
                                    onClick={run}
                                    disabled={!valid || !!busy}
                                    className="text-button"
                                  >
                                    Generate your first backtest{" "}
                                    <ArrowRight size={14} />
                                  </button>
                                </>
                              )}
                            </div>
                          )}
                          <div className="performance-footer">
                            <span>
                              <span className="status-dot" />
                              {health?.market_provider.startsWith("synthetic")
                                ? "Synthetic demo prices · Not actual market returns"
                                : "Adjusted close · Dividends reinvested"}
                            </span>
                            <button
                              disabled={!series || !!busy}
                              onClick={exportResult}
                            >
                              <Download size={14} /> Export
                            </button>
                          </div>
                        </section>
                      )}
                      <section className="panel holdings-panel">
                        <div className="panel-heading">
                          <div>
                            <h2>
                              Portfolio holdings{" "}
                              <span className="number-badge">
                                {draft.holdings.length}
                              </span>
                            </h2>
                            <p>
                              A focused view of the companies behind your
                              thesis.
                            </p>
                          </div>
                          <button
                            onClick={() => setModal("stock")}
                            disabled={draft.holdings.length >= 50}
                          >
                            <Plus size={15} /> Add stock
                          </button>
                        </div>
                        <div className="holdings-tools">
                          <div>
                            <button
                              onClick={() => distribute(false)}
                              disabled={!draft.holdings.length}
                            >
                              Equal weight
                            </button>
                            <span>·</span>
                            <button
                              onClick={() => distribute(true)}
                              disabled={!draft.holdings.length || total <= 0}
                            >
                              Normalize
                            </button>
                          </div>
                          <span
                            className={
                              valid ? "allocation-valid" : "allocation-invalid"
                            }
                          >
                            {valid ? (
                              <Check size={13} />
                            ) : (
                              <Activity size={13} />
                            )}{" "}
                            {(total * 100).toFixed(2)}% allocated
                          </span>
                        </div>
                        <div className="table-scroll">
                          <table>
                            <thead>
                              <tr>
                                <th>COMPANY</th>
                                <th>EXPOSURE</th>
                                <th className="align-right">WEIGHT</th>
                                <th aria-label="Actions" />
                              </tr>
                            </thead>
                            <tbody>
                              {draft.holdings.map((h, i) => (
                                <tr key={h.ticker}>
                                  <td>
                                    <div className="company">
                                      <div
                                        className="ticker-icon"
                                        style={{
                                          background:
                                            colors[i % colors.length] + "16",
                                          color: colors[i % colors.length],
                                        }}
                                      >
                                        {h.ticker.slice(0, 2)}
                                      </div>
                                      <div>
                                        <strong>{h.ticker}</strong>
                                        <small>{h.company_name}</small>
                                      </div>
                                    </div>
                                  </td>
                                  <td>
                                    <button
                                      className="sector-tag"
                                      onClick={() => setResearchHolding(h)}
                                    >
                                      {h.theme_tag || "Custom"}
                                      {h.sources.length > 0 && (
                                        <ArrowUpRight size={11} />
                                      )}
                                    </button>
                                  </td>
                                  <td>
                                    <div className="weight-cell">
                                      <div className="weight-track">
                                        <span
                                          style={{
                                            width: `${Math.min(100, h.target_weight * 300)}%`,
                                            background:
                                              colors[i % colors.length],
                                          }}
                                        />
                                      </div>
                                      <label>
                                        <input
                                          aria-label={`${h.ticker} weight percent`}
                                          type="number"
                                          min="0"
                                          max="100"
                                          step="0.1"
                                          value={Number(
                                            (h.target_weight * 100).toFixed(2),
                                          )}
                                          onChange={(e) =>
                                            changeWeight(i, e.target.value)
                                          }
                                        />
                                        <span>%</span>
                                      </label>
                                    </div>
                                  </td>
                                  <td>
                                    <button
                                      className="remove"
                                      aria-label={`Remove ${h.ticker}`}
                                      onClick={() =>
                                        setDraft((d) => ({
                                          ...d,
                                          holdings: d.holdings.filter(
                                            (x) => x.ticker !== h.ticker,
                                          ),
                                        }))
                                      }
                                    >
                                      <X size={14} />
                                    </button>
                                  </td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                          {!draft.holdings.length && (
                            <div className="empty-small">
                              <Layers3 size={26} />
                              <h3>Your portfolio is a blank canvas.</h3>
                              <p>
                                Add a stock or start with a researched theme.
                              </p>
                              <button onClick={() => setModal("stock")}>
                                <Plus size={14} /> Add your first stock
                              </button>
                            </div>
                          )}
                        </div>
                        <div className="table-footer">
                          <span>
                            {draft.holdings.length} companies · US-listed
                            equities
                          </span>
                          <button
                            disabled={!draft.holdings.length}
                            onClick={() =>
                              setDraft((d) => ({ ...d, holdings: [] }))
                            }
                          >
                            Clear all
                          </button>
                        </div>
                      </section>
                      {result?.status === "completed" && (
                        <section className="panel">
                          <div className="panel-heading">
                            <div>
                              <h2>Risk & attribution</h2>
                              <p>
                                Calculated from saved portfolio version{" "}
                                {result.portfolio_version}.
                              </p>
                            </div>
                            <span className="pill">
                              ENGINE {result.engine_version}
                            </span>
                          </div>
                          <div className="risk-grid">
                            {[
                              ["Sharpe ratio", "sharpe"],
                              ["Sortino ratio", "sortino"],
                              [
                                "Annualized volatility",
                                "annualized_volatility",
                              ],
                              ["Beta", "beta"],
                              ["Alpha", "alpha"],
                              ["Tracking error", "tracking_error"],
                              ["Turnover", "turnover"],
                              ["Winning days", "win_rate"],
                            ].map(([label, key]) => (
                              <div key={key}>
                                <small>{label}</small>
                                <strong>
                                  {m[key] == null
                                    ? "—"
                                    : ["sharpe", "sortino", "beta"].includes(
                                          key,
                                        )
                                      ? m[key]!.toFixed(2)
                                      : pct(m[key])}
                                </strong>
                              </div>
                            ))}
                          </div>
                          <div className="table-scroll">
                            <table>
                              <thead>
                                <tr>
                                  <th>HOLDING</th>
                                  <th>CONTRIBUTION</th>
                                  <th>AVG. WEIGHT</th>
                                  <th>NET P&L</th>
                                </tr>
                              </thead>
                              <tbody>
                                {attribution.map((a) => (
                                  <tr key={a.ticker}>
                                    <td>
                                      <strong>{a.ticker}</strong>
                                    </td>
                                    <td
                                      className={a.pnl >= 0 ? "positive" : ""}
                                    >
                                      {pct(a.contribution_to_return)}
                                    </td>
                                    <td>
                                      {(a.average_weight * 100).toFixed(1)}%
                                    </td>
                                    <td>{money(a.pnl)}</td>
                                  </tr>
                                ))}
                              </tbody>
                            </table>
                          </div>
                          <div className="table-footer">
                            Contribution includes transaction costs and sums to
                            total portfolio return.
                          </div>
                        </section>
                      )}
                    </>
                  )}
                  {result?.status === "completed" && tab === "Overview" && (
                    <Diagnostics id={result.id} />
                  )}
                  {tab === "Research" && (
                    <section className="panel">
                      <div className="panel-heading">
                        <div>
                          <h2>Research behind the basket</h2>
                          <p>
                            Inspect each company’s role and supporting
                            references.
                          </p>
                        </div>
                        <button onClick={() => setModal("research")}>
                          <Sparkles size={15} /> Explore a theme
                        </button>
                      </div>
                      <div className="research-cards">
                        {draft.holdings.map((h) => (
                          <div className="research-card" key={h.ticker}>
                            <span className="pill">{h.ticker}</span>
                            <h3>{h.company_name}</h3>
                            <p>
                              {h.rationale ||
                                "Manually added holding. No research evidence attached."}
                            </p>
                            {h.sources.map((s) => (
                              <a
                                key={s.url}
                                href={s.url}
                                target="_blank"
                                rel="noreferrer"
                              >
                                {s.title}
                                <ArrowUpRight size={13} />
                              </a>
                            ))}
                          </div>
                        ))}
                      </div>
                    </section>
                  )}
                  {tab === "Backtest history" && (
                    <section className="panel">
                      <div className="panel-heading">
                        <div>
                          <h2>Backtest history</h2>
                          <p>
                            Immutable results, tied to the exact portfolio you
                            tested.
                          </p>
                        </div>
                      </div>
                      {runs.length ? (
                        <div className="history-list">
                          {runs.map((r) => (
                            <button
                              key={r.id}
                              onClick={() => {
                                setResult(r);
                                setConfig(r.config);
                                setTab("Overview");
                              }}
                            >
                              <div className="history-icon">
                                <Activity size={18} />
                              </div>
                              <div>
                                <strong>
                                  {r.config.benchmark} comparison · Version{" "}
                                  {r.portfolio_version}
                                </strong>
                                <small>
                                  {new Date(r.created_at).toLocaleString()} ·{" "}
                                  {r.config.rebalance_frequency} rebalance
                                </small>
                              </div>
                              <span className="pill">{r.status}</span>
                              <strong>{pct(r.metrics.total_return)}</strong>
                              <ChevronRight size={16} />
                            </button>
                          ))}
                        </div>
                      ) : (
                        <div className="empty-small">
                          <Activity size={28} />
                          <h3>Your experiments will live here.</h3>
                          <p>
                            Generate a backtest to start your research history.
                          </p>
                        </div>
                      )}
                    </section>
                  )}
                </div>
                <aside className="studio-rail">
                  <section className="panel backtest-panel">
                    <div className="panel-heading">
                      <h2>
                        <Settings2 size={17} /> Backtest setup
                      </h2>
                      <span className="pill">DAILY</span>
                    </div>
                    <div className="setup-fields">
                      <label>
                        Benchmark
                        <select
                          value={config.benchmark}
                          onChange={(e) =>
                            setConfig((c) => ({
                              ...c,
                              benchmark: e.target.value as Config["benchmark"],
                            }))
                          }
                        >
                          <option value="SPY">SPY · S&P 500</option>
                          <option value="QQQ">QQQ · Nasdaq 100</option>
                        </select>
                      </label>
                      <label>
                        Time period
                        <div className="period-presets">
                          {[1, 3, 5].map((years) => (
                            <button
                              key={years}
                              className={
                                Math.abs(
                                  (new Date(config.end_date).getTime() -
                                    new Date(config.start_date).getTime()) /
                                    86400000 -
                                    years * 365,
                                ) < 4
                                  ? "active"
                                  : ""
                              }
                              onClick={() => {
                                const d = new Date(config.end_date);
                                d.setFullYear(d.getFullYear() - years);
                                setConfig((c) => ({
                                  ...c,
                                  start_date: d.toISOString().slice(0, 10),
                                }));
                              }}
                            >
                              {years} year{years > 1 ? "s" : ""}
                            </button>
                          ))}
                        </div>
                      </label>
                      <div className="date-fields">
                        <label>
                          Start date
                          <input
                            type="date"
                            value={config.start_date}
                            onChange={(e) =>
                              setConfig((c) => ({
                                ...c,
                                start_date: e.target.value,
                              }))
                            }
                          />
                        </label>
                        <label>
                          End date
                          <input
                            type="date"
                            value={config.end_date}
                            max={new Date().toISOString().slice(0, 10)}
                            onChange={(e) =>
                              setConfig((c) => ({
                                ...c,
                                end_date: e.target.value,
                              }))
                            }
                          />
                        </label>
                      </div>
                      <label>
                        Initial investment
                        <div className="input-prefix">
                          <span>$</span>
                          <input
                            type="number"
                            min={100}
                            max={1e9}
                            value={config.initial_capital}
                            onChange={(e) =>
                              setConfig((c) => ({
                                ...c,
                                initial_capital: Number(e.target.value),
                              }))
                            }
                          />
                          <span>USD</span>
                        </div>
                      </label>
                      <label>
                        Rebalance frequency
                        <select
                          value={config.rebalance_frequency}
                          onChange={(e) =>
                            setConfig((c) => ({
                              ...c,
                              rebalance_frequency: e.target
                                .value as Config["rebalance_frequency"],
                            }))
                          }
                        >
                          <option value="monthly">Monthly</option>
                          <option value="quarterly">Quarterly</option>
                          <option value="none">Buy and hold</option>
                        </select>
                      </label>
                      <details>
                        <summary>
                          Advanced assumptions <ChevronDown size={13} />
                        </summary>
                        <div className="advanced-fields">
                          <label>
                            Commission (bps)
                            <input
                              type="number"
                              min={0}
                              max={100}
                              step={1}
                              value={config.commission_bps}
                              onChange={(e) =>
                                setConfig((c) => ({
                                  ...c,
                                  commission_bps: Number(e.target.value),
                                }))
                              }
                            />
                          </label>
                          <label>
                            Slippage (bps)
                            <input
                              type="number"
                              min={0}
                              max={100}
                              step={1}
                              value={config.slippage_bps}
                              onChange={(e) =>
                                setConfig((c) => ({
                                  ...c,
                                  slippage_bps: Number(e.target.value),
                                }))
                              }
                            />
                          </label>
                          <label>
                            Risk-free rate (%)
                            <input
                              type="number"
                              min={0}
                              max={25}
                              step={0.1}
                              value={config.risk_free_rate * 100}
                              onChange={(e) =>
                                setConfig((c) => ({
                                  ...c,
                                  risk_free_rate: Number(e.target.value) / 100,
                                }))
                              }
                            />
                          </label>
                          <p>
                            Dividends reinvested through adjusted close.
                            Fractional units. No separate dividend credits.
                          </p>
                        </div>
                      </details>
                      <button
                        className="primary generate-button"
                        disabled={!valid || !!busy || activeJob}
                        onClick={run}
                      >
                        {activeJob || busy === "Generating backtest" ? (
                          <Loader2 className="spin" size={16} />
                        ) : (
                          <Activity size={16} />
                        )}{" "}
                        {activeJob
                          ? "Running backtest…"
                          : stale
                            ? "Generate updated backtest"
                            : "Generate backtest"}
                        {!activeJob && <ArrowRight size={15} />}
                      </button>
                      <p className="button-note">
                        {dirty
                          ? "Saves your allocation before running."
                          : "Tests the exact saved portfolio version."}
                      </p>
                    </div>
                  </section>
                  <section className="panel allocation-panel">
                    <div className="panel-heading">
                      <h2>Allocation</h2>
                      <span>{draft.holdings.length} holdings</span>
                    </div>
                    <div className="allocation-bar">
                      {draft.holdings.map((h, i) => (
                        <div
                          key={h.ticker}
                          style={{
                            width: `${Math.max(0, h.target_weight) * 100}%`,
                            background: colors[i % colors.length],
                          }}
                          title={`${h.ticker}: ${(h.target_weight * 100).toFixed(1)}%`}
                        />
                      ))}
                    </div>
                    <div className="allocation-list">
                      {Object.entries(
                        draft.holdings.reduce<Record<string, number>>(
                          (acc, h) => {
                            acc[h.theme_tag || "Custom"] =
                              (acc[h.theme_tag || "Custom"] || 0) +
                              h.target_weight;
                            return acc;
                          },
                          {},
                        ),
                      ).map(([tag, weight], i) => (
                        <div key={tag}>
                          <span>
                            <i
                              style={{
                                background:
                                  colors[
                                    draft.holdings.findIndex(
                                      (h) => (h.theme_tag || "Custom") === tag,
                                    ) % colors.length
                                  ],
                              }}
                            />
                            {tag}
                          </span>
                          <strong>{(weight * 100).toFixed(1)}%</strong>
                        </div>
                      ))}
                    </div>
                    <div className="allocation-bottom">
                      <span>Total allocation</span>
                      <strong
                        className={valid ? "positive" : "allocation-invalid"}
                      >
                        {(total * 100).toFixed(2)}%
                      </strong>
                    </div>
                  </section>
                  <div className="research-prompt">
                    <div className="research-spark">
                      <Sparkles size={20} />
                    </div>
                    <h3>Start with a bigger idea.</h3>
                    <p>
                      Explore a theme and discover the companies building it.
                    </p>
                    <button onClick={() => setModal("research")}>
                      Research a theme <ArrowUpRight size={14} />
                    </button>
                  </div>
                  <button
                    className="rail-link"
                    disabled={result?.status !== "completed"}
                    onClick={() => setModal("compare")}
                  >
                    <Copy size={14} /> Compare saved backtests{" "}
                    <ArrowUpRight size={13} />
                  </button>
                  <button
                    className="rail-link"
                    onClick={() => setModal("settings")}
                  >
                    <Settings2 size={14} /> Edit portfolio details{" "}
                    <ArrowUpRight size={13} />
                  </button>
                  <button
                    className="rail-link"
                    disabled={!selected || dirty || !valid}
                    onClick={() => {
                      setModal("trade");
                      setPreview(null);
                      setTradeConfirmed(false);
                    }}
                  >
                    <Layers3 size={14} /> Preview paper basket{" "}
                    <ArrowUpRight size={13} />
                  </button>
                </aside>
              </div>
              <div className="methodology-note">
                <ShieldCheck size={17} />
                <p>
                  <strong>Research with perspective.</strong> A custom basket is
                  not a registered ETF. Retrospective results reflect today’s
                  holdings and cannot establish historical selection skill.{" "}
                  {health?.market_provider.startsWith("synthetic")
                    ? "This workspace uses synthetic prices for demonstration."
                    : "Past performance does not predict future returns."}
                </p>
              </div>
            </>
          )}
          <footer className="page-footer">
            <span>
              aquarius <span> / </span> Ideas into perspective.
            </span>
            <span>
              Portfolio research & simulation <span>·</span> USD
            </span>
          </footer>
        </main>
      </div>
      {(modal || researchHolding) && (
        <div
          className="modal-backdrop"
          onMouseDown={(e) => {
            if (e.target === e.currentTarget) {
              setModal(null);
              setResearchHolding(null);
            }
          }}
        >
          <section
            className="modal"
            role="dialog"
            aria-modal="true"
            aria-label={
              researchHolding ? "Holding research" : `${modal} dialog`
            }
          >
            <button
              className="modal-close icon-button"
              aria-label="Close dialog"
              onClick={() => {
                setModal(null);
                setResearchHolding(null);
              }}
            >
              <X size={20} />
            </button>
            {researchHolding ? (
              <>
                <span className="pill">{researchHolding.ticker}</span>
                <h2>{researchHolding.company_name}</h2>
                <p>
                  {researchHolding.rationale ||
                    "This holding was added manually. Research references have not been attached."}
                </p>
                {researchHolding.sources.map((s) => (
                  <a
                    className="source-link"
                    key={s.url}
                    href={s.url}
                    target="_blank"
                    rel="noreferrer"
                  >
                    <ArrowUpRight size={15} />
                    {s.title}
                  </a>
                ))}
              </>
            ) : (
              <>
                {modal === "compare" && result && (
                  <Compare etfs={etfs} current={result} />
                )}
                {modal === "stock" && (
                  <>
                    <div className="modal-symbol">
                      <Search />
                    </div>
                    <h2>Add a company</h2>
                    <p>
                      Search the supported universe, then set your allocation.
                    </p>
                    <input
                      autoFocus
                      placeholder="Search company or ticker…"
                      aria-label="Search company or ticker"
                      value={query}
                      onChange={(e) => setQuery(e.target.value)}
                    />
                    <div className="symbol-results">
                      {symbols.map((s) => (
                        <button
                          disabled={draft.holdings.some(
                            (h) => h.ticker === s.ticker,
                          )}
                          key={s.ticker}
                          onClick={() => addStock(s)}
                        >
                          <span>
                            <strong>{s.ticker}</strong>
                            <small>{s.company_name}</small>
                          </span>
                          {draft.holdings.some((h) => h.ticker === s.ticker) ? (
                            <Check size={16} />
                          ) : (
                            <Plus size={16} />
                          )}
                        </button>
                      ))}
                      {!symbols.length && (
                        <p>
                          No catalog match.{" "}
                          {health?.market_provider.startsWith("synthetic")
                            ? "The demo supports a fixed symbol catalog."
                            : "You can add a provider-validated ticker below."}
                        </p>
                      )}
                    </div>
                    {!health?.market_provider.startsWith("synthetic") &&
                      query && (
                        <button
                          onClick={() =>
                            addStock({
                              ticker: query.toUpperCase().trim(),
                              company_name: query.toUpperCase().trim(),
                              theme_tag: "Custom",
                            })
                          }
                        >
                          Add {query.toUpperCase()} · validate on save
                        </button>
                      )}
                  </>
                )}
                {modal === "research" && (
                  <>
                    <div className="modal-symbol">
                      <Sparkles />
                    </div>
                    <h2>What’s your next big idea?</h2>
                    <p>
                      Choose a theme. We’ll assemble an editable basket with
                      company references.
                    </p>
                    <label>
                      Your investment theme
                      <textarea
                        autoFocus
                        rows={4}
                        value={prompt}
                        onChange={(e) => setPrompt(e.target.value)}
                      />
                    </label>
                    <div className="theme-chips">
                      {[
                        "AI infrastructure",
                        "Semiconductors",
                        "Clean energy",
                        "Healthcare",
                      ].map((t) => (
                        <button
                          key={t}
                          onClick={() =>
                            setPrompt(
                              `Build a portfolio focused on ${t.toLowerCase()}`,
                            )
                          }
                        >
                          {t}
                        </button>
                      ))}
                    </div>
                    <div className="form-row">
                      <label>
                        Maximum holdings
                        <input
                          type="number"
                          min={2}
                          max={20}
                          value={maxNames}
                          onChange={(e) => setMaxNames(Number(e.target.value))}
                        />
                      </label>
                      <label>
                        Maximum weight (%)
                        <input
                          type="number"
                          min={5}
                          max={100}
                          value={maxWeight}
                          onChange={(e) => setMaxWeight(Number(e.target.value))}
                        />
                      </label>
                    </div>
                    <div className="modal-note">
                      {health?.research_mode === "openai"
                        ? "AI research uses web search and citations checked against retrieved sources. Review every suggestion."
                        : "Curated company research · This starter uses a transparent source catalog, not autonomous AI."}{" "}
                      Weights and supported symbols are validated
                      deterministically.
                    </div>
                    <button
                      className="primary full"
                      disabled={!!busy || prompt.length < 8}
                      onClick={() =>
                        action("Researching", async () => {
                          const r = await api<{
                            etf: ETF;
                            research: { warnings: string[] };
                          }>("/v1/etfs/generate", {
                            method: "POST",
                            body: JSON.stringify({
                              prompt,
                              max_holdings: maxNames,
                              max_weight: maxWeight / 100,
                            }),
                          });
                          await loadList();
                          setModal(null);
                          router.push(`/etf/${r.etf.id}`);
                          setNotice(
                            "Research portfolio created. Review the company references and edit your weights before backtesting.",
                          );
                        })
                      }
                    >
                      {busy === "Researching" ? (
                        <Loader2 size={16} className="spin" />
                      ) : (
                        <Sparkles size={16} />
                      )}{" "}
                      Generate portfolio <ArrowRight size={16} />
                    </button>
                  </>
                )}
                {modal === "settings" && (
                  <>
                    <h2>Portfolio details</h2>
                    <p>Give your idea a name and a clear thesis.</p>
                    <label>
                      Portfolio name
                      <input
                        autoFocus
                        maxLength={120}
                        value={draft.name}
                        onChange={(e) =>
                          setDraft((d) => ({ ...d, name: e.target.value }))
                        }
                      />
                    </label>
                    <label>
                      Custom symbol
                      <input
                        maxLength={12}
                        value={draft.symbol}
                        onChange={(e) =>
                          setDraft((d) => ({
                            ...d,
                            symbol: e.target.value.toUpperCase(),
                          }))
                        }
                      />
                    </label>
                    <label>
                      Thesis
                      <textarea
                        rows={4}
                        maxLength={4000}
                        value={draft.description}
                        onChange={(e) =>
                          setDraft((d) => ({
                            ...d,
                            description: e.target.value,
                          }))
                        }
                      />
                    </label>
                    <button
                      className="primary full"
                      onClick={() => setModal(null)}
                    >
                      Done
                    </button>
                  </>
                )}
                {modal === "trade" && (
                  <>
                    <span className="pill">PAPER ONLY</span>
                    <h2>Preview your basket</h2>
                    <p>
                      Review every notional order before any paper submission.
                    </p>
                    <label>
                      Investment amount ($)
                      <input
                        type="number"
                        min={1}
                        max={1e7}
                        value={investment}
                        onChange={(e) => {
                          setInvestment(Number(e.target.value));
                          setPreview(null);
                          setTradeConfirmed(false);
                        }}
                      />
                    </label>
                    <button
                      className="full"
                      disabled={!!busy}
                      onClick={() =>
                        action("Sizing orders", async () => {
                          if (!selected) return;
                          const p = await api<Preview>("/v1/orders/preview", {
                            method: "POST",
                            body: JSON.stringify({
                              etf_id: selected.id,
                              portfolio_version: selected.version,
                              investment,
                            }),
                          });
                          setPreview(p);
                        })
                      }
                    >
                      Generate order preview
                    </button>
                    {preview && (
                      <>
                        <table>
                          <thead>
                            <tr>
                              <th>SYMBOL</th>
                              <th>SIDE</th>
                              <th>NOTIONAL</th>
                            </tr>
                          </thead>
                          <tbody>
                            {preview.orders.map((o) => (
                              <tr key={o.symbol}>
                                <td>{o.symbol}</td>
                                <td>Buy</td>
                                <td>${o.notional}</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                        <p>
                          Residual cash: ${preview.residual_cash.toFixed(2)}
                        </p>
                        <div className="modal-note">
                          {preview.warning}
                          <br />
                          {preview.broker_validated
                            ? "Broker account and fractional eligibility checked. Preview expires in 10 minutes."
                            : "Sizing preview only. Broker submission is disabled until authenticated paper trading is configured."}
                        </div>
                        {preview.broker_validated && (
                          <>
                            <label className="checkbox-label">
                              <input
                                type="checkbox"
                                checked={tradeConfirmed}
                                onChange={(e) =>
                                  setTradeConfirmed(e.target.checked)
                                }
                              />{" "}
                              I have reviewed every order in this paper basket.
                            </label>
                            <button
                              className="primary full"
                              disabled={!tradeConfirmed || !!busy}
                              onClick={() =>
                                action("Submitting paper orders", async () => {
                                  const r = await api<{
                                    orders: { status: string }[];
                                  }>("/v1/orders/paper", {
                                    method: "POST",
                                    body: JSON.stringify({
                                      preview_id: preview.id,
                                      confirmed: true,
                                    }),
                                  });
                                  setNotice(
                                    `Paper basket status: ${r.orders.map((o) => o.status).join(", ")}. Orders may fill asynchronously.`,
                                  );
                                  setModal(null);
                                })
                              }
                            >
                              Submit reviewed paper basket
                            </button>
                          </>
                        )}
                      </>
                    )}
                  </>
                )}
                {modal === "help" && (
                  <>
                    <div className="modal-symbol">
                      <FlaskConical />
                    </div>
                    <h2>Build. Test. Understand.</h2>
                    <div className="help-steps">
                      <div>
                        <b>01</b>
                        <span>
                          <strong>Make the portfolio yours</strong>
                          <p>
                            Add companies, edit weights, and normalize to 100%.
                            Save creates a persistent portfolio version.
                          </p>
                        </span>
                      </div>
                      <div>
                        <b>02</b>
                        <span>
                          <strong>Generate a backtest explicitly</strong>
                          <p>
                            Choose dates, costs, benchmark and rebalance
                            cadence. The Python engine tests the exact saved
                            holdings.
                          </p>
                        </span>
                      </div>
                      <div>
                        <b>03</b>
                        <span>
                          <strong>Inspect the assumptions</strong>
                          <p>
                            Daily adjusted closes include dividends and splits.
                            Missing history fails visibly. Fees apply to buys
                            and sells, including initial allocation.
                          </p>
                        </span>
                      </div>
                    </div>
                    <div className="modal-note">
                      Sharpe uses arithmetic annualized daily returns and sample
                      volatility. CAGR uses elapsed calendar days. Undefined
                      risk ratios display as —. Intraday simulation,
                      point-in-time ML, and live trading are not enabled in this
                      release.
                    </div>
                    <a
                      className="source-link"
                      href="/api/docs"
                      target="_blank"
                      rel="noreferrer"
                    >
                      Explore the API documentation <ArrowUpRight size={15} />
                    </a>
                  </>
                )}
              </>
            )}
            {error && (
              <div role="alert" className="alert error">
                {error}
              </div>
            )}
          </section>
        </div>
      )}
    </div>
  );
}
