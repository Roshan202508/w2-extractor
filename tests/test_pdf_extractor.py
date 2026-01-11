"""Tests for PDF extraction"""
import pytest
from decimal import Decimal

from api.services.pdf_extractor import W2DataExtractor, W2ExtractedData
from api.exceptions import PDFParsingException, DataExtractionException


class TestW2DataExtractor:

    @pytest.fixture
    def extractor(self):
        return W2DataExtractor()

    @pytest.mark.asyncio
    async def test_extract_valid_w2(self, extractor, sample_w2_pdf_content):
        result = await extractor.extract(sample_w2_pdf_content)
        assert result.ein is not None
        assert result.ssn is not None
        assert result.wages is not None
        assert result.federal_tax_withheld is not None

    @pytest.mark.asyncio
    async def test_invalid_pdf_raises(self, extractor, invalid_pdf_content):
        with pytest.raises(PDFParsingException):
            await extractor.extract(invalid_pdf_content)

    @pytest.mark.asyncio
    async def test_empty_pdf_raises(self, extractor, empty_pdf_content):
        with pytest.raises((PDFParsingException, DataExtractionException)):
            await extractor.extract(empty_pdf_content)

    def test_format_ein(self, extractor):
        assert extractor._format_ein("123456789") == "12-3456789"
        assert extractor._format_ein("12-3456789") == "12-3456789"

    def test_format_ssn(self, extractor):
        assert extractor._format_ssn("123456789") == "123-45-6789"
        assert extractor._format_ssn("123-45-6789") == "123-45-6789"

    def test_parse_currency(self, extractor):
        assert extractor._parse_currency("1,234.56") == Decimal("1234.56")
        assert extractor._parse_currency("1234.56") == Decimal("1234.56")
        assert extractor._parse_currency("invalid") is None

    def test_to_dict(self):
        data = W2ExtractedData(
            ein="12-3456789",
            ssn="123-45-6789",
            wages=Decimal("75000.00"),
            federal_tax_withheld=Decimal("12500.00"),
        )
        result = data.to_dict()
        assert result["ein"] == "12-3456789"
        assert result["wages"] == "75000.00"


class TestEINExtraction:

    @pytest.fixture
    def extractor(self):
        return W2DataExtractor()

    def test_ein_with_hyphen(self, extractor):
        text = "Employer identification number (EIN): 12-3456789"
        assert extractor._find_ein(text) == "12-3456789"

    def test_ein_without_hyphen(self, extractor):
        text = "b Employer's EIN 123456789"
        assert extractor._find_ein(text) == "12-3456789"


class TestSSNExtraction:

    @pytest.fixture
    def extractor(self):
        return W2DataExtractor()

    def test_ssn_with_hyphens(self, extractor):
        text = "a Employee's social security number 123-45-6789"
        assert extractor._find_ssn(text) == "123-45-6789"

    def test_ssn_without_hyphens(self, extractor):
        text = "Social Security Number: 123456789"
        assert extractor._find_ssn(text) == "123-45-6789"


class TestCurrencyExtraction:

    @pytest.fixture
    def extractor(self):
        return W2DataExtractor()

    def test_wages_extraction(self, extractor):
        text = "1 Wages, tips, other compensation $75,000.00"
        assert extractor._find_currency(text, "wages") == Decimal("75000.00")

    def test_fed_tax_extraction(self, extractor):
        text = "2 Federal income tax withheld $12,500.00"
        assert extractor._find_currency(text, "fed_tax") == Decimal("12500.00")
