from apartment_application_service.pdf import _set_need_appearances, _set_pdf_fields


class MockAnnotation:
    def __init__(self, field_type, field_name, appearance=None):
        self.FT = field_type
        self.T = field_name
        self.AP = appearance


class MockPage:
    def __init__(self, annotations):
        self.Annots = annotations


class MockPdf:
    def __init__(self, pages):
        self.pages = pages


class MockAcroForm:
    pass


class MockRoot:
    def __init__(self, acroform=None):
        if acroform is not None:
            self.AcroForm = acroform


class MockPdfWithRoot:
    def __init__(self, root):
        self.Root = root


def test_set_pdf_fields_text_field_keeps_existing_appearance():
    annotation = MockAnnotation(
        field_type="/Tx",
        field_name="TestField",
        appearance={"/N": "existing"},
    )
    pdf = MockPdf(pages=[MockPage([annotation])])

    _set_pdf_fields(pdf, {"TestField": "Filled value"}, idx=None)

    assert annotation.AP == {"/N": "existing"}


def test_set_need_appearances_sets_flag_when_acroform_exists():
    acroform = MockAcroForm()
    pdf = MockPdfWithRoot(root=MockRoot(acroform=acroform))

    _set_need_appearances(pdf)

    assert pdf.Root.AcroForm.NeedAppearances is True


def test_set_need_appearances_does_nothing_without_acroform():
    pdf = MockPdfWithRoot(root=MockRoot())

    _set_need_appearances(pdf)

    assert not hasattr(pdf.Root, "AcroForm")
