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
# CARBON CATALOGUE (ILLUSTRATIVE ESTIMATES)
# =========================================================

@st.cache_data(ttl=300)
def load_carbon_catalogue():
    """Fetch all catalogue rows; Supabase REST defaults to 1000 rows."""
    rows = []
    start = 0
    while True:
        page = (
            supabase.table("carbon_reference")
            .select("product_name,category,reference_unit,avoided_co2e_kg_per_item")
            .order("product_name")
            .range(start, start + 499)
            .execute()
        ).data or []
        rows.extend(page)
        if len(page) < 500:
            break
        start += 500
    return rows


def carbon_choices():
    """Only per-item references are directly usable as per-item values.

    Values per kg cannot be assigned to one retail package without its mass.
    """
    try:
        all_rows = load_carbon_catalogue()
    except Exception as exc:
        st.warning("Carbon catalogue unavailable: " + str(exc))
        return []
    return [r for r in all_rows
            if str(r.get("reference_unit", "")).strip().lower()
            in {"item", "device", "pair", "pack", "unit", "piece"}
            and r.get("avoided_co2e_kg_per_item") is not None]


def carbon_label(row):
    if row is None:
        return "No reference selected (CO2e unavailable)"
    return (f"{row['product_name']} — "
            f"{float(row['avoided_co2e_kg_per_item']):.3f} kg CO2e / "
            f"{row['reference_unit']} (illustrative)")


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
        "Accountability",
        "ESG Insights"
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

        st.markdown("**ESG evidence (optional, for reporting)**")
        unit_weight_kg = st.number_input("Weight per item (kg)", min_value=0.0, value=0.0, step=0.05, format="%.3f", help="Enter 0 if unknown.")
        product_condition = st.selectbox("Product condition", ["New", "Near expiry", "Refurbished", "Cosmetic damage", "Other"])
        expected_unsold_fate = st.selectbox("Expected fate if unsold", ["Unknown", "Disposed", "Donated", "Stored", "Returned to supplier"])
        disposal_probability = st.number_input("Estimated disposal probability (0–1)", min_value=0.0, max_value=1.0, value=0.0, step=0.05, help="Use documented historical rates if available. 0 means unknown/not evidenced, not that waste risk is zero.")

        st.markdown("**Carbon reference (optional)**")
        st.caption(
            "Choose only a comparable product and package unit. "
            "These are scenario estimates, not verified CO2 savings. "
            "If there is no appropriate match, leave it blank."
        )
        manual_carbon_options = [None] + carbon_choices()
        selected_carbon = st.selectbox(
            "Carbon reference for this item",
            manual_carbon_options,
            format_func=carbon_label,
            key="manual_carbon_reference"
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
                        batch_status,

                    "co2e_per_unit": (
                        float(selected_carbon["avoided_co2e_kg_per_item"])
                        if selected_carbon is not None else None
                    ),
                    "unit_weight_kg": float(unit_weight_kg) if unit_weight_kg > 0 else None,
                    "product_condition": product_condition,
                    "expected_unsold_fate": expected_unsold_fate,
                    "disposal_probability": float(disposal_probability) if expected_unsold_fate == "Disposed" else None
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
        "Upload an inventory export from your existing POS or "
        "inventory system. Circular Quest converts different "
        "retailer formats into one standard structure."
    )

    # -----------------------------------------------------
    # LOAD SAVED POS MAPPINGS
    # -----------------------------------------------------

    mapping_response = (
        supabase
        .table("pos_mappings")
        .select("*")
        .eq("merchant_id", merchant_id)
        .execute()
    )

    saved_mappings = mapping_response.data

    uploaded_file = st.file_uploader(
        "Upload POS inventory CSV",
        type=["csv"]
    )

    if uploaded_file is not None:

        try:

            df = pd.read_csv(uploaded_file)

        except Exception as e:

            st.error("Could not read CSV file.")
            st.exception(e)
            st.stop()

        if df.empty:

            st.warning("The uploaded file contains no products.")
            st.stop()

        # -------------------------------------------------
        # STEP 1 — RAW DATA
        # -------------------------------------------------

        st.subheader("1. POS Data Detected")

        st.dataframe(
            df,
            use_container_width=True,
            hide_index=True
        )

        st.caption(
            f"{len(df)} products detected."
        )

        st.divider()

        # -------------------------------------------------
        # STEP 2 — MAPPING METHOD
        # -------------------------------------------------

        st.subheader("2. Map POS Columns")

        mapping_options = [
            "Create New Mapping"
        ]

        for mapping in saved_mappings:

            mapping_options.append(
                mapping["mapping_name"]
            )

        selected_mapping_name = st.selectbox(
            "POS Mapping",
            mapping_options
        )

        columns = [
            "-- Select --"
        ] + list(df.columns)

        # -------------------------------------------------
        # SAVED MAPPING
        # -------------------------------------------------

        if selected_mapping_name != "Create New Mapping":

            selected_mapping = next(
                mapping
                for mapping in saved_mappings
                if mapping["mapping_name"]
                == selected_mapping_name
            )

            sku_column = selected_mapping["sku_column"]
            name_column = selected_mapping["name_column"]
            quantity_column = selected_mapping["quantity_column"]
            price_column = selected_mapping["price_column"]
            expiry_column = selected_mapping["expiry_column"]

            required_saved_columns = [
                sku_column,
                name_column,
                quantity_column,
                price_column,
                expiry_column
            ]

            missing_columns = [
                column
                for column in required_saved_columns
                if column not in df.columns
            ]

            if missing_columns:

                st.error(
                    "This CSV does not match the saved POS format. "
                    "Missing columns: "
                    + ", ".join(missing_columns)
                )

                st.stop()

            st.success(
                f"✓ Saved mapping '{selected_mapping_name}' applied."
            )

            st.write({
                "Product SKU": sku_column,
                "Product Name": name_column,
                "Quantity": quantity_column,
                "Original Price": price_column,
                "Expiry Date": expiry_column
            })

        # -------------------------------------------------
        # NEW MAPPING
        # -------------------------------------------------

        else:

            col1, col2 = st.columns(2)

            with col1:

                sku_column = st.selectbox(
                    "Product SKU",
                    columns,
                    key="new_sku"
                )

                name_column = st.selectbox(
                    "Product Name",
                    columns,
                    key="new_name"
                )

                quantity_column = st.selectbox(
                    "Quantity Remaining",
                    columns,
                    key="new_quantity"
                )

            with col2:

                price_column = st.selectbox(
                    "Original Price",
                    columns,
                    key="new_price"
                )

                expiry_column = st.selectbox(
                    "Expiry Date",
                    columns,
                    key="new_expiry"
                )

            mapping_name = st.text_input(
                "Save this format as",
                placeholder="e.g. FreshBasket POS"
            )

            if st.button("Save POS Mapping"):

                required = [
                    sku_column,
                    name_column,
                    quantity_column,
                    price_column,
                    expiry_column
                ]

                if "-- Select --" in required:

                    st.error(
                        "Please map all required columns first."
                    )

                elif not mapping_name.strip():

                    st.error(
                        "Please enter a name for this POS mapping."
                    )

                else:

                    new_mapping = {
                        "merchant_id": merchant_id,
                        "mapping_name": mapping_name.strip(),
                        "sku_column": sku_column,
                        "name_column": name_column,
                        "quantity_column": quantity_column,
                        "price_column": price_column,
                        "expiry_column": expiry_column
                    }

                    try:

                        supabase.table(
                            "pos_mappings"
                        ).insert(
                            new_mapping
                        ).execute()

                        st.success(
                            "✓ POS mapping saved. "
                            "It can be reused for future uploads."
                        )

                    except Exception as e:

                        st.error(
                            "Could not save POS mapping."
                        )

                        st.exception(e)

        # -------------------------------------------------
        # STEP 3 — STANDARDISE
        # -------------------------------------------------

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
                        df[sku_column].astype(str),

                    "product_name":
                        df[name_column].astype(str),

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

                standardized_df = (
                    standardized_df.dropna()
                )

                standardized_df["quantity"] = (
                    standardized_df["quantity"]
                    .astype(int)
                )

                st.divider()

                st.subheader(
                    "3. Circular Quest Standard Format"
                )

                st.success(
                    "✓ POS data successfully standardised."
                )

                st.dataframe(
                    standardized_df,
                    use_container_width=True,
                    hide_index=True
                )

                # -----------------------------------------
                # STEP 4 — SELECT SURPLUS PRODUCTS
                # -----------------------------------------

                st.divider()

                st.subheader(
                    "4. Select Genuine Surplus"
                )

                st.write(
                    "A normal POS export may contain many products. "
                    "Select only products that are genuinely being "
                    "declared as surplus."
                )

                product_options = []

                for index, row in standardized_df.iterrows():

                    label = (
                        f"{row['merchant_sku']} — "
                        f"{row['product_name']} "
                        f"({row['quantity']} available)"
                    )

                    product_options.append(label)

                selected_products = st.multiselect(
                    "Products to declare as surplus",
                    product_options
                )

                if selected_products:

                    st.divider()

                    st.subheader(
                        "5. Surplus Details"
                    )

                    surplus_reason = st.selectbox(
                        "Surplus Reason",
                        [
                            "Near Expiry",
                            "Seasonal Surplus",
                            "Discontinued",
                            "Cosmetic Damage",
                            "Forecasting Error",
                            "Other"
                        ],
                        key="bulk_reason"
                    )

                    discount_percentage = st.slider(
                        "Surplus Discount",
                        min_value=10,
                        max_value=90,
                        value=40,
                        step=5
                    )

                    eligible_until = st.date_input(
                        "Circular Quest Eligibility End Date",
                        key="bulk_eligible_until"
                    )

                    # Load merchant outlets

                    outlets = load_outlets(
                        merchant_id
                    )

                    outlet_names = [
                        outlet["outlet_name"]
                        for outlet in outlets
                    ]

                    selected_outlet_name = st.selectbox(
                        "Outlet",
                        outlet_names,
                        key="bulk_outlet"
                    )

                    selected_outlet = next(
                        outlet
                        for outlet in outlets
                        if outlet["outlet_name"]
                        == selected_outlet_name
                    )

                    outlet_id = selected_outlet["id"]

                    # -------------------------------------
                    # PREVIEW
                    # -------------------------------------

                    selected_rows = []

                    for selected_product in selected_products:

                        sku = selected_product.split(
                            " — "
                        )[0]

                        matching_row = (
                            standardized_df[
                                standardized_df[
                                    "merchant_sku"
                                ] == sku
                            ]
                        )

                        if not matching_row.empty:

                            row = matching_row.iloc[0]

                            surplus_price = (
                                row["original_price"]
                                * (
                                    1
                                    - discount_percentage
                                    / 100
                                )
                            )

                            selected_rows.append({

                                "merchant_sku":
                                    row["merchant_sku"],

                                "product_name":
                                    row["product_name"],

                                "quantity":
                                    int(row["quantity"]),

                                "original_price":
                                    float(
                                        row["original_price"]
                                    ),

                                "surplus_price":
                                    round(
                                        float(
                                            surplus_price
                                        ),
                                        2
                                    ),

                                "expiry_date":
                                    row["expiry_date"]
                            })

                    preview_df = pd.DataFrame(
                        selected_rows
                    )

                    st.write(
                        "**Import Preview**"
                    )

                    st.dataframe(
                        preview_df,
                        use_container_width=True,
                        hide_index=True
                    )

                    st.markdown("**ESG assumptions for this uploaded selection**")
                    bulk_weight = st.number_input("Weight per item (kg), all selected products", min_value=0.0, value=0.0, step=0.05, format="%.3f", key="bulk_weight")
                    bulk_condition = st.selectbox("Condition", ["New", "Near expiry", "Refurbished", "Cosmetic damage", "Other"], key="bulk_condition")
                    bulk_fate = st.selectbox("Expected fate if unsold", ["Unknown", "Disposed", "Donated", "Stored", "Returned to supplier"], key="bulk_fate")
                    bulk_probability = st.number_input("Disposal probability (0–1)", min_value=0.0, max_value=1.0, value=0.0, step=0.05, key="bulk_probability")
                    st.caption("For differing products, register separately to use individual weights and assumptions.")

                    st.markdown("**Optional carbon references for selected items**")
                    st.caption(
                        "Select a comparable per-item reference for each product. "
                        "Leave unmatched products blank. Values are illustrative."
                    )
                    bulk_carbon_options = [None] + carbon_choices()
                    for row in selected_rows:
                        choice = st.selectbox(
                            f"Reference for {row['product_name']} ({row['merchant_sku']})",
                            bulk_carbon_options,
                            format_func=carbon_label,
                            key=f"carbon_bulk_{merchant_id}_{row['merchant_sku']}"
                        )
                        row["co2e_per_unit"] = (
                            float(choice["avoided_co2e_kg_per_item"])
                            if choice is not None else None
                        )

                    # -------------------------------------
                    # REGISTER BUTTON
                    # -------------------------------------

                    if st.button(
                        "Validate & Register Selected Surplus",
                        type="primary"
                    ):

                        (
                            cap,
                            already_eligible,
                            remaining_allowance
                        ) = get_remaining_allowance(
                            merchant_id
                        )

                        successful = 0
                        rejected = 0
                        partial = 0

                        results = []

                        for item in selected_rows:

                            item_expiry = (
                                item["expiry_date"]
                                .date()
                            )

                            eligible, message = (
                                check_surplus_eligibility(
                                    surplus_reason,
                                    item_expiry,
                                    eligible_until
                                )
                            )

                            if not eligible:

                                rejected += 1

                                results.append({

                                    "Product":
                                        item[
                                            "product_name"
                                        ],

                                    "Result":
                                        "Rejected",

                                    "Details":
                                        message
                                })

                                continue

                            requested_quantity = (
                                item["quantity"]
                            )

                            eligible_quantity = min(
                                requested_quantity,
                                remaining_allowance
                            )

                            if eligible_quantity == 0:

                                status = "ineligible"

                                rejected += 1

                            elif (
                                eligible_quantity
                                < requested_quantity
                            ):

                                status = (
                                    "partially_eligible"
                                )

                                partial += 1

                            else:

                                status = "active"

                                successful += 1

                            new_batch = {

                                "merchant_id":
                                    merchant_id,

                                "outlet_id":
                                    outlet_id,

                                "merchant_sku":
                                    item[
                                        "merchant_sku"
                                    ],

                                "product_name":
                                    item[
                                        "product_name"
                                    ],

                                "category":
                                    "Food",

                                "quantity_registered":
                                    requested_quantity,

                                "quantity_remaining":
                                    eligible_quantity,

                                "quantity_eligible":
                                    eligible_quantity,

                                "original_price":
                                    item[
                                        "original_price"
                                    ],

                                "surplus_price":
                                    item[
                                        "surplus_price"
                                    ],

                                "surplus_reason":
                                    surplus_reason,

                                "expiry_date":
                                    item_expiry
                                    .isoformat(),

                                "eligible_until":
                                    eligible_until
                                    .isoformat(),

                                "status":
                                    status,

                                "co2e_per_unit":
                                    item.get("co2e_per_unit"),
                                "unit_weight_kg": float(bulk_weight) if bulk_weight > 0 else None,
                                "product_condition": bulk_condition,
                                "expected_unsold_fate": bulk_fate,
                                "disposal_probability": float(bulk_probability) if bulk_fate == "Disposed" else None
                            }

                            try:

                                supabase.table(
                                    "surplus_batches"
                                ).insert(
                                    new_batch
                                ).execute()

                                remaining_allowance -= (
                                    eligible_quantity
                                )

                                if status == "active":

                                    result_text = (
                                        f"{eligible_quantity} "
                                        "units approved"
                                    )

                                elif (
                                    status
                                    == "partially_eligible"
                                ):

                                    result_text = (
                                        f"{eligible_quantity} "
                                        f"of "
                                        f"{requested_quantity} "
                                        "units approved"
                                    )

                                else:

                                    result_text = (
                                        "Recorded but "
                                        "not eligible"
                                    )

                                results.append({

                                    "Product":
                                        item[
                                            "product_name"
                                        ],

                                    "Result":
                                        status,

                                    "Details":
                                        result_text
                                })

                            except Exception as e:

                                rejected += 1

                                results.append({

                                    "Product":
                                        item[
                                            "product_name"
                                        ],

                                    "Result":
                                        "Database Error",

                                    "Details":
                                        str(e)
                                })

                        st.divider()

                        st.subheader(
                            "Import Results"
                        )

                        st.dataframe(
                            pd.DataFrame(results),
                            use_container_width=True,
                            hide_index=True
                        )

                        st.success(
                            "POS surplus processing complete."
                        )

            except Exception as e:
                st.error("The POS file could not be processed.")
                st.exception(e)

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
                    item["eligible_until"],

                "Illustrative CO2e per unit (kg)":
                    item.get("co2e_per_unit")
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

# =========================================================
# ESG INSIGHTS — GRI 306-INFORMED, NOT CERTIFIED DISCLOSURE
# =========================================================

elif page == "ESG Insights":
    st.header("🌱 ESG Insights")
    st.caption("GRI 306-informed prototype. Completed sales are distinguished from estimated waste prevention and scenario-based CO₂e. Not a certified ESG report.")

    try:
        batches = load_inventory(merchant_id)
        sales = (supabase.table("surplus_sales").select("*")
                 .eq("merchant_id", merchant_id).order("sold_at", desc=True).execute().data)
    except Exception as e:
        st.error("Could not load ESG records. Run the supplied ESG SQL migration first.")
        st.exception(e)
        st.stop()

    by_id = {int(b["id"]): b for b in batches}
    st.subheader("Record a completed surplus sale (demo)")
    st.info("Record a sale only when it actually occurred. This demo is not connected to a live POS. Refunds must be recorded separately; do not record the same transaction twice.")
    options = [b for b in batches if b.get("status") in ("active", "partially_eligible") and int(b.get("quantity_remaining") or 0) > 0 and str(b.get("eligible_until") or "") >= date.today().isoformat()]
    if options:
        with st.form("sale_form"):
            chosen = st.selectbox("Eligible batch", options, format_func=lambda b: f"#{b['id']} — {b['product_name']} ({b['quantity_remaining']} available)")
            units = st.number_input("Units actually sold", min_value=1, max_value=int(chosen["quantity_remaining"]), value=1, step=1)
            receipt_ref = st.text_input("Receipt / transaction ID (unique for this merchant)")
            sale_confirm = st.form_submit_button("Record completed sale", type="primary")
        if sale_confirm:
            if not receipt_ref.strip():
                st.error("Enter a receipt/transaction ID.")
            else:
                try:
                    # Database function updates stock and creates the sale in one transaction.
                    supabase.rpc("record_surplus_sale", {
                        "p_merchant_id": int(merchant_id),
                        "p_batch_id": int(chosen["id"]),
                        "p_quantity": int(units),
                        "p_receipt_ref": receipt_ref.strip()
                    }).execute()
                    st.success("Sale recorded and inventory updated. Refresh to view ESG totals.")
                    st.rerun()
                except Exception as e:
                    st.error("Sale was not recorded. Check that the transaction ID is new and the stock is available.")
                    st.exception(e)
    else:
        st.info("No eligible, unexpired inventory with stock available for a new sale.")

    st.divider()
    st.subheader("Measured activity vs estimated impact")
    valid_sales = [r for r in sales if not r.get("refunded", False)]
    total_units = sum(int(r["quantity"]) for r in valid_sales)
    total_revenue = sum(float(r["quantity"]) * float(r["unit_sale_price"]) for r in valid_sales)
    total_discount = sum(float(r["quantity"]) * max(0, float(r["unit_original_price"]) - float(r["unit_sale_price"])) for r in valid_sales)
    mass_known = sum(float(r["quantity"]) * float(r["unit_weight_kg"]) for r in valid_sales if r.get("unit_weight_kg") is not None)
    mass_missing = sum(int(r["quantity"]) for r in valid_sales if r.get("unit_weight_kg") is None)
    potential_mass = sum(float(r["quantity"]) * float(r["unit_weight_kg"]) * float(r["disposal_probability"]) for r in valid_sales if r.get("unit_weight_kg") is not None and r.get("disposal_probability") is not None and r.get("expected_unsold_fate") == "Disposed")
    co2_scenario = sum(float(r["quantity"]) * float(r["co2e_per_unit"]) for r in valid_sales if r.get("co2e_per_unit") is not None)
    co2_missing = sum(int(r["quantity"]) for r in valid_sales if r.get("co2e_per_unit") is None)
    cols = st.columns(3)
    cols[0].metric("Confirmed units sold", f"{total_units:,}")
    cols[1].metric("Revenue recovered", f"S${total_revenue:,.2f}")
    cols[2].metric("Customer discount value", f"S${total_discount:,.2f}")
    cols = st.columns(3)
    cols[0].metric("Known redistributed mass", f"{mass_known:,.2f} kg")
    cols[1].metric("Potential waste avoided (scenario)", f"{potential_mass:,.2f} kg")
    cols[2].metric("Illustrative avoided CO₂e", f"{co2_scenario:,.2f} kg")
    if mass_missing or co2_missing:
        st.warning(f"Incomplete coverage: {mass_missing} sold units lack weight; {co2_missing} lack carbon factors. Totals exclude unknown values.")
    st.caption("Potential waste avoided = Σ(sold units × item mass × assumed probability of disposal), only when expected fate is 'Disposed'. CO₂e = Σ(sold units × scenario avoided-CO₂e per unit). These are not verified GHG inventory reductions or automatically GRI 306-4 waste diversion.")

    st.subheader("Sales ledger")
    if sales:
        st.dataframe(pd.DataFrame(sales), hide_index=True, use_container_width=True)
        st.download_button("Download sales records (CSV)", pd.DataFrame(sales).to_csv(index=False), "circular_quest_esg_sales.csv", "text/csv")
    else:
        st.info("No sales recorded yet. Registering inventory alone does not count as a sale or waste prevented.")
