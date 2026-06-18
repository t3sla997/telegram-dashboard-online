
import json
from pathlib import Path
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from collections import Counter, defaultdict
from html import escape

import streamlit as st
import streamlit.components.v1 as components
import plotly.graph_objects as go
import requests


LOCAL_TZ = ZoneInfo("Europe/Rome")

st.set_page_config(
    page_title="Traffico Telegram Online",
    page_icon="🌐",
    layout="wide"
)


LOCAL_CONFIG_PATH = Path(r"C:\Users\Administrator\supabase_config.json")


EVENT_LABELS = {
    "sent_group_message": "Msg gruppi inviati",
    "received_group_message": "Msg gruppi ricevuti",
    "received_private_message": "Privati ricevuti",
    "sent_private_voice": "Vocali privati",
    "sent_private_message_2": "Secondo messaggio privato",
    "sent_private_link": "Link privati",
    "mention_received": "Menzioni",
    "reply_to_bot_message": "Reply al bot",
    "login_ok": "Login OK",
    "login_error": "Login errori",
    "send_group_error": "Errori invio gruppo",
    "send_group_floodwait": "FloodWait gruppo",
    "blocked_group_detected": "Gruppi bloccati",
    "blocked_group_skip": "Skip gruppi bloccati",
    "account_heartbeat": "Heartbeat account",
    "test_metric": "Test metric",
}

DEFAULT_GRAPH_EVENTS = [
    "sent_group_message",
    "received_private_message",
    "sent_private_link",
    "mention_received",
    "reply_to_bot_message",
    "login_error",
    "send_group_error",
    "blocked_group_detected",
]

DEFAULT_KPIS = [
    "ACCOUNT_ACTIVE",
    "ACCOUNT_INACTIVE",
    "sent_group_message",
    "received_group_message",
    "received_private_message",
    "sent_private_link",
    "mention_received",
]

KPI_LABELS = {
    "ACCOUNT_ACTIVE": "Account attivi",
    "ACCOUNT_INACTIVE": "Account inattivi",
    **EVENT_LABELS
}


def load_config():
    # In locale leggiamo prima il file JSON, così non compare l'errore rosso "No secrets files found".
    if LOCAL_CONFIG_PATH.exists():
        return json.loads(LOCAL_CONFIG_PATH.read_text(encoding="utf-8"))

    # In Streamlit Cloud useremo invece st.secrets.
    try:
        return {
            "SUPABASE_URL": st.secrets["SUPABASE_URL"],
            "SUPABASE_SERVICE_ROLE_KEY": st.secrets["SUPABASE_SERVICE_ROLE_KEY"],
        }
    except Exception as e:
        st.error(
            "Config Supabase non trovata. In locale serve "
            "C:\\Users\\Administrator\\supabase_config.json; online servono i secrets Streamlit."
        )
        st.stop()


config = load_config()

SUPABASE_URL = config["SUPABASE_URL"].rstrip("/")
SUPABASE_KEY = config["SUPABASE_SERVICE_ROLE_KEY"]

HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
}


def parse_ts(ts):
    if not ts:
        return None
    try:
        return datetime.fromisoformat(str(ts).replace("Z", "+00:00")).astimezone(LOCAL_TZ)
    except Exception:
        return None


def iso(dt):
    return dt.astimezone(timezone.utc).isoformat()


def label_for_event(event_type):
    return EVENT_LABELS.get(event_type, event_type)


def label_for_kpi(item):
    return KPI_LABELS.get(item, item)


def sb_get(table, params=None, timeout=60):
    url = f"{SUPABASE_URL}/rest/v1/{table}"

    r = requests.get(
        url,
        headers=HEADERS,
        params=params or {},
        timeout=timeout
    )

    if r.status_code not in (200, 206):
        raise RuntimeError(f"Supabase GET {table} status={r.status_code}: {r.text[:1000]}")

    return r.json()


def short_value(v, max_len=160):
    if v is None:
        return ""

    # Converte timestamp Supabase/UTC in ora italiana per le tabelle.
    if isinstance(v, str) and "T" in v and ("+00:00" in v or v.endswith("Z")):
        dt = parse_ts(v)
        if dt:
            s = dt.strftime("%Y-%m-%d %H:%M:%S")
        else:
            s = str(v)
    else:
        s = str(v)

    if len(s) > max_len:
        return s[:max_len] + "..."
    return s


def status_badge(is_active):
    if is_active:
        return '<span class="badge active">ATTIVO</span>'
    return '<span class="badge inactive">INATTIVO</span>'


def render_table(rows, columns, max_rows=200, status_key=None, height=420):
    if not rows:
        components.html("<p>Nessun dato.</p>", height=80)
        return

    html = """
    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
            margin: 0;
            padding: 0;
            color: #262730;
            background: white;
        }
        .table-wrap {
            width: 100%;
            overflow: auto;
            border: 1px solid #ececec;
            border-radius: 10px;
        }
        table {
            border-collapse: collapse;
            width: 100%;
            font-size: 13px;
        }
        th {
            position: sticky;
            top: 0;
            background: #f8f9fb;
            border-bottom: 1px solid #ddd;
            padding: 8px;
            text-align: left;
            white-space: nowrap;
            z-index: 2;
        }
        td {
            border-bottom: 1px solid #eee;
            padding: 7px 8px;
            vertical-align: top;
            white-space: nowrap;
        }
        tr.active-row { background: #f6fff8; }
        tr.inactive-row { background: #fff5f5; }
        .badge {
            padding: 3px 8px;
            border-radius: 999px;
            font-weight: 700;
            font-size: 12px;
        }
        .badge.active {
            background: #d7f8df;
            color: #137333;
        }
        .badge.inactive {
            background: #ffd6d6;
            color: #a10000;
        }
    </style>
    <div class="table-wrap">
    <table>
    <thead>
    <tr>
    """

    for key, label in columns:
        html += f"<th>{escape(label)}</th>"

    html += "</tr></thead><tbody>"

    for row in rows[:max_rows]:
        is_active = bool(row.get(status_key)) if status_key else False
        row_class = "active-row" if is_active else "inactive-row" if status_key else ""

        html += f'<tr class="{row_class}">'

        for key, label in columns:
            value = row.get(key, "")

            if key == status_key:
                value_html = status_badge(bool(value))
            else:
                value_html = escape(short_value(value))

            html += f"<td>{value_html}</td>"

        html += "</tr>"

    html += "</tbody></table></div>"

    components.html(html, height=height, scrolling=True)


def floor_bucket(dt, hours):
    # Per periodi lunghi raggruppo per ora, per periodi brevi per minuto.
    if hours <= 3:
        return dt.replace(second=0, microsecond=0)
    return dt.replace(minute=0, second=0, microsecond=0)


def load_data(hours):
    now = datetime.now(timezone.utc)
    since = now - timedelta(hours=hours)

    metrics = sb_get(
        "metrics_minute",
        params={
            "select": "*",
            "minute": f"gte.{iso(since)}",
            "order": "minute.asc",
            "limit": "10000"
        }
    )

    groups = sb_get(
        "group_metrics",
        params={
            "select": "*",
            "minute": f"gte.{iso(since)}",
            "order": "minute.desc",
            "limit": "10000"
        }
    )

    accounts = sb_get(
        "account_status",
        params={
            "select": "*",
            "order": "updated_at.desc",
            "limit": "300"
        }
    )

    errors = sb_get(
        "recent_errors",
        params={
            "select": "*",
            "ts": f"gte.{iso(since)}",
            "order": "ts.desc",
            "limit": "300"
        }
    )

    return metrics, groups, accounts, errors


def filter_by_accounts(rows, selected_accounts):
    if not selected_accounts:
        return rows
    return [r for r in rows if r.get("account") in selected_accounts]


def aggregate_metric_counts(metrics):
    counter = Counter()

    for r in metrics:
        et = r.get("event_type")
        count = int(r.get("count") or 0)
        if et:
            counter[et] += count

    return counter


def make_line_chart(metrics, selected_events, hours):
    if not selected_events:
        return None

    buckets = defaultdict(Counter)

    for r in metrics:
        et = r.get("event_type")
        if et not in selected_events:
            continue

        dt = parse_ts(r.get("minute"))
        if not dt:
            continue

        bucket = floor_bucket(dt, hours)
        buckets[bucket][et] += int(r.get("count") or 0)

    if not buckets:
        return None

    x_values = sorted(buckets.keys())
    fig = go.Figure()

    for et in selected_events:
        y_values = [buckets[x].get(et, 0) for x in x_values]
        if sum(y_values) == 0:
            continue

        fig.add_trace(go.Scatter(
            x=x_values,
            y=y_values,
            mode="lines+markers",
            name=label_for_event(et)
        ))

    fig.update_layout(
        title="Eventi online per periodo — ora italiana",
        height=430,
        margin=dict(l=20, r=20, t=55, b=20),
        xaxis_title="Ora italiana",
        yaxis_title="Conteggio",
        legend_title="Evento",
    )

    return fig


def aggregate_groups(groups):
    agg = {}

    for r in groups:
        gid = r.get("group_id")
        if not gid:
            continue

        if gid not in agg:
            agg[gid] = {
                "group_title": r.get("group_title") or "(nome non salvato)",
                "group_id": gid,
                "sent": 0,
                "received": 0,
                "mentions": 0,
                "reply_bot": 0,
                "errors": 0,
                "blocked": 0,
                "score": 0,
                "rows": 0,
            }

        row = agg[gid]
        if r.get("group_title"):
            row["group_title"] = r.get("group_title")

        row["sent"] += int(r.get("sent") or 0)
        row["received"] += int(r.get("received") or 0)
        row["mentions"] += int(r.get("mentions") or 0)
        row["reply_bot"] += int(r.get("reply_bot") or 0)
        row["errors"] += int(r.get("errors") or 0)
        row["blocked"] += int(r.get("blocked") or 0)
        row["score"] += float(r.get("score") or 0)
        row["rows"] += 1

    rows = list(agg.values())
    rows.sort(key=lambda x: x["score"], reverse=True)
    return rows


def make_group_chart(group_rows):
    top = group_rows[:20]
    if not top:
        return None

    labels = []
    values = []

    for r in top[::-1]:
        title = r.get("group_title") or "(senza nome)"
        gid = r.get("group_id")
        labels.append(f"{title} | {gid}")
        values.append(r.get("score") or 0)

    fig = go.Figure(go.Bar(
        x=values,
        y=labels,
        orientation="h"
    ))

    fig.update_layout(
        title="Top 20 gruppi online per score",
        height=620,
        margin=dict(l=20, r=20, t=55, b=20),
        xaxis_title="Score",
        yaxis_title="Gruppo",
    )

    return fig


def make_event_distribution_chart(metric_counts):
    rows = metric_counts.most_common(30)
    if not rows:
        return None

    labels = [label_for_event(k) for k, v in rows][::-1]
    values = [v for k, v in rows][::-1]

    fig = go.Figure(go.Bar(
        x=values,
        y=labels,
        orientation="h"
    ))

    fig.update_layout(
        title="Distribuzione eventi online",
        height=520,
        margin=dict(l=20, r=20, t=55, b=20),
        xaxis_title="Conteggio",
        yaxis_title="Evento",
    )

    return fig


# ============================================================
# UI
# ============================================================

st.title("🌐 Traffico Telegram Online")
st.caption("Gli orari sono convertiti in Europe/Rome / ora italiana.")

with st.sidebar:
    st.header("Filtri")

    hours = st.selectbox(
        "Periodo",
        options=[1, 3, 6, 12, 24, 48, 72, 168],
        index=4,
        format_func=lambda x: f"Ultime {x} ore" if x < 168 else "Ultimi 7 giorni"
    )

    refresh_seconds = st.selectbox(
        "Refresh automatico",
        options=[30, 60, 120, 300],
        index=1,
        format_func=lambda x: f"{x} secondi"
    )

st.markdown(
    f"""
    <script>
        setTimeout(function(){{
            window.location.reload();
        }}, {refresh_seconds * 1000});
    </script>
    """,
    unsafe_allow_html=True
)

try:
    metrics, groups, accounts, errors = load_data(hours)
except Exception as e:
    st.error(f"Errore caricamento dati da Supabase: {type(e).__name__}: {e}")
    st.stop()

all_accounts = sorted({a.get("account") for a in accounts if a.get("account")})

with st.sidebar:
    selected_accounts = st.multiselect(
        "Account",
        options=all_accounts,
        default=all_accounts
    )

metrics = filter_by_accounts(metrics, selected_accounts)
groups = filter_by_accounts(groups, selected_accounts)
accounts = filter_by_accounts(accounts, selected_accounts)
errors = filter_by_accounts(errors, selected_accounts)

metric_counts = aggregate_metric_counts(metrics)
all_event_types = sorted(metric_counts.keys())

with st.sidebar:
    selected_graph_events = st.multiselect(
        "Eventi nel grafico",
        options=all_event_types,
        default=[x for x in DEFAULT_GRAPH_EVENTS if x in all_event_types],
        format_func=label_for_event
    )

    selected_kpis = st.multiselect(
        "Metriche in alto",
        options=["ACCOUNT_ACTIVE", "ACCOUNT_INACTIVE"] + all_event_types,
        default=[x for x in DEFAULT_KPIS if x in ["ACCOUNT_ACTIVE", "ACCOUNT_INACTIVE"] + all_event_types],
        format_func=label_for_kpi
    )

active_count = sum(1 for a in accounts if a.get("is_active"))
inactive_count = len(accounts) - active_count

kpi_values = {
    "ACCOUNT_ACTIVE": active_count,
    "ACCOUNT_INACTIVE": inactive_count,
}

for et in all_event_types:
    kpi_values[et] = metric_counts.get(et, 0)

if selected_kpis:
    for i in range(0, len(selected_kpis), 6):
        chunk = selected_kpis[i:i+6]
        cols = st.columns(len(chunk))

        for col, item in zip(cols, chunk):
            with col:
                st.metric(label_for_kpi(item), kpi_values.get(item, 0))

st.subheader("👤 Stato account online")

account_rows = []

for a in accounts:
    account_rows.append({
        "is_active": a.get("is_active"),
        "account": a.get("account"),
        "last_seen": a.get("last_seen"),
        "current_proxy": a.get("current_proxy"),
        "last_login_ok": a.get("last_login_ok"),
        "last_error": a.get("last_error"),
        "sent_group_1h": a.get("sent_group_1h"),
        "received_group_1h": a.get("received_group_1h"),
        "private_received_1h": a.get("private_received_1h"),
        "private_link_1h": a.get("private_link_1h"),
        "mentions_1h": a.get("mentions_1h"),
        "blocked_groups_1h": a.get("blocked_groups_1h"),
        "updated_at": a.get("updated_at"),
    })

account_rows.sort(key=lambda r: (not bool(r.get("is_active")), r.get("account") or ""))

render_table(
    account_rows,
    [
        ("is_active", "Stato"),
        ("account", "Account"),
        ("last_seen", "Last seen"),
        ("current_proxy", "Proxy"),
        ("last_login_ok", "Last login OK"),
        ("sent_group_1h", "Msg gruppi 1h"),
        ("received_group_1h", "Ricevuti gruppi 1h"),
        ("private_received_1h", "Privati 1h"),
        ("private_link_1h", "Link privati 1h"),
        ("mentions_1h", "Menzioni 1h"),
        ("blocked_groups_1h", "Blocked 1h"),
        ("last_error", "Ultimo errore"),
        ("updated_at", "Updated"),
    ],
    max_rows=300,
    status_key="is_active",
    height=440
)

st.subheader("📈 Andamento eventi online")

fig_line = make_line_chart(metrics, selected_graph_events, hours)

if fig_line:
    st.plotly_chart(fig_line, use_container_width=True)
else:
    st.info("Nessun evento selezionato o nessun dato nel periodo.")

st.subheader("🔥 Gruppi migliori online")

group_rows = aggregate_groups(groups)

fig_group = make_group_chart(group_rows)

if fig_group:
    st.plotly_chart(fig_group, use_container_width=True)

render_table(
    group_rows,
    [
        ("group_title", "Nome gruppo"),
        ("group_id", "ID gruppo"),
        ("score", "Score"),
        ("sent", "Msg inviati"),
        ("received", "Msg ricevuti"),
        ("mentions", "Menzioni"),
        ("reply_bot", "Reply bot"),
        ("errors", "Errori"),
        ("blocked", "Blocked"),
        ("rows", "Righe aggregate"),
    ],
    max_rows=200,
    height=430
)

st.subheader("📌 Distribuzione eventi online")

fig_dist = make_event_distribution_chart(metric_counts)

if fig_dist:
    st.plotly_chart(fig_dist, use_container_width=True)
else:
    st.info("Nessuna distribuzione disponibile.")

st.subheader("🚨 Errori recenti online")

error_rows = []

for e in errors[:300]:
    error_rows.append({
        "ts": e.get("ts"),
        "account": e.get("account"),
        "group_id": e.get("group_id"),
        "error_type": e.get("error_type"),
        "error_message": e.get("error_message"),
        "metadata": e.get("metadata"),
    })

render_table(
    error_rows,
    [
        ("ts", "Timestamp"),
        ("account", "Account"),
        ("group_id", "Gruppo"),
        ("error_type", "Tipo"),
        ("error_message", "Errore"),
        ("metadata", "Metadata"),
    ],
    max_rows=300,
    height=430
)
