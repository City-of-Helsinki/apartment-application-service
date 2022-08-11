# flake8: noqa E501
import datetime
from dateutil.tz import tzoffset

apartment_mock_data = {
    "_language": "fi",
    "additional_information": "Jotain tekstiä tähän",
    "apartment_address": "Hasontestauskatu 33 A5",
    "apartment_holding_type": "Asumisoikeushuoneisto",
    "apartment_number": "A5",
    "apartment_published": True,
    "apartment_state_of_sale": "OPEN_FOR_APPLICATIONS",
    "apartment_structure": "5h+k+s",
    "application_url": "http://example.com/application/add/haso/641",
    "debt_free_sales_price": 0,
    "floor": 5,
    "floor_max": 5,
    "has_apartment_sauna": True,
    "has_balcony": True,
    "has_terrace": True,
    "has_yard": False,
    "housing_company_fee": 0,
    "living_area": 99.0,
    "loan_share": 0,
    "maintenance_fee": 0,
    "nid": 646,
    "parking_fee": 2000,
    "parking_fee_explanation": "Parkkipaikka varattava etukäteen",
    "price_m2": 0,
    "project_acc_financeofficer": "Antti Asia-Mies",
    "project_apartment_count": 10,
    "project_application_end_time": datetime.datetime(
        2022, 2, 28, 6, 35, 42, tzinfo=tzoffset(None, 7200)
    ),
    "project_application_start_time": datetime.datetime(
        2022, 2, 2, 15, 0, tzinfo=tzoffset(None, 7200)
    ),
    "project_archived": False,
    "project_barred_bank_account": "FI21 1234 5600 0007 85",
    "project_building_type": "BLOCK_OF_FLATS",
    "project_city": "Helsinki",
    "project_constructor": "Reiska Rakentaja",
    "project_contract_actual_application_end_date": "2022-02-22T00:00:00+02:00",
    "project_contract_apartment_completion_selection_1": True,
    "project_contract_apartment_completion_selection_1_date": "2020-02-20T00:00:00+02:00",
    "project_contract_apartment_completion_selection_2": True,
    "project_contract_apartment_completion_selection_2_end": datetime.datetime(
        2022, 3, 3, 0, 0, tzinfo=tzoffset(None, 7200)
    ),
    "project_contract_apartment_completion_selection_2_start": datetime.datetime(
        2022, 1, 1, 0, 0, tzinfo=tzoffset(None, 7200)
    ),
    "project_contract_apartment_completion_selection_3": True,
    "project_contract_apartment_completion_selection_3_date": "2022-05-05T00:00:00+03:00",
    "project_contract_article_of_association": "Pykälä",
    "project_contract_bill_of_sale_terms": "muuta tietoa asumisoikeussopimus välilehden alla",
    "project_contract_building_collateral_release_date": "2022-02-20T00:00:00+02:00",
    "project_contract_business_id": "X233223",
    "project_contract_collateral_amount": 100000,
    "project_contract_collateral_amount_fixed": False,
    "project_contract_collateral_type": "Vakuutus tyyppi tähän",
    "project_contract_construction_end_date": "2022-02-22T00:00:00+02:00",
    "project_contract_construction_permit_requested": "2020-02-20T00:00:00+02:00",
    "project_contract_construction_phase_meaning": "ALL",
    "project_contract_construction_start_date": "2020-02-20T00:00:00+02:00",
    "project_contract_customer_document_handover": "Jotain asiakirjoja mitä luovutetaan asiakkaalle sopumuksenteossa",
    "project_contract_default_collateral": "Surituskyvyttömyysvakuus tulee tänne näin",
    "project_contract_depositary": "Säilyttäjä tähän",
    "project_contract_estimated_handover_date_end": "2020-03-03T00:00:00+02:00",
    "project_contract_estimated_handover_date_start": "2020-02-02T00:00:00+02:00",
    "project_contract_location_block": "Sijaintikorttilin tekstikenttä tässä",
    "project_contract_material_selection_date": "2020-05-20T00:00:00+03:00",
    "project_contract_material_selection_description": "Materiaalivalintoja täsmennetään joiltain osin",
    "project_contract_material_selection_later": True,
    "project_contract_other_terms": "Jotain ehtoja kauppakirjan tietojen alla",
    "project_contract_plot": "ownership",
    "project_contract_project_id": "k11nt3ist0tunnu5",
    "project_contract_repository": "Säilytyspaikka tähän",
    "project_contract_right_of_occupancy_payment_verification": "Asumisoikeusmaksun tarkistuksesta lätinää tähän",
    "project_contract_rs_bank": "är äs pankki",
    "project_contract_transfer_restriction": True,
    "project_contract_usage_fees": "Niitä maksellaan kun joudetaan",
    "project_contract_warranty_deposit_release_date": "2022-02-20T00:00:00+02:00",
    "project_description": "<p>Kohde jolla voi testata haso-hakemuksia</p>\r\n",
    "project_district": "Herttoniemi",
    "project_energy_class": "A",
    "project_estate_agent": "Mikko Parviainen",
    "project_estate_agent_email": "mikko.parviainen@example.com",
    "project_estate_agent_phone": "09 310 15507",
    "project_estimated_completion": "Joskus keväällä",
    "project_estimated_completion_date": datetime.datetime(
        2020, 2, 20, 0, 0, tzinfo=tzoffset(None, 7200)
    ),
    "project_has_elevator": True,
    "project_has_sauna": False,
    "project_heating_options": ["Maalämpö"],
    "project_holding_type": "RIGHT_OF_RESIDENCE_APARTMENT",
    "project_housing_company": "HasoHakemuTesti",
    "project_housing_manager": "Ilkka Isännöitsijä",
    "project_id": 641,
    "project_manager": "Pertti Päällikkö",
    "project_material_choice_dl": datetime.datetime(
        2022, 1, 10, 0, 0, tzinfo=tzoffset(None, 7200)
    ),
    "project_new_development_status": "READY_TO_MOVE",
    "project_new_housing": True,
    "project_ownership_type": "HASO",
    "project_possession_transfer_date": datetime.datetime(
        2020, 2, 20, 0, 0, tzinfo=tzoffset(None, 7200)
    ),
    "project_postal_code": "012345",
    "project_premarketing_end_time": datetime.datetime(
        2022, 1, 1, 2, 0, tzinfo=tzoffset(None, 7200)
    ),
    "project_premarketing_start_time": datetime.datetime(
        2021, 1, 1, 1, 0, tzinfo=tzoffset(None, 7200)
    ),
    "project_publication_end_time": datetime.datetime(
        2023, 1, 1, 10, 0, tzinfo=tzoffset(None, 7200)
    ),
    "project_publication_start_time": datetime.datetime(
        2020, 1, 1, 10, 0, tzinfo=tzoffset(None, 7200)
    ),
    "project_published": True,
    "project_realty_id": "123456A",
    "project_regular_bank_account": "FI21 1234 5600 0007 85",
    "project_sanitation": "Malmin Kiinteistöhoito Oy",
    "project_shareholder_meeting_date": datetime.datetime(
        2023, 2, 2, 18, 0, tzinfo=tzoffset(None, 7200)
    ),
    "project_site_area": 1000.0,
    "project_site_renter": "Helsingin kaupunki",
    "project_state_of_sale": "FOR_SALE",
    "project_street_address": "Hasontestauskatu 33",
    "project_url": "http://example.com/fi/node/641",
    "project_uuid": "efddabe8-11d3-4df1-a419-00f4e3c6f5d1",
    "project_zoning_info": "https://www.google.fi",
    "project_zoning_status": "Vahvistettu asemakaava",
    "publish_on_etuovi": False,
    "publish_on_oikotie": False,
    "right_of_occupancy_deposit": 1400000,
    "right_of_occupancy_fee": 50000,
    "right_of_occupancy_payment": 2400000,
    "room_count": 0,
    "sales_price": 0,
    "services_description": "Hyvien kulkuyhteyksien varrella",
    "showing_times": [
        datetime.datetime(2021, 5, 9, 0, 0, tzinfo=tzoffset(None, 10800))
    ],
    "site_owner": "Oma",
    "storage_description": "Runsaasti säilytystilaa",
    "title": "Hasontestauskatu 33 A5",
    "url": "http://example.com/fi/node/646",
    "uuid": "6caac7f4-0fe8-42a3-aef0-b962dcc395ad",
    "water_fee": 4000,
    "water_fee_explanation": "9e lisämaksu jokaiselta asukkaalta",
}
