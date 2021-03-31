from rest_framework.viewsets import ViewSet
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework import status

from elasticsearch_dsl import Search

from django_etuovi.etuovi import send_items  # , create_xml_file
from django_oikotie.oikotie import create_housing_companies, create_apartments

from connections.etuovi.etuovi_mapper import map_apartment_to_item
from connections.oikotie.oikotie_mapper import (
    map_oikotie_housing_company,
    map_oikotie_apartment,
)
from connections.utils import create_elastic_connection


class ConnectionsRPC(ViewSet):
    """
    An RPC class for calling special prosedures via api.
    """

    create_elastic_connection()

    @action(methods=["get"], detail=False, url_path="send_etuovi_xml")
    def send_etuovi_xml(self, request):
        s_obj = Search().exclude("match", _language="en")
        s_obj.execute()
        scan = s_obj.scan()
        items = []

        for hit in scan:
            try:
                m = map_apartment_to_item(hit)
                items.append(m)
            except ValueError as e:
                print(f"-- could not map apartment {hit.meta.id}:", str(e))
                pass
        try:
            send_items(items)
        except AttributeError:
            pass
        except Exception as e:
            print("-- apartment XML not created:", {str(e)})
            pass

        return Response(
            f"Fetched {s_obj.count()} appartements", status=status.HTTP_200_OK
        )

    @action(methods=["get"], detail=False, url_path="send_oikotie_xml")
    def send_oikotie_xml(self, request):
        s_obj = Search().exclude("match", _language="en")
        s_obj.execute()
        scan = s_obj.scan()
        apartments = []
        housing_companies = []

        for hit in scan:
            try:
                hc = map_oikotie_housing_company(hit)
                housing_companies.append(hc)
            except ValueError as e:
                print(f"-- could not map housing company {hit.meta.id}:", str(e))
                pass
            try:
                a = map_oikotie_apartment(hit)
                apartments.append(a)
            except ValueError as e:
                print(f"-- could not map apartment {hit.meta.id}:", str(e))
                pass
        try:
            create_housing_companies(housing_companies)
        except AttributeError:
            pass
        except Exception as e:
            print("-- housing company XML not created:", {str(e)})
            pass
        try:
            create_apartments(apartments)
        except AttributeError:
            pass
        except Exception as e:
            print("-- apartment XML not created:", {str(e)})
            pass
        return Response(
            f"Fetched {s_obj.count()} apartments", status=status.HTTP_200_OK
        )
