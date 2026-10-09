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
