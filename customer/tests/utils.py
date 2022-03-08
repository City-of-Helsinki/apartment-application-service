from customer.models import Customer


def assert_customer_list_match_data(customer: Customer, data: dict):
    assert data["id"] == customer.id
    assert data["primary_first_name"] == customer.primary_profile.first_name
    assert data["primary_last_name"] == customer.primary_profile.last_name
    assert data["primary_email"] == customer.primary_profile.email
    assert data["primary_phone_number"] == customer.primary_profile.phone_number
    if customer.secondary_profile:
        assert data["secondary_first_name"] == customer.secondary_profile.first_name
        assert data["secondary_last_name"] == customer.secondary_profile.last_name
