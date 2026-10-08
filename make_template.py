import pandas as pd
from io import BytesIO

def make_template(include_company=False):
    buf = BytesIO()
    with pd.ExcelWriter(buf, engine='openpyxl') as w:
        pd.DataFrame({'code': ['y1', 'y2', 'y3'], 'year': [2024, 2025, 2026]}).to_excel(w, 'yearref', index=False)

        pd.DataFrame({'group_product': [''], 'product': [''], 'sub-product': [''],
                       'l1': [''], 'l2': [''], 'l3': [''], 'l4': [''], 'idx': [1],
                       'y1': [0.0], 'y2': [0.0], 'y3': [0.0]}).to_excel(w, 'topline', index=False)

        pd.DataFrame({'l4': [''], 'idx': [1], 'y1': [0.0], 'y2': [0.0], 'y3': [0.0]}).to_excel(w, 'gs_year_input', index=False)

        pd.DataFrame({'l4': [''], 'idx': [1], 'Enterprise': [0.0], 'SMB': [0.0],
                       'Government': [0.0]}).to_excel(w, 'gs_segment_input', index=False)

        pd.DataFrame({'l4': [''], 'idx': [1], 'Jawa': [0.0], 'Sumatra': [0.0],
                       'Kalimantan': [0.0]}).to_excel(w, 'gs_region_input', index=False)

        pd.DataFrame({'l4': [''], 'idx': [1], 'Banking': [0.0], 'Telco': [0.0],
                       'Manufacturing': [0.0]}).to_excel(w, 'gs_industry_input', index=False)

        if include_company:
            pd.DataFrame({'l4': [''], 'idx': [1], 'Company_A': [0.0],
                           'Company_B': [0.0]}).to_excel(w, 'gs_company_input', index=False)

        cols = ['l4', 'idx', 'segment', 'region', 'industry']
        if include_company:
            cols.append('company')
        pd.DataFrame(columns=cols).to_excel(w, 'block_list', index=False)

    buf.seek(0)
    return buf.getvalue()
