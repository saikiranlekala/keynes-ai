from fastapi import FastAPI
import boto3
import time
from datetime import date, timedelta

app = FastAPI()

athena = boto3.client(
    "athena",
    region_name="us-east-1"
)

DATABASE = "domo_reports_s3"
TABLE = "client_reporting_date_dataset"
OUTPUT_BUCKET = "s3://keynes-athena-results-slekkala/"


# ATHENA QUERY EXECUTOR

def run_athena_query(query):
    response = athena.start_query_execution(
        QueryString=query,
        QueryExecutionContext={"Database": DATABASE},
        ResultConfiguration={"OutputLocation": OUTPUT_BUCKET}
    )
    query_execution_id = response["QueryExecutionId"]
    while True:
        status = athena.get_query_execution(QueryExecutionId=query_execution_id)
        state = status["QueryExecution"]["Status"]["State"]
        if state == "SUCCEEDED":
            break
        if state in ["FAILED", "CANCELLED"]:
            return []
        time.sleep(2)
    results = athena.get_query_results(QueryExecutionId=query_execution_id)
    rows = results["ResultSet"]["Rows"]
    headers = [col.get("VarCharValue", "") for col in rows[0]["Data"]]
    parsed_rows = []
    for row in rows[1:]:
        values = [col.get("VarCharValue", "") for col in row["Data"]]
        parsed_rows.append(dict(zip(headers, values)))
    return parsed_rows


# HOME

@app.get("/")
def home():
    return {"message": "Keynes Analytics API Running"}


# GET ADVERTISERS

@app.get("/advertisers")
def get_advertisers():
    query = f"SELECT DISTINCT advertiser FROM {TABLE} ORDER BY advertiser"
    data = run_athena_query(query)
    advertisers = [row["advertiser"] for row in data if row.get("advertiser")]
    return {"total_advertisers": len(advertisers), "advertisers": advertisers}


# CURRENT DATE + PRE-COMPUTED RANGES

@app.get("/current-date")
def current_date():
    today = date.today()
    this_week_start = today - timedelta(days=today.weekday())
    last_week_start = this_week_start - timedelta(days=7)
    last_week_end = this_week_start - timedelta(days=1)
    this_month_start = today.replace(day=1)
    last_month_end = this_month_start - timedelta(days=1)
    last_month_start = last_month_end.replace(day=1)
    last_month_same_end = last_month_start + timedelta(days=(today.day - 1))
    return {
        "today": str(today),
        "this_week":      {"start": str(this_week_start),            "end": str(today)},
        "last_week":      {"start": str(last_week_start),            "end": str(last_week_end)},
        "this_month":     {"start": str(this_month_start),           "end": str(today)},
        "last_month_mtd": {"start": str(last_month_start),           "end": str(last_month_same_end)},
        "last_30_days":   {"start": str(today - timedelta(days=30)), "end": str(today)},
        "last_7_days":    {"start": str(today - timedelta(days=7)),  "end": str(today)}
    }


# RAW ATHENA QUERY — called directly by Claude via MCP

@app.post("/query")
def query(payload: dict):
    sql = payload.get("sql")
    if not sql:
        return {"error": "No SQL provided"}
    data = run_athena_query(sql)
    return {"results": data}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)