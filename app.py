"""Nassau Candy – Factory-to-Customer Shipping Route Efficiency Dashboard.
Run:  streamlit run app.py
Place Nassau_Candy_Shipping_Analysis.xlsx in the same folder."""
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from analysis import FACTORIES, US_ABBR, load_clean, route_table

DATA_FILE = "Nassau_Candy_Shipping_Analysis.xlsx"
st.set_page_config(page_title="Nassau Candy – Route Efficiency", page_icon="🍬", layout="wide")


@st.cache_data(show_spinner="Loading and cleaning data…")
def get_data():
    return load_clean(DATA_FILE)


df = get_data()

# ------------------------------------------------------------------ sidebar filters
st.sidebar.title("🍬 Filters")
dmin, dmax = df["Order Date"].min().date(), df["Order Date"].max().date()
date_range = st.sidebar.date_input("Order date range", (dmin, dmax), min_value=dmin, max_value=dmax)
regions = st.sidebar.multiselect("Region", sorted(df["Region"].unique()), default=sorted(df["Region"].unique()))
state_opts = sorted(df[df["Region"].isin(regions)]["State/Province"].unique())
states = st.sidebar.multiselect("State / Province (optional)", state_opts)
modes = st.sidebar.multiselect("Ship mode", sorted(df["Ship Mode"].unique()), default=sorted(df["Ship Mode"].unique()))
factories = st.sidebar.multiselect("Factory", sorted(df["Factory"].unique()), default=sorted(df["Factory"].unique()))
threshold = st.sidebar.slider("Delay threshold (days)", 1, 10, 5,
                              help="A shipment is 'delayed' if its lead time exceeds this many days.")
min_ship = st.sidebar.slider("Min. shipments per route (for rankings)", 1, 100, 20)

if len(date_range) == 2:
    f = df[(df["Order Date"].dt.date >= date_range[0]) & (df["Order Date"].dt.date <= date_range[1])]
else:
    f = df
f = f[f["Region"].isin(regions) & f["Ship Mode"].isin(modes) & f["Factory"].isin(factories)]
if states:
    f = f[f["State/Province"].isin(states)]
if f.empty:
    st.warning("No shipments match the current filters.")
    st.stop()

# ------------------------------------------------------------------ header & KPIs
st.title("Factory-to-Customer Shipping Route Efficiency")
st.caption("Nassau Candy Distributor • Lead time = Ship Date − Order Date, baseline-corrected per order cohort "
           "(see 'Data notes' tab).")

rt_state = route_table(f, "State/Province", threshold)
rt_region = route_table(f, "Region", threshold)
k1, k2, k3, k4, k5 = st.columns(5)
k1.metric("Shipments", f"{len(f):,}")
k2.metric("Avg lead time", f"{f['Lead Time'].mean():.2f} d")
k3.metric("Delay frequency", f"{(f['Lead Time'] > threshold).mean():.1%}")
k4.metric("Routes (factory→state)", f"{len(rt_state):,}")
k5.metric("Lead-time std dev", f"{f['Lead Time'].std():.2f} d")

tab1, tab2, tab3, tab4, tab5 = st.tabs(
    ["Route Efficiency", "Geographic Map", "Ship Mode Comparison", "Route Drill-Down", "Data notes"])

# ------------------------------------------------------------------ 1. route efficiency overview
with tab1:
    level = st.radio("Route level", ["Factory → Region", "Factory → State"], horizontal=True)
    rt = rt_region if level == "Factory → Region" else rt_state
    ranked = rt[rt.Shipments >= min_ship].reset_index(drop=True)
    st.subheader("Average lead time by route")
    if ranked.empty:
        st.info("No routes meet the minimum shipment count – lower the slider.")
    else:
        top_n = st.slider("Routes to display", 5, min(40, len(ranked)), min(15, len(ranked)))
        view = ranked.sort_values("Avg_Lead_Time").head(top_n) if st.toggle("Show fastest routes", True) \
            else ranked.sort_values("Avg_Lead_Time", ascending=False).head(top_n)
        fig = px.bar(view.sort_values("Avg_Lead_Time"), x="Avg_Lead_Time", y="Route", orientation="h",
                     color="Delay_Frequency", color_continuous_scale="RdYlGn_r",
                     labels={"Avg_Lead_Time": "Avg lead time (days)", "Delay_Frequency": "Delay freq."})
        fig.update_layout(height=max(350, 28 * len(view)), yaxis_title=None)
        st.plotly_chart(fig, use_container_width=True)

        st.subheader("Route performance leaderboard")
        cols = ["Rank", "Route", "Shipments", "Avg_Lead_Time", "Lead_Time_Std", "Delay_Frequency",
                "Route_Efficiency_Score"]
        a, b = st.columns(2)
        a.markdown("**Top 10 most efficient**")
        a.dataframe(ranked.head(10)[cols].style.format({"Avg_Lead_Time": "{:.2f}", "Lead_Time_Std": "{:.2f}",
                    "Delay_Frequency": "{:.1%}", "Route_Efficiency_Score": "{:.0f}"}), hide_index=True)
        b.markdown("**Bottom 10 least efficient**")
        b.dataframe(ranked.tail(10).iloc[::-1][cols].style.format({"Avg_Lead_Time": "{:.2f}",
                    "Lead_Time_Std": "{:.2f}", "Delay_Frequency": "{:.1%}", "Route_Efficiency_Score": "{:.0f}"}),
                    hide_index=True)
    st.caption("Efficiency score = 100 × (1 − min-max normalised average lead time) across the routes shown.")

# ------------------------------------------------------------------ 2. geographic map
with tab2:
    metric = st.selectbox("Map metric", ["Avg lead time (days)", "Delay frequency", "Shipment volume",
                                         "Bottleneck index"])
    g = f[f["Country/Region"] == "United States"].groupby("State/Province").agg(
        Shipments=("Order ID", "count"), Avg_Lead_Time=("Lead Time", "mean"),
        Delay_Frequency=("Lead Time", lambda x: (x > threshold).mean())).reset_index()
    g["Code"] = g["State/Province"].map(US_ABBR)
    g = g.dropna(subset=["Code"])
    # Bottleneck index = volume percentile × lead-time percentile (high volume AND slow)
    g["Bottleneck index"] = (g.Shipments.rank(pct=True) * g.Avg_Lead_Time.rank(pct=True)).round(3)
    col = {"Avg lead time (days)": "Avg_Lead_Time", "Delay frequency": "Delay_Frequency",
           "Shipment volume": "Shipments", "Bottleneck index": "Bottleneck index"}[metric]
    fig = px.choropleth(g, locations="Code", locationmode="USA-states", color=col, scope="usa",
                        hover_name="State/Province", hover_data=["Shipments", "Avg_Lead_Time", "Delay_Frequency"],
                        color_continuous_scale="RdYlGn_r" if col != "Shipments" else "Blues")
    fac = pd.DataFrame([(k, *v) for k, v in FACTORIES.items()], columns=["Factory", "lat", "lon"])
    fig.add_trace(go.Scattergeo(lat=fac.lat, lon=fac.lon, text=fac.Factory, mode="markers+text",
                                textposition="top center", marker=dict(size=10, color="black", symbol="star"),
                                name="Factories", geo="geo"))
    fig.update_layout(height=550, margin=dict(l=0, r=0, t=10, b=0))
    st.plotly_chart(fig, use_container_width=True)
    st.subheader("Regional bottlenecks (high volume + slow)")
    bn = g[(g.Shipments >= g.Shipments.median()) & (g.Avg_Lead_Time >= g.Avg_Lead_Time.median())] \
        .sort_values("Bottleneck index", ascending=False)
    st.dataframe(bn[["State/Province", "Shipments", "Avg_Lead_Time", "Delay_Frequency", "Bottleneck index"]]
                 .style.format({"Avg_Lead_Time": "{:.2f}", "Delay_Frequency": "{:.1%}"}), hide_index=True)
    reg = f.groupby("Region").agg(Shipments=("Order ID", "count"), Avg_Lead_Time=("Lead Time", "mean"),
                                  Delay_Frequency=("Lead Time", lambda x: (x > threshold).mean())).reset_index()
    st.dataframe(reg.style.format({"Avg_Lead_Time": "{:.2f}", "Delay_Frequency": "{:.1%}"}), hide_index=True)

# ------------------------------------------------------------------ 3. ship mode comparison
with tab3:
    m = f.groupby("Ship Mode").agg(Shipments=("Order ID", "count"), Avg_Lead_Time=("Lead Time", "mean"),
                                   Std=("Lead Time", "std"), Sales=("Sales", "sum"), Units=("Units", "sum"),
                                   Profit=("Gross Profit", "sum"),
                                   Delay=("Lead Time", lambda x: (x > threshold).mean())).reset_index()
    m["Sales per unit"] = m.Sales / m.Units
    m["Margin"] = m.Profit / m.Sales
    order = ["Same Day", "First Class", "Second Class", "Standard Class"]
    c1, c2 = st.columns(2)
    c1.plotly_chart(px.bar(m, x="Ship Mode", y="Avg_Lead_Time", color="Ship Mode", category_orders={"Ship Mode": order},
                           title="Average lead time by ship mode", labels={"Avg_Lead_Time": "days"}),
                    use_container_width=True)
    c2.plotly_chart(px.box(f, x="Ship Mode", y="Lead Time", color="Ship Mode", category_orders={"Ship Mode": order},
                           title="Lead-time distribution"), use_container_width=True)
    st.subheader("Cost–time trade-off (descriptive)")
    st.dataframe(m.set_index("Ship Mode").loc[[o for o in order if o in set(m["Ship Mode"])]]
                 .style.format({"Avg_Lead_Time": "{:.2f}", "Std": "{:.2f}", "Sales": "${:,.0f}", "Profit": "${:,.0f}",
                                "Delay": "{:.1%}", "Sales per unit": "${:.2f}", "Margin": "{:.1%}"}))
    st.caption("Sales/unit and margin are nearly identical across modes, and freight cost is not in the dataset, "
               "so faster modes cannot be shown to cost more or less. See report for discussion.")
    mix = pd.crosstab(f["Region"], f["Ship Mode"], normalize="index").reset_index().melt("Region")
    st.plotly_chart(px.bar(mix, x="Region", y="value", color="Ship Mode", title="Ship-mode mix by region",
                           labels={"value": "share"}), use_container_width=True)

# ------------------------------------------------------------------ 4. drill-down
with tab4:
    c1, c2 = st.columns(2)
    sel_state = c1.selectbox("State / Province", sorted(f["State/Province"].unique()))
    s = f[f["State/Province"] == sel_state]
    fac_opts = ["All"] + sorted(s["Factory"].unique())
    sel_fac = c2.selectbox("Factory", fac_opts)
    if sel_fac != "All":
        s = s[s["Factory"] == sel_fac]
    st.subheader(f"State-level performance – {sel_state}")
    a, b, c = st.columns(3)
    a.metric("Shipments", len(s)); b.metric("Avg lead time", f"{s['Lead Time'].mean():.2f} d")
    c.metric("Delay freq.", f"{(s['Lead Time'] > threshold).mean():.1%}")
    by_f = s.groupby(["Factory", "Ship Mode"]).agg(Shipments=("Order ID", "count"),
                                                    Avg_Lead_Time=("Lead Time", "mean")).reset_index()
    st.dataframe(by_f.style.format({"Avg_Lead_Time": "{:.2f}"}), hide_index=True)
    st.subheader("Order-level shipment timelines")
    st.plotly_chart(px.histogram(s, x="Lead Time", color="Ship Mode", nbins=12, title="Lead-time distribution"),
                    use_container_width=True)
    show = s[["Order ID", "Order Date", "Ship Date", "Ship Mode", "Factory", "City", "Lead Time", "Product Name",
              "Sales"]].sort_values("Lead Time", ascending=False)
    st.dataframe(show, hide_index=True)
    st.download_button("Download filtered data (CSV)", f.to_csv(index=False).encode(), "filtered_shipments.csv")

# ------------------------------------------------------------------ 5. notes
with tab5:
    st.markdown("""
**Date handling.** Order/Ship dates were stored in mixed formats (day-first text and Excel date cells whose day and
month were swapped). The app normalises both to true dates.

**Baseline correction.** Even after that, raw lead times are 900–1,640 days because the source dates carry a constant
shift per order-ID year cohort (≈908, ≈1,273 and ≈1,639 days, each varying by only ~10 days). The dashboard subtracts
each cohort's minimum so lead time reflects the *relative* shipping duration (0–11 days). After correction, ship modes
separate cleanly (Same Day < First < Second < Standard), which supports the correction. Absolute delivery days should
still be verified against carrier records.

**Factory assignment.** Each product is mapped to its factory using the project's product–factory table; a route is
Factory → Customer State / Region.

**Limitations.** No carrier, promised delivery date, freight cost or destination coordinates exist in the data. State
centroids are used for distance; the delay threshold is user-defined.""")
