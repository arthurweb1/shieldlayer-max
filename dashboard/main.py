"""ShieldLayer Max — Enterprise Analytics Dashboard.

Three panels:
  1. Cost-Savings Tracker  — cache hit rate, estimated cloud spend avoided
  2. EU AI Act Compliance Heatmap — radar chart of compliance by article
  3. PII Metrics — entity type breakdown over time

Run: streamlit run dashboard/main.py
"""
from __future__ import annotations

import asyncio
import json
import os
from datetime import datetime, timedelta, timezone
from typing import Any

import asyncpg
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="ShieldLayer Max — Analytics",
    page_icon="🛡",
    layout="wide",
)

# ── Obsidian Vault CSS ────────────────────────────────────────────────────────
st.markdown("""
<style>
  @import url('https://api.fontshare.com/v2/css?f[]=clash-display@700,600&display=swap');
  @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600&display=swap');
  .stApp { background: #0D0D0D; color: #F8F8F8; }
  h1, h2, h3 { font-family: 'Clash Display', sans-serif !important; color: #DFFF00; }
  .metric-card {
    background: rgba(255,255,255,0.03);
    border: 1px solid rgba(223,255,0,0.2);
    padding: 20px 24px;
    margin-bottom: 12px;
  }
  .metric-value { font-family: 'JetBrains Mono', monospace; font-size: 2rem; color: #DFFF00; }
  .metric-label { font-size: 0.75rem; letter-spacing: 0.15em; text-transform: uppercase; color: rgba(248,248,248,0.4); }
  .stMetric label { color: rgba(248,248,248,0.5) !important; font-size: 0.7rem !important; letter-spacing: 0.1em !important; text-transform: uppercase !important; }
  .stMetric [data-testid="stMetricValue"] { font-family: 'JetBrains Mono', monospace !important; color: #DFFF00 !important; }
  div[data-testid="stHorizontalBlock"] > div { border-right: 1px solid rgba(248,248,248,0.06); }
  div[data-testid="stHorizontalBlock"] > div:last-child { border-right: none; }
</style>
""", unsafe_allow_html=True)

PLOTLY_LAYOUT = dict(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(family="JetBrains Mono, monospace", color="#F8F8F8"),
    xaxis=dict(gridcolor="rgba(248,248,248,0.06)", linecolor="rgba(248,248,248,0.1)"),
    yaxis=dict(gridcolor="rgba(248,248,248,0.06)", linecolor="rgba(248,248,248,0.1)"),
    margin=dict(l=40, r=20, t=40, b=40),
)

CYBER_LIME = "#DFFF00"

# ── DB connection ─────────────────────────────────────────────────────────────
def _get_dsn() -> str:
    from app.config import get_settings
    s = get_settings()
    # Use RO user if password is configured
    if s.postgres_ro_password:
        import re
        dsn = re.sub(r"postgresql://[^:]+:[^@]+@", f"postgresql://shieldlayer_ro:{s.postgres_ro_password}@", s.postgres_dsn)
        return dsn
    return s.postgres_dsn


@st.cache_data(ttl=30)
def load_audit_data(hours: int = 24) -> pd.DataFrame:
    """Load audit events from the last N hours. Cached 30s."""
    async def _fetch() -> list[dict]:
        dsn = _get_dsn()
        pool = await asyncpg.create_pool(dsn, min_size=1, max_size=3)
        since = datetime.now(timezone.utc) - timedelta(hours=hours)
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """SELECT ts, compliant, article_ref, duration_ms,
                          pii_stats, cached
                   FROM audit_events
                   WHERE ts >= $1
                   ORDER BY ts ASC""",
                since,
            )
        await pool.close()
        result = []
        for r in rows:
            d = dict(r)
            # asyncpg returns JSONB as str if codec not set — parse defensively
            if isinstance(d.get("pii_stats"), str):
                d["pii_stats"] = json.loads(d["pii_stats"])
            result.append(d)
        return result

    try:
        rows = asyncio.run(_fetch())
    except Exception as e:
        st.error(f"Database connection failed: {e}")
        return pd.DataFrame()

    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows)
    df["ts"] = pd.to_datetime(df["ts"], utc=True)
    df["hour"] = df["ts"].dt.floor("h")
    return df


# ── Header ────────────────────────────────────────────────────────────────────
st.title("■ ShieldLayer Max")
st.caption("Enterprise AI Governance · Analytics Dashboard")

col_r, col_p = st.columns([3, 1])
with col_p:
    hours = st.selectbox("Window", [1, 6, 24, 168], index=2, format_func=lambda h: f"Last {h}h")

df = load_audit_data(hours)

if df.empty:
    st.warning("No audit data found for the selected window. Is the proxy receiving traffic?")
    st.stop()

# ═══════════════════════════════════════════════════════════════════════════════
# PANEL 1 — COST-SAVINGS TRACKER
# ═══════════════════════════════════════════════════════════════════════════════
st.markdown("---")
st.subheader("Cost-Savings Tracker")

total_requests  = len(df)
cached_requests = int(df["cached"].sum()) if "cached" in df.columns else 0
cache_hit_rate  = cached_requests / total_requests if total_requests > 0 else 0

# Estimate avg tokens per request (rough heuristic: 500 tokens)
AVG_TOKENS = 500
from app.config import get_settings as _gs
_price = _gs().cloud_price_per_1k_tokens
saved_tokens  = cached_requests * AVG_TOKENS
saved_cost    = saved_tokens / 1000 * _price
total_cost    = total_requests * AVG_TOKENS / 1000 * _price
avoided_pct   = cache_hit_rate * 100

c1, c2, c3, c4 = st.columns(4)
c1.metric("Total Requests",   f"{total_requests:,}")
c2.metric("Cache Hits",       f"{cached_requests:,}", delta=f"{avoided_pct:.1f}% hit rate")
c3.metric("Estimated Savings", f"€{saved_cost:.2f}",  delta=f"of €{total_cost:.2f} total")
c4.metric("Avg Latency",      f"{df['duration_ms'].mean():.0f} ms")

# Cache hit rate over time
if "hour" in df.columns and len(df["hour"].unique()) > 1:
    hourly = df.groupby("hour").agg(
        total=("cached", "count"),
        hits=("cached", "sum"),
    ).reset_index()
    hourly["hit_rate"] = hourly["hits"] / hourly["total"] * 100

    fig_cache = go.Figure()
    fig_cache.add_trace(go.Bar(
        x=hourly["hour"], y=hourly["hit_rate"],
        name="Cache Hit %",
        marker_color=CYBER_LIME,
        marker_opacity=0.8,
    ))
    fig_cache.update_layout(
        title="Cache Hit Rate (% per hour)",
        yaxis_title="Hit Rate %",
        yaxis_range=[0, 100],
        **PLOTLY_LAYOUT,
    )
    st.plotly_chart(fig_cache, use_container_width=True)

# ═══════════════════════════════════════════════════════════════════════════════
# PANEL 2 — EU AI ACT COMPLIANCE HEATMAP (RADAR)
# ═══════════════════════════════════════════════════════════════════════════════
st.markdown("---")
st.subheader("EU AI Act Compliance Heatmap")

ARTICLES = ["Art. 10", "Art. 11", "Art. 12", "Art. 13", "Art. 14", "Art. 15"]

# Count violations per article
violations: dict[str, int] = {}
if "article_ref" in df.columns:
    blocked = df[df["compliant"] == False]
    for art in ARTICLES:
        violations[art] = int((blocked["article_ref"].str.contains(art, na=False)).sum())

total_blocked = int((df["compliant"] == False).sum()) if "compliant" in df.columns else 0
compliance_rate = (1 - total_blocked / total_requests) * 100 if total_requests > 0 else 100

# Radar: compliance score per article (inverse of violation density)
max_v = max(violations.values()) if violations and max(violations.values()) > 0 else 1
radar_values = [max(0, 100 - (violations.get(a, 0) / max_v * 100)) for a in ARTICLES]
radar_values_closed = radar_values + [radar_values[0]]
articles_closed = ARTICLES + [ARTICLES[0]]

fig_radar = go.Figure()
fig_radar.add_trace(go.Scatterpolar(
    r=radar_values_closed,
    theta=articles_closed,
    fill="toself",
    name="Compliance Score",
    line_color=CYBER_LIME,
    fillcolor="rgba(223,255,0,0.08)",
))
fig_radar.update_layout(
    polar=dict(
        bgcolor="rgba(0,0,0,0)",
        radialaxis=dict(
            visible=True, range=[0, 100],
            gridcolor="rgba(248,248,248,0.1)",
            linecolor="rgba(248,248,248,0.1)",
            tickfont=dict(color="rgba(248,248,248,0.4)", size=9),
        ),
        angularaxis=dict(
            gridcolor="rgba(248,248,248,0.1)",
            linecolor="rgba(248,248,248,0.15)",
            tickfont=dict(color="#F8F8F8", size=11),
        ),
    ),
    title=f"Compliance Score by Article — Overall: {compliance_rate:.1f}%",
    paper_bgcolor="rgba(0,0,0,0)",
    font=dict(family="JetBrains Mono, monospace", color="#F8F8F8"),
    margin=dict(l=60, r=60, t=60, b=40),
)

r_col, v_col = st.columns([2, 1])
with r_col:
    st.plotly_chart(fig_radar, use_container_width=True)
with v_col:
    st.markdown("**Violations by Article**")
    for art, cnt in violations.items():
        color = "#FF2D55" if cnt > 0 else "rgba(248,248,248,0.3)"
        st.markdown(
            f'<div style="font-family:JetBrains Mono;font-size:12px;padding:4px 0;'
            f'border-bottom:1px solid rgba(248,248,248,0.06)">'
            f'<span style="color:{CYBER_LIME}">{art}</span> '
            f'<span style="color:{color};float:right">{cnt} violations</span>'
            f'</div>',
            unsafe_allow_html=True,
        )
    st.markdown(f"<br><small style='color:rgba(248,248,248,0.3)'>Total blocked: {total_blocked} / {total_requests}</small>", unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════════════════════════
# PANEL 3 — PII METRICS
# ═══════════════════════════════════════════════════════════════════════════════
st.markdown("---")
st.subheader("PII Metrics")

# Aggregate pii_stats across all rows
entity_totals: dict[str, int] = {}
if "pii_stats" in df.columns:
    for stats in df["pii_stats"]:
        if isinstance(stats, dict):
            for entity, count in stats.items():
                entity_totals[entity] = entity_totals.get(entity, 0) + count

if entity_totals:
    ent_df = pd.DataFrame(
        sorted(entity_totals.items(), key=lambda x: x[1], reverse=True),
        columns=["entity_type", "count"],
    )

    fig_pii = go.Figure(go.Bar(
        x=ent_df["entity_type"],
        y=ent_df["count"],
        marker_color=CYBER_LIME,
        marker_opacity=0.85,
    ))
    fig_pii.update_layout(
        title="PII Entity Types Masked (Total)",
        xaxis_title="Entity Type",
        yaxis_title="Count",
        **PLOTLY_LAYOUT,
    )
    st.plotly_chart(fig_pii, use_container_width=True)

    # PII over time
    if "hour" in df.columns and len(df["hour"].unique()) > 1:
        time_records = []
        for _, row in df.iterrows():
            stats = row.get("pii_stats", {})
            if isinstance(stats, dict):
                for entity, count in stats.items():
                    time_records.append({"hour": row["hour"], "entity": entity, "count": count})

        if time_records:
            time_df = pd.DataFrame(time_records)
            pivot = time_df.groupby(["hour", "entity"])["count"].sum().unstack(fill_value=0).reset_index()

            fig_time = go.Figure()
            colors = [CYBER_LIME, "#00FFF9", "#FF2D55", "#FF9F0A", "#30D158", "#BF5AF2"]
            for i, col in enumerate([c for c in pivot.columns if c != "hour"]):
                fig_time.add_trace(go.Scatter(
                    x=pivot["hour"], y=pivot[col],
                    name=col,
                    mode="lines+markers",
                    line=dict(color=colors[i % len(colors)], width=2),
                    marker=dict(size=4),
                ))
            fig_time.update_layout(
                title="PII Events per Hour by Entity Type",
                yaxis_title="Count",
                **PLOTLY_LAYOUT,
            )
            st.plotly_chart(fig_time, use_container_width=True)
else:
    st.info("No PII data found for the selected window.")

# ── Footer ────────────────────────────────────────────────────────────────────
st.markdown("---")
st.caption(f"ShieldLayer Max · Last refreshed: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')} · EU AI Act Art. 10/12/13")
