// lib/ws.ts
"use client";

import { useEffect, useRef, useState } from "react";
import type { MetricsSnapshot } from "@/types/gateway";

const BASE_WS = (
  process.env.NEXT_PUBLIC_GATEWAY_URL ?? "http://localhost:8000"
).replace(/^http/, "ws");

export function useMetricsFeed(fallback: MetricsSnapshot): MetricsSnapshot {
  const [metrics, setMetrics] = useState<MetricsSnapshot>(fallback);
  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    let cancelled = false;

    const connect = () => {
      if (cancelled) return;
      const ws = new WebSocket(`${BASE_WS}/v1/metrics/ws`);
      ws.onmessage = (e) => {
        try {
          setMetrics(JSON.parse(e.data));
        } catch {}
      };
      ws.onclose = () => {
        if (!cancelled) setTimeout(connect, 3000);
      };
      wsRef.current = ws;
    };

    connect();
    return () => {
      cancelled = true;
      wsRef.current?.close();
    };
  }, []);

  return metrics;
}
