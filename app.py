from fastapi import FastAPI
import boto3
import time
import os
import json
from datetime import date, timedelta, datetime

app = FastAPI()

athena = boto3.client(
    "athena",
    region_name="us-east-1"
)

DATABASE = "domo_reports_s3"

TABLE = "client_reporting_date_dataset"

OUTPUT_BUCKET = "s3://keynes-athena-results-slekkala/"

# CREATE LOGS DIRECTORY

os.makedirs("logs", exist_ok=True)


# ATHENA QUERY EXECUTOR WITH LOGGING

def run_athena_query(query):

    start_time = time.time()

    response = athena.start_query_execution(
        QueryString=query,
        QueryExecutionContext={
            "Database": DATABASE
        },
        ResultConfiguration={
            "OutputLocation": OUTPUT_BUCKET
        }
    )

    query_execution_id = response["QueryExecutionId"]

    while True:

        status = athena.get_query_execution(
            QueryExecutionId=query_execution_id
        )

        state = status["QueryExecution"]["Status"]["State"]

        if state == "SUCCEEDED":
            break

        if state in ["FAILED", "CANCELLED"]:

            execution_time = round(
                time.time() - start_time,
                2
            )

            log_data = {
                "timestamp": str(datetime.utcnow()),
                "query": query,
                "execution_time_seconds": execution_time,
                "status": state,
                "query_execution_id": query_execution_id
            }

            with open("logs/query_logs.txt", "a") as f:
                f.write(json.dumps(log_data) + "\n")

            return []

        time.sleep(2)

    results = athena.get_query_results(
        QueryExecutionId=query_execution_id
    )

    rows = results["ResultSet"]["Rows"]

    headers = [
        col.get("VarCharValue", "")
        for col in rows[0]["Data"]
    ]

    parsed_rows = []

    for row in rows[1:]:

        values = [
            col.get("VarCharValue", "")
            for col in row["Data"]
        ]

        parsed_rows.append(
            dict(zip(headers, values))
        )

    execution_time = round(
        time.time() - start_time,
        2
    )

    log_data = {
        "timestamp": str(datetime.utcnow()),
        "query": query,
        "execution_time_seconds": execution_time,
        "status": "SUCCEEDED",
        "query_execution_id": query_execution_id,
        "rows_returned": len(parsed_rows)
    }

    # SAVE ALL QUERY LOGS

    with open("logs/query_logs.txt", "a") as f:
        f.write(json.dumps(log_data) + "\n")

    # SAVE SLOW QUERIES

    if execution_time > 5:

        with open("logs/slow_queries.txt", "a") as f:
            f.write(json.dumps(log_data) + "\n")

    return parsed_rows


# HOME

@app.get("/")
def home():

    return {
        "message": "Keynes Analytics API Running"
    }


# CURRENT DATE + PRE-COMPUTED RANGES

@app.get("/current-date")
def current_date():

    today = date.today()

    this_week_start = today - timedelta(
        days=today.weekday()
    )

    last_week_start = this_week_start - timedelta(days=7)

    last_week_end = this_week_start - timedelta(days=1)

    this_month_start = today.replace(day=1)

    last_month_end = this_month_start - timedelta(days=1)

    last_month_start = last_month_end.replace(day=1)

    last_month_same_end = last_month_start + timedelta(
        days=(today.day - 1)
    )

    return {

        "today": str(today),

        "this_week": {
            "start": str(this_week_start),
            "end": str(today)
        },

        "last_week": {
            "start": str(last_week_start),
            "end": str(last_week_end)
        },

        "this_month": {
            "start": str(this_month_start),
            "end": str(today)
        },

        "last_month_mtd": {
            "start": str(last_month_start),
            "end": str(last_month_same_end)
        },

        "last_30_days": {
            "start": str(today - timedelta(days=30)),
            "end": str(today)
        },

        "last_7_days": {
            "start": str(today - timedelta(days=7)),
            "end": str(today)
        }
    }


# RAW ATHENA QUERY EXECUTION

@app.post("/query")
def query(payload: dict):

    sql = payload.get("sql")

    if not sql:

        return {
            "error": "No SQL provided"
        }

    data = run_athena_query(sql)

    return {
        "results": data
    }


# QUERY LOG VIEWER

@app.get("/query-logs")
def query_logs():

    logs = []

    try:

        with open("logs/query_logs.txt", "r") as f:

            for line in f.readlines()[-50:]:
                logs.append(json.loads(line))

    except:

        return {
            "message": "No logs found"
        }

    return {
        "total_logs": len(logs),
        "logs": logs
    }


# QUERY STATS

@app.get("/query-stats")
def query_stats():

    logs = []

    try:

        with open("logs/query_logs.txt", "r") as f:

            for line in f:
                logs.append(json.loads(line))

    except:

        return {
            "message": "No logs found"
        }

    if not logs:

        return {
            "message": "No query data available"
        }

    total_queries = len(logs)

    successful_queries = len([
        log for log in logs
        if log.get("status") == "SUCCEEDED"
    ])

    failed_queries = total_queries - successful_queries

    execution_times = [
        log.get("execution_time_seconds", 0)
        for log in logs
    ]

    avg_execution_time = round(
        sum(execution_times) / len(execution_times),
        2
    )

    max_execution_time = max(execution_times)

    return {

        "total_queries": total_queries,

        "successful_queries": successful_queries,

        "failed_queries": failed_queries,

        "avg_execution_time_seconds": avg_execution_time,

        "max_execution_time_seconds": max_execution_time
    }


# SLOW QUERY VIEWER

@app.get("/slow-queries")
def slow_queries():

    logs = []

    try:

        with open("logs/slow_queries.txt", "r") as f:

            for line in f.readlines()[-50:]:
                logs.append(json.loads(line))

    except:

        return {
            "message": "No slow queries found"
        }

    return {
        "total_slow_queries": len(logs),
        "slow_queries": logs
    }


if __name__ == "__main__":

    import uvicorn

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000
    )