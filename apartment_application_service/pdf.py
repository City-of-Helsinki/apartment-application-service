import dataclasses
from datetime import date
from decimal import Decimal
from io import BytesIO
from typing import ClassVar, Dict, Iterable, Optional, Union

from pikepdf import Name, Pdf, String

PDF_TEMPLATE_DIRECTORY = "pdf_templates"

DataDict = Dict[str, str]


class PDFError(Exception):
    pass


@dataclasses.dataclass
class PDFData:
    """Base class for data used to populate a PDF template's fields."""

    # mapping from PDFData.field -> actual template PDF field name
    FIELD_MAPPING: ClassVar[Dict[str, str]] = {}
    # optional mapping from actual template PDF field name -> fixed font size
    FIELD_FONT_SIZES: ClassVar[Dict[str, int]] = {}
    # default font size for all text fields to keep browser PDF viewers from
    # auto-enlarging field contents inconsistently.
    FIELD_DEFAULT_FONT_SIZE: ClassVar[Optional[int]] = 11

    def __post_init__(self, *args, **kwargs):
        annots = [a for a in self.__annotations__ if a != "FIELD_MAPPING"]
        keys = self.FIELD_MAPPING.keys()
        assert (
            not annots - keys
        ), f"The following fields are missing from FIELD_MAPPING: {annots - keys}."

    def to_data_dict(self) -> DataDict:
        """Convert the data to a DataDict that is used to populate the PDF's fields.

        Formats some types of values in a way that should fit most usages. If a field
        requires a different representation, the field should be provided to the
        dataclass as a string with the formatting already applied."""

        data_dict: DataDict = {}
        for field in dataclasses.fields(self):
            original_value = getattr(self, field.name)
            if original_value is None:
                value = ""
            else:
                if isinstance(original_value, bool):
                    value = original_value
                elif isinstance(original_value, date):
                    value = original_value.strftime("%-d.%-m.%Y")
                elif isinstance(original_value, Decimal):
                    value = str(original_value).replace(".", ",")
                else:
                    value = str(original_value)
            data_dict[self.FIELD_MAPPING[field.name]] = value
        return data_dict


class PDFCurrencyField:
    def __init__(
        self, *, euros: Decimal = None, cents: int = None, prefix=None, suffix=None
    ):
        if euros is None and cents is None:
            self.value = None
            return

        self.value = euros if euros is not None else Decimal(cents) / 100
        self.prefix = prefix or ""
        self.suffix = suffix or ""

    def formatted_number_string(self) -> str:
        return (
            format(self.value.quantize(Decimal(".01")), ",")
            .replace(",", " ")
            .replace(".", ",")
        )

    def __str__(self):
        return (
            (self.prefix + self.formatted_number_string() + self.suffix)
            if self.value is not None
            else ""
        )


def create_pdf(
    template_file_name: str, pdf_data_list: Union[PDFData, Iterable[PDFData]]
) -> BytesIO:
    pdf: Optional[Pdf]
    if not isinstance(pdf_data_list, Iterable):
        pdf_data_list = [pdf_data_list]
        pdf = None
    else:
        pdf = Pdf.new()

    for idx, pdf_data in enumerate(pdf_data_list):
        field_font_sizes = getattr(pdf_data, "FIELD_FONT_SIZES", {})
        field_default_font_size = getattr(pdf_data, "FIELD_DEFAULT_FONT_SIZE", None)
        single_pdf = _create_pdf(
            f"{PDF_TEMPLATE_DIRECTORY}/{template_file_name}",
            pdf_data.to_data_dict(),
            idx,
            field_font_sizes,
            field_default_font_size,
        )
        if pdf is None:  # Only one repetition of data
            pdf = single_pdf  # Output the single filled PDF
            break
        if not hasattr(pdf.Root, "AcroForm") and hasattr(single_pdf.Root, "AcroForm"):
            acroform = pdf.copy_foreign(single_pdf.Root.AcroForm)
            pdf.Root.AcroForm = acroform
            del pdf.Root.AcroForm.Fields
            _set_need_appearances(pdf)
        pdf.pages.extend(single_pdf.pages)
    pdf_bytes = BytesIO()
    if pdf is not None:
        pdf.save(pdf_bytes)
    pdf_bytes.seek(0)

    return pdf_bytes


def _get_checkbox_checked_value(annotation: object):
    # NOTE: There is no universal value for a checked checkbox
    # https://stackoverflow.com/a/48412434/4558221
    # Try to mitigate this by figuring out
    # what the value for the "checked" state is
    # Its stored in the key "/AP" and its "/On", "/Yes" or "/1"
    # 9.6.2025
    checked_value = "/On"
    annotation_ap_keys = annotation.AP["/D"].keys()

    if "/Yes" in annotation_ap_keys:
        checked_value = "/Yes"
    elif "/1" in annotation_ap_keys:
        checked_value = "/1"

    return checked_value


def _set_annotation_font_size(
    annot: object,
    font_size: Optional[int],
    apply_to_parent: bool = True,
) -> None:
    if font_size is None:
        return

    da = String(f"/Helv {font_size} Tf 0 g")
    annot.DA = da
    if apply_to_parent and hasattr(annot, "Parent"):
        annot.Parent.DA = da


def _set_parent_field_value_if_needed(
    annot: object,
    data_dict: DataDict,
    field_font_sizes: Dict[str, int],
    field_default_font_size: Optional[int],
) -> bool:
    if hasattr(annot, "FT") or not hasattr(annot, "Parent"):
        return False

    field_name = str(annot.Parent.T)
    if field_name not in data_dict:
        return False

    pdf_value = String(data_dict[field_name])
    annot.Parent.V = pdf_value
    annot.Parent.DV = pdf_value

    font_size = field_font_sizes.get(field_name, field_default_font_size)
    _set_annotation_font_size(annot, font_size)
    return True


def _set_text_field_value(
    annot: object,
    field_name: str,
    data_dict: DataDict,
    field_font_sizes: Dict[str, int],
    field_default_font_size: Optional[int],
) -> None:
    pdf_value = String(data_dict[field_name])
    annot.V = pdf_value
    annot.DV = pdf_value

    font_size = field_font_sizes.get(field_name, field_default_font_size)
    _set_annotation_font_size(annot, font_size)


def _set_checkbox_field_value(annot: object, value: str) -> None:
    if not value:
        return

    checked_value = _get_checkbox_checked_value(annot)
    pdf_value = Name(checked_value)
    annot.AS = pdf_value
    annot.V = pdf_value


def _set_regular_field_value(
    annot: object,
    field_name: str,
    data_dict: DataDict,
    field_font_sizes: Dict[str, int],
    field_default_font_size: Optional[int],
) -> None:
    if annot.FT == "/Tx":
        _set_text_field_value(
            annot,
            field_name,
            data_dict,
            field_font_sizes,
            field_default_font_size,
        )
        return

    if annot.FT == "/Btn":
        _set_checkbox_field_value(annot, data_dict[field_name])
        return

    raise PDFError(f"Field {field_name} has an unsupported type {annot.FT}")


def _set_pdf_fields(
    pdf: Pdf,
    data_dict: DataDict,
    idx: None,
    field_font_sizes: Optional[Dict[str, int]] = None,
    field_default_font_size: Optional[int] = None,
) -> None:
    field_font_sizes = field_font_sizes or {}

    for page in pdf.pages:
        for annot in getattr(page, "Annots", []):
            if _set_parent_field_value_if_needed(
                annot,
                data_dict,
                field_font_sizes,
                field_default_font_size,
            ):
                continue
            if not hasattr(annot, "T") or (field_name := str(annot.T)) not in data_dict:
                continue
            if idx is not None:
                # In case of merging multiple PDFs, need to rename the field, otherwise
                # every field with the same name will display same values (latest value)
                annot.T = String(str(annot.T) + "_" + str(idx))
            _set_regular_field_value(
                annot,
                field_name,
                data_dict,
                field_font_sizes,
                field_default_font_size,
            )


def _set_need_appearances(pdf: Pdf) -> None:
    if hasattr(pdf.Root, "AcroForm"):
        pdf.Root.AcroForm.NeedAppearances = True


def _create_pdf(
    template_file_name: str,
    data_dict: DataDict,
    idx=None,
    field_font_sizes: Optional[Dict[str, int]] = None,
    field_default_font_size: Optional[int] = None,
) -> Pdf:
    pdf = Pdf.open(template_file_name)
    _set_pdf_fields(
        pdf,
        data_dict,
        idx=idx,
        field_font_sizes=field_font_sizes,
        field_default_font_size=field_default_font_size,
    )
    _set_need_appearances(pdf)
    return pdf
