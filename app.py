from pathlib import Path
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from dash import Dash, dcc, html, Input, Output, ctx


# One row = one order-product line. Order ID is absent: do not count orders.
BASE_DIR = Path(__file__).resolve().parent if "__file__" in globals() else Path.cwd()
DATA_PATH = BASE_DIR / "data" / "superstore_orders.csv"
if not DATA_PATH.exists():  # notebook is one folder above the standalone project
    DATA_PATH = BASE_DIR / "superstore_app" / "data" / "superstore_orders.csv"
df = pd.read_csv(DATA_PATH, parse_dates=["Order Date"])
required = ["Row ID", "Order Date", "Region", "Category", "Sales", "Profit"]
assert df[required].notna().all().all(), "Missing classroom data values"
assert df["Row ID"].is_unique, "Expected one unique Row ID per order line"
assert len(df) == 51290, "Use the supplied, unchanged classroom CSV"
df = df.assign(Year=df["Order Date"].dt.year)  # original CSV is never modified
REGIONS = sorted(df["Region"].unique())
YEARS = sorted(int(y) for y in df["Year"].unique())
CATEGORIES = sorted(df["Category"].unique())

def empty_figure(title):
    fig = go.Figure()
    fig.add_annotation(text="No matching rows. Choose a region/category.", showarrow=False)
    fig.update_layout(title=title, template="plotly_white")
    return fig


ASSETS_DIR = DATA_PATH.parent.parent / "assets"
app = Dash(__name__, assets_folder=str(ASSETS_DIR))
server = app.server  # deployment target for gunicorn app:server
app.title = "Superstore Explorer"


app.layout = html.Main([

    # ── Page header ────────────────────────────────────────────────────────
    html.Header([
        html.Div([
            html.H1("Superstore Sales Explorer"),
            html.P("How do sales and profit vary by region, category, and year?",
                   className="subtitle"),
        ], className="header-text"),
    ], className="page-header"),

    # ── Filter controls ────────────────────────────────────────────────────
    html.Section([
        html.H2("Filters", className="section-label"),
        html.Div([
            html.Div([
                html.Label("Region", htmlFor="regions"),
                html.Span("Select one or more", className="hint"),
                dcc.Dropdown(id="regions", options=REGIONS, value=REGIONS,
                             multi=True, closeOnSelect=False,
                             placeholder="Pick regions…"),
            ], className="control"),
            html.Div([
                html.Label("Year", htmlFor="year"),
                html.Span("Drag to change", className="hint"),
                dcc.Slider(id="year", min=min(YEARS), max=max(YEARS), step=1,
                           marks={y: str(y) for y in YEARS}, value=max(YEARS),
                           updatemode="mouseup"),
            ], className="control"),
            html.Div([
                html.Label("Category", htmlFor="categories"),
                html.Span("Select one or more", className="hint"),
                dcc.Dropdown(id="categories", options=CATEGORIES, value=CATEGORIES,
                             multi=True, closeOnSelect=False,
                             placeholder="Pick categories…"),
            ], className="control"),
            html.Div([
                html.Label("Metric", htmlFor="metric"),
                html.Span("Applies to both charts", className="hint"),
                dcc.RadioItems(
                    id="metric",
                    options=[
                        {"label": " Sales", "value": "Sales"},
                        {"label": " Profit", "value": "Profit"},
                    ],
                    value="Sales",
                    inline=True,
                    inputStyle={"marginRight": "6px"},
                    labelStyle={"marginRight": "20px"},
                ),
            ], className="control"),
        ], className="controls"),
    ], className="filters-section"),

    # ── Summary bar ────────────────────────────────────────────────────────
    html.Div([
        html.Div(id="summary", className="summary", role="status"),
        html.Button("Clear chart selection", id="reset", n_clicks=0),
    ], className="summary-row"),
    html.P("Click a bar to drill into monthly trends. Use the Category filter or "
           "the button above to broaden the selection.", className="chart-hint"),

    # ── Charts ─────────────────────────────────────────────────────────────
    html.Div([
        dcc.Graph(id="category-bar"),
        dcc.Graph(id="monthly-line"),
    ], className="charts"),

    html.Footer("Global Superstore · 2011–2014 · one row = one order line"),

], className="page")


# A control supplies a value. pandas performs the actual filtering.
def filter_rows(regions, year, categories):
    mask = (df["Region"].isin(regions or [])
            & df["Year"].eq(year)
            & df["Category"].isin(categories or []))
    return df.loc[mask].copy()

@app.callback(Output("category-bar", "figure"),
              Input("regions", "value"), Input("year", "value"),
              Input("metric", "value"), Input("categories", "value"))
def update_overview(regions, year, metric, categories):
    dff = filter_rows(regions, year, categories)
    if dff.empty:
        return empty_figure(f"{metric} by category")
    totals = dff.groupby("Category", as_index=False)[metric].sum()
    color = "#2463a6" if metric == "Sales" else "#b85c00"
    fig = px.bar(totals, x="Category", y=metric, template="plotly_white",
                 title=f"{metric} by category — {year}",
                 color_discrete_sequence=[color])
    return fig

@app.callback(Output("monthly-line", "figure"), Output("summary", "children"),
              Input("regions", "value"), Input("year", "value"),
              Input("category-bar", "clickData"), Input("reset", "n_clicks"),
              Input("metric", "value"), Input("categories", "value"))
def update_detail(regions, year, click_data, reset_clicks, metric, categories):
    dff = filter_rows(regions, year, categories)
    # Click on a bar narrows to that one category; Reset/control changes show all selected.
    category = None
    if ctx.triggered_id == "category-bar" and click_data:
        clicked = click_data["points"][0]["x"]
        if not categories or clicked in categories:
            category = clicked
            dff = dff.loc[dff["Category"].eq(category)]
    scope = category or ("All categories" if not categories or set(categories) == set(CATEGORIES)
                         else ", ".join(sorted(categories)))
    summary = (f"Detail: {scope} | Year: {year} | Sales: ${dff['Sales'].sum():,.0f} | "
               f"Profit: ${dff['Profit'].sum():,.0f} | Order lines: {len(dff):,}")
    if dff.empty:
        return empty_figure(f"Monthly {metric.lower()}"), summary
    monthly = dff.groupby(pd.Grouper(key="Order Date", freq="MS"))[metric].sum().reset_index()
    color = "#2463a6" if metric == "Sales" else "#b85c00"
    fig = px.line(monthly, x="Order Date", y=metric, markers=True,
                  title=f"Monthly {metric.lower()} — {scope}", template="plotly_white",
                  color_discrete_sequence=[color])
    return fig, summary


if __name__ == "__main__":
    app.run(debug=False, port=8050)


