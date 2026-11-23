import csv, io
from src.db import save_job

def import_jobs_csv(uploaded_file):
    content = uploaded_file.getvalue().decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(content))
    count = 0
    for row in reader:
        if row.get("title") and row.get("company") and row.get("jd"):
            save_job(row["title"], row["company"], row.get("location",""),
                     row.get("url",""), row.get("source","CSV"), row["jd"])
            count += 1
    return count
