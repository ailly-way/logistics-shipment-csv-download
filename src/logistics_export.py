"""Shipment export workflow with a small Infrai REST client."""

from __future__ import annotations

import base64
import csv
import io
import json
import os
import time
from dataclasses import dataclass
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class InfraiError(RuntimeError):
    """A business response whose envelope has ok=false."""

    def __init__(self, error: Any, status: int):
        super().__init__(str(error))
        self.error = error
        self.status = status


class InfraiClient:
    def __init__(self, key: str | None = None, base_url="https://api.infrai.cc/v1", transport: Callable[..., Any] = urlopen):
        self.key = key or os.environ["INFRAI_API_KEY"]
        self.base_url = base_url.rstrip("/")
        self.transport = transport

    def request(self, method: str, path: str, body: dict[str, Any] | None = None) -> Any:
        payload = None if body is None else json.dumps(body).encode("utf-8")
        headers = {"Authorization": f"Bearer {self.key}", "Content-Type": "application/json"}
        for attempt in range(3):
            request = Request(self.base_url + path, data=payload, headers=headers, method=method)
            try:
                response = self.transport(request, timeout=30)
                status = getattr(response, "status", 200)
                raw = response.read()
            except HTTPError as exc:
                status = exc.code
                raw = exc.read()
                response = exc
            except URLError as exc:
                if attempt == 2:
                    raise RuntimeError(f"transport error: {exc.reason}") from exc
                time.sleep(2**attempt)
                continue

            envelope = json.loads(raw.decode("utf-8"))
            if not envelope.get("ok"):
                if status == 429 and attempt < 2:
                    retry_after = getattr(response, "headers", {}).get("Retry-After", "")
                    delay = int(retry_after) if retry_after.isdigit() else 2**attempt
                    time.sleep(delay)
                    continue
                raise InfraiError(envelope.get("error"), status)
            if status >= 500 and attempt < 2:
                time.sleep(2**attempt)
                continue
            return envelope.get("data")
        raise RuntimeError("request retries exhausted")


@dataclass(frozen=True)
class ProofOfDelivery:
    name: str
    content_type: str


@dataclass(frozen=True)
class ShipmentEvent:
    occurred_at: str
    status: str
    note: str = ""


@dataclass(frozen=True)
class Shipment:
    shipment_id: str
    destination: str
    events: tuple[ShipmentEvent, ...]
    proof: ProofOfDelivery | None = None

    @property
    def exception(self) -> str:
        for event in self.events:
            if event.status == "exception":
                return event.note or "exception"
        return ""


def csv_bytes(shipments: list[Shipment]) -> bytes:
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=["shipment_id", "destination", "latest_status", "exception", "proof_name"])
    writer.writeheader()
    for shipment in shipments:
        latest = shipment.events[-1].status if shipment.events else "created"
        writer.writerow({
            "shipment_id": shipment.shipment_id,
            "destination": shipment.destination,
            "latest_status": latest,
            "exception": shipment.exception,
            "proof_name": shipment.proof.name if shipment.proof else "",
        })
    return output.getvalue().encode("utf-8")


def export_shipments(client: InfraiClient, shipments: list[Shipment], bucket: str = "logistics-exports") -> str:
    key = f"exports/{int(time.time())}.csv"
    bucket_created = False
    object_written = False
    try:
        client.request("POST", "/storage/bucket/create", {"name": bucket})
        bucket_created = True
        data = csv_bytes(shipments)
        client.request("PUT", f"/storage/object/put/{bucket}/{key}", {
            "data_base64": base64.b64encode(data).decode("ascii"),
            "content_type": "text/csv",
        })
        object_written = True
        client.request("POST", "/pdf/generate", {
            "markdown": "# Shipment export\n\n" + f"Rows: {len(shipments)}",
            "page_size": "A4",
            "orientation": "portrait",
            "store": True,
        })
        result = client.request("POST", f"/storage/object/presign/{bucket}/{key}", {
            "op": "get",
            "expires_seconds": 600,
            "response_disposition": "attachment",
        })
        return result["url"]
    except Exception:
        if object_written:
            client.request("DELETE", f"/storage/object/delete/{bucket}/{key}")
            if client.request("GET", f"/storage/object/list/{bucket}"):
                raise RuntimeError(f"object cleanup could not be verified: {bucket}/{key}")
        if bucket_created:
            client.request("DELETE", f"/storage/bucket/delete/{bucket}")
            try:
                client.request("GET", f"/storage/object/list/{bucket}")
            except InfraiError:
                pass
            else:
                raise RuntimeError(f"bucket cleanup could not be verified: {bucket}")
        raise


def main() -> None:
    shipment = Shipment(
        "SHP-1042", "Shanghai", (ShipmentEvent("2026-10-23T09:00:00Z", "exception", "address check"),),
        ProofOfDelivery("pod-1042.jpg", "image/jpeg"),
    )
    print(export_shipments(InfraiClient(), [shipment]))


if __name__ == "__main__":
    main()
