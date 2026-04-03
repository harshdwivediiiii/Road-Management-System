from __future__ import annotations

from datetime import datetime

from flask import Response

try:
    from dash import Dash, Input, Output, dash_table, dcc, html
    import plotly.graph_objects as go
except ImportError:  # pragma: no cover - optional dependency fallback
    Dash = None
    Input = Output = dash_table = dcc = html = go = None

from storage import get_all_potholes, get_counts, get_hourly_counts, get_severity_counts, get_status_counts, get_zone_counts


BG = "#0b0f1a"
PANEL = "#111827"
ORANGE = "#f97316"
GREEN = "#22c55e"
RED = "#ef4444"
YELLOW = "#eab308"
BLUE = "#38bdf8"
FONT = "IBM Plex Mono, Courier New, monospace"


def make_card(title: str, value_id: str, color: str):
    """Build a single stat card."""
    return html.Div(
        [
            html.Div(title, style={"color": "#94a3b8", "fontSize": "12px"}),
            html.Div(id=value_id, style={"color": color, "fontSize": "28px", "fontWeight": "700"}),
        ],
        style={"background": PANEL, "padding": "18px", "borderRadius": "14px", "border": f"1px solid {color}33"},
    )


def build_layout():
    """Construct the dashboard layout tree."""
    return html.Div(
        [
            dcc.Interval(id="refresh", interval=3000, n_intervals=0),
            html.Div(
                [
                    html.Div(
                        [
                            html.H1("ROADWATCH AI", style={"margin": "0", "color": "#f8fafc"}),
                            html.Div("AUTHORITY OPERATIONS CENTER · LIVE", style={"color": "#94a3b8"}),
                        ]
                    ),
                    html.A(
                        "LIVE CAMERA",
                        href="/camera/view",
                        target="_blank",
                        style={
                            "justifySelf": "center",
                            "background": BLUE,
                            "color": BG,
                            "padding": "10px 18px",
                            "borderRadius": "999px",
                            "fontWeight": "700",
                            "textDecoration": "none",
                            "border": f"1px solid {BLUE}",
                        },
                    ),
                    html.Div(id="live-clock", style={"color": "#f8fafc", "fontSize": "18px"}),
                    html.Div("LIVE", style={"background": GREEN, "color": BG, "padding": "8px 16px", "borderRadius": "999px", "fontWeight": "700"}),
                ],
                style={"display": "grid", "gridTemplateColumns": "1fr auto auto auto", "gap": "16px", "alignItems": "center", "marginBottom": "20px"},
            ),
            html.Div(
                [
                    make_card("Potholes Detected", "card-total", BLUE),
                    make_card("Pending Repair", "card-pending", RED),
                    make_card("In Progress", "card-progress", YELLOW),
                    make_card("Fixed", "card-fixed", GREEN),
                    make_card("High Severity", "card-high", ORANGE),
                    make_card("Fix Rate %", "card-rate", GREEN),
                ],
                style={"display": "grid", "gridTemplateColumns": "repeat(6, 1fr)", "gap": "14px", "marginBottom": "20px"},
            ),
            html.Div(
                [
                    dcc.Graph(id="hourly-chart"),
                    dcc.Graph(id="status-chart"),
                    dcc.Graph(id="severity-chart"),
                ],
                style={"display": "grid", "gridTemplateColumns": "2fr 1fr 1fr", "gap": "16px", "marginBottom": "20px"},
            ),
            html.Div(
                [
                    dcc.Graph(id="zone-chart"),
                    dcc.Graph(id="funnel-chart"),
                ],
                style={"display": "grid", "gridTemplateColumns": "2fr 1fr", "gap": "16px", "marginBottom": "20px"},
            ),
            html.Div(id="zone-progress", style={"display": "grid", "gap": "10px", "marginBottom": "20px"}),
            html.Div(
                [
                    html.Div(
                        [
                            html.Button("All", id="filter-all", n_clicks=0, style={"marginRight": "8px"}),
                            html.Button("Pending", id="filter-pending", n_clicks=0, style={"marginRight": "8px"}),
                            html.Button("In Progress", id="filter-progress", n_clicks=0, style={"marginRight": "8px"}),
                            html.Button("Fixed", id="filter-fixed", n_clicks=0),
                        ],
                        style={"marginBottom": "12px"},
                    ),
                    dash_table.DataTable(
                        id="live-table",
                        columns=[
                            {"name": "Type", "id": "hazard_type"},
                            {"name": "Zone", "id": "zone"},
                            {"name": "Address", "id": "address"},
                            {"name": "Severity", "id": "severity"},
                            {"name": "Status", "id": "status"},
                            {"name": "Maps Link", "id": "maps_link", "presentation": "markdown"},
                            {"name": "Time", "id": "timestamp"},
                        ],
                        style_header={"backgroundColor": PANEL, "color": "#f8fafc", "border": f"1px solid {BLUE}22"},
                        style_data={"backgroundColor": PANEL, "color": "#e2e8f0", "border": f"1px solid {BLUE}11"},
                        style_cell={"fontFamily": FONT, "textAlign": "left", "padding": "10px"},
                        style_data_conditional=[
                            {"if": {"filter_query": '{status} = "Pending"'}, "color": RED},
                            {"if": {"filter_query": '{status} = "Fixed"'}, "color": GREEN},
                            {"if": {"filter_query": '{status} = "In Progress"'}, "color": YELLOW},
                        ],
                        page_size=20,
                    ),
                ],
                style={"background": PANEL, "padding": "16px", "borderRadius": "14px"},
            ),
        ],
        style={"background": BG, "minHeight": "100vh", "padding": "24px", "fontFamily": FONT},
    )


def init_dashboard(flask_app):
    """Attach the Plotly Dash dashboard to the Flask app."""
    if Dash is None:
        @flask_app.get("/dashboard/")
        def dashboard_unavailable():
            return Response("Dashboard dependencies are not installed in the active environment.", mimetype="text/plain")

        return None

    dash_app = Dash(__name__, server=flask_app, url_base_pathname="/dashboard/")
    dash_app.layout = build_layout()

    @dash_app.callback(
        Output("card-total", "children"),
        Output("card-pending", "children"),
        Output("card-progress", "children"),
        Output("card-fixed", "children"),
        Output("card-high", "children"),
        Output("card-rate", "children"),
        Output("live-clock", "children"),
        Output("hourly-chart", "figure"),
        Output("status-chart", "figure"),
        Output("severity-chart", "figure"),
        Output("zone-chart", "figure"),
        Output("funnel-chart", "figure"),
        Output("zone-progress", "children"),
        Output("live-table", "data"),
        Input("refresh", "n_intervals"),
        Input("filter-all", "n_clicks"),
        Input("filter-pending", "n_clicks"),
        Input("filter-progress", "n_clicks"),
        Input("filter-fixed", "n_clicks"),
    )
    def refresh_dashboard(_, all_clicks, pending_clicks, progress_clicks, fixed_clicks):
        counts = get_counts()
        statuses = get_status_counts()
        severities = get_severity_counts()
        hourly = get_hourly_counts()
        zones = get_zone_counts()
        total = counts["total"]
        fix_rate = round((counts["fixed"] / total) * 100, 2) if total else 0.0

        hourly_fig = go.Figure(
            data=[go.Scatter(x=[item["hour"] for item in hourly], y=[item["count"] for item in hourly], fill="tozeroy", line={"color": BLUE})]
        )
        status_fig = go.Figure(data=[go.Pie(labels=list(statuses.keys()), values=list(statuses.values()), hole=0.6, marker={"colors": [RED, GREEN, YELLOW]})])
        severity_fig = go.Figure(data=[go.Pie(labels=list(severities.keys()), values=list(severities.values()), hole=0.6, marker={"colors": [ORANGE, YELLOW, BLUE]})])
        zone_fig = go.Figure(data=[go.Bar(x=[z["count"] for z in zones], y=[z["zone"] for z in zones], orientation="h", marker={"color": ORANGE})])
        funnel_fig = go.Figure(data=[go.Funnel(y=["Detected", "In Progress", "Fixed"], x=[counts["total"], counts["in_progress"], counts["fixed"]], marker={"color": [BLUE, YELLOW, GREEN]})])

        for fig in [hourly_fig, status_fig, severity_fig, zone_fig, funnel_fig]:
            fig.update_layout(paper_bgcolor=PANEL, plot_bgcolor=PANEL, font={"color": "#e2e8f0", "family": FONT}, margin={"l": 40, "r": 20, "t": 40, "b": 40})

        button_state = {
            "All": all_clicks,
            "Pending": pending_clicks,
            "In Progress": progress_clicks,
            "Fixed": fixed_clicks,
        }
        selected_status = max(button_state, key=button_state.get)

        potholes = get_all_potholes(limit=20)
        if selected_status != "All":
            potholes = [item for item in potholes if item.get("status") == selected_status]

        table_rows = []
        for item in potholes:
            row = dict(item)
            row["maps_link"] = f"[Open Map]({item.get('maps_link', '#')})"
            table_rows.append(row)

        progress_rows = []
        for zone in zones:
            progress_rows.append(
                html.Div(
                    [
                        html.Div(f"{zone['zone']} · {zone['resolved_percent']}%", style={"color": "#e2e8f0", "marginBottom": "4px"}),
                        html.Div(
                            html.Div(style={"width": f"{zone['resolved_percent']}%", "height": "100%", "background": GREEN, "borderRadius": "999px"}),
                            style={"height": "10px", "background": "#1f2937", "borderRadius": "999px"},
                        ),
                    ],
                    style={"background": PANEL, "padding": "12px", "borderRadius": "12px"},
                )
            )

        return (
            str(counts["total"]),
            str(counts["pending"]),
            str(counts["in_progress"]),
            str(counts["fixed"]),
            str(counts["high_severity"]),
            f"{fix_rate}%",
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            hourly_fig,
            status_fig,
            severity_fig,
            zone_fig,
            funnel_fig,
            progress_rows,
            table_rows,
        )

    return dash_app
