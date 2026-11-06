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
    parts = list(chunks(original, limit=360))
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


def test_mixed_script_chunks_respect_model_token_budget():
    import unicodedata
    from app.vocalizer import MAX_INPUT_TOKENS, complete_text, split_marks
    original = ('한글 café أحمد🙂 ' * 100) + 'العربية'
    parts = list(chunks(original))
    assert ''.join(parts) == original
    for part in parts:
        tokens = [c for c in unicodedata.normalize('NFD', part)
                  if unicodedata.category(c) != 'Mn']
        assert len(tokens) <= MAX_INPUT_TOKENS
        assert [c for c, _ in split_marks(complete_text(part))] == [c for c, _ in split_marks(part)]


def test_jais_opt_in_recovers_whitespace_and_uses_rawi_on_failure(monkeypatch):
    from app import jais

    monkeypatch.setenv('IFM_API_KEY', 'test-key')
    calls = []
    def predict(text, key, timeout):
        calls.append((text, key, timeout))
        return 'ذَهَبَ الطَّالِبُ'
    monkeypatch.setattr(jais, 'predict', predict)
    with TestClient(app) as client:
        data = {'text': 'ذَهَب\n\tالطالب'}
        local = client.post('/api/tashkeel', json=data)
        assert local.headers['X-Tashkeel-Engine'] == 'rawi'
        assert not calls
        selected = {'X-Tashkeel-Mode': 'jais'}
        remote = client.post('/api/tashkeel', json=data, headers=selected)
        assert remote.headers['X-Tashkeel-Engine'] == 'jais'
        assert remote.json()['text'] == 'ذَهَبَ\n\tالطَّالِبُ'
        assert calls == [(data['text'], 'test-key', jais.CHUNK_TIMEOUT)]
        monkeypatch.setattr(jais, 'predict', lambda *args: None)
        failed = client.post('/api/tashkeel', json=data, headers=selected)
        assert failed.headers['X-Tashkeel-Engine'] == 'rawi'
        assert failed.json() == local.json()


def test_jais_word_recovery_never_copies_changed_letters():
    from app.jais import recover_harakat

    source = 'هذا الطالب كتب كتابا أمس.'
    local = 'هَذَا الطَّالِبُ كَتَبَ كِتَابًا أَمْسَ.'
    prediction = 'هَذَا الطَّالِبُ كَتَبَ كِتَاباً الْيَوْمَ.'
    result, engine = recover_harakat(source, prediction, lambda _: local)
    assert engine == 'jais+rawi'
    assert result == local


def test_jais_word_batches_paragraphs_and_preserves_runs_and_binary_parts(monkeypatch):
    from app import jais

    monkeypatch.setenv('IFM_API_KEY', 'test-key')
    batches = []
    def predict_batch(texts, key):
        batches.append(texts)
        return [mark(text) for text in texts]
    monkeypatch.setattr(jais, 'predict_word_batch', predict_batch)
    with TestClient(app) as client:
        files = {'file': ('arabic.docx', make_docx())}
        local = client.post('/api/document', files=files)
        assert local.headers['X-Tashkeel-Engine'] == 'rawi'
        assert not batches
        result = client.post('/api/document', files=files, headers={'X-Tashkeel-Mode': 'jais'})
        assert batches == [['اللغة العربية', 'جميلة']]
        assert result.status_code == 200
        assert result.headers['X-Tashkeel-Engine'] == 'jais'
        with ZipFile(BytesIO(result.content)) as docx:
            root = etree.fromstring(docx.read('word/document.xml'))
            assert ''.join(root.itertext()) == mark('اللغة العربيةجميلة')
            assert len(list(root.iter(W + 'r'))) == 3
            assert docx.read('word/media/image.png') == b'unchanged-image'



def test_word_uses_rawi_only_for_unavailable_jais_batches(monkeypatch):
    from app import jais

    monkeypatch.setenv('IFM_API_KEY', 'test-key')
    monkeypatch.setattr(jais, 'WORD_BATCH_ITEMS', 1)
    def predict_batch(texts, key):
        # A spelling change in a successful batch must preserve the source.
        return ['لغة أخرى'] if texts == ['اللغة العربية'] else [None]
    monkeypatch.setattr(jais, 'predict_word_batch', predict_batch)
    fallbacks = []
    def fallback(text):
        fallbacks.append(text)
        return mark(text)
    monkeypatch.setattr(jais, 'complete_text', fallback)
    with TestClient(app) as client:
        result = client.post('/api/document', files={'file': ('arabic.docx', make_docx())},
                             headers={'X-Tashkeel-Mode': 'jais'})
        assert result.status_code == 200
        assert result.headers['X-Tashkeel-Engine'] == 'jais+rawi'
        assert fallbacks == ['جميلة']
        with ZipFile(BytesIO(result.content)) as docx:
            root = etree.fromstring(docx.read('word/document.xml'))
            assert ''.join(root.itertext()) == 'اللغة العربية' + mark('جميلة')
