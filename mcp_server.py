from fastmcp import FastMCP
import requests

BASE_URL = "http://localhost:8000"
mcp = FastMCP("Keynes Advertiser Intelligence")


@mcp.tool()
def get_current_date():
    """
    Returns today's real date and pre-computed date ranges.
    ALWAYS call this first when the user uses any relative date term:
    'this month', 'last month', 'this week', 'last week', 'today',
    'yesterday', 'recent', 'last 7 days', 'last 30 days'.
    Never guess or assume dates from memory.
    """
    response = requests.get(f"{BASE_URL}/current-date")
    return response.json()


@mcp.tool()
def query_athena(sql: str):
    """
    Executes a SQL query against Athena and returns results.
    Pick the correct table based on the question:
    - client_reporting_date_dataset                  -> daily trends, spend, ROAS, CTR, device, browser, creative
    - client_reporting_geo_dataset                   -> geography, state, region, DMA, country
    - client_reporting_network_dataset_myreports     -> network, site, publisher, supply vendor
    - client_reporting_hour_dataset                  -> hour of day, daypart, day of week

    CRITICAL DATE FILTER RULE:
    The date column is of type DATE. Always filter using:
        WHERE date BETWEEN DATE 'YYYY-MM-DD' AND DATE 'YYYY-MM-DD'
    The DATE keyword before the string is REQUIRED for Athena to cast correctly.
    Example: WHERE date BETWEEN DATE '2026-05-01' AND DATE '2026-05-25'
    Never use string comparison or CAST() for date filtering — always use DATE 'YYYY-MM-DD'.
    """
    response = requests.post(f"{BASE_URL}/query", json={"sql": sql})
    return response.json()


if __name__ == "__main__":
    mcp.run(
        transport="sse",
        host="0.0.0.0",
        port=9000
    )