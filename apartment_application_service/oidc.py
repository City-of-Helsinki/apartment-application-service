from helusers._oidc_auth_impl import ApiTokenAuthentication


# borrowed from https://github.com/City-of-Helsinki/palvelutarjotin/blob/cf57294e0ea0bf9aafad4ecfb22729d6882823e5/palvelutarjotin/oidc.py#L4  # noqa: E501
class TunnistamoFixedApiTokenAuthentication(ApiTokenAuthentication):
    def __convert_amr_to_list(self, id_token):
        """
        OIDC's amr validation fails, since Tunnistamo sends the amr as a string
        instead of a list:
        https://github.com/City-of-Helsinki/tunnistamo/commit/a1b434bbbff92466a144f914a98985008d0ea836.
        To fix the claim validation issue, convert the id_token amr to list
        when a string is given.
        """
        if id_token["amr"] and not isinstance(id_token["amr"], list):
            id_token["amr"] = [id_token["amr"]]

    def validate_claims(self, id_token):
        self.__convert_amr_to_list(id_token)
        super().validate_claims(id_token)
