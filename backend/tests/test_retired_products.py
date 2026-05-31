from fastapi.testclient import TestClient


def test_retired_product_detail_is_404(api_client: TestClient) -> None:
    r = api_client.get("/knowledge/products/clo-enjoyable-life-income-plan")
    assert r.status_code == 404
