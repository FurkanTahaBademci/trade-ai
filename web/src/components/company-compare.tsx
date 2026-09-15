"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import type { CompanyComparisonData, CompanyCompareStock } from "@/lib/types";
import { formatMoney, formatPercent, signalName } from "@/lib/format";
import { normalizeTicker } from "@/lib/turkish";
import { Icon } from "./icon";

const COMPANY_COLORS = [
  { stroke: "#00d26a", fill: "rgba(0, 210, 106, 0.18)", text: "text-[#00d26a]", bg: "bg-[#00d26a]" },
  { stroke: "#f59e0b", fill: "rgba(245, 158, 11, 0.18)", text: "text-[#f59e0b]", bg: "bg-[#f59e0b]" },
  { stroke: "#8b5cf6", fill: "rgba(139, 92, 246, 0.18)", text: "text-[#8b5cf6]", bg: "bg-[#8b5cf6]" },
  { stroke: "#f43f5e", fill: "rgba(244, 63, 94, 0.18)", text: "text-[#f43f5e]", bg: "bg-[#f43f5e]" },
];

const PRESET_COMPARISONS = [
  { label: "Havacılık", tickers: ["THYAO", "PGSUS"] },
  { label: "Bankacılık", tickers: ["GARAN", "AKBNK", "ISCTR"] },
  { label: "Demir-Çelik", tickers: ["EREGL", "KRDMD"] },
  { label: "Perakende", tickers: ["BIMAS", "MGROS"] },
  { label: "Sanayi & Enerji", tickers: ["ASELS", "TUPRS"] },
];

export function CompanyCompareView({ initialData }: { initialData: CompanyComparisonData | null }) {
  const router = useRouter();
  const [data, setData] = useState<CompanyComparisonData | null>(initialData);
  const [newTickerInput, setNewTickerInput] = useState("");
  const [activeTab, setActiveTab] = useState<"all" | "multiples" | "consensus" | "chart">("all");

  const companies = data?.companies || [];
  const tickers = data?.tickers || [];

  function handleSelectPreset(presetTickers: string[]) {
    router.push(`/karsilastir?tickers=${presetTickers.join(",")}`);
  }

  function handleRemoveTicker(tickerToRemove: string) {
    if (tickers.length <= 2) return;
    const remaining = tickers.filter((t) => t !== tickerToRemove);
    router.push(`/karsilastir?tickers=${remaining.join(",")}`);
  }

  function handleAddTicker(e: React.FormEvent) {
    e.preventDefault();
    const t = normalizeTicker(newTickerInput);
    if (!t || tickers.includes(t) || tickers.length >= 4) return;
    const updated = [...tickers, t];
    setNewTickerInput("");
    router.push(`/karsilastir?tickers=${updated.join(",")}`);
  }

  // Radar Grafigi Koordinat Hesaplamasi
  // 5 Eksen: Değerleme, Kârlılık, Momentum, Analistler, AI Sinyal
  const radarAxes = data?.dimensions || [
    { key: "valuation", label: "Değerleme" },
    { key: "profitability", label: "Kârlılık" },
    { key: "momentum", label: "Momentum" },
    { key: "analysts", label: "Analistler" },
    { key: "ai_sentiment", label: "AI Sinyal" },
  ];

  const radarCoords = useMemo(() => {
    const center = 150;
    const radius = 100;
    const totalAxes = radarAxes.length;

    // Eksen cizgileri ve etiket koordinatlari
    const axesLines = radarAxes.map((axis, i) => {
      const angle = (Math.PI * 2 * i) / totalAxes - Math.PI / 2;
      const x = center + radius * Math.cos(angle);
      const y = center + radius * Math.sin(angle);
      const labelX = center + (radius + 22) * Math.cos(angle);
      const labelY = center + (radius + 16) * Math.sin(angle);
      return { ...axis, x, y, labelX, labelY, angle };
    });

    // Her sirket icin poligon noktalari
    const polygons = companies.map((c, compIdx) => {
      const points = radarAxes.map((axis, i) => {
        const score = c.radar_scores[axis.key as keyof typeof c.radar_scores] ?? 50;
        const normalizedScore = Math.max(10, Math.min(100, score)) / 100;
        const currentRadius = radius * normalizedScore;
        const angle = (Math.PI * 2 * i) / totalAxes - Math.PI / 2;
        const px = center + currentRadius * Math.cos(angle);
        const py = center + currentRadius * Math.sin(angle);
        return `${px.toFixed(1)},${py.toFixed(1)}`;
      }).join(" ");

      return {
        ticker: c.ticker,
        points,
        color: COMPANY_COLORS[compIdx % COMPANY_COLORS.length],
      };
    });

    return { center, radius, axesLines, polygons };
  }, [radarAxes, companies]);

  // Normalize Getiri Cizgi Grafigi
  const chartPoints = data?.normalized_chart || [];
  const chartSvg = useMemo(() => {
    if (chartPoints.length < 2 || !tickers.length) return null;

    let minVal = 0;
    let maxVal = 0;
    chartPoints.forEach((pt) => {
      tickers.forEach((t) => {
        const v = typeof pt[t] === "number" ? (pt[t] as number) : 0;
        if (v < minVal) minVal = v;
        if (v > maxVal) maxVal = v;
      });
    });

    const pad = Math.max(5, (maxVal - minVal) * 0.1);
    const domainMin = minVal - pad;
    const domainMax = maxVal + pad;
    const range = domainMax - domainMin || 1;

    const width = 600;
    const height = 200;
    const pLeft = 40;
    const pRight = 20;
    const pTop = 15;
    const pBottom = 25;
    const plotW = width - pLeft - pRight;
    const plotH = height - pTop - pBottom;

    // Sifir cizgisi (Base = 0%)
    const zeroY = pTop + plotH * (1 - (0 - domainMin) / range);

    const paths = tickers.map((t, idx) => {
      const d = chartPoints.map((pt, i) => {
        const x = pLeft + (i / (chartPoints.length - 1)) * plotW;
        const val = typeof pt[t] === "number" ? (pt[t] as number) : 0;
        const y = pTop + plotH * (1 - (val - domainMin) / range);
        return `${i === 0 ? "M" : "L"} ${x.toFixed(1)} ${y.toFixed(1)}`;
      }).join(" ");

      const lastPt = chartPoints[chartPoints.length - 1];
      const lastVal = typeof lastPt[t] === "number" ? (lastPt[t] as number) : 0;

      return {
        ticker: t,
        d,
        lastVal,
        color: COMPANY_COLORS[idx % COMPANY_COLORS.length],
      };
    });

    return { width, height, zeroY, domainMin, domainMax, paths };
  }, [chartPoints, tickers]);

  if (!data || !companies.length) {
    return (
      <div className="panel-flat p-12 text-center text-sm text-[var(--text-muted)]">
        <Icon name="activity" size={32} className="mx-auto mb-3 opacity-50" />
        <p className="font-medium text-[var(--text)]">Karşılaştırma için şirketler yüklenemedi.</p>
        <p className="mt-1">Lütfen geçerli en az 2 hisse kodu giriniz.</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* 1. Üst Seçici ve Hazır Kıyaslama Hapları */}
      <div className="rounded-[16px] border border-[var(--border)] bg-[var(--surface)] p-4 shadow-xs">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
          {/* Seçili hisseler ve kaldırma butonları */}
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-xs font-semibold uppercase tracking-wider text-[var(--text-muted)]">
              Karşılaştırılan ({tickers.length}/4):
            </span>
            {companies.map((comp, idx) => {
              const color = COMPANY_COLORS[idx % COMPANY_COLORS.length];
              return (
                <div
                  key={comp.ticker}
                  className="flex items-center gap-2 rounded-[10px] border px-3 py-1.5 text-xs font-semibold shadow-2xs"
                  style={{
                    borderColor: color.stroke,
                    backgroundColor: `color-mix(in srgb, ${color.stroke} 8%, transparent)`,
                  }}
                >
                  <span className="h-2 w-2 rounded-full" style={{ backgroundColor: color.stroke }} />
                  <span className="font-bold text-[var(--text)]">{comp.ticker}</span>
                  <span className="text-[11px] font-normal text-[var(--text-muted)]">
                    {comp.name.slice(0, 16)}
                  </span>
                  {tickers.length > 2 && (
                    <button
                      type="button"
                      onClick={() => handleRemoveTicker(comp.ticker)}
                      className="ml-1 text-[var(--text-muted)] hover:text-[var(--negative)]"
                      title="Kaldır"
                    >
                      ×
                    </button>
                  )}
                </div>
              );
            })}

            {/* Yeni hisse ekleme formu */}
            {tickers.length < 4 && (
              <form onSubmit={handleAddTicker} className="flex items-center gap-1.5">
                <input
                  type="text"
                  placeholder="+ Hisse (örn: SAHOL)"
                  value={newTickerInput}
                  onChange={(e) => setNewTickerInput(e.target.value)}
                  className="input h-8 w-28 text-xs font-medium uppercase"
                />
                <button type="submit" className="btn-secondary h-8 px-2.5 text-xs">
                  Ekle
                </button>
              </form>
            )}
          </div>

          {/* Hazır kıyaslama butonları */}
          <div className="no-scrollbar flex items-center gap-1.5 overflow-x-auto text-xs">
            <span className="shrink-0 text-[11px] text-[var(--text-muted)]">Hazır:</span>
            {PRESET_COMPARISONS.map((preset) => (
              <button
                key={preset.label}
                type="button"
                onClick={() => handleSelectPreset(preset.tickers)}
                className="shrink-0 rounded-[8px] border border-[var(--border)] bg-[var(--surface-raised)] px-2.5 py-1 text-[11px] font-medium text-[var(--text-secondary)] transition hover:border-[var(--primary)] hover:text-[var(--primary)]"
              >
                {preset.label}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* 2. Radar Grafik & Performans Görsel Paneli */}
      <div className="grid gap-6 lg:grid-cols-12">
        {/* A. 5-Eksenli Spider / Radar Grafiği */}
        <div className="flex flex-col justify-between rounded-[16px] border border-[var(--border)] bg-[var(--surface)] p-5 shadow-xs lg:col-span-5">
          <div>
            <div className="flex items-center justify-between border-b border-[var(--border-subtle)] pb-3">
              <div>
                <h3 className="text-sm font-semibold tracking-[-0.01em] text-[var(--text)]">
                  Çok Boyutlu Radar Analizi
                </h3>
                <p className="text-[11px] text-[var(--text-muted)]">
                  Değerleme, Kârlılık, Momentum, Analist ve AI Sinyal dengesi
                </p>
              </div>
              <span className="pill text-[10px] font-semibold">5 Eksen</span>
            </div>

            {/* SVG Radar */}
            <div className="relative my-4 flex items-center justify-center">
              <svg width="300" height="300" viewBox="0 0 300 300" className="overflow-visible">
                {/* Dairesel / Çokgen Seviye Çizgileri (%25, %50, %75, %100) */}
                {[0.25, 0.5, 0.75, 1.0].map((level) => {
                  const r = radarCoords.radius * level;
                  const pts = radarCoords.axesLines.map((axis) => {
                    const px = radarCoords.center + r * Math.cos(axis.angle);
                    const py = radarCoords.center + r * Math.sin(axis.angle);
                    return `${px.toFixed(1)},${py.toFixed(1)}`;
                  }).join(" ");
                  return (
                    <polygon
                      key={level}
                      points={pts}
                      fill="none"
                      stroke="var(--border)"
                      strokeWidth={level === 1.0 ? "1.5" : "1"}
                      strokeDasharray={level === 1.0 ? "none" : "3,3"}
                      opacity={0.6}
                    />
                  );
                })}

                {/* Eksen Kılavuz Çizgileri */}
                {radarCoords.axesLines.map((axis) => (
                  <line
                    key={axis.key}
                    x1={radarCoords.center}
                    y1={radarCoords.center}
                    x2={axis.x}
                    y2={axis.y}
                    stroke="var(--border)"
                    strokeWidth="1"
                    opacity={0.7}
                  />
                ))}

                {/* Eksen Etiketleri */}
                {radarCoords.axesLines.map((axis) => (
                  <text
                    key={axis.key}
                    x={axis.labelX}
                    y={axis.labelY}
                    textAnchor="middle"
                    dominantBaseline="middle"
                    className="fill-[var(--text-secondary)] text-[10px] font-semibold"
                  >
                    {axis.label}
                  </text>
                ))}

                {/* Şirket Poligonları */}
                {radarCoords.polygons.map((poly) => (
                  <g key={poly.ticker}>
                    <polygon
                      points={poly.points}
                      fill={poly.color.fill}
                      stroke={poly.color.stroke}
                      strokeWidth="2.5"
                      strokeLinejoin="round"
                    />
                  </g>
                ))}
              </svg>
            </div>
          </div>

          {/* Radar Lejantı */}
          <div className="flex flex-wrap items-center justify-center gap-4 border-t border-[var(--border-subtle)] pt-3 text-xs">
            {companies.map((c, idx) => {
              const color = COMPANY_COLORS[idx % COMPANY_COLORS.length];
              return (
                <div key={c.ticker} className="flex items-center gap-1.5 font-medium text-[var(--text)]">
                  <span className="h-2.5 w-2.5 rounded-full" style={{ backgroundColor: color.stroke }} />
                  <span className="font-bold">{c.ticker}</span>
                  <span className="text-[10px] text-[var(--text-muted)]">
                    (Skor: {c.signal.composite_score} · {signalName(c.signal.label)})
                  </span>
                </div>
              );
            })}
          </div>
        </div>

        {/* B. 1-Yıllık Karşılaştırmalı Getiri Çizgisi (Normalized Return) */}
        <div className="flex flex-col justify-between rounded-[16px] border border-[var(--border)] bg-[var(--surface)] p-5 shadow-xs lg:col-span-7">
          <div>
            <div className="flex items-center justify-between border-b border-[var(--border-subtle)] pb-3">
              <div>
                <h3 className="text-sm font-semibold tracking-[-0.01em] text-[var(--text)]">
                  1 Yıllık Normalize Getiri Performansı
                </h3>
                <p className="text-[11px] text-[var(--text-muted)]">
                  Başlangıç tarihi = 0% baz alınarak kümülatif getiri farkı
                </p>
              </div>
              <span className="pill text-[10px] font-semibold text-[var(--positive)]">
                Kümülatif %
              </span>
            </div>

            {/* SVG Çizgi Grafiği */}
            {chartSvg ? (
              <div className="relative my-4">
                <svg
                  viewBox={`0 0 ${chartSvg.width} ${chartSvg.height}`}
                  className="w-full overflow-visible"
                >
                  {/* Sıfır Ekseni */}
                  <line
                    x1="35"
                    y1={chartSvg.zeroY}
                    x2={chartSvg.width}
                    y2={chartSvg.zeroY}
                    stroke="var(--border)"
                    strokeWidth="1.5"
                    strokeDasharray="4,4"
                  />
                  <text
                    x="28"
                    y={chartSvg.zeroY + 3}
                    textAnchor="end"
                    className="fill-[var(--text-muted)] text-[9px]"
                  >
                    0%
                  </text>

                  {/* Tepe / Dip değer etiketleri */}
                  <text
                    x="28"
                    y="20"
                    textAnchor="end"
                    className="fill-[var(--text-muted)] text-[9px]"
                  >
                    {formatPercent(chartSvg.domainMax)}
                  </text>
                  <text
                    x="28"
                    y={chartSvg.height - 15}
                    textAnchor="end"
                    className="fill-[var(--text-muted)] text-[9px]"
                  >
                    {formatPercent(chartSvg.domainMin)}
                  </text>

                  {/* Şirket Getiri Eğrileri */}
                  {chartSvg.paths.map((p) => (
                    <path
                      key={p.ticker}
                      d={p.d}
                      fill="none"
                      stroke={p.color.stroke}
                      strokeWidth="2.5"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                    />
                  ))}
                </svg>
              </div>
            ) : (
              <div className="grid h-48 place-items-center text-xs text-[var(--text-muted)]">
                Karşılaştırmalı getiri grafiği için yeterli geçmiş veri bekleniyor.
              </div>
            )}
          </div>

          {/* Son Getiri Özeti */}
          <div className="flex flex-wrap items-center justify-between gap-3 border-t border-[var(--border-subtle)] pt-3 text-xs">
            {companies.map((c, idx) => {
              const color = COMPANY_COLORS[idx % COMPANY_COLORS.length];
              return (
                <div key={c.ticker} className="flex items-center gap-2">
                  <span className="h-2 w-2 rounded-full" style={{ backgroundColor: color.stroke }} />
                  <span className="font-semibold text-[var(--text)]">{c.ticker}</span>
                  <span
                    className={`font-bold ${
                      c.price.change_1y_pct >= 0 ? "text-[var(--positive)]" : "text-[var(--negative)]"
                    }`}
                  >
                    {formatPercent(c.price.change_1y_pct, true)}
                  </span>
                </div>
              );
            })}
          </div>
        </div>
      </div>

      {/* 3. Kapsamlı Yan Yana Finansal Kıyaslama Tablosu */}
      <div className="overflow-hidden rounded-[16px] border border-[var(--border)] bg-[var(--surface)] shadow-xs">
        <div className="flex flex-col gap-3 border-b border-[var(--border)] p-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h3 className="text-sm font-semibold tracking-[-0.01em] text-[var(--text)]">
              Detaylı Finansal ve Teknik Kıyaslama Matrisi
            </h3>
            <p className="text-xs text-[var(--text-muted)]">
              Çarpanlar, Bilanço Rasyoları, Analist Hedefleri ve AI Sinyal Gücü
            </p>
          </div>
          <div className="flex rounded-[10px] border border-[var(--border)] bg-[var(--surface-raised)] p-0.5 text-xs">
            <button
              type="button"
              onClick={() => setActiveTab("all")}
              className={`rounded-[8px] px-3 py-1 font-medium transition ${
                activeTab === "all" ? "bg-[var(--surface)] font-semibold text-[var(--text)]" : "text-[var(--text-muted)]"
              }`}
            >
              Tümü
            </button>
            <button
              type="button"
              onClick={() => setActiveTab("multiples")}
              className={`rounded-[8px] px-3 py-1 font-medium transition ${
                activeTab === "multiples" ? "bg-[var(--surface)] font-semibold text-[var(--text)]" : "text-[var(--text-muted)]"
              }`}
            >
              Değerleme & Bilanço
            </button>
            <button
              type="button"
              onClick={() => setActiveTab("consensus")}
              className={`rounded-[8px] px-3 py-1 font-medium transition ${
                activeTab === "consensus" ? "bg-[var(--surface)] font-semibold text-[var(--text)]" : "text-[var(--text-muted)]"
              }`}
            >
              Analist & Sinyal
            </button>
          </div>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead>
              <tr className="border-b border-[var(--border-subtle)] bg-[var(--surface-raised)] text-[var(--text-muted)]">
                <th className="p-3.5 font-semibold">Metrik / Gösterge</th>
                {companies.map((c, idx) => {
                  const color = COMPANY_COLORS[idx % COMPANY_COLORS.length];
                  return (
                    <th key={c.ticker} className="p-3.5 font-bold text-[var(--text)]">
                      <div className="flex items-center gap-1.5">
                        <span className="h-2 w-2 rounded-full" style={{ backgroundColor: color.stroke }} />
                        <Link href={`/piyasalar/${c.ticker}`} className="hover:underline">
                          {c.ticker}
                        </Link>
                      </div>
                      <span className="block text-[10px] font-normal text-[var(--text-muted)]">
                        {c.sector}
                      </span>
                    </th>
                  );
                })}
              </tr>
            </thead>
            <tbody className="divide-y divide-[var(--border-subtle)]">
              {/* Piyasa Fiyatı & Hacim */}
              <tr>
                <td className="p-3.5 font-medium text-[var(--text-secondary)]">Son Fiyat</td>
                {companies.map((c) => (
                  <td key={c.ticker} className="p-3.5 font-semibold text-[var(--text)]">
                    ₺{c.price.last_price.toFixed(2)}
                  </td>
                ))}
              </tr>
              <tr>
                <td className="p-3.5 font-medium text-[var(--text-secondary)]">Günlük Değişim</td>
                {companies.map((c) => (
                  <td
                    key={c.ticker}
                    className={`p-3.5 font-semibold ${
                      c.price.change_1d_pct >= 0 ? "text-[var(--positive)]" : "text-[var(--negative)]"
                    }`}
                  >
                    {formatPercent(c.price.change_1d_pct, true)}
                  </td>
                ))}
              </tr>
              <tr>
                <td className="p-3.5 font-medium text-[var(--text-secondary)]">1 Aylık Değişim</td>
                {companies.map((c) => (
                  <td
                    key={c.ticker}
                    className={`p-3.5 font-semibold ${
                      c.price.change_1m_pct >= 0 ? "text-[var(--positive)]" : "text-[var(--negative)]"
                    }`}
                  >
                    {formatPercent(c.price.change_1m_pct, true)}
                  </td>
                ))}
              </tr>
              <tr>
                <td className="p-3.5 font-medium text-[var(--text-secondary)]">Piyasa Değeri</td>
                {companies.map((c) => (
                  <td key={c.ticker} className="p-3.5 text-[var(--text-secondary)]">
                    {formatMoney(c.price.market_cap_try, true)}
                  </td>
                ))}
              </tr>

              {/* Değerleme Çarpanları */}
              {(activeTab === "all" || activeTab === "multiples") && (
                <>
                  <tr className="bg-[var(--surface-raised)] font-semibold text-[var(--text)]">
                    <td colSpan={companies.length + 1} className="p-2.5 text-[11px] uppercase tracking-wider">
                      Değerleme Çarpanları & Kârlılık
                    </td>
                  </tr>
                  <tr>
                    <td className="p-3.5 font-medium text-[var(--text-secondary)]">
                      Fiyat / Kazanç (F/K)
                    </td>
                    {companies.map((c) => (
                      <td key={c.ticker} className="p-3.5 font-medium text-[var(--text)]">
                        {c.multiples.pe_ratio !== null ? `${c.multiples.pe_ratio}x` : "—"}
                      </td>
                    ))}
                  </tr>
                  <tr>
                    <td className="p-3.5 font-medium text-[var(--text-secondary)]">
                      Piyasa Değeri / Defter Değeri (PD/DD)
                    </td>
                    {companies.map((c) => (
                      <td key={c.ticker} className="p-3.5 font-medium text-[var(--text)]">
                        {c.multiples.pb_ratio !== null ? `${c.multiples.pb_ratio}x` : "—"}
                      </td>
                    ))}
                  </tr>
                  <tr>
                    <td className="p-3.5 font-medium text-[var(--text-secondary)]">
                      Özkaynak Kârlılığı (ROE %)
                    </td>
                    {companies.map((c) => (
                      <td
                        key={c.ticker}
                        className={`p-3.5 font-semibold ${
                          (c.multiples.roe_pct ?? 0) >= 20
                            ? "text-[var(--positive)]"
                            : "text-[var(--text)]"
                        }`}
                      >
                        {c.multiples.roe_pct !== null ? `${c.multiples.roe_pct}%` : "—"}
                      </td>
                    ))}
                  </tr>
                  <tr>
                    <td className="p-3.5 font-medium text-[var(--text-secondary)]">
                      Net Kâr Marjı (%)
                    </td>
                    {companies.map((c) => (
                      <td key={c.ticker} className="p-3.5 text-[var(--text)]">
                        {c.multiples.net_margin_pct !== null ? `${c.multiples.net_margin_pct}%` : "—"}
                      </td>
                    ))}
                  </tr>
                  <tr>
                    <td className="p-3.5 font-medium text-[var(--text-secondary)]">
                      Borç / Özkaynak Oranı
                    </td>
                    {companies.map((c) => (
                      <td key={c.ticker} className="p-3.5 text-[var(--text)]">
                        {c.multiples.debt_to_equity !== null ? c.multiples.debt_to_equity : "—"}
                      </td>
                    ))}
                  </tr>
                </>
              )}

              {/* Analist & Sinyal Matrisi */}
              {(activeTab === "all" || activeTab === "consensus") && (
                <>
                  <tr className="bg-[var(--surface-raised)] font-semibold text-[var(--text)]">
                    <td colSpan={companies.length + 1} className="p-2.5 text-[11px] uppercase tracking-wider">
                      Analist Beklentisi & TradeAI Sinyali
                    </td>
                  </tr>
                  <tr>
                    <td className="p-3.5 font-medium text-[var(--text-secondary)]">
                      TradeAI Kompozit Puanı
                    </td>
                    {companies.map((c) => (
                      <td key={c.ticker} className="p-3.5">
                        <span
                          className={`pill font-bold ${
                            c.signal.composite_score >= 60
                              ? "pill-positive"
                              : c.signal.composite_score <= 40
                              ? "pill-negative"
                              : "pill-neutral"
                          }`}
                        >
                          {c.signal.composite_score} / 100 ({signalName(c.signal.label)})
                        </span>
                      </td>
                    ))}
                  </tr>
                  <tr>
                    <td className="p-3.5 font-medium text-[var(--text-secondary)]">
                      Ortalama Analist Hedef Fiyatı
                    </td>
                    {companies.map((c) => (
                      <td key={c.ticker} className="p-3.5 font-medium text-[var(--text)]">
                        {c.consensus.target_price ? `₺${c.consensus.target_price.toFixed(2)}` : "—"}
                      </td>
                    ))}
                  </tr>
                  <tr>
                    <td className="p-3.5 font-medium text-[var(--text-secondary)]">
                      Konsensüs Getiri Potansiyeli
                    </td>
                    {companies.map((c) => (
                      <td
                        key={c.ticker}
                        className={`p-3.5 font-bold ${
                          (c.consensus.upside_pct ?? 0) > 0
                            ? "text-[var(--positive)]"
                            : "text-[var(--text-muted)]"
                        }`}
                      >
                        {c.consensus.upside_pct !== null
                          ? formatPercent(c.consensus.upside_pct, true)
                          : "—"}
                      </td>
                    ))}
                  </tr>
                  <tr>
                    <td className="p-3.5 font-medium text-[var(--text-secondary)]">
                      Kurum Tavsiye Dağılımı
                    </td>
                    {companies.map((c) => (
                      <td key={c.ticker} className="p-3.5 text-[11px] text-[var(--text-muted)]">
                        {c.consensus.buy_count} Al / {c.consensus.hold_count} Tut / {c.consensus.sell_count} Sat
                      </td>
                    ))}
                  </tr>
                </>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
