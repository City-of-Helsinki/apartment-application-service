from io import BytesIO
import itertools
import re
import subprocess
from typing import List

import pytest
from pypdf import PdfReader

def assert_pdf_has_text(pdf: bytes, text: str) -> bool:
    """
    Check if the PDF file contains the given text.
    """
    pdf_text_content = "\n".join(get_cleaned_pdf_texts(pdf))
    assert (
        text in pdf_text_content
    ), f"Text {text!r} was not found in PDF text:\n{pdf_text_content}"


def get_cleaned_pdf_texts(pdf: bytes) -> List[str]:
    result = []
    for text_line in get_pdf_text_lines(pdf):
        cleaned = re.sub(r"\s+", " ", text_line).strip()
        if cleaned:
            result.append(cleaned)
    return result


def get_pdf_text_lines(pdf: bytes) -> List[str]:
    reader = PdfReader(BytesIO(pdf))
    # extract text from all pages as strings, split into lines, flatten into one list
    return itertools.chain.from_iterable(
        page.extract_text().splitlines()
        for page in
        reader.pages
    )


    pass
    # pdftotext = "pdftotext"
    # try:
    #     retcode = subprocess.call([pdftotext, "-v"], stdout=subprocess.DEVNULL)
    # except FileNotFoundError:
    #     return pytest.skip("pdftotext is not available")
    # if retcode != 0:
    #     return pytest.skip("pdftotext not functioning")

    # process = subprocess.Popen(
    #     [pdftotext, "-layout", "-", "-"],
    #     stdin=subprocess.PIPE,
    #     stdout=subprocess.PIPE,
    #     stderr=subprocess.PIPE,
    # )
    # (stdout, stderr) = process.communicate(input=pdf)
    # if process.returncode != 0:
    #     msg = f"pdftotext failed with code {process.returncode}: {stderr}"
    #     raise RuntimeError(msg)
    # return stdout.decode("utf-8", errors="replace").splitlines()


def remove_pdf_id(pdf: bytes) -> bytes:
    """
    Remove the /ID entry from the PDF file.
    """
    return re.sub(rb"/ID\s+\[<[^]]+>\]", b"", pdf)
