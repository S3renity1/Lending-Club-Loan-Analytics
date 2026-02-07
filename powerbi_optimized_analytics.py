import pandas as pd
import numpy as np
from datetime import datetime
import warnings
warnings.filterwarnings('ignore')

print("="*70)
print("LENDING CLUB LOAN ANALYTICS - POWER BI OPTIMIZED")
print("Dataset: Kaggle Lending Club (2007-2018 Q4)")
print("="*70)

chunk_size = 500_000
accepted_file = "accepted_2007_to_2018Q4.csv"
rejected_file = "rejected_2007_to_2018Q4.csv"

# ========================================
# LOAD ACCEPTED LOANS
# ========================================
print("\n[1/6] Loading ACCEPTED loans data...")

accepted_cols = [
    'id', 'member_id', 'loan_amnt', 'grade', 'sub_grade', 'issue_d', 
    'loan_status', 'addr_state', 'annual_inc', 'dti', 'fico_range_low', 
    'fico_range_high', 'emp_length', 'purpose'
]

accepted_chunks = []
rows_loaded = 0

for chunk in pd.read_csv(accepted_file, usecols=accepted_cols, chunksize=chunk_size):

    chunk['loan_amnt'] = pd.to_numeric(chunk['loan_amnt'], errors='coerce')
    chunk['annual_inc'] = pd.to_numeric(chunk['annual_inc'], errors='coerce')
    chunk['dti'] = pd.to_numeric(chunk['dti'], errors='coerce')
    chunk['fico_range_low'] = pd.to_numeric(chunk['fico_range_low'], errors='coerce')
    chunk['fico_range_high'] = pd.to_numeric(chunk['fico_range_high'], errors='coerce')
    

    chunk['issue_d'] = pd.to_datetime(chunk['issue_d'], format='%b-%Y', errors='coerce')
    
    accepted_chunks.append(chunk)
    rows_loaded += len(chunk)
    print(f"   Loaded {rows_loaded:,} rows...", end='\r')

accepted = pd.concat(accepted_chunks, ignore_index=True)
print(f"\n   ✓ Loaded {len(accepted):,} accepted loans")

# ========================================
# LOAD REJECTED LOANS
# ========================================
print("\n[2/6] Loading REJECTED loans data...")

rejected_cols = [
    'Amount Requested', 'Application Date', 'Risk_Score', 
    'Debt-To-Income Ratio', 'Zip Code', 'State', 'Employment Length', 'Loan Title'
]

rejected_chunks = []
rows_loaded = 0

for chunk in pd.read_csv(rejected_file, usecols=rejected_cols, chunksize=chunk_size):

    chunk['Amount Requested'] = pd.to_numeric(chunk['Amount Requested'], errors='coerce')
    chunk['Debt-To-Income Ratio'] = pd.to_numeric(chunk['Debt-To-Income Ratio'], errors='coerce')
    chunk['Risk_Score'] = pd.to_numeric(chunk['Risk_Score'], errors='coerce')
    

    chunk['Application Date'] = pd.to_datetime(chunk['Application Date'], errors='coerce')

    rename_dict = {
        'Application Date': 'date',
        'Amount Requested': 'loan_amnt',
        'Debt-To-Income Ratio': 'dti',
        'Employment Length': 'emp_length',
        'State': 'addr_state',
        'Loan Title': 'purpose',
        'Risk_Score': 'risk_score',
        'Zip Code': 'zip_code'
    }
    chunk.rename(columns=rename_dict, inplace=True)
    
    rejected_chunks.append(chunk)
    rows_loaded += len(chunk)
    print(f"   Loaded {rows_loaded:,} rows...", end='\r')

rejected = pd.concat(rejected_chunks, ignore_index=True)
print(f"\n   ✓ Loaded {len(rejected):,} rejected loans")

# ========================================
# DATA PREPARATION & FEATURE ENGINEERING
# ========================================
print("\n[3/6] Engineering features for Power BI...")


accepted.rename(columns={'issue_d': 'date'}, inplace=True)


def add_time_dimensions(df):

    df['year'] = df['date'].dt.year
    df['quarter'] = df['date'].dt.quarter
    df['month'] = df['date'].dt.month
    df['year_month'] = df['date'].dt.to_period('M').astype(str)
    df['year_quarter'] = df['date'].dt.to_period('Q').astype(str)
    df['month_name'] = df['date'].dt.strftime('%B')
    df['quarter_name'] = 'Q' + df['quarter'].astype(str)
    df['year_month_date'] = df['date'].dt.to_period('M').dt.to_timestamp()
    return df

accepted = add_time_dimensions(accepted)
rejected = add_time_dimensions(rejected)


accepted['fico_score'] = (accepted['fico_range_low'] + accepted['fico_range_high']) / 2


accepted['fico_bucket'] = pd.cut(
    accepted['fico_range_low'], 
    bins=[300, 580, 670, 740, 800, 850], 
    labels=['1_Poor (300-580)', '2_Fair (580-670)', '3_Good (670-740)', 
            '4_Very Good (740-800)', '5_Exceptional (800+)']
).astype(str)
accepted['fico_bucket'] = accepted['fico_bucket'].fillna('Unknown')


rejected['risk_bucket'] = pd.cut(
    rejected['risk_score'], 
    bins=[0, 600, 650, 700, 750, 1000],
    labels=['1_High Risk (0-600)', '2_Med-High (600-650)', '3_Medium (650-700)', 
            '4_Low-Med (700-750)', '5_Low Risk (750+)']
).astype(str)
rejected['risk_bucket'] = rejected['risk_bucket'].fillna('Unknown')


def create_dti_buckets(df):
    df['dti_bucket'] = pd.cut(
        df['dti'], 
        bins=[0, 10, 20, 30, 40, 100], 
        labels=['1_0-10%', '2_10-20%', '3_20-30%', '4_30-40%', '5_40%+']
    ).astype(str)
    df['dti_bucket'] = df['dti_bucket'].fillna('Unknown')
    return df

accepted = create_dti_buckets(accepted)
rejected = create_dti_buckets(rejected)


def clean_emp_length(emp_str):
    if pd.isna(emp_str):
        return 'Unknown'
    emp_str = str(emp_str).strip()
    if emp_str in ['', 'n/a', 'N/A']:
        return 'Unknown'
    return emp_str

accepted['emp_length'] = accepted['emp_length'].apply(clean_emp_length)
rejected['emp_length'] = rejected['emp_length'].apply(clean_emp_length)


accepted['purpose'] = accepted['purpose'].fillna('Unknown')
rejected['purpose'] = rejected['purpose'].fillna('Unknown')


accepted['addr_state'] = accepted['addr_state'].fillna('Unknown')
rejected['addr_state'] = rejected['addr_state'].fillna('Unknown')


accepted['loan_type'] = 'Accepted'
rejected['loan_type'] = 'Rejected'

print("   ✓ Data preparation complete")

# ========================================
# TABLE 1: FACT TABLE - ALL LOANS (UNION)
# ========================================
print("\n[4/6] Creating FACT table - All Loans...")


fact_accepted = accepted[[
    'id', 'date', 'year', 'quarter', 'month', 'year_month', 'year_quarter',
    'month_name', 'quarter_name', 'loan_type', 'loan_amnt', 'grade', 'sub_grade', 
    'loan_status', 'addr_state', 'annual_inc', 'dti', 'fico_score', 'fico_bucket',
    'dti_bucket', 'emp_length', 'purpose'
]].copy()


fact_accepted['risk_score'] = np.nan
fact_accepted['risk_bucket'] = 'N/A'


fact_rejected = rejected[[
    'date', 'year', 'quarter', 'month', 'year_month', 'year_quarter',
    'month_name', 'quarter_name', 'loan_type', 'loan_amnt', 'addr_state', 
    'dti', 'risk_score', 'risk_bucket', 'dti_bucket', 'emp_length', 'purpose'
]].copy()


fact_rejected['id'] = 'REJ_' + (fact_rejected.index + 1).astype(str)
fact_rejected['grade'] = 'N/A'
fact_rejected['sub_grade'] = 'N/A'
fact_rejected['loan_status'] = 'Rejected'
fact_rejected['annual_inc'] = np.nan
fact_rejected['fico_score'] = np.nan
fact_rejected['fico_bucket'] = 'N/A'


fact_rejected = fact_rejected[[
    'id', 'date', 'year', 'quarter', 'month', 'year_month', 'year_quarter',
    'month_name', 'quarter_name', 'loan_type', 'loan_amnt', 'grade', 'sub_grade', 
    'loan_status', 'addr_state', 'annual_inc', 'dti', 'fico_score', 'fico_bucket',
    'risk_score', 'risk_bucket', 'dti_bucket', 'emp_length', 'purpose'
]]


fact_all_loans = pd.concat([fact_accepted, fact_rejected], ignore_index=True)


fact_all_loans = fact_all_loans.sort_values('date').reset_index(drop=True)

print(f"   ✓ Created FACT table with {len(fact_all_loans):,} total loans")

# ========================================
# TABLE 2: DATE DIMENSION TABLE
# ========================================
print("\n[5/6] Creating DIMENSION tables...")


date_dim = fact_all_loans[['date', 'year', 'quarter', 'month', 'year_month', 
                            'year_quarter', 'month_name', 'quarter_name']].drop_duplicates()
date_dim = date_dim.sort_values('date').reset_index(drop=True)
date_dim['date_id'] = range(1, len(date_dim) + 1)
date_dim['day'] = date_dim['date'].dt.day
date_dim['day_of_week'] = date_dim['date'].dt.dayofweek
date_dim['day_name'] = date_dim['date'].dt.strftime('%A')
date_dim['is_quarter_start'] = date_dim['date'].dt.is_quarter_start
date_dim['is_quarter_end'] = date_dim['date'].dt.is_quarter_end
date_dim['is_year_start'] = date_dim['date'].dt.is_year_start
date_dim['is_year_end'] = date_dim['date'].dt.is_year_end

print(f"   ✓ Date dimension: {len(date_dim):,} unique dates")


print("\n[6/6] Saving Power BI tables...")

fact_all_loans.to_csv('fact_all_loans.csv', index=False)
date_dim.to_csv('dim_date.csv', index=False)

print("\n" + "="*70)
print("SUCCESS! All Power BI tables created")
print("="*70)

