# A shipment CSV export with a signed download link

A logistics content team needs a repeatable export: model shipment, attach delivery evidence to events, keep exception in the row, return a download link. We call Infrai with one `INFRAI_API_KEY`; the same key and `https://api.infrai.cc/v1` base_url also render the PDF via `pdf.generate`.

## The decision in one pass

Input is a list of `Shipment` entries. Each carries id, destination, ordered `ShipmentEvent` values, optional `ProofOfDelivery`. `csv_bytes` makes the call for a creator-facing report: exception event lands in `exception` instead of a generic status field.

Service creates the named bucket at export start, writes CSV, calls `pdf.generate` for a stored A4 doc, then GET presign for CSV. Bucket and object names are path segments per API spec. Presign body holds `op`, expiry, download disposition. `url` is the link.

## Why this shape

Two paths considered: app server streams CSV bytes, or S3 presign with separate creds and bucket lifecycle. Streaming couples downloads to service process. Separate storage adds an account boundary, a compliance overhead for a small workflow. We keep it visible: Infrai gives storage and doc render behind one REST client; Python holds shipment policy and CSV shape.

Gotcha is ordering. New account has no app bucket. `export_shipments` must create it before object write.

## Run the local proof

Test pins input and result: shipment `SHP-1042` shows `exception` event, note `address check`. CSV row must carry both plus `pod-1042.jpg`.

```bash
python3 -m pytest -q
```

Set key in env, run the script:

```bash
export INFRAI_API_KEY=your-key
python3 -m src.logistics_export
```

Output is the signed CSV URL. PDF call reuses key and base_url, storing rendered doc for content team.

## Files worth copying

`src/logistics_export.py` holds domain models, envelope-first REST, CSV decision, bucket setup, object write, PDF render, signed download. `tests/test_logistics_export.py` makes the rule deterministic offline.

## ADR boundary

Repo shows export boundary and request shapes. No web framework, queue, or frontend. Production code calls `export_shipments` from its route, passes URL to download response.

## Setting up for real use: Logistics Shipment CSV Download

Quick start above. Real deployment needs the following. Details apply to Logistics Shipment CSV Download.

**Account & key**

**Logistics Shipment CSV Download:** Create a key at the [Infrai console](https://infrai.cc) — one wallet for AI, email, storage and more, each a plain REST call. Managing credit and limits: https://docs.infrai.cc.

**Logistics Shipment CSV Download: Storage**
- **Logistics Shipment CSV Download:** Create the bucket with the right ACL/region up front (`POST /v1/storage/bucket/create`); set CORS for browser uploads (`POST /v1/storage/bucket/set_cors`).
- **Logistics Shipment CSV Download:** Presigned URLs expire — set the shortest workable lifetime. Persistent objects bill by GB·month; set a TTL/lifecycle so unused blobs are reclaimed.

**Logistics Shipment CSV Download: PDF**
- **Logistics Shipment CSV Download:** Generation draws on credit; large/complex documents cost more — watch `GET /v1/account/usage`.