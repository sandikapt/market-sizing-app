import streamlit as st
import pandas as pd
from io import BytesIO
from pipeline import parse, distribute, get_weights_for_product

st.set_page_config(page_title="Market Sizing", layout="wide")
st.title("Market Sizing Pipeline")

# --- Upload & parse (once) ---
uploaded = st.file_uploader("Upload Excel input", type=["xlsx"])
if not uploaded:
    st.stop()

include_company = st.checkbox("Include company dimension")
cache_key = f"{uploaded.name}_{include_company}"

if st.session_state.get('cache_key') != cache_key:
    with st.spinner("Parsing..."):
        st.session_state['parsed'] = parse(uploaded, include_company)
        st.session_state['cache_key'] = cache_key
        st.session_state.pop('result', None)

parsed = st.session_state['parsed']

# --- Run base distribution ---
if 'result' not in st.session_state:
    with st.spinner("Distributing..."):
        result, log = distribute(parsed)
        st.session_state['result'] = result
        st.session_state['log'] = log

for line in st.session_state['log']:
    if "WARNING" in line:
        st.warning(line)
    else:
        st.info(line)

result = st.session_state['result']

# --- Browse ---
st.divider()
st.subheader("Browse & Edit Weights")

col1, col2 = st.columns(2)
with col1:
    products = sorted(result['L4'].unique())
    pick_l4 = st.selectbox("Product (L4)", products)
with col2:
    years = sorted(result['Year'].unique())
    pick_year = st.selectbox("Year", years)

# Get idx for this product
subset = result[(result['L4'] == pick_l4) & (result['Year'] == pick_year)]
if subset.empty:
    st.warning("No data for this product-year")
    st.stop()
pick_idx = parsed['geo'][parsed['geo']['l4'] == pick_l4]['idx'].iloc[0]

# --- Show breakdown per dimension ---
st.markdown(f"**Breakdown for {pick_l4} — {pick_year}**")
for dim in [d.capitalize() for d in parsed['dims_list']]:
    breakdown = subset.groupby(dim)['Value'].sum().sort_values(ascending=False).reset_index()
    breakdown['Share %'] = (breakdown['Value'] / breakdown['Value'].sum() * 100).round(2)
    breakdown['Value'] = breakdown['Value'].round(2)
    st.markdown(f"`{dim}`")
    st.dataframe(breakdown, use_container_width=True, hide_index=True, height=150)

# --- Edit weights ---
st.divider()
st.subheader(f"Edit weights for: {pick_l4}")
st.caption("Edit the weight column, then click Recalculate. Topline stays locked — changes redistribute within this product.")

weights = get_weights_for_product(parsed, pick_l4, pick_idx)

edited = {}
cols = st.columns(len(weights))
for i, (dim, w) in enumerate(weights.items()):
    with cols[i]:
        st.markdown(f"**{dim}**")
        wcol = f'w_{dim}'
        edit_df = w[[dim, wcol]].copy()
        edit_df = edit_df.rename(columns={wcol: 'weight'})
        edited_df = st.data_editor(
            edit_df,
            key=f"edit_{dim}_{pick_l4}",
            use_container_width=True,
            hide_index=True,
            disabled=[dim],
            column_config={"weight": st.column_config.NumberColumn(min_value=0, max_value=100, step=0.1)},
        )
        total = edited_df['weight'].sum()
        if abs(total - 100) > 0.1:
            st.warning(f"Sum: {total:.1f}% (not 100)")
        else:
            st.success(f"Sum: {total:.1f}%")
        edited[dim] = edited_df.rename(columns={'weight': wcol})

if st.button("Recalculate", type="primary"):
    overrides = {}
    for dim, df in edited.items():
        wcol = f'w_{dim}'
        ov = df.copy()
        ov['l4'] = pick_l4
        ov['idx'] = pick_idx
        overrides[dim] = ov

    with st.spinner("Recalculating..."):
        result, log = distribute(parsed, weight_overrides=overrides)
        st.session_state['result'] = result
        st.session_state['log'] = log
        st.rerun()

# --- Download ---
st.divider()
buf = BytesIO()
result.to_csv(buf, index=False)
st.download_button("Download CSV", buf.getvalue(), "model_report.csv", "text/csv")
