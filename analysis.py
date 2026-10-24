"""Core analytics for the Nassau Candy factory-to-customer route efficiency project."""
import datetime as dt
import numpy as np
import pandas as pd

FACTORIES = {
    "Lot's O' Nuts":   (32.881893, -111.768036),
    "Wicked Choccy's": (32.076176, -81.088371),
    "Sugar Shack":     (48.11914, -96.18115),
    "Secret Factory":  (41.446333, -90.565487),
    "The Other Factory": (35.1175, -89.971107),
}
PRODUCT_FACTORY = {
    "Wonka Bar - Nutty Crunch Surprise": "Lot's O' Nuts",
    "Wonka Bar - Fudge Mallows": "Lot's O' Nuts",
    "Wonka Bar -Scrumdiddlyumptious": "Lot's O' Nuts",
    "Wonka Bar - Milk Chocolate": "Wicked Choccy's",
    "Wonka Bar - Triple Dazzle Caramel": "Wicked Choccy's",
    "Laffy Taffy": "Sugar Shack", "SweeTARTS": "Sugar Shack", "Nerds": "Sugar Shack",
    "Fun Dip": "Sugar Shack", "Fizzy Lifting Drinks": "Sugar Shack",
    "Everlasting Gobstopper": "Secret Factory", "Lickable Wallpaper": "Secret Factory",
    "Wonka Gum": "Secret Factory",
    "Hair Toffee": "The Other Factory", "Kazookles": "The Other Factory",
}
# Approximate geographic centroids (lat, lon) of customer states / provinces
STATE_XY = {
 'Alabama':(32.8,-86.8),'Alberta':(55.0,-115.0),'Arizona':(34.2,-111.7),'Arkansas':(34.9,-92.4),
 'British Columbia':(53.7,-127.6),'California':(37.2,-119.5),'Colorado':(39.0,-105.5),'Connecticut':(41.6,-72.7),
 'Delaware':(39.0,-75.5),'District of Columbia':(38.9,-77.0),'Florida':(28.6,-82.4),'Georgia':(32.7,-83.4),
 'Idaho':(44.4,-114.6),'Illinois':(40.0,-89.2),'Indiana':(39.9,-86.3),'Iowa':(42.1,-93.5),'Kansas':(38.5,-98.4),
 'Kentucky':(37.5,-85.3),'Louisiana':(31.1,-92.0),'Maine':(45.4,-69.2),'Manitoba':(55.0,-97.0),
 'Maryland':(39.0,-76.8),'Massachusetts':(42.3,-71.8),'Michigan':(44.3,-85.4),'Minnesota':(46.3,-94.3),
 'Mississippi':(32.7,-89.7),'Missouri':(38.4,-92.5),'Montana':(47.0,-109.6),'Nebraska':(41.5,-99.8),
 'Nevada':(39.3,-116.6),'New Brunswick':(46.5,-66.2),'New Hampshire':(43.7,-71.6),'New Jersey':(40.2,-74.7),
 'New Mexico':(34.4,-106.1),'New York':(42.9,-75.5),'Newfoundland and Labrador':(53.1,-57.7),
 'North Carolina':(35.6,-79.4),'North Dakota':(47.5,-100.5),'Nova Scotia':(45.0,-63.0),'Ohio':(40.3,-82.8),
 'Oklahoma':(35.6,-97.5),'Ontario':(50.0,-85.0),'Oregon':(43.9,-120.6),'Pennsylvania':(40.9,-77.8),
 'Prince Edward Island':(46.4,-63.3),'Quebec':(52.0,-72.0),'Rhode Island':(41.7,-71.5),
 'Saskatchewan':(54.0,-106.0),'South Carolina':(33.9,-80.9),'South Dakota':(44.4,-100.2),
 'Tennessee':(35.9,-86.4),'Texas':(31.5,-99.3),'Utah':(39.3,-111.7),'Vermont':(44.0,-72.7),
 'Virginia':(37.5,-78.8),'Washington':(47.4,-120.5),'West Virginia':(38.6,-80.6),'Wisconsin':(44.6,-89.9),
 'Wyoming':(43.0,-107.5),
}
US_ABBR = {'Alabama':'AL','Arizona':'AZ','Arkansas':'AR','California':'CA','Colorado':'CO','Connecticut':'CT',
 'Delaware':'DE','District of Columbia':'DC','Florida':'FL','Georgia':'GA','Idaho':'ID','Illinois':'IL',
 'Indiana':'IN','Iowa':'IA','Kansas':'KS','Kentucky':'KY','Louisiana':'LA','Maine':'ME','Maryland':'MD',
 'Massachusetts':'MA','Michigan':'MI','Minnesota':'MN','Mississippi':'MS','Missouri':'MO','Montana':'MT',
 'Nebraska':'NE','Nevada':'NV','New Hampshire':'NH','New Jersey':'NJ','New Mexico':'NM','New York':'NY',
 'North Carolina':'NC','North Dakota':'ND','Ohio':'OH','Oklahoma':'OK','Oregon':'OR','Pennsylvania':'PA',
 'Rhode Island':'RI','South Carolina':'SC','South Dakota':'SD','Tennessee':'TN','Texas':'TX','Utah':'UT',
 'Vermont':'VT','Virginia':'VA','Washington':'WA','West Virginia':'WV','Wisconsin':'WI','Wyoming':'WY'}


def haversine(lat1, lon1, lat2, lon2):
    r = 3958.8
    p1, p2 = np.radians(lat1), np.radians(lat2)
    a = np.sin((p2 - p1) / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(np.radians(lon2 - lon1) / 2) ** 2
    return 2 * r * np.arcsin(np.sqrt(a))


def _fix_date(v):
    """Strings are dd-mm-yyyy; true datetimes are Excel mis-parses (day/month swapped)."""
    if isinstance(v, (dt.datetime, pd.Timestamp)):
        return pd.Timestamp(v.year, v.day, v.month)
    return pd.to_datetime(v, format="%d-%m-%Y")


def load_clean(path):
    d = pd.read_excel(path, sheet_name="Original Data")
    raw_n = len(d)
    d["Order Date"] = d["Order Date"].map(_fix_date)
    d["Ship Date"] = d["Ship Date"].map(_fix_date)
    d["Lead Time (Raw)"] = (d["Ship Date"] - d["Order Date"]).dt.days
    d = d.drop_duplicates()
    d = d[d["Lead Time (Raw)"] >= 0].copy()
    # The source dates carry a constant shift per Order-ID year cohort (raw lead times of ~908 / ~1273 / ~1639
    # days, each varying only by ~10 days). Removing each cohort's baseline (its minimum) recovers a realistic
    # 0-11 day lead time that separates cleanly by ship mode (Same Day < First < Second < Standard).
    d["Cohort"] = d["Order ID"].str[3:7]
    d["Lead Time"] = d["Lead Time (Raw)"] - d.groupby("Cohort")["Lead Time (Raw)"].transform("min")
    for c in ["Country/Region", "City", "State/Province", "Region", "Ship Mode", "Division"]:
        d[c] = d[c].astype(str).str.strip()
    d["Product Name"] = d["Product Name"].str.strip()
    d["Factory"] = d["Product Name"].map(PRODUCT_FACTORY)
    d["Route (State)"] = d["Factory"] + " → " + d["State/Province"]
    d["Route (Region)"] = d["Factory"] + " → " + d["Region"]
    d["Order Year"] = d["Order Date"].dt.year
    xy = d["State/Province"].map(STATE_XY)
    d["dest_lat"] = xy.str[0]; d["dest_lon"] = xy.str[1]
    d["fac_lat"] = d["Factory"].map(lambda f: FACTORIES[f][0])
    d["fac_lon"] = d["Factory"].map(lambda f: FACTORIES[f][1])
    d["Distance (mi)"] = haversine(d.fac_lat, d.fac_lon, d.dest_lat, d.dest_lon)
    d.attrs["raw_rows"] = raw_n
    return d


def route_table(d, level="State/Province", threshold=None, min_orders=1):
    """Aggregate by route; threshold = lead time (days) above which a shipment counts as delayed."""
    if threshold is None:
        threshold = d["Lead Time"].quantile(0.75)
    key = ["Factory", level]
    g = d.assign(delayed=(d["Lead Time"] > threshold)).groupby(key).agg(
        Shipments=("Order ID", "count"), Orders=("Order ID", "nunique"),
        Avg_Lead_Time=("Lead Time", "mean"), Median_Lead_Time=("Lead Time", "median"),
        Lead_Time_Std=("Lead Time", "std"), Delay_Frequency=("delayed", "mean"),
        Sales=("Sales", "sum"), Avg_Distance=("Distance (mi)", "mean")).reset_index()
    g["Lead_Time_Std"] = g["Lead_Time_Std"].fillna(0)
    g = g[g.Shipments >= min_orders].copy()
    lo, hi = g.Avg_Lead_Time.min(), g.Avg_Lead_Time.max()
    g["Route_Efficiency_Score"] = 100 * (1 - (g.Avg_Lead_Time - lo) / (hi - lo)) if hi > lo else 100.0
    g["Route"] = g["Factory"] + " → " + g[level]
    g["Rank"] = g.Avg_Lead_Time.rank(method="first").astype(int)
    return g.sort_values("Avg_Lead_Time").reset_index(drop=True)
