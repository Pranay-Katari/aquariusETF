"use client";
import { useEffect, useRef, useState } from "react";
import {
  AreaSeries,
  LineSeries,
  createChart,
  ColorType,
  type Time,
} from "lightweight-charts";
import type { Series } from "@/lib/types";
import { money } from "@/lib/api";
export default function PerformanceChart({
  data,
  normalized = false,
}: {
  data: Series;
  normalized?: boolean;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const [hover, setHover] = useState("");
  useEffect(() => {
    if (!ref.current) return;
    const chart = createChart(ref.current, {
      height: 310,
      width: ref.current.clientWidth,
      layout: {
        background: { type: ColorType.Solid, color: "transparent" },
        textColor: "#858a90",
        fontFamily: "Arial",
        fontSize: 11,
        attributionLogo: true,
      },
      grid: { vertLines: { visible: false }, horzLines: { color: "#eceef0" } },
      rightPriceScale: {
        borderVisible: false,
        scaleMargins: { top: 0.12, bottom: 0.07 },
      },
      timeScale: { borderVisible: false, timeVisible: false },
      crosshair: {
        vertLine: { color: "#b7bdc5", labelBackgroundColor: "#212b36" },
        horzLine: { color: "#b7bdc5", labelBackgroundColor: "#212b36" },
      },
    });
    const portfolio = chart.addSeries(AreaSeries, {
      lineColor: "#347961",
      topColor: "rgba(66,134,108,0.14)",
      bottomColor: "rgba(66,134,108,0)",
      lineWidth: 2,
      priceLineVisible: false,
      lastValueVisible: false,
    });
    const benchmark = chart.addSeries(LineSeries, {
      color: "#aab2c2",
      lineWidth: 2,
      lineStyle: 2,
      priceLineVisible: false,
      lastValueVisible: false,
    });
    const map = (points: Series["portfolio"]) =>
      points.map((p) => ({
        time: p.time as Time,
        value: normalized ? (p.value / points[0].value) * 100 : p.value,
      }));
    portfolio.setData(map(data.portfolio));
    benchmark.setData(map(data.benchmark));
    chart.timeScale().fitContent();
    chart.subscribeCrosshairMove((p) => {
      const a = p.seriesData.get(portfolio);
      const b = p.seriesData.get(benchmark);
      if (a && b && "value" in a && "value" in b)
        setHover(
          `Portfolio ${normalized ? a.value.toFixed(2) : money(a.value)}  ·  Benchmark ${normalized ? b.value.toFixed(2) : money(b.value)}  ·  Spread ${(a.value - b.value).toFixed(2)}`,
        );
      else setHover("");
    });
    const observer = new ResizeObserver(() => {
      if (ref.current) {
        chart.applyOptions({ width: ref.current.clientWidth });
        chart.timeScale().fitContent();
      }
    });
    observer.observe(ref.current);
    return () => {
      observer.disconnect();
      chart.remove();
    };
  }, [data, normalized]);
  return (
    <>
      <div className="chart-hover">
        {hover || "Hover to inspect portfolio and benchmark values"}
      </div>
      <div
        ref={ref}
        className="chart-canvas"
        aria-label="Portfolio and benchmark performance chart"
      />
      <div className="chart-attribution">
        TradingView Lightweight Charts™ · Copyright © 2025 TradingView, Inc.{" "}
        <a href="https://www.tradingview.com/" target="_blank" rel="noreferrer">
          TradingView
        </a>{" "}
        · Daily adjusted-close data
      </div>
    </>
  );
}
