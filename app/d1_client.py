import json
import urllib.request
import urllib.error
from typing import List, Dict, Any, Optional
from .config import settings

class CloudflareD1Client:
    """
    Client for interacting directly with Cloudflare D1 SQLite database via Cloudflare REST API.
    """
    def __init__(self, account_id: Optional[str] = None, database_id: Optional[str] = None, api_token: Optional[str] = None):
        self.account_id = account_id or getattr(settings, "CLOUDFLARE_ACCOUNT_ID", None) or getattr(settings, "R2_ACCOUNT_ID", None)
        self.database_id = database_id or getattr(settings, "CLOUDFLARE_D1_DATABASE_ID", None)
        self.api_token = api_token or getattr(settings, "CLOUDFLARE_API_TOKEN", None)

    def is_configured(self) -> bool:
        return bool(self.account_id and self.database_id and self.api_token)

    def query(self, sql: str, params: Optional[List[Any]] = None) -> Dict[str, Any]:
        if not self.is_configured():
            raise ValueError("Cloudflare D1 credentials are not fully set in .env")

        url = f"https://api.cloudflare.com/client/v4/accounts/{self.account_id}/d1/database/{self.database_id}/query"
        headers = {
            "Authorization": f"Bearer {self.api_token}",
            "Content-Type": "application/json"
        }
        
        payload = {"sql": sql}
        if params:
            payload["params"] = params

        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers=headers, method="POST")

        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                result = json.loads(resp.read().decode("utf-8"))
                if result.get("success"):
                    return result.get("result", [{}])[0]
                else:
                    errors = result.get("errors", [])
                    raise RuntimeError(f"Cloudflare D1 Error: {errors}")
        except urllib.error.HTTPError as e:
            err_body = e.read().decode("utf-8")
            raise RuntimeError(f"Cloudflare D1 HTTP {e.code}: {err_body}")

def execute_d1_query(sql: str, params: Optional[List[Any]] = None) -> Dict[str, Any]:
    client = CloudflareD1Client()
    return client.query(sql, params)
