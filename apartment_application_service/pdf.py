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

    def __str__(self):
        return (
            (
                self.prefix
                + format(self.value.quantize(Decimal(".01")), ",")
                .replace(",", " ")
                .replace(".", ",")
                + self.suffix
            )
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
        single_pdf = _create_pdf(
            f"{PDF_TEMPLATE_DIRECTORY}/{template_file_name}",
            pdf_data.to_data_dict(),
            idx,
        )
        if pdf is None:  # Only one repetition of data
            pdf = single_pdf  # Output the single filled PDF
            break
        if not hasattr(pdf.Root, "AcroForm") and hasattr(single_pdf.Root, "AcroForm"):
            acroform = pdf.copy_foreign(single_pdf.Root.AcroForm)
            pdf.Root.AcroForm = acroform
            del pdf.Root.AcroForm.Fields
            pdf.Root.AcroForm.NeedAppearances = True
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


def _set_pdf_fields(pdf: Pdf, data_dict: DataDict, idx: None) -> None:
    for page in pdf.pages:
        for annot in getattr(page, "Annots", []):
            if not hasattr(annot, "FT") and str(annot.Parent.T) in data_dict:
                pdf_value = String(data_dict[str(annot.Parent.T)])
                annot.Parent.V = pdf_value
                annot.Parent.DV = pdf_value
                continue
            if not hasattr(annot, "T") or (field_name := str(annot.T)) not in data_dict:
                continue
            if idx is not None:
                # In case of merging multiple PDFs, need to rename the field, otherwise
                # every field with the same name will display same values (latest value)
                annot.T = String(str(annot.T) + "_" + str(idx))
            if annot.FT == "/Tx":  # text field
                pdf_value = String(data_dict[field_name])
                annot.V = pdf_value
                annot.DV = pdf_value
                # Required to show the filled fields in almost every MacOS PDF viewer
                # Source: https://stackoverflow.com/a/63025285
                annot.AP = ""
            elif annot.FT == "/Btn":  # checkbox
                if not data_dict[field_name]:
                    # Not checked
                    continue

                checked_value = _get_checkbox_checked_value(annot)

                pdf_value = Name(checked_value)
                annot.AS = pdf_value
                annot.V = pdf_value
            else:
                raise PDFError(f"Field {field_name} has an unsupported type {annot.FT}")


def _create_pdf(template_file_name: str, data_dict: DataDict, idx=None) -> Pdf:
    pdf = Pdf.open(template_file_name)
    _set_pdf_fields(pdf, data_dict, idx=idx)
    return pdf
