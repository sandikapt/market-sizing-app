import pandas as pd
import numpy as np

KEYS = ['l4', 'idx']
NO_COMPANY_SEGMENTS = ['Government']


def is_filled(v):
    return pd.notna(v) and str(v).strip().upper() not in ('', 'ALL')


def load_dim(xls, dim):
    df = xls.parse(f'gs_{dim}_input')
    cols = [c for c in df.columns if c not in KEYS]
    long = df.melt(id_vars=KEYS, value_vars=cols, var_name=dim, value_name=f'w_{dim}')
    long[f'w_{dim}'] = long[f'w_{dim}'].fillna(0)
    return long[long[f'w_{dim}'] > 0], cols


def parse(file_bytes, include_company=False):
    """Parse Excel into intermediate structures. Returns dict with everything needed."""
    xls = pd.ExcelFile(file_bytes)
    dims_list = ['segment', 'region', 'industry'] + (['company'] if include_company else [])

    # Load dimensional weights (keep raw per-dimension weights)
    dims = {}
    dim_labels = {}
    for d in dims_list:
        df, labels = load_dim(xls, d)
        dims[d] = df
        dim_labels[d] = labels

    # Build combinations
    geo = dims['segment']
    for d in ['region', 'industry']:
        geo = geo.merge(dims[d], on=KEYS)

    if include_company:
        skip = geo['segment'].isin(NO_COMPANY_SEGMENTS)
        with_co = geo[~skip].merge(dims['company'], on=KEYS)
        no_co = geo[skip].assign(company='-', w_company=100.0)
        geo = pd.concat([with_co, no_co], ignore_index=True)

    # Blocklist
    blocklist = xls.parse('block_list')
    blocked = np.zeros(len(geo), dtype=bool)
    for _, rule in blocklist.iterrows():
        if not include_company and 'company' in rule.index and is_filled(rule.get('company')):
            continue
        conds = {c: rule[c] for c in dims_list + KEYS if c in rule.index and is_filled(rule.get(c))}
        if not conds:
            continue
        mask = np.ones(len(geo), dtype=bool)
        for c, v in conds.items():
            if c == 'idx':
                mask &= (geo[c] == v).values
            else:
                mask &= (geo[c].astype(str).str.strip() == str(v).strip()).values
        blocked |= mask
    geo = geo[~blocked]

    # Topline
    topline = xls.parse('topline')
    yearref = xls.parse('yearref')
    year_map = dict(zip(yearref['code'], yearref['year']))
    meta = [c for c in ['group_product', 'product', 'sub-product', 'l1', 'l2', 'l3', 'l4', 'idx']
            if c in topline.columns]
    tl = topline.melt(id_vars=meta, var_name='year_code', value_name='value')
    tl['year'] = tl['year_code'].map(year_map)
    tl = tl.dropna(subset=['year']).drop(columns='year_code')

    return {
        'geo': geo,
        'topline': tl,
        'meta': meta,
        'dims_list': dims_list,
        'dims': dims,
        'dim_labels': dim_labels,
    }


def distribute(parsed, weight_overrides=None):
    """Distribute topline using geo weights. Optional weight_overrides: dict of {dim: DataFrame}."""
    geo = parsed['geo'].copy()
    tl = parsed['topline']
    dims_list = parsed['dims_list']
    meta = parsed['meta']

    # Apply overrides: replace w_{dim} for specific product
    if weight_overrides:
        for dim, ov in weight_overrides.items():
            wcol = f'w_{dim}'
            for _, row in ov.iterrows():
                mask = (geo['l4'] == row['l4']) & (geo['idx'] == row['idx']) & (geo[dim] == row[dim])
                geo.loc[mask, wcol] = row[wcol]

    # Recalculate combined weight
    geo['weight'] = np.prod([geo[f'w_{d}'] / 100 for d in dims_list], axis=0)
    geo = geo[geo['weight'] > 0]

    # Distribute
    group = KEYS + ['year']
    df = tl.merge(geo, on=KEYS)
    df['share'] = df['weight'] / df.groupby(group)['weight'].transform('sum')
    df['Value'] = (df['value'] * df['share']).fillna(0)

    # Reconcile
    log = []
    inp = tl.groupby(group)['value'].sum()
    out = df.groupby(group)['Value'].sum()
    check = pd.concat([inp.rename('input'), out.rename('output')], axis=1).fillna(0)
    check['gap'] = check['input'] - check['output']
    bad = check[check['gap'].abs() > 1e-6]
    if len(bad):
        log.append(f"WARNING: {len(bad)} product-years not fully distributed")
    else:
        log.append("Reconciliation passed")
    log.append(f"Total: {check['input'].sum():,.2f} in | {check['output'].sum():,.2f} out")
    log.append(f"Combinations: {len(geo):,} | Output rows: {(df['Value'] != 0).sum():,}")

    # Format output
    rename = {'idx': 'IDX', 'group_product': 'Group_Product', 'product': 'Product',
              'sub-product': 'Sub_Product', 'l1': 'L1', 'l2': 'L2', 'l3': 'L3', 'l4': 'L4',
              'year': 'Year', 'segment': 'Segment', 'region': 'Region',
              'industry': 'Industry', 'company': 'Company'}
    out_cols = [rename.get(c, c) for c in meta + ['year'] + dims_list] + ['Value']
    result = df[df['Value'] != 0].rename(columns=rename)
    result['Year'] = result['Year'].astype(int)

    return result[out_cols], log


def get_weights_for_product(parsed, l4, idx):
    """Get current weights per dimension for one product. Returns {dim: DataFrame}."""
    geo = parsed['geo']
    mask = (geo['l4'] == l4) & (geo['idx'] == idx)
    product_geo = geo[mask]

    weights = {}
    for d in parsed['dims_list']:
        wcol = f'w_{d}'
        w = product_geo.groupby(d)[wcol].first().reset_index()
        w = w.sort_values(wcol, ascending=False)
        weights[d] = w

    return weights
