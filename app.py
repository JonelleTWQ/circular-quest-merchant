import streamlit as st
from supabase import create_client

st.set_page_config(
    page_title="Circular Quest Merchant Portal",
    page_icon="♻️",
    layout="wide"
)

# -----------------------------
# DATABASE CONNECTION
# -----------------------------

supabase = create_client(
    st.secrets["SUPABASE_URL"],
    st.secrets["SUPABASE_KEY"]
)

# -----------------------------
# HEADER
# -----------------------------

st.title("♻️ Circular Quest")
st.subheader("Merchant Portal")

# -----------------------------
# LOAD MERCHANTS
# -----------------------------

try:
    response = (
        supabase
        .table("merchants")
        .select("*")
        .order("id")
        .execute()
    )

    merchants = response.data

except Exception as e:
    st.error("Could not connect to the Circular Quest database.")
    st.exception(e)
    st.stop()

# -----------------------------
# MERCHANT SELECTION
# -----------------------------

if not merchants:
    st.warning("No merchants found.")
    st.stop()

merchant_names = [merchant["merchant_name"] for merchant in merchants]

selected_name = st.selectbox(
    "Select merchant",
    merchant_names
)

selected_merchant = next(
    merchant
    for merchant in merchants
    if merchant["merchant_name"] == selected_name
)

merchant_id = selected_merchant["id"]

st.success(f"Logged in as {selected_name}")

st.divider()

page = st.sidebar.radio(
    "Navigation",
    [
        "Dashboard",
        "Register Surplus",
        "POS Upload",
        "Inventory",
        "Accountability"
    ]
)

# -----------------------------
# LOAD SURPLUS INVENTORY
# -----------------------------

inventory_response = (
    supabase
    .table("surplus_batches")
    .select("*")
    .eq("merchant_id", merchant_id)
    .execute()
)

inventory = inventory_response.data

active_inventory = [
    item for item in inventory
    if item["status"] == "active"
]

total_remaining = sum(
    item["quantity_remaining"]
    for item in active_inventory
)

# -----------------------------
# DASHBOARD
# -----------------------------

st.header("Dashboard")

col1, col2, col3 = st.columns(3)

with col1:
    st.metric(
        "Active Surplus",
        f"{total_remaining} units"
    )

with col2:
    st.metric(
        "Active Batches",
        len(active_inventory)
    )

with col3:
    st.metric(
        "Integration",
        selected_merchant["integration_type"].upper()
    )

st.divider()

# -----------------------------
# INVENTORY
# -----------------------------

st.header("Current Surplus Inventory")

if active_inventory:

    display_data = []

    for item in active_inventory:
        display_data.append({
            "Product": item["product_name"],
            "Category": item["category"],
            "Remaining": item["quantity_remaining"],
            "Original Price": item["original_price"],
            "Surplus Price": item["surplus_price"],
            "Reason": item["surplus_reason"],
            "Eligible Until": item["eligible_until"]
        })

    st.dataframe(
        display_data,
        use_container_width=True
    )

else:
    st.info("No active surplus inventory.")

# -----------------------------
# ACCOUNTABILITY
# -----------------------------

st.divider()
st.header("🛡️ Surplus Accountability")

stats_response = (
    supabase
    .table("merchant_monthly_stats")
    .select("*")
    .eq("merchant_id", merchant_id)
    .order("month")
    .execute()
)

stats = stats_response.data

if stats:

    latest = stats[-1]

    previous = stats[:-1]

    if previous:

        historical_rates = [
            row["units_surplus"] / row["units_procured"]
            for row in previous
            if row["units_procured"] > 0
        ]

        baseline_rate = (
            sum(historical_rates) / len(historical_rates)
        )

    else:
        baseline_rate = 0

    current_rate = (
        latest["units_surplus"] / latest["units_procured"]
        if latest["units_procured"] > 0
        else 0
    )

    excess_units = max(
        0,
        latest["units_surplus"]
        - latest["eligible_surplus_cap"]
    )

    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric(
            "Historical Baseline",
            f"{baseline_rate * 100:.1f}%"
        )

    with col2:
        st.metric(
            "Current Surplus Rate",
            f"{current_rate * 100:.1f}%"
        )

    with col3:
        st.metric(
            "Eligible Surplus Cap",
            f"{latest['eligible_surplus_cap']} units"
        )

    if current_rate <= baseline_rate * 1.10:

        st.success(
            "🟢 GREEN — Surplus levels are within the expected range."
        )

    elif current_rate <= baseline_rate * 1.50:

        st.warning(
            "🟠 AMBER — Surplus has increased above the historical baseline."
        )

    else:

        st.error(
            "🔴 RED — Significant surplus anomaly detected."
        )

    if excess_units > 0:

        st.warning(
            f"{excess_units} surplus units exceed the current "
            "Circular Quest eligibility allowance and will not "
            "receive Circular Quest incentives."
        )

else:

    st.info(
        "No historical accountability data is available for this merchant."
    )
