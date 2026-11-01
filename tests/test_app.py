from io import BytesIO
from zipfile import ZipFile
from lxml import etree
from fastapi.testclient import TestClient
import pytest
from app.documents import chunks, process_docx, vocalize, W
from app.main import app


def make_docx(xml=None, extra=None):
    output = BytesIO()
    with ZipFile(output, 'w') as z:
        z.writestr('[Content_Types].xml', '<Types/>')
        z.writestr('word/document.xml', xml or f'<w:document xmlns:w="{W[1:-1]}"><w:body><w:p><w:r><w:rPr><w:b/></w:rPr><w:t>اللغة </w:t></w:r><w:r><w:t>العربية</w:t></w:r></w:p><w:tbl><w:tr><w:tc><w:p><w:r><w:t>جميلة</w:t></w:r></w:p></w:tc></w:tr></w:tbl></w:body></w:document>')
        z.writestr('word/media/image.png', b'unchanged-image')
        if extra:
            z.writestr('word/header1.xml', extra)
    return output.getvalue()


def mark(text):
    return ''.join(c + ('َ' if 'ء' <= c <= 'ي' and c != 'ّ' else '') for c in text)


def test_chunking_preserves_every_character():
    original = ('اللغة العربية جميلة. \n' * 100) + ('ع' * 800)
    parts = list(chunks(original))
    assert ''.join(parts) == original
    assert all(len(p) <= 360 for p in parts)
    assert vocalize('hello\n123', mark) == 'hello\n123'


def test_docx_preserves_runs_tables_images_and_headers():
    header = f'<w:hdr xmlns:w="{W[1:-1]}"><w:p><w:r><w:t>عنوان</w:t></w:r></w:p></w:hdr>'
    data = process_docx(make_docx(extra=header), mark)
    with ZipFile(BytesIO(data)) as z:
        root = etree.fromstring(z.read('word/document.xml'))
        assert len(list(root.iter(W + 'b'))) == 1
        assert len(list(root.iter(W + 'tbl'))) == 1
        assert ''.join(root.itertext()) == mark('اللغة العربيةجميلة')
        assert z.read('word/media/image.png') == b'unchanged-image'
        assert 'َ' in z.read('word/header1.xml').decode()
        assert len(list(root.iter(W + 'r'))) == 3


def test_existing_mark_in_separate_run():
    xml = f'<w:document xmlns:w="{W[1:-1]}"><w:body><w:p><w:r><w:t>ع</w:t></w:r><w:r><w:t>َربي</w:t></w:r></w:p></w:body></w:document>'
    data = process_docx(make_docx(xml), lambda text: 'عَرَبِيَ')
    with ZipFile(BytesIO(data)) as z:
        root = etree.fromstring(z.read('word/document.xml'))
        assert ''.join(root.itertext()) == 'عَرَبِيَ'
        assert [n.text for n in root.iter(W + 't')] == ['ع', 'َرَبِيَ']


def test_invalid_file_and_expansion_rejected():
    with pytest.raises(ValueError): process_docx(b'not a zip', mark)
    with pytest.raises(ValueError): process_docx(make_docx().replace(b'word/document.xml', b'word/xxxxxxxx.xml'), mark)


def test_inference_cannot_change_base_text():
    with pytest.raises(ValueError, match='الحفاظ'): process_docx(make_docx(), lambda text: 'نص آخر')


def test_api_real_model_and_document_roundtrip():
    with TestClient(app) as client:
        response = client.post('/api/tashkeel', json={'text': 'اللغة العربية جميلة'})
        assert response.status_code == 200
        assert 'َ' in response.json()['text'] or 'ِ' in response.json()['text']
        assert response.headers['cache-control'] == 'no-store'
        assert client.post('/api/tashkeel', json={'text': 'hello'}).status_code == 422
        assert client.post('/api/tashkeel', json={'text': 'ع' * 20001}).status_code == 422
        assert client.post('/api/document', files={'file': ('bad.doc', b'bad')}).status_code == 422
        response = client.post('/api/document', files={'file': ('arabic.docx', make_docx())})
        assert response.status_code == 200
        with ZipFile(BytesIO(response.content)) as z:
            root = etree.fromstring(z.read('word/document.xml'))
            assert 'َ' in ''.join(root.itertext())
            assert len(list(root.iter(W + 'b'))) == 1
        assert client.get('/').status_code == 200
