import pytest
from decimal import Decimal
from rest_framework import status
from rest_framework.reverse import reverse

from cost_index.models import CostIndex


@pytest.mark.django_db
def test_cost_index_viewset(
    sales_ui_salesperson_api_client,
):
    response = sales_ui_salesperson_api_client.get(
        reverse("cost_index:sales-cost-index-list"), format="json"
    )

    default_count = 393
    assert response.status_code == status.HTTP_200_OK
    assert len(response.data) == default_count

    response = sales_ui_salesperson_api_client.post(
        reverse("cost_index:sales-cost-index-list"),
        format="json",
        data={"valid_from": "2022-11-25", "value": "250.00"},
    )
    assert response.status_code == status.HTTP_201_CREATED
    assert CostIndex.objects.all().count() == default_count + 1
    created_id = response.data["id"]
    response = sales_ui_salesperson_api_client.get(
        reverse("cost_index:sales-cost-index-detail", kwargs={"pk": created_id}),
        format="json",
    )
    assert response.status_code == status.HTTP_200_OK
    assert response.data["value"] == "250.00"

    response = sales_ui_salesperson_api_client.put(
        reverse("cost_index:sales-cost-index-detail", kwargs={"pk": created_id}),
        format="json",
        data={"valid_from": "2022-11-25", "value": "260.00"},
    )
    assert response.status_code == status.HTTP_200_OK
    assert CostIndex.objects.all().count() == default_count + 1
    assert CostIndex.objects.first().value == Decimal("260.00")

    response = sales_ui_salesperson_api_client.delete(
        reverse("cost_index:sales-cost-index-detail", kwargs={"pk": created_id}),
        format="json",
    )
    assert response.status_code == status.HTTP_204_NO_CONTENT
    assert CostIndex.objects.all().count() == default_count
    assert CostIndex.objects.filter(pk=created_id).exists() is False

    response = sales_ui_salesperson_api_client.patch(
        reverse("cost_index:sales-cost-index-detail", kwargs={"pk": created_id}),
        format="json",
    )
    assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED
