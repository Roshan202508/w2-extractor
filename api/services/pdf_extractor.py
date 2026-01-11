"""
PDF extraction for W-2 forms

Extracts: EIN, SSN, Wages (Box 1), Federal Tax Withheld (Box 2)
"""
import io
import logging
import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

import fitz  # pymupdf

from api.exceptions import DataExtractionException, PDFParsingException

logger = logging.getLogger(__name__)


@dataclass
class W2ExtractedData:
    """Container for extracted W-2 data"""
    ein: str
    ssn: str
    wages: Decimal
    federal_tax_withheld: Decimal

    def to_dict(self):
        return {
            "ein": self.ein,
            "ssn": self.ssn,
            "wages": str(self.wages),
            "federal_tax_withheld": str(self.federal_tax_withheld),
        }


class W2DataExtractor:
    """
    Extracts data from W-2 PDF forms.
    
    Uses multiple strategies:
    1. Look for labels like "Employer identification number" and find values nearby
    2. Pattern matching for EIN/SSN formats
    3. Heuristics to filter out false positives
    """

    # regex patterns
    EIN_PATTERN = re.compile(r"\b(\d{2}[-]?\d{7})\b")
    SSN_PATTERN = re.compile(r"\b(\d{3}[-]?\d{2}[-]?\d{4})\b")
    CURRENCY_PATTERN = re.compile(r"\$?\s*([\d,]+\.?\d{0,2})")

    # label patterns for finding fields
    LABELS = {
        "wages": [
            r"(?i)wages[,\s]+tips[,\s]+other\s+comp",
            r"(?i)box\s*1\b",
            r"(?i)1\s+wages",
        ],
        "fed_tax": [
            r"(?i)federal\s+income\s+tax\s+withheld",
            r"(?i)box\s*2\b",
            r"(?i)2\s+federal",
        ],
        "ein": [
            r"(?i)employer.*identification.*number",
            r"(?i)employer'?s?\s+EIN",
            r"(?i)box\s*b\b",
        ],
        "ssn": [
            r"(?i)employee'?s?\s+social\s+security",
            r"(?i)social\s+security\s+number",
            r"(?i)box\s*a\b",
        ],
    }

    def __init__(self):
        # pre-compile label patterns
        self._label_patterns = {
            key: [re.compile(p) for p in patterns]
            for key, patterns in self.LABELS.items()
        }

    async def extract(self, file_content: bytes) -> W2ExtractedData:
        """Main extraction method"""
        text = self._get_text(file_content)
        return self._parse_text(text)

    def _get_text(self, content: bytes) -> str:
        """Extract text from PDF using PyMuPDF"""
        try:
            doc = fitz.open(stream=content, filetype="pdf")
            
            if doc.page_count == 0:
                doc.close()
                raise PDFParsingException("PDF has no pages", code="empty_pdf")

            text_parts = []
            for page in doc:
                text = page.get_text()
                if text:
                    text_parts.append(text)
            
            doc.close()
            full_text = "\n".join(text_parts)

            if not full_text.strip():
                raise PDFParsingException(
                    "No extractable text - might be a scanned document",
                    code="no_text_content",
                )

            logger.debug(f"Extracted {len(full_text)} chars from PDF")
            return full_text

        except PDFParsingException:
            raise
        except Exception as e:
            logger.error(f"PDF parse error: {e}")
            raise PDFParsingException(f"Failed to parse PDF: {e}", code="pdf_parse_error")

    def _parse_text(self, text: str) -> W2ExtractedData:
        """Parse extracted text to find W-2 fields"""
        errors = []

        ein = self._find_ein(text)
        if not ein:
            errors.append(("ein", "EIN"))

        ssn = self._find_ssn(text)
        if not ssn:
            errors.append(("ssn", "SSN"))

        wages = self._find_currency(text, "wages")
        if wages is None:
            errors.append(("wages", "Wages (Box 1)"))

        fed_tax = self._find_currency(text, "fed_tax")
        if fed_tax is None:
            errors.append(("federal_tax_withheld", "Federal Tax (Box 2)"))

        if errors:
            missing = [name for _, name in errors]
            raise DataExtractionException(
                f"Could not extract: {', '.join(missing)}",
                code="missing_fields",
                field=errors[0][0],
            )

        return W2ExtractedData(ein=ein, ssn=ssn, wages=wages, federal_tax_withheld=fed_tax)

    def _find_ein(self, text: str):
        """Find EIN in text"""
        # try finding near labels first
        for pattern in self._label_patterns["ein"]:
            match = pattern.search(text)
            if match:
                search_area = text[match.start():match.start() + 200]
                ein_match = self.EIN_PATTERN.search(search_area)
                if ein_match:
                    return self._format_ein(ein_match.group(1))

        # fallback: find all EIN-like numbers
        all_matches = self.EIN_PATTERN.findall(text)
        for m in all_matches:
            normalized = m.replace("-", "")
            # EINs don't start with 9 (that's usually SSN)
            if len(normalized) == 9 and not normalized.startswith("9"):
                return self._format_ein(m)

        return None

    def _find_ssn(self, text: str):
        """Find SSN in text"""
        # try labels first
        for pattern in self._label_patterns["ssn"]:
            match = pattern.search(text)
            if match:
                search_area = text[match.start():match.start() + 200]
                ssn_match = self.SSN_PATTERN.search(search_area)
                if ssn_match:
                    return self._format_ssn(ssn_match.group(1))

        # fallback
        all_matches = self.SSN_PATTERN.findall(text)
        for m in all_matches:
            normalized = m.replace("-", "")
            if len(normalized) == 9:
                area = int(normalized[:3])
                # SSN area can't be 000, 666, or 900-999
                if area != 0 and area != 666 and area < 900:
                    return self._format_ssn(m)

        return None

    def _find_currency(self, text: str, label_key: str):
        """Find currency value near a label"""
        for pattern in self._label_patterns[label_key]:
            match = pattern.search(text)
            if match:
                search_area = text[match.end():match.end() + 100]
                currency_match = self.CURRENCY_PATTERN.search(search_area)
                if currency_match:
                    return self._parse_currency(currency_match.group(1))
        return None

    def _format_ein(self, ein: str) -> str:
        normalized = ein.replace("-", "")
        return f"{normalized[:2]}-{normalized[2:]}" if len(normalized) == 9 else ein

    def _format_ssn(self, ssn: str) -> str:
        normalized = ssn.replace("-", "")
        return f"{normalized[:3]}-{normalized[3:5]}-{normalized[5:]}" if len(normalized) == 9 else ssn

    def _parse_currency(self, value: str):
        try:
            cleaned = value.replace(",", "").strip()
            return Decimal(cleaned) if cleaned else None
        except (InvalidOperation, ValueError):
            return None
