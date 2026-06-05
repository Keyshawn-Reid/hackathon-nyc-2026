import os
import requests
from dotenv import load_dotenv

load_dotenv()

API_URL = os.getenv("CA_API_URL", "").rstrip("/")
CLIENT_ID = os.getenv("CA_CLIENT_ID", "")
CLIENT_SECRET = os.getenv("CA_CLIENT_SECRET", "")
SCOPES = os.getenv("CA_SCOPES", "workorders:read assets:read locations:read")

_TOKEN_MUTATION = """
mutation ApplicationToken($input: ApplicationClientCredentialsInput!) {
  applicationClientCredentialsToken(input: $input) {
    accessToken
    refreshToken
    tokenType
    expiresIn
    scope
  }
}
"""

_WORK_ORDERS_QUERY = """
query FetchWorkOrders($limit: Int!) {
  workOrders(limit: $limit) {
    totalCount
    nodes {
      id
      title
      description
      severity
      executionPriority
      startDate
      endDate
      createdAt
      workOrderStage { id name color_code }
      location { id locationName address city state }
    }
  }
}
"""


def get_access_token() -> dict:
    payload = {
        "query": _TOKEN_MUTATION,
        "variables": {
            "input": {
                "clientId": CLIENT_ID,
                "clientSecret": CLIENT_SECRET,
                "scope": SCOPES,
            }
        },
    }
    resp = requests.post(API_URL, json=payload, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    if "errors" in data:
        raise RuntimeError(f"GraphQL auth error: {data['errors']}")
    return data["data"]["applicationClientCredentialsToken"]


def graphql_request(query: str, variables: dict = None, token: str = None) -> dict:
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    payload = {"query": query}
    if variables:
        payload["variables"] = variables
    resp = requests.post(API_URL, json=payload, headers=headers, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    if "errors" in data:
        raise RuntimeError(f"GraphQL error: {data['errors']}")
    return data["data"]


def fetch_work_orders(limit: int = 25, token: str = None) -> dict:
    return graphql_request(_WORK_ORDERS_QUERY, variables={"limit": limit}, token=token)
