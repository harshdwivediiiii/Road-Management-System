from __future__ import annotations

from collections import Counter
from datetime import datetime

from flask import Response

from storage import (
    get_all_potholes,
    get_counts,
    get_hourly_counts,
    get_severity_counts,
    get_status_counts,
    get_zone_counts,
)


# ── Data helpers — mirror the API logic but call storage directly ────
# Flask dev-server is single-threaded so HTTP self-calls deadlock.
# These functions replicate what /api/potholes, /api/stats and
# /api/hotspots return, but without going through the network.


def _data_potholes(limit: int = 100) -> list:
    """Same result as GET /api/potholes → potholes list."""
    try:
        return get_all_potholes(limit=limit)
    except Exception as exc:
        print(f"[DASHBOARD][ERROR] potholes query failed: {exc}")
        return []


def _data_stats() -> dict:
    """Same result as GET /api/stats."""
    try:
        counts = get_counts()
        total = counts.get("total", 0)
        fixed = counts.get("fixed", 0)
        fix_rate = round((fixed / total) * 100, 2) if total else 0.0
        return {
            **counts,
            "fix_rate": fix_rate,
            "hourly": get_hourly_counts(hours=8),
            "zones": get_zone_counts(),
            "status_counts": get_status_counts(),
            "severity_counts": get_severity_counts(),
        }
    except Exception as exc:
        print(f"[DASHBOARD][ERROR] stats query failed: {exc}")
        return {}


def _data_hotspots() -> list:
    """Same result as GET /api/hotspots."""
    try:
        zones = get_zone_counts()
        return [z for z in zones if z.get("count", 0) > 1]
    except Exception as exc:
        print(f"[DASHBOARD][ERROR] hotspots query failed: {exc}")
        return []


# ── Dash imports (graceful fallback) ─────────────────────────────────
try:
    import dash
    import plotly.graph_objects as go
    from dash import Input, Output, State, callback_context, dash_table, dcc, html
except ImportError:  # pragma: no cover
    dash = None
    go = None
    Input = Output = State = callback_context = dash_table = dcc = html = None


COLORS = {
    "bg": "#0b0f1a",
    "panel": "#111827",
    "orange": "#f97316",
    "green": "#22c55e",
    "red": "#ef4444",
    "yellow": "#eab308",
    "blue": "#38bdf8",
    "purple": "#a78bfa",
    "text": "#e5e7eb",
    "muted": "#94a3b8",
}


# ── Mount entrypoint ─────────────────────────────────────────────────


def mount_dashboard(server):
    """Mount the Plotly Dash dashboard on the shared Flask server."""
    if dash is None:

        @server.get("/dashboard/")
        def dashboard_unavailable() -> Response:
            return Response(
                "<h1>RoadWatch AI Dashboard</h1>"
                "<p>Dash is not installed in this environment.</p>",
                mimetype="text/html",
            )

        print("[DASH][WARN] Dash not installed. Fallback route registered.")
        return None

    app = dash.Dash(
        __name__,
        server=server,
        routes_pathname_prefix="/dashboard/",
        suppress_callback_exceptions=True,
    )
    app.title = "RoadWatch AI Dashboard"
    app.layout = _build_layout()
    _register_callbacks(app)
    return app


# ── Reusable style helpers ───────────────────────────────────────────


def _panel_style() -> dict:
    return {
        "backgroundColor": COLORS["panel"],
        "border": "1px solid #1f2937",
        "borderRadius": "18px",
        "padding": "18px",
        "boxShadow": "0 12px 30px rgba(0,0,0,0.2)",
    }


def _card(title: str, value_id: str, color: str):
    return html.Div(
        [
            html.Div(title, style={"color": COLORS["muted"], "fontSize": "12px"}),
            html.Div(
                id=value_id,
                style={"color": color, "fontSize": "30px", "fontWeight": "700"},
            ),
        ],
        style=_panel_style(),
    )


def _btn_style(color: str) -> dict:
    return {
        "backgroundColor": color,
        "color": "#05070d",
        "border": "none",
        "borderRadius": "999px",
        "padding": "8px 14px",
        "fontWeight": "700",
        "cursor": "pointer",
    }


def _chart_layout(title: str) -> dict:
    return {
        "title": {"text": title, "font": {"color": COLORS["text"]}},
        "paper_bgcolor": COLORS["panel"],
        "plot_bgcolor": COLORS["panel"],
        "font": {
            "color": COLORS["text"],
            "family": "'IBM Plex Mono', 'Courier New', monospace",
        },
        "margin": {"l": 40, "r": 20, "t": 50, "b": 30},
    }


# ── Layout ───────────────────────────────────────────────────────────


def _build_layout():
    return html.Div(
        [
            # Auto-refresh every 3 s
            dcc.Interval(id="refresh", interval=3000, n_intervals=0),
            dcc.Store(id="status-filter", data="All"),
            # ── Header ───────────────────────────────────────────
            html.Div(
                [
                    html.Div(
                        [
                            html.Div(
                                "ROADWATCH AI",
                                style={"fontSize": "36px", "fontWeight": "700"},
                            ),
                            html.Div(
                                "AUTHORITY OPERATIONS CENTER - LIVE",
                                style={"color": COLORS["muted"], "marginTop": "6px"},
                            ),
                        ]
                    ),
                    html.Div(
                        [
                            html.Div(
                                id="live-clock",
                                style={"fontSize": "20px", "textAlign": "right"},
                            ),
                            # New Clickable Button connected to backend route
                            html.A(
                                html.Button(
                                    "LIVE",
                                    style={
                                        "padding": "6px 20px",
                                        "backgroundColor": COLORS["green"],
                                        "color": "#03130a",
                                        "borderRadius": "999px",
                                        "fontWeight": "700",
                                        "border": "none",
                                        "cursor": "pointer",
                                    },
                                ),
                                href="/camera/start",
                                target="_blank",  # Opens camera in a new window/process
                                style={
                                    "marginTop": "8px",
                                    "display": "inline-block",
                                    "textDecoration": "none",
                                },
                            ),
                        ]
                    ),
                ],
                style={
                    "display": "flex",
                    "justifyContent": "space-between",
                    "alignItems": "center",
                    "marginBottom": "20px",
                },
            ),
            # ── Stat cards (/api/stats) ──────────────────────────
            html.Div(
                [
                    _card("Potholes Detected", "card-total", COLORS["blue"]),
                    _card("Pending Repair", "card-pending", COLORS["red"]),
                    _card("In Progress", "card-progress", COLORS["yellow"]),
                    _card("Fixed", "card-fixed", COLORS["green"]),
                    _card("High Severity", "card-high", COLORS["orange"]),
                    _card("Fix Rate %", "card-rate", COLORS["green"]),
                ],
                style={
                    "display": "grid",
                    "gridTemplateColumns": "repeat(6, 1fr)",
                    "gap": "14px",
                    "marginBottom": "20px",
                },
            ),
            # ── Charts row 1 (/api/stats) ────────────────────────
            html.Div(
                [
                    dcc.Graph(id="hourly-chart", style=_panel_style()),
                    dcc.Graph(id="status-chart", style=_panel_style()),
                    dcc.Graph(id="severity-chart", style=_panel_style()),
                ],
                style={
                    "display": "grid",
                    "gridTemplateColumns": "1.5fr 1fr 1fr",
                    "gap": "14px",
                    "marginBottom": "20px",
                },
            ),
            # ── Charts row 2 (/api/stats) ────────────────────────
            html.Div(
                [
                    dcc.Graph(id="zone-chart", style=_panel_style()),
                    dcc.Graph(id="funnel-chart", style=_panel_style()),
                ],
                style={
                    "display": "grid",
                    "gridTemplateColumns": "1.5fr 1fr",
                    "gap": "14px",
                    "marginBottom": "20px",
                },
            ),
            # ── Zone progress (/api/potholes) ────────────────────
            html.Div(
                id="zone-progress",
                style={**_panel_style(), "marginBottom": "20px"},
            ),
            # ── Hotspot zones (/api/hotspots) ────────────────────
            html.Div(
                [
                    html.Div(
                        "HOTSPOT ZONES",
                        style={
                            "fontSize": "16px",
                            "fontWeight": "700",
                            "color": COLORS["orange"],
                            "marginBottom": "14px",
                            "letterSpacing": "1px",
                        },
                    ),
                    html.Div(id="hotspot-list"),
                ],
                style={**_panel_style(), "marginBottom": "20px"},
            ),
            # ── Live table with filters (/api/potholes) ─────────
            html.Div(
                [
                    html.Div(
                        [
                            html.Button(
                                "All",
                                id="filter-all",
                                n_clicks=0,
                                style=_btn_style(COLORS["blue"]),
                            ),
                            html.Button(
                                "Pending",
                                id="filter-pending",
                                n_clicks=0,
                                style=_btn_style(COLORS["red"]),
                            ),
                            html.Button(
                                "In Progress",
                                id="filter-progress",
                                n_clicks=0,
                                style=_btn_style(COLORS["yellow"]),
                            ),
                            html.Button(
                                "Fixed",
                                id="filter-fixed",
                                n_clicks=0,
                                style=_btn_style(COLORS["green"]),
                            ),
                        ],
                        style={
                            "display": "flex",
                            "gap": "10px",
                            "marginBottom": "12px",
                        },
                    ),
                    dash_table.DataTable(
                        id="live-table",
                        columns=[
                            {"name": "Type", "id": "hazard_type"},
                            {"name": "Zone", "id": "zone"},
                            {"name": "Address", "id": "address"},
                            {"name": "Severity", "id": "severity"},
                            {"name": "Status", "id": "status"},
                            {
                                "name": "Maps Link",
                                "id": "maps_link",
                                "presentation": "markdown",
                            },
                            {"name": "Time", "id": "timestamp"},
                        ],
                        style_as_list_view=True,
                        style_header={
                            "backgroundColor": "#172033",
                            "color": COLORS["text"],
                            "border": "none",
                        },
                        style_cell={
                            "backgroundColor": COLORS["panel"],
                            "color": COLORS["text"],
                            "border": "none",
                            "padding": "10px",
                            "fontFamily": "'IBM Plex Mono', 'Courier New', monospace",
                            "textAlign": "left",
                            "whiteSpace": "normal",
                            "height": "auto",
                        },
                        style_data_conditional=[
                            {
                                "if": {"filter_query": '{status} = "Pending"'},
                                "color": COLORS["red"],
                            },
                            {
                                "if": {"filter_query": '{status} = "Fixed"'},
                                "color": COLORS["green"],
                            },
                            {
                                "if": {"filter_query": '{status} = "In Progress"'},
                                "color": COLORS["yellow"],
                            },
                        ],
                        page_size=20,
                    ),
                ],
                style=_panel_style(),
            ),
        ],
        style={
            "minHeight": "100vh",
            "background": "radial-gradient(circle at top left, #172033 0%, #0b0f1a 55%)",
            "padding": "24px",
            "fontFamily": "'IBM Plex Mono', 'Courier New', monospace",
            "color": COLORS["text"],
        },
    )


# ── Callbacks ────────────────────────────────────────────────────────


def _register_callbacks(app) -> None:

    # ── Cards  <-  /api/stats logic ──────────────────────────────────
    @app.callback(
        Output("card-total", "children"),
        Output("card-pending", "children"),
        Output("card-progress", "children"),
        Output("card-fixed", "children"),
        Output("card-high", "children"),
        Output("card-rate", "children"),
        Output("live-clock", "children"),
        Input("refresh", "n_intervals"),
    )
    def update_cards(_):
        s = _data_stats()
        return (
            s.get("total", 0),
            s.get("pending", 0),
            s.get("in_progress", 0),
            s.get("fixed", 0),
            s.get("high_severity", 0),
            f"{s.get('fix_rate', 0)}%",
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        )

    # ── Charts  <-  /api/stats + /api/potholes logic ────────────────
    @app.callback(
        Output("hourly-chart", "figure"),
        Output("status-chart", "figure"),
        Output("severity-chart", "figure"),
        Output("zone-chart", "figure"),
        Output("funnel-chart", "figure"),
        Output("zone-progress", "children"),
        Input("refresh", "n_intervals"),
    )
    def update_charts(_):
        s = _data_stats()
        records = _data_potholes(limit=10000)

        # Hourly area chart
        hourly = s.get("hourly", [])
        hourly_fig = go.Figure(
            go.Scatter(
                x=[h["hour"] for h in hourly],
                y=[h["count"] for h in hourly],
                fill="tozeroy",
                line={"color": COLORS["blue"], "width": 3},
            )
        )
        hourly_fig.update_layout(_chart_layout("Hourly Detections"))

        # Status donut
        st = s.get("status_counts", {"Pending": 0, "Fixed": 0, "In Progress": 0})
        status_fig = go.Figure(
            go.Pie(
                labels=list(st.keys()),
                values=list(st.values()),
                hole=0.55,
                marker={"colors": [COLORS["red"], COLORS["green"], COLORS["yellow"]]},
            )
        )
        status_fig.update_layout(_chart_layout("Repair Status"))

        # Severity donut
        sv = s.get("severity_counts", {"High": 0, "Medium": 0, "Low": 0})
        severity_fig = go.Figure(
            go.Pie(
                labels=list(sv.keys()),
                values=list(sv.values()),
                hole=0.55,
                marker={"colors": [COLORS["orange"], COLORS["yellow"], COLORS["blue"]]},
            )
        )
        severity_fig.update_layout(_chart_layout("Severity Split"))

        # Zone horizontal bar
        zones = s.get("zones", [])
        zone_fig = go.Figure(
            go.Bar(
                x=[z["count"] for z in zones],
                y=[z["zone"] for z in zones],
                orientation="h",
                marker={"color": COLORS["blue"]},
            )
        )
        zone_fig.update_layout(_chart_layout("Zones Ranked"))

        # Repair funnel
        funnel_fig = go.Figure(
            go.Funnel(
                y=["Detected", "In Progress", "Fixed"],
                x=[s.get("total", 0), s.get("in_progress", 0), s.get("fixed", 0)],
                marker={"color": [COLORS["blue"], COLORS["yellow"], COLORS["green"]]},
            )
        )
        funnel_fig.update_layout(_chart_layout("Repair Funnel"))

        # Zone progress bars (needs individual records)
        progress = []
        for z in zones[:8]:
            name = z["zone"]
            total = z["count"]
            fixed_n = sum(
                1
                for r in records
                if r.get("zone") == name and r.get("status") == "Fixed"
            )
            pct = round((fixed_n / total) * 100, 2) if total else 0.0
            progress.append(
                html.Div(
                    [
                        html.Div(f"{name}  -  {pct}%", style={"marginBottom": "6px"}),
                        html.Div(
                            html.Div(
                                style={
                                    "width": f"{pct}%",
                                    "height": "10px",
                                    "backgroundColor": COLORS["green"],
                                    "borderRadius": "999px",
                                }
                            ),
                            style={
                                "backgroundColor": "#1f2937",
                                "borderRadius": "999px",
                            },
                        ),
                    ],
                    style={"marginBottom": "14px"},
                )
            )

        return hourly_fig, status_fig, severity_fig, zone_fig, funnel_fig, progress

    # ── Hotspots  <-  /api/hotspots logic ────────────────────────────
    @app.callback(
        Output("hotspot-list", "children"),
        Input("refresh", "n_intervals"),
    )
    def update_hotspots(_):
        hotspots = _data_hotspots()
        if not hotspots:
            return html.Div(
                "No hotspot zones detected.",
                style={"color": COLORS["muted"]},
            )

        chips = []
        for spot in hotspots:
            zone = spot.get("zone", "Unknown")
            count = spot.get("count", 0)
            chips.append(
                html.Div(
                    [
                        html.Span(zone, style={"fontWeight": "700"}),
                        html.Span(
                            f"  {count}",
                            style={
                                "marginLeft": "8px",
                                "backgroundColor": COLORS["red"],
                                "color": "#fff",
                                "borderRadius": "999px",
                                "padding": "2px 10px",
                                "fontSize": "12px",
                                "fontWeight": "700",
                            },
                        ),
                    ],
                    style={
                        "display": "inline-flex",
                        "alignItems": "center",
                        "backgroundColor": "#1f2937",
                        "borderRadius": "12px",
                        "padding": "10px 16px",
                        "marginRight": "10px",
                        "marginBottom": "10px",
                        "border": f"1px solid {COLORS['orange']}44",
                    },
                )
            )
        return html.Div(chips, style={"display": "flex", "flexWrap": "wrap"})

    # ── Table status filter ──────────────────────────────────────────
    @app.callback(
        Output("status-filter", "data"),
        Input("filter-all", "n_clicks"),
        Input("filter-pending", "n_clicks"),
        Input("filter-progress", "n_clicks"),
        Input("filter-fixed", "n_clicks"),
        State("status-filter", "data"),
    )
    def update_filter(_a, _b, _c, _d, current):
        trigger = (
            callback_context.triggered[0]["prop_id"].split(".")[0]
            if callback_context.triggered
            else ""
        )
        mapping = {
            "filter-all": "All",
            "filter-pending": "Pending",
            "filter-progress": "In Progress",
            "filter-fixed": "Fixed",
        }
        return mapping.get(trigger, current)

    # ── Live table  <-  /api/potholes logic ──────────────────────────
    @app.callback(
        Output("live-table", "data"),
        Input("refresh", "n_intervals"),
        Input("status-filter", "data"),
    )
    def update_table(_, status_filter):
        records = _data_potholes(limit=50)
        if status_filter != "All":
            records = [r for r in records if r.get("status") == status_filter]
        # Build fresh dicts so we never mutate the in-memory store
        rows = []
        for r in records:
            row = dict(r)
            link = row.get("maps_link", "#")
            # Guard: only wrap if not already wrapped
            if not link.startswith("[Open Map]"):
                row["maps_link"] = f"[Open Map]({link})"
            rows.append(row)
        return rows
