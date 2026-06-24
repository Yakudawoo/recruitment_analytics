import os
from typing import Any

import requests
from dotenv import load_dotenv


load_dotenv()


class GreenhouseApiClient:
    """
    Client used to consume the Mock Greenhouse API.

    In production, this layer would be replaced by a real Greenhouse API client
    configured with Greenhouse authentication, pagination, retries and rate-limit handling.
    """

    def __init__(self, base_url: str | None = None):
        self.base_url = (base_url or os.getenv("MOCK_GREENHOUSE_BASE_URL")).rstrip("/")

        if not self.base_url:
            raise RuntimeError("Missing MOCK_GREENHOUSE_BASE_URL environment variable")

    def get_paginated_resource(
        self,
        endpoint: str,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        all_records = []
        offset = 0

        while True:
            response = requests.get(
                f"{self.base_url}/{endpoint.lstrip('/')}",
                params={
                    "limit": limit,
                    "offset": offset,
                },
                timeout=10,
            )

            response.raise_for_status()

            payload = response.json()
            records = payload.get("data", [])

            all_records.extend(records)

            total_count = payload.get("count", len(all_records))
            offset += limit

            if offset >= total_count:
                break

        return all_records

    def health(self) -> dict[str, Any]:
        response = requests.get(f"{self.base_url}/health", timeout=10)
        response.raise_for_status()
        return response.json()

    def get_jobs(self) -> list[dict[str, Any]]:
        return self.get_paginated_resource("/jobs")

    def get_openings(self) -> list[dict[str, Any]]:
        return self.get_paginated_resource("/openings")

    def get_candidates(self) -> list[dict[str, Any]]:
        return self.get_paginated_resource("/candidates")

    def get_applications(self) -> list[dict[str, Any]]:
        return self.get_paginated_resource("/applications")

    def get_offers(self) -> list[dict[str, Any]]:
        return self.get_paginated_resource("/offers")

    def get_application_events(self) -> list[dict[str, Any]]:
        return self.get_paginated_resource("/application-events")
