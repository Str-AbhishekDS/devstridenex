# /path/to/bench/apps/your_app/import_industries.py
import frappe
import pandas as pd
import glob
import traceback
import time


CHUNK_SIZE = 500       # reduced from 5000 → avoids lock timeout
RETRY_ATTEMPTS = 3     # retry each chunk on timeout
RETRY_DELAY = 5        # seconds between retries


def insert_chunk_with_retry(chunk_rows, attempt=1):
    """Insert a chunk; retry on lock timeout."""
    try:
        frappe.db.bulk_insert(
            "Industry list",
            fields=list(chunk_rows[0].keys()),
            values=[list(r.values()) for r in chunk_rows],
            ignore_duplicates=True,
        )
        frappe.db.commit()
        return True

    except frappe.QueryTimeoutError:
        frappe.db.rollback()
        if attempt < RETRY_ATTEMPTS:
            print(f"  ⚠️  Lock timeout on chunk — retrying ({attempt}/{RETRY_ATTEMPTS}) in {RETRY_DELAY}s...")
            time.sleep(RETRY_DELAY)
            return insert_chunk_with_retry(chunk_rows, attempt + 1)
        else:
            print(f"  ❌ Chunk failed after {RETRY_ATTEMPTS} attempts — falling back to row-by-row insert")
            return insert_row_by_row(chunk_rows)

    except Exception as e:
        frappe.db.rollback()
        print(f"  ❌ Chunk error: {e}")
        return False


def insert_row_by_row(chunk_rows):
    """Last-resort: insert one row at a time so bad rows don't block good ones."""
    success = 0
    for row in chunk_rows:
        try:
            frappe.db.bulk_insert(
                "Industry list",
                fields=list(row.keys()),
                values=[list(row.values())],
                ignore_duplicates=True,
            )
            frappe.db.commit()
            success += 1
        except Exception as e:
            frappe.db.rollback()
            print(f"    ⚠️  Skipped row ({row.get('company_name', '?')}): {e}")
    print(f"  Row-by-row: {success}/{len(chunk_rows)} inserted")
    return success > 0


def build_row(row):
    return {
        "name":                               row["company_name"],
        "company_name":                       row.get("company_name"),
        "business_type":                      row.get("business_type"),
        "other_business_type":                row.get("other_business_type"),
        "gst_number":                         row.get("gst_number"),
        "industry_sector":                    row.get("industry_sector"),
        "other_industry_sector":              row.get("other_industry_sector"),
        "about":                              row.get("about"),
        "company_size":                       row.get("company_size"),
        "link_of_company":                    row.get("link_of_company"),
        "email":                              row.get("email"),
        "country":                            row.get("country"),
        "state":                              row.get("state"),
        "district":                           row.get("district"),
        "tahsil":                             row.get("tahsil"),
        "city":                               row.get("city"),
        "address_line_1":                     row.get("address_line_1"),
        "address_line_2":                     row.get("address_line_2"),
        "pincode":                            str(row.get("pincode")) if row.get("pincode") else None,
        "latitude":                           row.get("latitude"),
        "longitude":                          row.get("longitude"),
        "map_link":                           row.get("map_link"),
        "employee_head_count":                str(row.get("employee_head_count")) if row.get("employee_head_count") else None,
        "internship_per_year":                str(row.get("internship_per_year")) if row.get("internship_per_year") else None,
        "turn_over_in_cr":                    str(row.get("turn_over_in_cr")) if row.get("turn_over_in_cr") else None,
        "company_website":                    row.get("company_website"),
        "average_fresher_recruited_per_year": str(row.get("average_fresher_recruited_per_year")) if row.get("average_fresher_recruited_per_year") else None,
        "status":                             row.get("status") or "Active",
        "approved_status":                    row.get("approved_status"),
        "headquarters":                       row.get("headquarters"),
        "cin":                                row.get("cin"),
        "terms_and_conditions":               row.get("terms_and_conditions"),
        "docstatus":                          0,
        "owner":                              "Administrator",
        "modified_by":                        "Administrator",
    }


def run():
    files = sorted(glob.glob("/home/dev/maharashtra_industries_*.xlsx"))

    if not files:
        print("No files found. Update the glob path.")
        return

    for file in files:
        print(f"\n📂 Processing: {file}")
        try:
            df = pd.read_excel(file)
        except Exception as e:
            print(f"❌ Could not read file: {e}")
            continue

        # Clean NaN → None
        df = df.where(pd.notnull(df), None)

        total = len(df)
        all_rows = [build_row(row) for _, row in df.iterrows()]

        inserted = 0
        failed_chunks = 0

        # Split into chunks
        chunks = [all_rows[i:i + CHUNK_SIZE] for i in range(0, total, CHUNK_SIZE)]
        total_chunks = len(chunks)

        for idx, chunk in enumerate(chunks, 1):
            success = insert_chunk_with_retry(chunk)
            if success:
                inserted += len(chunk)
            else:
                failed_chunks += 1

            # Progress every 10 chunks
            if idx % 10 == 0 or idx == total_chunks:
                pct = round(idx / total_chunks * 100)
                print(f"  Progress: {idx}/{total_chunks} chunks ({pct}%) — {inserted} rows inserted")

        print(f"\n✅ File done: {file}")
        print(f"   Total rows : {total}")
        print(f"   Inserted   : {inserted}")
        print(f"   Failed chks: {failed_chunks}")