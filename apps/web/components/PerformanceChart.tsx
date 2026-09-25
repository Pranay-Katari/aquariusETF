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
      height: 340,
      width: ref.current.clientWidth,
      layout: {
        background: { type: ColorType.Solid, color: "transparent" },
        textColor: "#9aacc1",
        fontFamily: "Manrope, Arial, sans-serif",
        fontSize: 11,
        attributionLogo: true,
      },
      grid: { vertLines: { visible: false }, horzLines: { color: "rgba(67, 92, 119, 0.35)", style: 2 } },
      rightPriceScale: {
        borderVisible: false,
        scaleMargins: { top: 0.12, bottom: 0.07 },
      },
      timeScale: { borderVisible: false, timeVisible: true, secondsVisible: false },
      crosshair: {
        vertLine: { color: "#3d516a", labelBackgroundColor: "#0c1726" },
        horzLine: { color: "#3d516a", labelBackgroundColor: "#0c1726" },
      },
    });
    const portfolio = chart.addSeries(AreaSeries, {
      lineColor: "#54f1ce",
      topColor: "rgba(84,241,206,0.30)",
      bottomColor: "rgba(84,241,206,0.015)",
      lineWidth: 3,
      priceLineVisible: false,
      lastValueVisible: false,
    });
    const benchmark = chart.addSeries(LineSeries, {
      color: "#8fa6ff",
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
      <div className="chart-legend"><span><i className="portfolio-dot" />Your portfolio</span><span><i className="benchmark-dot" />Benchmark</span><em>{normalized ? "Indexed to 100" : "Portfolio value"}</em></div>
      <div className="chart-hover">{hover || "Move across the chart to inspect each session"}</div>
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
