from drf_spectacular import openapi
from typing import List, Optional


class AutoSchema(openapi.AutoSchema):
    def get_tags(self) -> List[str]:
        """Use verbose names instead of URL path components as tags."""
        try:
            return [self._verbose_name_plural.capitalize()]
        except AttributeError:
            return super().get_tags()

    def get_summary(self) -> Optional[str]:
        """
        Give some sensible default summaries for each type of endpoint.
        These can be overridden with e.g. @extend_schema_view if needed.
        """
        default_summaries = {
            "create": f"Create {self._verbose_name}",
            "list": f"Get list of {self._verbose_name_plural}",
            "retrieve": f"Get {self._verbose_name}",
            "update": f"Update {self._verbose_name}",
            "partial_update": f"Patch {self._verbose_name}",
            "destroy": f"Delete {self._verbose_name}",
        }
        return default_summaries.get(self.view.action, super().get_summary())

    def get_description(self) -> str:
        """
        Give some sensible default descriptions for each type of endpoint.
        These can be overridden with e.g. @extend_schema_view if needed.
        """
        default_descriptions = {
            "create": f"Create a new {self._verbose_name} instance with the given details.",  # noqa: E501
            "list": f"Return a list of all accessible {self._verbose_name_plural}.",
            "retrieve": f"Return the details of the given {self._verbose_name} instance.",  # noqa: E501
            "update": f"Update the given {self._verbose_name} with new details.",
            "partial_update": f"Partially update the given {self._verbose_name} with new details.",  # noqa: E501
            "destroy": f"Delete the given {self._verbose_name} instance.",
        }
        return default_descriptions.get(self.view.action, super().get_description())

    @property
    def _model_meta(self):
        # noinspection PyProtectedMember
        return self.view.serializer_class.Meta.model._meta

    @property
    def _verbose_name(self):
        return self._model_meta.verbose_name

    @property
    def _verbose_name_plural(self):
        return self._model_meta.verbose_name_plural
