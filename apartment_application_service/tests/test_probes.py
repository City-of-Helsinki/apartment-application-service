def test_liveness_probe(client):
    response = client.get("/healthz")
    assert response.status_code == 200


def test_readiness_probe(client):
    response = client.get("/readiness")
    assert response.status_code == 200
