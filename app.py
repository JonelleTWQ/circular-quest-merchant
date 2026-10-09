import streamlit as st
import pandas as pd

from datetime import date
from supabase import create_client


# =========================================================
# PAGE CONFIGURATION
# =========================================================

st.set_page_config(
    page_title="Circular Quest Merchant Portal",
    page_icon="♻️",
    layout="wide"
)


# =========================================================
# DATABASE CONNECTION
# =========================================================

supabase = create_client(
    st.secrets["SUPABASE_URL"],
    st.secrets["SUPABASE_KEY"]
)


# =========================================================
# HELPER FUNCTIONS
# =========================================================

def load_merchants():
    """Load all merchants from Supabase."""

    response = (
        supabase
        .table("merchants")
        .select("*")
        .order("id")
        .execute()
    )

    return response.data


def load_inventory(merchant_id):
    """Load all surplus batches belonging to one merchant."""

    response = (
        supabase
        .table("surplus_batches")
        .select("*")
        .eq("merchant_id", merchant_id)
        .order("registered_at", desc=True)
        .execute()
    )

    return response.data


def load_outlets(merchant_id):
    """Load active outlets belonging to one merchant."""

    response = (
        supabase
        .table("outlets")
        .select("*")
        .eq("merchant_id", merchant_id)
        .eq("active", True)
        .order("id")
        .execute()
    )

    return response.data


def load_stats(merchant_id):
    """Load accountability statistics for one merchant."""

    response = (
        supabase
        .table("merchant_monthly_stats")
        .select("*")
        .eq("merchant_id", merchant_id)
        .order("month")
        .execute()
    )

    return response.data


def check_surplus_eligibility(
    reason,
    expiry_date,
    eligible_until
):
    """
    Simple prototype rules engine.

    IMPORTANT:
    The 7-day near-expiry rule is only a demonstration rule.
    A production system would use configurable rules based on
    product category and retailer requirements.
    """

    today = date.today()

    if eligible_until < today:
        return False, "The eligibility period has already ended."

    if reason == "Near Expiry":

        days_to_expiry = (expiry_date - today).days

        if days_to_expiry < 0:
            return False, "The product has already expired."

        if days_to_expiry > 7:
            return (
                False,
                "For this prototype, near-expiry products must "
                "be within 7 days of expiry."
            )

    return True, "Product meets the current surplus criteria."


def get_accountability_values(stats):
    """
    Calculate historical baseline and current surplus rate.
    """

    if not stats:
        return None

    latest = stats[-1]
    previous = stats[:-1]

    historical_rates = []

    for row in previous:

        if row["units_procured"] > 0:

            rate = (
                row["units_surplus"]
                / row["units_procured"]
            )

            historical_rates.append(rate)

    if historical_rates:

        baseline_rate = (
            sum(historical_rates)
            / len(historical_rates)
        )

    else:

        baseline_rate = 0

    if latest["units_procured"] > 0:

        current_rate = (
            latest["units_surplus"]
            / latest["units_procured"]
        )

    else:

        current_rate = 0

    return {
        "latest": latest,
        "baseline_rate": baseline_rate,
        "current_rate": current_rate
    }


def get_remaining_allowance(merchant_id):
    """
    Calculate how many additional units can currently receive
    Circular Quest incentives.

    For the MVP, the latest merchant_monthly_stats record
    provides the cap.

    Only batches registered during the same calendar month as
    that statistics record count against that month's cap.
    """

    stats = load_stats(merchant_id)

    if not stats:
        return 0, 0, 0

    latest = stats[-1]

    cap = latest["eligible_surplus_cap"]

    latest_month = latest["month"][:7]

    inventory = load_inventory(merchant_id)

    already_eligible = 0

    for batch in inventory:

        registered_at = batch.get("registered_at")

        if not registered_at:
            continue

        batch_month = registered_at[:7]

        if batch_month == latest_month:

            already_eligible += (
                batch.get("quantity_eligible") or 0
            )

    remaining = max(
        0,
        cap - already_eligible
    )

    return cap, already_eligible, remaining


# =========================================================
# HEADER
# =========================================================

st.title("♻️ Circular Quest")
st.subheader("Merchant Portal")


# =========================================================
# LOAD MERCHANTS
# =========================================================

try:

    merchants = load_merchants()

except Exception as e:

    st.error(
        "Could not connect to the Circular Quest database."
    )

    st.exception(e)

    st.stop()


if not merchants:

    st.warning("No merchants found.")

    st.stop()


# =========================================================
# DEMO MERCHANT SELECTOR
# =========================================================

st.sidebar.title("♻️ Circular Quest")

merchant_names = [
    merchant["merchant_name"]
    for merchant in merchants
]

selected_name = st.sidebar.selectbox(
    "Demo Merchant",
    merchant_names
)

selected_merchant = next(
    merchant
    for merchant in merchants
    if merchant["merchant_name"] == selected_name
)

merchant_id = selected_merchant["id"]


# =========================================================
# NAVIGATION
# =========================================================

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

st.sidebar.divider()

st.sidebar.caption(
    "Competition prototype — merchant authentication "
    "will replace the demo merchant selector."
)


# =========================================================
# MERCHANT HEADER
# =========================================================

st.write(
    f"**Merchant:** {selected_name}"
)

st.write(
    f"**Integration:** "
    f"{selected_merchant['integration_type'].upper()}"
)

st.divider()


# =========================================================
# DASHBOARD
# =========================================================

if page == "Dashboard":

    st.header("Dashboard")

    try:

        inventory = load_inventory(merchant_id)

        active_inventory = [
            item
            for item in inventory
            if item["status"] in [
                "active",
                "partially_eligible"
            ]
        ]

        total_remaining = sum(
            item["quantity_remaining"]
            for item in active_inventory
        )

        stats = load_stats(merchant_id)

        cap, already_eligible, remaining_allowance = (
            get_remaining_allowance(merchant_id)
        )

        col1, col2, col3, col4 = st.columns(4)

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
                "Monthly Eligibility Cap",
                f"{cap} units"
            )

        with col4:

            st.metric(
                "Allowance Remaining",
                f"{remaining_allowance} units"
            )

        st.divider()

        st.subheader("Current Surplus Inventory")

        if active_inventory:

            display_data = []

            for item in active_inventory:

                display_data.append({

                    "Product":
                        item["product_name"],

                    "Category":
                        item["category"],

                    "Remaining":
                        item["quantity_remaining"],

                    "Eligible":
                        item.get(
                            "quantity_eligible",
                            0
                        ),

                    "Original Price":
                        item["original_price"],

                    "Surplus Price":
                        item["surplus_price"],

                    "Reason":
                        item["surplus_reason"],

                    "Eligible Until":
                        item["eligible_until"]
                })

            st.dataframe(
                pd.DataFrame(display_data),
                use_container_width=True,
                hide_index=True
            )

        else:

            st.info(
                "No active surplus inventory."
            )

        # Quick accountability summary

        st.divider()

        st.subheader("🛡️ Accountability Status")

        values = get_accountability_values(stats)

        if values:

            baseline = values["baseline_rate"]
            current = values["current_rate"]

            if baseline == 0:

                st.info(
                    "Not enough historical data to "
                    "calculate a baseline."
                )

            elif current <= baseline * 1.10:

                st.success(
                    "🟢 GREEN — Surplus levels are "
                    "within the expected range."
                )

            elif current <= baseline * 1.50:

                st.warning(
                    "🟠 AMBER — Surplus has increased "
                    "above the historical baseline."
                )

            else:

                st.error(
                    "🔴 RED — Significant surplus "
                    "anomaly detected."
                )

        else:

            st.info(
                "No accountability data available."
            )

    except Exception as e:

        st.error(
            "Could not load dashboard data."
        )

        st.exception(e)


# =========================================================
# REGISTER SURPLUS
# =========================================================

elif page == "Register Surplus":

    st.header("➕ Register Surplus")

    st.write(
        "Manually register surplus inventory. "
        "This option is designed for retailers that "
        "do not require direct POS integration."
    )

    try:

        outlets = load_outlets(merchant_id)

    except Exception as e:

        st.error("Could not load merchant outlets.")
        st.exception(e)
        st.stop()

    if not outlets:

        st.warning(
            "This merchant has no active outlets."
        )

        st.stop()

    outlet_names = [
        outlet["outlet_name"]
        for outlet in outlets
    ]

    selected_outlet_name = st.selectbox(
        "Outlet",
        outlet_names
    )

    selected_outlet = next(
        outlet
        for outlet in outlets
        if outlet["outlet_name"]
        == selected_outlet_name
    )

    outlet_id = selected_outlet["id"]

    # Show current allowance

    cap, already_eligible, remaining_allowance = (
        get_remaining_allowance(merchant_id)
    )

    col1, col2, col3 = st.columns(3)

    with col1:

        st.metric(
            "Eligibility Cap",
            f"{cap} units"
        )

    with col2:

        st.metric(
            "Already Eligible",
            f"{already_eligible} units"
        )

    with col3:

        st.metric(
            "Remaining Allowance",
            f"{remaining_allowance} units"
        )

    st.divider()

    with st.form("surplus_registration_form"):

        merchant_sku = st.text_input(
            "Product SKU"
        )

        product_name = st.text_input(
            "Product Name"
        )

        category = st.selectbox(
            "Category",
            [
                "Food",
                "Beverage",
                "Personal Care",
                "Household",
                "Clothing",
                "Electronics",
                "Other"
            ]
        )

        quantity = st.number_input(
            "Surplus Quantity",
            min_value=1,
            step=1
        )

        original_price = st.number_input(
            "Original Price ($)",
            min_value=0.01,
            step=0.10,
            format="%.2f"
        )

        surplus_price = st.number_input(
            "Surplus Price ($)",
            min_value=0.00,
            step=0.10,
            format="%.2f"
        )

        surplus_reason = st.selectbox(
            "Reason for Surplus",
            [
                "Near Expiry",
                "Seasonal Surplus",
                "Discontinued",
                "Cosmetic Damage",
                "Forecasting Error",
                "Other"
            ]
        )

        expiry_date = st.date_input(
            "Expiry Date"
        )

        eligible_until = st.date_input(
            "Circular Quest Eligibility End Date"
        )

        submitted = st.form_submit_button(
            "Check & Register Surplus",
            type="primary"
        )

    if submitted:

        errors = []

        if not merchant_sku.strip():

            errors.append(
                "Product SKU is required."
            )

        if not product_name.strip():

            errors.append(
                "Product name is required."
            )

        if surplus_price >= original_price:

            errors.append(
                "Surplus price must be lower "
                "than the original price."
            )

        if errors:

            for error in errors:

                st.error(error)

        else:

            eligible, message = (
                check_surplus_eligibility(
                    surplus_reason,
                    expiry_date,
                    eligible_until
                )
            )

            if not eligible:

                st.error(
                    f"❌ Not eligible: {message}"
                )

            else:

                # Recalculate immediately before insert
                # in case data has changed.

                (
                    cap,
                    already_eligible,
                    remaining_allowance
                ) = get_remaining_allowance(
                    merchant_id
                )

                eligible_quantity = min(
                    int(quantity),
                    int(remaining_allowance)
                )

                if eligible_quantity == 0:

                    batch_status = "ineligible"

                elif eligible_quantity < quantity:

                    batch_status = "partially_eligible"

                else:

                    batch_status = "active"

                new_batch = {

                    "merchant_id":
                        merchant_id,

                    "outlet_id":
                        outlet_id,

                    "merchant_sku":
                        merchant_sku.strip(),

                    "product_name":
                        product_name.strip(),

                    "category":
                        category,

                    "quantity_registered":
                        int(quantity),

                    "quantity_remaining":
                        int(eligible_quantity),

                    "quantity_eligible":
                        int(eligible_quantity),

                    "original_price":
                        float(original_price),

                    "surplus_price":
                        float(surplus_price),

                    "surplus_reason":
                        surplus_reason,

                    "expiry_date":
                        expiry_date.isoformat(),

                    "eligible_until":
                        eligible_until.isoformat(),

                    "status":
                        batch_status
                }

                try:

                    supabase.table(
                        "surplus_batches"
                    ).insert(
                        new_batch
                    ).execute()

                    if eligible_quantity == quantity:

                        st.success(
                            f"✅ {quantity} units were "
                            "successfully registered and "
                            "approved for Circular Quest."
                        )

                    elif eligible_quantity > 0:

                        st.warning(
                            f"⚠️ {quantity} units were recorded "
                            f"as surplus, but only "
                            f"{eligible_quantity} units are "
                            "eligible for Circular Quest "
                            "incentives because of the "
                            "merchant's remaining allowance."
                        )

                    else:

                        st.warning(
                            "The surplus was recorded, but "
                            "0 units are eligible for Circular "
                            "Quest incentives because the "
                            "merchant has reached its current "
                            "eligibility allowance."
                        )

                except Exception as e:

                    st.error(
                        "The product passed eligibility checks "
                        "but could not be saved."
                    )

                    st.exception(e)


# =========================================================
# POS UPLOAD
# =========================================================

elif page == "POS Upload":

    st.header("📤 POS / Inventory Upload")

    st.write(
        "Upload a CSV exported from your existing POS or "
        "inventory system. Circular Quest maps different "
        "retailer formats into one standard data structure."
    )

    st.info(
        "This prototype demonstrates interoperability. "
        "Retailers do not need to replace their existing "
        "POS systems."
    )

    uploaded_file = st.file_uploader(
        "Upload POS inventory CSV",
        type=["csv"]
    )

    if uploaded_file is not None:

        try:

            df = pd.read_csv(uploaded_file)

        except Exception as e:

            st.error(
                "The CSV file could not be read."
            )

            st.exception(e)

            st.stop()

        if df.empty:

            st.warning(
                "The uploaded CSV contains no products."
            )

            st.stop()

        st.subheader("1. Detected POS Data")

        st.dataframe(
            df,
            use_container_width=True,
            hide_index=True
        )

        st.caption(
            f"{len(df)} rows detected."
        )

        st.divider()

        st.subheader(
            "2. Match POS Columns to Circular Quest"
        )

        columns = [
            "-- Select --"
        ] + list(df.columns)

        col1, col2 = st.columns(2)

        with col1:

            sku_column = st.selectbox(
                "Product SKU",
                columns,
                key="sku_mapping"
            )

            name_column = st.selectbox(
                "Product Name",
                columns,
                key="name_mapping"
            )

            quantity_column = st.selectbox(
                "Quantity Remaining",
                columns,
                key="quantity_mapping"
            )

        with col2:

            price_column = st.selectbox(
                "Original Price",
                columns,
                key="price_mapping"
            )

            expiry_column = st.selectbox(
                "Expiry Date",
                columns,
                key="expiry_mapping"
            )

        required_mappings = [
            sku_column,
            name_column,
            quantity_column,
            price_column,
            expiry_column
        ]

        if "-- Select --" not in required_mappings:

            try:

                standardized_df = pd.DataFrame({

                    "merchant_sku":
                        df[sku_column],

                    "product_name":
                        df[name_column],

                    "quantity":
                        pd.to_numeric(
                            df[quantity_column],
                            errors="coerce"
                        ),

                    "original_price":
                        pd.to_numeric(
                            df[price_column],
                            errors="coerce"
                        ),

                    "expiry_date":
                        pd.to_datetime(
                            df[expiry_column],
                            errors="coerce"
                        )
                })

                st.divider()

                st.subheader(
                    "3. Circular Quest Standard Format"
                )

                st.success(
                    "✅ POS columns successfully mapped "
                    "to the Circular Quest standard."
                )

                st.dataframe(
                    standardized_df,
                    use_container_width=True,
                    hide_index=True
                )

                invalid_rows = (
                    standardized_df[
                        standardized_df.isnull().any(axis=1)
                    ]
                )

                if not invalid_rows.empty:

                    st.warning(
                        f"{len(invalid_rows)} row(s) contain "
                        "invalid or missing values and would "
                        "require review before import."
                    )

                st.info(
                    "Next stage: the merchant will select "
                    "which of these products are genuinely "
                    "surplus, provide the surplus reason and "
                    "discounted price, and Circular Quest "
                    "will run eligibility and accountability "
                    "checks before publishing them."
                )

            except Exception as e:

                st.error(
                    "The selected columns could not be "
                    "converted."
                )

                st.exception(e)

        else:

            st.info(
                "Match all five required fields to continue."
            )


# =========================================================
# INVENTORY
# =========================================================

elif page == "Inventory":

    st.header("📦 Surplus Inventory")

    try:

        inventory = load_inventory(merchant_id)

    except Exception as e:

        st.error(
            "Could not load inventory."
        )

        st.exception(e)

        st.stop()

    if inventory:

        display_data = []

        for item in inventory:

            registered = (
                item["quantity_registered"]
            )

            eligible = (
                item.get(
                    "quantity_eligible",
                    0
                )
            )

            display_data.append({

                "Batch ID":
                    item["id"],

                "SKU":
                    item["merchant_sku"],

                "Product":
                    item["product_name"],

                "Category":
                    item["category"],

                "Registered":
                    registered,

                "Eligible":
                    eligible,

                "Remaining":
                    item["quantity_remaining"],

                "Original Price":
                    item["original_price"],

                "Surplus Price":
                    item["surplus_price"],

                "Reason":
                    item["surplus_reason"],

                "Status":
                    item["status"],

                "Eligible Until":
                    item["eligible_until"]
            })

        st.dataframe(
            pd.DataFrame(display_data),
            use_container_width=True,
            hide_index=True
        )

        total_registered = sum(
            item["quantity_registered"]
            for item in inventory
        )

        total_eligible = sum(
            item.get(
                "quantity_eligible",
                0
            )
            for item in inventory
        )

        col1, col2 = st.columns(2)

        with col1:

            st.metric(
                "Total Surplus Registered",
                f"{total_registered} units"
            )

        with col2:

            st.metric(
                "Total Approved for Circular Quest",
                f"{total_eligible} units"
            )

    else:

        st.info(
            "No surplus batches have been registered."
        )


# =========================================================
# ACCOUNTABILITY
# =========================================================

elif page == "Accountability":

    st.header("🛡️ Surplus Accountability")

    st.write(
        "Circular Quest monitors surplus patterns so that "
        "retailers cannot use the platform as an incentive "
        "to intentionally over-order inventory."
    )

    try:

        stats = load_stats(merchant_id)

    except Exception as e:

        st.error(
            "Could not load accountability data."
        )

        st.exception(e)

        st.stop()

    if stats:

        values = get_accountability_values(stats)

        latest = values["latest"]
        baseline_rate = values["baseline_rate"]
        current_rate = values["current_rate"]

        excess_units = max(
            0,
            latest["units_surplus"]
            - latest["eligible_surplus_cap"]
        )

        col1, col2, col3, col4 = st.columns(4)

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

        with col4:

            st.metric(
                "Excess Surplus",
                f"{excess_units} units"
            )

        st.divider()

        if baseline_rate == 0:

            st.info(
                "Not enough historical data is available "
                "to calculate an accountability status."
            )

        elif current_rate <= baseline_rate * 1.10:

            st.success(
                "🟢 GREEN — Surplus levels are within "
                "the expected historical range."
            )

        elif current_rate <= baseline_rate * 1.50:

            st.warning(
                "🟠 AMBER — Surplus has increased above "
                "the historical baseline. Eligibility "
                "remains capped and the increase should "
                "be reviewed."
            )

        else:

            st.error(
                "🔴 RED — Significant surplus anomaly "
                "detected. Additional surplus will not "
                "automatically receive Circular Quest "
                "incentives."
            )

        if excess_units > 0:

            st.warning(
                f"{excess_units} surplus units exceed the "
                "current Circular Quest eligibility allowance."
            )

        st.divider()

        st.subheader("Historical Surplus Performance")

        chart_data = []

        for row in stats:

            if row["units_procured"] > 0:

                surplus_rate = (
                    row["units_surplus"]
                    / row["units_procured"]
                    * 100
                )

            else:

                surplus_rate = 0

            chart_data.append({

                "Month":
                    row["month"],

                "Surplus Rate (%)":
                    surplus_rate
            })

        chart_df = pd.DataFrame(chart_data)

        chart_df["Month"] = pd.to_datetime(
            chart_df["Month"]
        )

        chart_df = chart_df.set_index("Month")

        st.line_chart(
            chart_df["Surplus Rate (%)"]
        )

        st.caption(
            "A sudden increase does not increase the "
            "merchant's Circular Quest eligibility cap."
        )

        st.divider()

        st.subheader("Monthly Records")

        stats_display = []

        for row in stats:

            rate = (
                row["units_surplus"]
                / row["units_procured"]
                * 100
                if row["units_procured"] > 0
                else 0
            )

            stats_display.append({

                "Month":
                    row["month"],

                "Units Procured":
                    row["units_procured"],

                "Normal Sales":
                    row["units_normal_sales"],

                "Surplus Units":
                    row["units_surplus"],

                "Surplus Rate":
                    f"{rate:.1f}%",

                "Eligibility Cap":
                    row["eligible_surplus_cap"]
            })

        st.dataframe(
            pd.DataFrame(stats_display),
            use_container_width=True,
            hide_index=True
        )

    else:

        st.info(
            "No historical accountability data is "
            "available for this merchant."
        )
