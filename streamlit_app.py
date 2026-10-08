from datetime import datetime, timezone, timedelta
WIB = timezone(timedelta(hours=7))
import streamlit as st
import pandas as pd
from io import BytesIO
from pipeline import parse, distribute, get_weights_for_product

st.set_page_config(page_title="Market Sizing", layout="wide")
st.title("Market Sizing Pipeline")

# --- Upload & parse (once) ---
from make_template import make_template
with st.expander("Need the input template?"):
    tc = st.checkbox("Include company dimension (template)")
    st.download_button(
        "Download template",
        make_template(tc),
        f"template_{'4d' if tc else '3d'}_{datetime.now(WIB).strftime('%Y%m%d_%H%M')}.xlsx",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )

uploaded = st.file_uploader("Upload Excel input", type=["xlsx"])
if not uploaded:
    st.stop()

include_company = st.checkbox("Include company dimension")

if st.button("Run pipeline", type="primary"):
    with st.spinner("Parsing & distributing..."):
        parsed = parse(uploaded, include_company)
        result, log = distribute(parsed)
        st.session_state['parsed'] = parsed
        st.session_state['result'] = result
        st.session_state['log'] = log

if 'parsed' not in st.session_state:
    st.stop()

parsed = st.session_state['parsed']

for line in st.session_state['log']:
    if "WARNING" in line:
        st.warning(line)
    else:
        st.info(line)

result = st.session_state['result']

# --- Browse ---
st.divider()
st.subheader("Review Breakdown")

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
st.subheader(f"Edit Weights — {pick_l4}")
st.caption("Edit weights, rebalance if needed, then click Apply & Recalculate.")

weights = get_weights_for_product(parsed, pick_l4, pick_idx)

# Init stored overrides
if 'weight_overrides' not in st.session_state:
    st.session_state['weight_overrides'] = {}

edited = {}
cols = st.columns(len(weights))
for i, (dim, w) in enumerate(weights.items()):
    with cols[i]:
        st.markdown(f"**{dim}**")
        wcol = f'w_{dim}'

        # Use stored override if exists for this product+dim
        store_key = f"{pick_l4}_{pick_idx}_{dim}"
        if store_key in st.session_state['weight_overrides']:
            edit_df = st.session_state['weight_overrides'][store_key].copy()
        else:
            edit_df = w[[dim, wcol]].copy().rename(columns={wcol: 'weight'})

        edited_df = st.data_editor(
            edit_df,
            key=f"edit_{dim}_{pick_l4}",
            use_container_width=True,
            hide_index=True,
            disabled=[dim],
            column_config={"weight": st.column_config.NumberColumn(min_value=0, max_value=100, step=0.1)},
        )

        total = edited_df['weight'].sum()
        diff = 100 - total

        if abs(diff) > 0.1:
            st.warning(f"Sum: {total:.1f}% (off by {diff:+.1f}%)")
            others = edited_df[edited_df['weight'] > 0][dim].tolist()
            if len(others) > 0:
                mode = st.radio(
                    "Rebalance",
                    ["All others", "Pick one", "Pick several"],
                    key=f"mode_{dim}_{pick_l4}",
                    horizontal=True,
                )
                target_items = None
                if mode == "Pick one":
                    t = st.selectbox("Move to:", others, key=f"one_{dim}_{pick_l4}")
                    target_items = [t]
                elif mode == "Pick several":
                    target_items = st.multiselect("Spread across:", others, key=f"multi_{dim}_{pick_l4}")

                if st.button("Rebalance", key=f"bal_{dim}"):
                    if mode == "All others":
                        mask = edited_df['weight'] > 0
                    else:
                        mask = edited_df[dim].isin(target_items or [])
                    if mask.any():
                        cur = edited_df.loc[mask, 'weight']
                        edited_df.loc[mask, 'weight'] = cur + diff * (cur / cur.sum())
                        st.session_state['weight_overrides'][store_key] = edited_df
                        st.rerun()
        else:
            st.success(f"Sum: {total:.1f}%")

        edited[dim] = edited_df

# Apply & Recalculate
all_balanced = all(abs(edited[d]['weight'].sum() - 100) <= 0.1 for d in weights)
if not all_balanced:
    st.warning("Rebalance all dimensions to 100% before recalculating")
else:
    if st.button("Apply & Recalculate", type="primary"):
        overrides = {}
        for dim, df in edited.items():
            wcol = f'w_{dim}'
            ov = df.rename(columns={'weight': wcol}).copy()
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
st.download_button("Download CSV", buf.getvalue(), f"model_report_{datetime.now(WIB).strftime('%Y%m%d_%H%M')}.csv", "text/csv")
