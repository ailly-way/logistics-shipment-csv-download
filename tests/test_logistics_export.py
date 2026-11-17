from src.logistics_export import ProofOfDelivery, Shipment, ShipmentEvent, csv_bytes


def test_exception_event_is_visible_in_creator_export():
    shipment = Shipment(
        "SHP-1042", "Shanghai", (ShipmentEvent("2026-10-23T09:00:00Z", "exception", "address check"),),
        ProofOfDelivery("pod-1042.jpg", "image/jpeg"),
    )

    text = csv_bytes([shipment]).decode("utf-8")

    assert "SHP-1042,Shanghai,exception,address check,pod-1042.jpg" in text
