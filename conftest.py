"""pytest fixtures"""
import io
import pytest


@pytest.fixture
def sample_w2_pdf_content():
    """Minimal valid PDF with W-2 data"""
    # this is a bare-bones PDF structure with text content
    return b"""%PDF-1.4
1 0 obj
<< /Type /Catalog /Pages 2 0 R >>
endobj
2 0 obj
<< /Type /Pages /Kids [3 0 R] /Count 1 >>
endobj
3 0 obj
<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792]
   /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>
endobj
4 0 obj
<< /Length 500 >>
stream
BT
/F1 12 Tf
50 700 Td
(Form W-2 Wage and Tax Statement 2024) Tj
0 -20 Td
(a Employee's social security number) Tj
0 -15 Td
(123-45-6789) Tj
0 -20 Td
(b Employer identification number (EIN)) Tj
0 -15 Td
(12-3456789) Tj
0 -20 Td
(1 Wages, tips, other compensation) Tj
0 -15 Td
($75,000.00) Tj
0 -20 Td
(2 Federal income tax withheld) Tj
0 -15 Td
($12,500.00) Tj
ET
endstream
endobj
5 0 obj
<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>
endobj
xref
0 6
0000000000 65535 f 
0000000009 00000 n 
0000000058 00000 n 
0000000115 00000 n 
0000000266 00000 n 
0000000819 00000 n 
trailer
<< /Size 6 /Root 1 0 R >>
startxref
896
%%EOF"""


@pytest.fixture
def sample_w2_pdf_file(sample_w2_pdf_content):
    """File-like object with sample PDF"""
    f = io.BytesIO(sample_w2_pdf_content)
    f.name = "test_w2.pdf"
    return f


@pytest.fixture
def invalid_pdf_content():
    """Not a valid PDF"""
    return b"this is not a pdf file"


@pytest.fixture
def empty_pdf_content():
    """Valid PDF structure but no pages"""
    return b"""%PDF-1.4
1 0 obj
<< /Type /Catalog /Pages 2 0 R >>
endobj
2 0 obj
<< /Type /Pages /Kids [] /Count 0 >>
endobj
xref
0 3
0000000000 65535 f 
0000000009 00000 n 
0000000058 00000 n 
trailer
<< /Size 3 /Root 1 0 R >>
startxref
115
%%EOF"""
