import dataclasses
from datetime import date
from decimal import Decimal
from io import BytesIO
from pikepdf import Pdf, String
from typing import ClassVar, Dict, List

PDF_TEMPLATE_DIRECTORY = "pdf_templates"

DataDict = Dict[str, str]


class PDFError(Exception):
    pass


@dataclasses.dataclass
class PDFData:
    """Base class for data used to populate a PDF template's fields."""

    # mapping from PDFData.field -> actual template PDF field name
    FIELD_MAPPING: ClassVar[Dict[str, str]] = {}

    def to_data_dict(self) -> DataDict:
        data_dict: DataDict = {}
        for field in dataclasses.fields(self):
            original_value = getattr(self, field.name)
            if field.type == date:
                value = original_value.strftime("%-d.%-m.%Y") if original_value else ""
            elif field.type == Decimal:
                value = str(original_value).replace(".", ",")
            else:
                value = str(original_value)
            data_dict[field.name] = value
            data_dict[self.FIELD_MAPPING[field.name]] = value
        return data_dict


def create_multi_page_pdf(template_file_name: str, pdf_data_list: List[PDFData]):
    pdf = Pdf.new()

    for pdf_data in pdf_data_list:
        single_pdf = _create_pdf(
            f"{PDF_TEMPLATE_DIRECTORY}/{template_file_name}", pdf_data.to_data_dict()
        )
        pdf.pages.extend(single_pdf.pages)

    pdf_bytes = BytesIO()
    pdf.save(pdf_bytes)
    pdf_bytes.seek(0)

    return pdf_bytes


def _set_pdf_fields(pdf: Pdf, data_dict: DataDict) -> None:
    for page in pdf.pages:
        for annot in page.Annots:
            if (field_name := str(annot.T)) not in data_dict:
                continue
            if annot.FT == "/Tx":  # text field
                pdf_value = String(data_dict[field_name])
                annot.V = pdf_value
                annot.DV = pdf_value
            else:
                raise PDFError(f"Field {field_name} has an unsupported type {annot.FT}")


def _create_pdf(template_file_name: str, data_dict: DataDict) -> Pdf:
    pdf = Pdf.open(template_file_name)
    _set_pdf_fields(pdf, data_dict)
    pdf.Root.AcroForm.NeedAppearances = 1
    return pdf
