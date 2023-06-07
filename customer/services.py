from datetime import date
from django.db import transaction
from typing import Optional, TypedDict

from customer.models import Customer
from users.models import Profile


class SecondaryProfileData(TypedDict):
    first_name: str
    last_name: str
    email: str
    phone_number: str
    street_address: str
    city: str
    postal_code: str
    contact_language: Optional[str]
    date_of_birth: date
    ssn_suffix: str


@transaction.atomic()
def get_or_create_customer_from_profiles(
    primary_profile: Profile,
    secondary_profile_data: SecondaryProfileData = None,
    has_children: bool = None,
) -> Customer:
    if not secondary_profile_data:
        # this is a single person Customer
        customer = Customer.objects.get_or_create(
            primary_profile=primary_profile,
            secondary_profile=None,
        )[0]
        customer.has_children = has_children
        customer.save()
        return customer

    secondary_profile_ssn = (
        secondary_profile_data["date_of_birth"].strftime("%d%m%y")
        + secondary_profile_data["ssn_suffix"]
    )

    try:
        # try to find a match from the primary profile's Customers using the secondary
        # profile's SSN
        customer = Customer.objects.get(
            primary_profile=primary_profile,
            secondary_profile__national_identification_number=secondary_profile_ssn,
        )
        customer.has_children = has_children
        customer.save()
        return customer
    except Customer.DoesNotExist:
        pass

    # there is no matching Customer found, create a new one
    secondary_profile = Profile.objects.create(
        first_name=secondary_profile_data["first_name"],
        last_name=secondary_profile_data["last_name"],
        email=secondary_profile_data["email"],
        phone_number=secondary_profile_data["phone_number"],
        street_address=secondary_profile_data["street_address"],
        city=secondary_profile_data["city"],
        postal_code=secondary_profile_data["postal_code"],
        # if there is no contact language for the secondary profile, use the contact
        # language of the primary profile
        contact_language=secondary_profile_data.get("contact_language")
        or primary_profile.contact_language,
        date_of_birth=secondary_profile_data["date_of_birth"],
        national_identification_number=secondary_profile_ssn,
    )
    customer = Customer.objects.create(
        primary_profile=primary_profile,
        secondary_profile=secondary_profile,
        has_children=has_children,
    )
    return customer
