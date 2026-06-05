import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

from criticalasset_client import get_access_token, fetch_work_orders


def main():
    print("Authenticating with CriticalAsset...")
    try:
        token_data = get_access_token()
    except Exception as e:
        print(f"Auth failed: {e}")
        sys.exit(1)

    access_token = token_data["accessToken"]
    print("Token ok")
    print(f"  expires_in : {token_data.get('expiresIn')} seconds")
    print(f"  scope      : {token_data.get('scope')}")
    print(f"  token_type : {token_data.get('tokenType')}")

    print("\nFetching work orders (limit=25)...")
    try:
        result = fetch_work_orders(limit=25, token=access_token)
    except Exception as e:
        print(f"Work order fetch failed: {e}")
        sys.exit(1)

    wo_data = result.get("workOrders", {})
    total = wo_data.get("totalCount", 0)
    nodes = wo_data.get("nodes", [])

    print(f"Total work orders: {total}")
    print(f"Returned in this page: {len(nodes)}")

    print("\nFirst 5 work orders:")
    for wo in nodes[:5]:
        stage = (wo.get("workOrderStage") or {}).get("name", "—")
        priority = wo.get("executionPriority", "—")
        loc = (wo.get("location") or {}).get("locationName", "—")
        print(f"  [{wo.get('id')}] {wo.get('title', '(no title)')}  |  stage: {stage}  |  priority: {priority}  |  location: {loc}")


if __name__ == "__main__":
    main()
