# xlsx_parser.py
# Excel parser with smart header detection and column renaming

import os
import re
from .base import download_file, normalize_col, HAS_PANDAS, sanitize_field_names_for_mongodb
import numpy as np
if HAS_PANDAS:
    import pandas as pd


def clean_header(col) -> str:
    """Clean a column header - remove newlines, extra spaces, normalize"""
    if HAS_PANDAS and pd.isna(col):
        return ""
    col_str = str(col)
    col_str = col_str.replace('\n', ' ').replace('\r', ' ')
    col_str = re.sub(r'\s+', ' ', col_str)
    col_str = col_str.strip()
    return col_str

def smart_dropna_columns(df: pd.DataFrame) -> pd.DataFrame:
    """
    Drop columns that are BOTH:
    1. All NaN values
    2. Have an unnamed/meaningless header
    
    Keep columns with meaningful headers (like years) even if all values are NaN.
    """
    cols_to_drop = []
    
    for col in df.columns:
        col_str = str(col)
        is_all_nan = df[col].isna().all()
        
        # Check if header looks meaningful (year, specific name, etc.)
        is_meaningful_header = (
            col_str.isdigit() or  # Year like "2020"
            (len(col_str) > 0 and not col_str.startswith('column_') and not col_str.startswith('unnamed'))
        )
        
        # Only drop if ALL NaN AND has meaningless header
        if is_all_nan and not is_meaningful_header:
            cols_to_drop.append(col)
    
    if cols_to_drop:
        # print(f"       🗑️  Dropping truly empty columns: {cols_to_drop}")
        df = df.drop(columns=cols_to_drop)
    
    return df



def detect_header_row(df_raw, max_rows: int = 15) -> int:
    """Detect which row contains the actual headers."""
    best_row = 0
    best_score = 0
    
    for i in range(min(max_rows, len(df_raw) - 1)):
        row = df_raw.iloc[i]
        next_row = df_raw.iloc[i + 1] if i + 1 < len(df_raw) else None
        
        non_null_count = row.notna().sum()
        total_cols = len(row)
        
        if non_null_count < total_cols * 0.5:
            continue
        
        string_count = sum(1 for v in row if isinstance(v, str) and len(str(v).strip()) > 0)
        
        data_score = 0
        if next_row is not None:
            for v in next_row:
                if isinstance(v, (int, float)) and not pd.isna(v):
                    data_score += 1
                elif isinstance(v, str) and v.strip().replace('.', '').replace('-', '').isdigit():
                    data_score += 1
        
        score = (
            (non_null_count / total_cols) * 30 +
            (string_count / total_cols) * 40 +
            (data_score / total_cols) * 30
        )
        
        header_keywords = ['id', 'name', 'date', 'type', 'total', 'count', 'number', 'no.', 'street', 'year', 'units']
        row_text = ' '.join(str(v).lower() for v in row if pd.notna(v))
        if any(kw in row_text for kw in header_keywords):
            score += 20
        
        if score > best_score:
            best_score = score
            best_row = i
    
    return best_row

def infer_column_name(series: pd.Series, col_index: int) -> str:
    """
    Infer a meaningful column name based on the data content.
    
    Args:
        series: The pandas Series (column data)
        col_index: The column index for fallback naming
        
    Returns:
        Inferred column name
    """
    # Check if it's a datetime column
    if pd.api.types.is_datetime64_any_dtype(series):
        return 'period'  # Use 'period' for date ranges
    
    # Try to detect date-like strings
    sample = series.dropna().head(5)
    if len(sample) > 0:
        first_val = str(sample.iloc[0])
        
        # Month-Year patterns like "Jan-20", "Feb-21", "Mar-2020"
        month_year_patterns = [
            r'^(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[- ]?\d{2,4}$',  # Jan-20, Feb 21
            r'^\d{2,4}[- ]?(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)$',  # 20-Jan, 2020 Feb
            r'^Q[1-4][- ]?\d{2,4}$',  # Q1-20, Q2 2021 (quarters)
            r'^\d{4}[- ]?Q[1-4]$',  # 2020-Q1, 2021 Q2
        ]
        for pattern in month_year_patterns:
            if re.match(pattern, first_val, re.IGNORECASE):
                return 'period'
        
        # Full date patterns
        date_patterns = [
            r'^\d{4}-\d{2}-\d{2}',  # YYYY-MM-DD
            r'^\d{2}/\d{2}/\d{4}',  # MM/DD/YYYY
            r'^\d{2}-\d{2}-\d{4}',  # DD-MM-YYYY
        ]
        for pattern in date_patterns:
            if re.match(pattern, first_val, re.IGNORECASE):
                return 'date'
    
    # Check if it's an ID-like column (integers that look like IDs)
    if pd.api.types.is_integer_dtype(series):
        if series.is_monotonic_increasing or series.is_monotonic_decreasing:
            return 'id'
    
    # Fallback to generic name
    return f'column_{col_index}'

def rename_unnamed_columns(df: pd.DataFrame) -> pd.DataFrame:
    """
    Rename 'Unnamed' columns based on their content instead of dropping them.
    
    Args:
        df: DataFrame with potentially unnamed columns
        
    Returns:
        DataFrame with renamed columns
    """
    new_columns = []
    unnamed_counter = {}
    
    for i, col in enumerate(df.columns):
        col_str = str(col)
        
        # Check if this is an unnamed column
        is_unnamed = (
            col_str.startswith('Unnamed:') or 
            col_str.startswith('unnamed:') or
            col_str.startswith('Unnamed_') or 
            col_str.startswith('unnamed_') or
            not col_str.strip()
        )
        
        if is_unnamed:
            # Infer a name based on content
            inferred_name = infer_column_name(df.iloc[:, i], i)
            
            # Handle duplicates
            if inferred_name in unnamed_counter:
                unnamed_counter[inferred_name] += 1
                inferred_name = f"{inferred_name}_{unnamed_counter[inferred_name]}"
            else:
                unnamed_counter[inferred_name] = 0
            
            new_columns.append(inferred_name)
            
        else:
            new_columns.append(col_str)
    
    df.columns = new_columns
    return df

def rename_percentage_columns(columns: list) -> list:
    """
    Rename '%' columns based on the preceding column.
    
    Example:
        ['Bachelor_Units', '%', 'One_Bedroom_Units', '%'] 
        → ['Bachelor_Units', 'Bachelor_Units_Pct', 'One_Bedroom_Units', 'One_Bedroom_Units_Pct']
    """
    new_columns = []
    last_named_col = None
    pct_counter = {}
    
    for i, col in enumerate(columns):
        col_clean = str(col).strip()
        
        # Check if this is a percentage column
        if col_clean in ['%', 'Pct', 'Percent', 'Percentage'] or col_clean.startswith('%.'):
            if last_named_col:
                new_name = f"{last_named_col}_Pct"
                if new_name in pct_counter:
                    pct_counter[new_name] += 1
                    new_name = f"{new_name}_{pct_counter[new_name]}"
                else:
                    pct_counter[new_name] = 0
                new_columns.append(new_name)
            else:
                new_columns.append(f"Percentage_{i}")
        elif col_clean.startswith('Unnamed:') or col_clean.startswith('Unnamed_'):
            new_columns.append(col_clean)
        else:
            new_columns.append(col_clean)
            if col_clean and not col_clean.startswith('Unnamed'):
                last_named_col = col_clean
    
    return new_columns


def parse_xlsx(url: str, filepath: str, sheet_name=0, header_row: int = None) -> tuple:
    """Download and parse an Excel file from URL with smart header detection."""
    download_file(url, filepath)
    records = []
    print(f"   📋 Parsing Excel file: {filepath}")
    if not HAS_PANDAS:
        print("       ⚠️ pandas not installed")
        return [], filepath
    
    try:
        if header_row is None:
            df_raw = pd.read_excel(filepath, sheet_name=sheet_name, header=None, 
                                   nrows=20, engine='openpyxl')
            header_row = detect_header_row(df_raw)
            # print(f"       📋 Auto-detected header at row {header_row}")
        
        df = pd.read_excel(filepath, sheet_name=sheet_name, header=header_row, engine='openpyxl')
        
        # Clean and normalize column names
        df.columns = [clean_header(col) for col in df.columns]
        df.columns = [normalize_col(col) if col else f"column_{i}" 
                      for i, col in enumerate(df.columns)]
        
        # Rename percentage columns based on preceding column
        df.columns = rename_percentage_columns(list(df.columns))
        
        # ═══════════════════════════════════════════════════════════════
        # FIX 2: Rename Unnamed columns instead of dropping them
        # ═══════════════════════════════════════════════════════════════
        df = rename_unnamed_columns(df)
        
        #FIX 3: Smart column dropping - keep columns with meaningful headers
        df = smart_dropna_columns(df)
        df = df.dropna(how='all')  # Remove empty rows
       

        df = remove_summary_rows(df)

        # Handle duplicate column names
        cols = []
        seen = {}
        for col in df.columns:
            if col in seen:
                seen[col] += 1
                cols.append(f"{col}_{seen[col]}")
            else:
                seen[col] = 0
                cols.append(col)
        df.columns = cols
        # 🔥 FIX: normalize percentage values
        df = normalize_percentage_values(df)

        df = df_nan_to_none(df)
        records = df.to_dict(orient='records')
        records = sanitize_field_names_for_mongodb(records) 

        print(f"       ✅ Parsed Excel file with openpyxl ({len(records)} rows)")
        
    except ImportError:
        try:
            if header_row is None:
                df_raw = pd.read_excel(filepath, sheet_name=sheet_name, header=None,
                                       nrows=20, engine='xlrd')
                header_row = detect_header_row(df_raw)
            
            df = pd.read_excel(filepath, sheet_name=sheet_name, header=header_row, engine='xlrd')
            df.columns = [clean_header(col) for col in df.columns]
            df.columns = [normalize_col(col) if col else f"column_{i}" 
                          for i, col in enumerate(df.columns)]
            df.columns = rename_percentage_columns(list(df.columns))
            
            cols_to_drop = [col for col in df.columns if str(col).startswith('Unnamed')]
            df = df.drop(columns=cols_to_drop, errors='ignore')
            # df = df.dropna(axis=1, how='all').dropna(how='all')
            df = smart_dropna_columns(df)
            df = df_nan_to_none(df)
            records = df.to_dict(orient='records')
            records = sanitize_field_names_for_mongodb(records) 
            # print(f"       ✅ Parsed Excel file with xlrd ({len(records)} rows)")
        except ImportError:
            print("       ❌ No Excel engine available. Install openpyxl or xlrd.")
        except Exception as e:
            print(f"       ❌ Excel parse failed: {e}")
    except Exception as e:
        print(f"       ❌ Excel parse failed: {e}")
    
    return records, filepath

def normalize_percentage_values(df: pd.DataFrame, decimals: int = 1) -> pd.DataFrame:
    """
    Convert Excel percentage values (0–1) to human-readable percentages (0–100).
    """
    for col in df.columns:
        if col.lower().endswith('_pct'):
            df[col] = df[col].apply(
                lambda x: round(x * 100, decimals)
                if isinstance(x, (int, float)) else x
            )
    return df


def parse_xlsx_all_sheets(url: str, filepath: str, header_row: int = None) -> tuple:
    """Download and parse all sheets from an Excel file."""
    download_file(url, filepath)
    all_records = {}
    
    if not HAS_PANDAS:
        return {}, filepath
    
    try:
        xlsx = pd.ExcelFile(filepath, engine='openpyxl')
        
        for sheet_name in xlsx.sheet_names:
            try:
                df_raw = pd.read_excel(filepath, sheet_name=sheet_name, header=None,
                                       nrows=20, engine='openpyxl')
                sheet_header_row = header_row if header_row is not None else detect_header_row(df_raw)
                
                df = pd.read_excel(filepath, sheet_name=sheet_name, header=sheet_header_row, 
                                   engine='openpyxl')
                
                # FIX 1: Convert numeric column names
                df.columns = convert_numeric_column_names(list(df.columns))
                
                # Clean column names
                df.columns = [clean_header(col) for col in df.columns]
                df.columns = [normalize_col(col) if col else f"column_{i}"
                              for i, col in enumerate(df.columns)]
                df.columns = rename_percentage_columns(list(df.columns))
                
                # FIX 2: Rename unnamed columns instead of dropping
                df = rename_unnamed_columns(df)
                
                # Clean up - use smart dropna to preserve meaningful columns
                df = smart_dropna_columns(df)

                df = df.dropna(how='all')  # Remove empty rows only
                df = normalize_percentage_values(df)
                df = df_nan_to_none(df)

                all_records[sheet_name] = df.to_dict(orient='records')
                all_records[sheet_name] = sanitize_field_names_for_mongodb(all_records[sheet_name]) 
                # print(f"       📋 Sheet '{sheet_name}': {len(all_records[sheet_name])} rows")
            except Exception as e:
                print(f" ⚠️ Failed to parse sheet '{sheet_name}': {e}")
                all_records[sheet_name] = []
        
        # print(f ✅ Parsed {len(all_records)} sheets from Excel file")
        
    except Exception as e:
        print(f"       ❌ Excel parse failed: {e}")
    
    return all_records, filepath


def parse_xlsx_from_file(filepath: str, sheet_name=0, header_row: int = None) -> list:
    """Parse an Excel file that's already downloaded (no URL)."""
    if not HAS_PANDAS:
        print("⚠️ pandas not installed")
        return []
    
    if not os.path.exists(filepath):
        print(f"❌ File not found: {filepath}")
        return []
    
    try:
        if header_row is None:
            df_raw = pd.read_excel(filepath, sheet_name=sheet_name, header=None,
                                   nrows=20, engine='openpyxl')
            header_row = detect_header_row(df_raw)
        
        df = pd.read_excel(filepath, sheet_name=sheet_name, header=header_row, engine='openpyxl')
        df.columns = [clean_header(col) for col in df.columns]
        df.columns = [normalize_col(col) if col else f"column_{i}" 
                      for i, col in enumerate(df.columns)]
        df.columns = rename_percentage_columns(list(df.columns))
        
        cols_to_drop = [col for col in df.columns if str(col).startswith('Unnamed')]
        df = df.drop(columns=cols_to_drop, errors='ignore')
        df = df.dropna(axis=1, how='all').dropna(how='all')

        #  FIX
        df = normalize_percentage_values(df)

        df = df_nan_to_none(df)
        records = df.to_dict(orient='records')
        records = sanitize_field_names_for_mongodb(records)
        return records
    except Exception as e:
        print(f"❌ Excel parse failed: {e}")
        return []


def convert_numeric_column_names(columns: list) -> list:
    """
    Convert numeric column names (like 2020, 2021.0) to strings.
    This ensures JSON serialization works correctly.
    """
    new_columns = []
    for col in columns:
        if isinstance(col, (int, float)):
            # Convert to string, removing .0 for floats
            if isinstance(col, float) and col.is_integer():
                new_columns.append(str(int(col)))
            else:
                new_columns.append(str(col))
        else:
            new_columns.append(col)
    return new_columns


def remove_summary_rows(df: pd.DataFrame) -> pd.DataFrame:
    """
    Drop rows that look like totals/subtotals or are mostly empty.
    Customize patterns as needed.
    """
    # Drop rows that are completely empty (already done, but safe)
    df = df.dropna(how='all')

    # Build a lowercase string for each row to inspect textual content
    row_text = df.astype(str).apply(lambda r: ' '.join(r.values).lower(), axis=1)

    # Keywords that usually indicate non-detail rows
    summary_keywords = [
        'total', 'subtotal', 'grand total', 'totals',
        'average', 'avg', 'summary'
    ]

    # Boolean mask: True for rows to keep
    mask = ~row_text.str.contains('|'.join(summary_keywords))

    return df[mask]



# def normalize_empty_to_null(df: pd.DataFrame) -> pd.DataFrame:
#     # Convert empty / whitespace-only strings to NaN so they become None in records
#     df = df.replace(r'^\s*$', np.nan, regex=True)  # handles "" and "   "
#     return df

# def df_nan_to_none(df: pd.DataFrame) -> pd.DataFrame:
#     # Replace pandas/NumPy NaN with real Python None
#     return df.where(pd.notnull(df), None)

def df_nan_to_none(df: pd.DataFrame) -> pd.DataFrame:
    """
    Convert pandas/NumPy NaN values to real Python None
    so JSON serialization produces null instead of NaN.
    """
    df = df.astype(object)          # critical step
    df = df.replace({np.nan: None}) # replace NaN → None
    return df
