import streamlit as st

st.set_page_config(
    page_title="Circular Quest Merchant Portal",
    page_icon="♻️",
    layout="wide"
)

st.title("♻️ Circular Quest")
st.subheader("Merchant Portal")

st.write("Welcome to the Circular Quest retailer management platform.")

st.divider()

col1, col2, col3 = st.columns(3)

with col1:
    st.metric("Active Surplus", "75 units")

with col2:
    st.metric("Items Rescued", "327")

with col3:
    st.metric("Surplus Status", "Green 🟢")
