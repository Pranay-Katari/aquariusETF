"use client";
import { useState, useEffect } from "react";
import { api, pct, money } from "@/lib/api";
import type { ETF, Backtest } from "@/lib/types";
export default function Compare({
  etfs,
  current,
}: {
  etfs: ETF[];
  current: Backtest;
}) {
  const [portfolio, setPortfolio] = useState(etfs[0]?.id || ""),
    [runs, setRuns] = useState<Backtest[]>([]),
    [other, setOther] = useState<Backtest | null>(null),
    [error, setError] = useState("");
  useEffect(() => {
    if (!portfolio) return;
    let active = true;
    api<Backtest[]>(`/v1/etfs/${portfolio}/backtests`)
      .then((r) => {
        if (active) {
          const completed = r.filter(
            (x) => x.status === "completed" && x.id !== current.id,
          );
          setRuns(completed);
          setOther(completed[0] || null);
        }
      })
      .catch((e) => setError(e.message));
    return () => {
      active = false;
    };
  }, [portfolio, current.id]);
  return (
    <>
      <h2>Compare an experiment</h2>
      <p>Choose a saved backtest to compare with the current result.</p>
      <label>
        Portfolio
        <select
          value={portfolio}
          onChange={(e) => setPortfolio(e.target.value)}
        >
          {etfs.map((e) => (
            <option key={e.id} value={e.id}>
              {e.name}
            </option>
          ))}
        </select>
      </label>
      <label>
        Backtest
        <select
          value={other?.id || ""}
          onChange={(e) =>
            setOther(runs.find((r) => r.id === e.target.value) || null)
          }
        >
          {runs.map((r) => (
            <option key={r.id} value={r.id}>
              v{r.portfolio_version} · {r.config.start_date} —{" "}
              {r.config.end_date} · {r.config.benchmark}
            </option>
          ))}
        </select>
      </label>
      {error && <p>{error}</p>}
      {other ? (
        <>
          <div className="modal-note">
            {JSON.stringify(current.config) !== JSON.stringify(other.config)
              ? "Compare assumptions carefully: portfolios, date ranges, capital or costs may differ."
              : "Both results use the same assumptions."}
          </div>
          <table>
            <thead>
              <tr>
                <th>METRIC</th>
                <th>CURRENT RUN</th>
                <th>COMPARISON</th>
              </tr>
            </thead>
            <tbody>
              {[
                ["Ending value", "ending_value"],
                ["Total return", "total_return"],
                ["CAGR", "cagr"],
                ["Max drawdown", "max_drawdown"],
                ["Volatility", "annualized_volatility"],
                ["Sharpe", "sharpe"],
              ].map(([label, key]) => (
                <tr key={key}>
                  <td>{label}</td>
                  {[current, other].map((r, i) => (
                    <td key={i}>
                      {key === "ending_value"
                        ? money(r.metrics[key])
                        : key === "sharpe"
                          ? (r.metrics[key]?.toFixed(2) ?? "—")
                          : pct(r.metrics[key])}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </>
      ) : (
        <div className="modal-note">
          No other completed runs for this portfolio. Generate another backtest
          or choose a different portfolio.
        </div>
      )}
    </>
  );
}
