"use client";

import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ComposedChart,
  Funnel,
  FunnelChart,
  Legend,
  Line,
  LineChart,
  Pie,
  PieChart,
  PolarAngleAxis,
  PolarGrid,
  Radar,
  RadarChart,
  RadialBar,
  RadialBarChart,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  Treemap,
  XAxis,
  YAxis,
  ZAxis,
} from "recharts";

import type { ChartSpec, ChartType } from "@/lib/types";
import { useTranslations } from "next-intl";

const PALETTE = [
  "#7dd3fc",
  "#a5b4fc",
  "#86efac",
  "#fcd34d",
  "#f9a8d4",
  "#c4b5fd",
];

function isKnownType(t: string): t is ChartType {
  return (
    t === "radar" ||
    t === "pie" ||
    t === "donut" ||
    t === "line" ||
    t === "area" ||
    t === "bar" ||
    t === "bar_horizontal" ||
    t === "scatter" ||
    t === "radial_bar" ||
    t === "funnel" ||
    t === "composed" ||
    t === "treemap"
  );
}

function ChartInner({
  c,
  idx,
  seriesValue,
  seriesIndex,
}: {
  c: ChartSpec;
  idx: number;
  seriesValue: string;
  seriesIndex: string;
}) {
  const stroke = PALETTE[idx % PALETTE.length];
  const data = c.data;

  switch (c.type) {
    case "radar":
      return (
        <RadarChart data={data}>
          <PolarGrid />
          <PolarAngleAxis
            dataKey="name"
            tick={{ fill: "var(--foreground)", fontSize: 11 }}
          />
          <Radar
            name={seriesValue}
            dataKey="value"
            stroke={stroke}
            fill={stroke}
            fillOpacity={0.35}
          />
          <Tooltip />
        </RadarChart>
      );
    case "pie":
      return (
        <PieChart>
          <Pie
            data={data}
            dataKey="value"
            nameKey="name"
            cx="50%"
            cy="50%"
            outerRadius={88}
            label
          >
            {data.map((_, i) => (
              <Cell key={i} fill={PALETTE[i % PALETTE.length]} />
            ))}
          </Pie>
          <Tooltip />
        </PieChart>
      );
    case "donut":
      return (
        <PieChart>
          <Pie
            data={data}
            dataKey="value"
            nameKey="name"
            cx="50%"
            cy="50%"
            innerRadius={48}
            outerRadius={88}
            label
          >
            {data.map((_, i) => (
              <Cell key={i} fill={PALETTE[i % PALETTE.length]} />
            ))}
          </Pie>
          <Tooltip />
        </PieChart>
      );
    case "line":
      return (
        <LineChart data={data}>
          <CartesianGrid strokeDasharray="3 3" opacity={0.35} />
          <XAxis
            dataKey="name"
            tick={{ fill: "var(--foreground)", fontSize: 11 }}
          />
          <YAxis tick={{ fill: "var(--foreground)", fontSize: 11 }} />
          <Tooltip />
          <Line type="monotone" dataKey="value" dot stroke={stroke} />
        </LineChart>
      );
    case "area":
      return (
        <AreaChart data={data}>
          <CartesianGrid strokeDasharray="3 3" opacity={0.35} />
          <XAxis
            dataKey="name"
            tick={{ fill: "var(--foreground)", fontSize: 11 }}
          />
          <YAxis tick={{ fill: "var(--foreground)", fontSize: 11 }} />
          <Tooltip />
          <Area
            type="monotone"
            dataKey="value"
            stroke={stroke}
            fill={stroke}
            fillOpacity={0.25}
          />
        </AreaChart>
      );
    case "bar":
      return (
        <BarChart data={data}>
          <CartesianGrid strokeDasharray="3 3" opacity={0.35} />
          <XAxis
            dataKey="name"
            tick={{ fill: "var(--foreground)", fontSize: 11 }}
          />
          <YAxis tick={{ fill: "var(--foreground)", fontSize: 11 }} />
          <Tooltip />
          <Bar dataKey="value" radius={[4, 4, 0, 0]}>
            {data.map((_, i) => (
              <Cell key={i} fill={PALETTE[i % PALETTE.length]} />
            ))}
          </Bar>
        </BarChart>
      );
    case "bar_horizontal":
      return (
        <BarChart layout="vertical" data={data} margin={{ left: 8, right: 16 }}>
          <CartesianGrid strokeDasharray="3 3" opacity={0.35} />
          <XAxis type="number" tick={{ fill: "var(--foreground)", fontSize: 11 }} />
          <YAxis
            type="category"
            dataKey="name"
            width={72}
            tick={{ fill: "var(--foreground)", fontSize: 10 }}
          />
          <Tooltip />
          <Bar dataKey="value" radius={[0, 4, 4, 0]}>
            {data.map((_, i) => (
              <Cell key={i} fill={PALETTE[i % PALETTE.length]} />
            ))}
          </Bar>
        </BarChart>
      );
    case "scatter": {
      const pts = data.map((d, i) => ({
        name: d.name,
        x: i,
        y: d.value,
      }));
      return (
        <ScatterChart margin={{ top: 8, right: 8, bottom: 8, left: 8 }}>
          <CartesianGrid strokeDasharray="3 3" opacity={0.35} />
          <XAxis
            type="number"
            dataKey="x"
            name={seriesIndex}
            tick={{ fill: "var(--foreground)", fontSize: 11 }}
          />
          <YAxis
            type="number"
            dataKey="y"
            name={seriesValue}
            tick={{ fill: "var(--foreground)", fontSize: 11 }}
          />
          <ZAxis range={[60, 60]} />
          <Tooltip cursor={{ strokeDasharray: "3 3" }} />
          <Scatter name={c.title} data={pts} fill={stroke} />
        </ScatterChart>
      );
    }
    case "radial_bar": {
      const rd = data.map((d, i) => ({
        name: d.name,
        value: d.value,
        fill: PALETTE[i % PALETTE.length],
      }));
      return (
        <RadialBarChart
          cx="50%"
          cy="50%"
          innerRadius="18%"
          outerRadius="90%"
          barSize={12}
          data={rd}
        >
          <RadialBar dataKey="value" background cornerRadius={4} />
          <Tooltip />
        </RadialBarChart>
      );
    }
    case "funnel":
      return (
        <FunnelChart>
          <Tooltip />
          <Funnel dataKey="value" data={data} isAnimationActive>
            {data.map((_, i) => (
              <Cell key={i} fill={PALETTE[i % PALETTE.length]} />
            ))}
          </Funnel>
        </FunnelChart>
      );
    case "composed": {
      const composedData = data.map((d) => ({
        name: d.name,
        value: d.value,
        value2:
          typeof d.value2 === "number"
            ? d.value2
            : Number(d.value) * 0.62,
      }));
      return (
        <ComposedChart data={composedData}>
          <CartesianGrid strokeDasharray="3 3" opacity={0.35} />
          <XAxis
            dataKey="name"
            tick={{ fill: "var(--foreground)", fontSize: 11 }}
          />
          <YAxis tick={{ fill: "var(--foreground)", fontSize: 11 }} />
          <Tooltip />
          <Legend />
          <Bar dataKey="value" fill={PALETTE[0]} radius={[2, 2, 0, 0]} />
          <Line
            type="monotone"
            dataKey="value2"
            stroke={PALETTE[2]}
            dot={false}
          />
        </ComposedChart>
      );
    }
    case "treemap": {
      const tree = [
        {
          name: c.title,
          children: data.map((d) => ({
            name: d.name,
            size: Math.max(1, d.value),
          })),
        },
      ];
      return (
        <Treemap
          data={tree}
          dataKey="size"
          aspectRatio={4 / 3}
          stroke="var(--border)"
          fill={PALETTE[0]}
          nameKey="name"
        >
          <Tooltip />
        </Treemap>
      );
    }
    default:
      return null;
  }
}

/** Matches backend GLOBAL_MAX_REPORT_CHARTS — keep in sync manually. */
const MAX_REPORT_CHARTS = 20;

export function ReportCharts({ charts }: { charts: ChartSpec[] }) {
  const t = useTranslations("report");
  const seriesValue = t("chartSeriesValue");
  const seriesIndex = t("chartSeriesIndex");
  const safe = charts.filter((c) => isKnownType(c.type));
  const list = (safe.length ? safe : charts).slice(0, MAX_REPORT_CHARTS);

  return (
    <div className="grid gap-6 print:grid-cols-1 md:grid-cols-2 xl:grid-cols-3">
      {list.map((c, idx) => {
        const tType = isKnownType(c.type) ? c.type : "pie";
        const spec = isKnownType(c.type) ? c : { ...c, type: "pie" as const };
        if (!isKnownType(c.type)) {
          console.warn("Unknown chart type, falling back to pie:", c.type);
        }
        return (
          <div
            key={`${c.title}-${idx}`}
            className="rounded-lg border border-border bg-card p-4 print:break-inside-avoid"
          >
            <div className="mb-2 text-sm font-medium">{c.title}</div>
            <div className="h-64 w-full print:h-56">
              <ResponsiveContainer width="100%" height="100%">
                <ChartInner
                  c={{ ...spec, type: tType }}
                  idx={idx}
                  seriesValue={seriesValue}
                  seriesIndex={seriesIndex}
                />
              </ResponsiveContainer>
            </div>
          </div>
        );
      })}
    </div>
  );
}
