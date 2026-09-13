"use client";
import { useEffect, useState } from "react";
import { api, money, pct } from "@/lib/api";
type Data = {
  rebalances: {
    time: string;
    initial: boolean;
    costs: number;
    trades: { ticker: string; notional: number }[];
  }[];
  drawdowns: {
    peak: string;
    trough: string;
    depth: number;
    recovery: string | null;
    duration_days: number;
  }[];
  rolling_21_session_returns: {
    time: string;
    portfolio: number;
    benchmark: number;
  }[];
};
export default function Diagnostics({ id }: { id: string }) {
  const [data, setData] = useState<Data | null>(null),
    [error, setError] = useState("");
  useEffect(() => {
    let active = true;
    api<Data>(`/v1/backtests/${id}/diagnostics`)
      .then((d) => {
        if (active) setData(d);
      })
      .catch((e) => {
        if (active) setError(e.message);
      });
    return () => {
      active = false;
    };
  }, [id]);
  if (error) return <div className="alert error">{error}</div>;
  if (!data) return null;
  const latest = data.rolling_21_session_returns.at(-1);
  return (
    <section className="panel diagnostics">
      <div className="panel-heading">
        <div>
          <h2>Inside the backtest</h2>
          <p>Rebalance activity, drawdown episodes, and rolling returns.</p>
        </div>
      </div>
      {latest && (
        <div className="rolling-summary">
          <span>
            Latest 21-session return<small>As of {latest.time}</small>
          </span>
          <strong>
            {pct(latest.portfolio)}
            <small>Portfolio</small>
          </strong>
          <strong>
            {pct(latest.benchmark)}
            <small>Benchmark</small>
          </strong>
        </div>
      )}
      <details>
        <summary>
          Largest drawdown episodes <span>{data.drawdowns.length}</span>
        </summary>
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                <th>PEAK</th>
                <th>TROUGH</th>
                <th>DEPTH</th>
                <th>RECOVERY</th>
              </tr>
            </thead>
            <tbody>
              {data.drawdowns.map((d, i) => (
                <tr key={i}>
                  <td>{d.peak}</td>
                  <td>{d.trough}</td>
                  <td>{pct(d.depth)}</td>
                  <td>{d.recovery || "Not recovered"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>
      <details>
        <summary>
          Rebalance ledger <span>{data.rebalances.length} events</span>
        </summary>
        <div className="ledger-scroll">
          <table>
            <thead>
              <tr>
                <th>DATE</th>
                <th>EVENT</th>
                <th>TRADED</th>
                <th>COSTS</th>
              </tr>
            </thead>
            <tbody>
              {data.rebalances.map((r) => (
                <tr key={r.time}>
                  <td>{r.time}</td>
                  <td>{r.initial ? "Initial allocation" : "Rebalance"}</td>
                  <td>
                    {money(
                      r.trades.reduce((s, t) => s + Math.abs(t.notional), 0),
                    )}
                  </td>
                  <td>${r.costs.toFixed(2)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>
    </section>
  );
}
