from unittest.mock import patch, MagicMock
from langchain_core.documents import Document
from server.ingest import load_documents_from_paths
from server.url_loader import load_url


def test_pdf_gets_source_type_pdf(tmp_path):
    pdf = tmp_path / "report.pdf"
    pdf.write_bytes(b"%PDF-1.4 fake")
    mock_doc = Document(page_content="Report content", metadata={"source": "report.pdf", "page": 0})
    with patch("server.ingest.PyPDFLoader") as MockLoader:
        MockLoader.return_value.load.return_value = [mock_doc]
        docs = load_documents_from_paths([str(pdf)])
    assert docs[0].metadata["source_type"] == "pdf"


def test_txt_gets_source_type_txt(tmp_path):
    txt = tmp_path / "notes.txt"
    txt.write_text("Some text content")
    docs = load_documents_from_paths([str(txt)])
    assert docs[0].metadata["source_type"] == "txt"


def test_csv_gets_source_type_csv(tmp_path):
    csv = tmp_path / "data.csv"
    csv.write_text("col1,col2\nval1,val2")
    docs = load_documents_from_paths([str(csv)])
    assert docs[0].metadata["source_type"] == "csv"


def test_url_gets_source_type_url():
    mock_resp = MagicMock()
    mock_resp.headers = {"content-type": "text/html"}
    mock_resp.content = b"<p>Hello world</p>" * 10
    mock_resp.text = "<p>Hello world</p>" * 10
    with patch("server.url_loader.httpx.get", return_value=mock_resp):
        docs = load_url("https://example.com")
    assert docs[0].metadata["source_type"] == "url"
