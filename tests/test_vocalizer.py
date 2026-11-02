import hashlib
import json

import numpy as np
import pytest

from app.vocalizer import ASSETS, MAX_INPUT_TOKENS, TashkeelUnavailable, Vocalizer, split_marks


@pytest.fixture(scope='module')
def model():
    return Vocalizer()


def test_bundled_artifacts_match_provenance():
    provenance = json.loads((ASSETS / 'PROVENANCE.json').read_text())
    assert provenance['precision'] == 'FP32'
    for name, expected in provenance['files'].items():
        data = (ASSETS / name).read_bytes()
        assert len(data) == expected['bytes']
        assert hashlib.sha256(data).hexdigest() == expected['sha256']


@pytest.mark.parametrize('text', [
    '  زار أحمد تونس؛ 2026 / report.docx 🙂.\n',
    'اللُّغة العَرَبية جميلة، مَرْيم تتعلم.',
    'أحمد وﻻ وعربي 한글 🙂',
    'عَُ نص به علامات مقدمة كما هي',
])
def test_source_characters_and_supplied_marks_are_preserved(model, text):
    original = split_marks(text)
    result = split_marks(model.complete(text))
    assert [c for c, _ in result] == [c for c, _ in original]
    for (_, supplied), (_, predicted) in zip(original, result, strict=True):
        assert set(supplied) <= set(predicted)


def test_non_arabic_is_unchanged(model):
    assert model.complete('hello\n123 🙂 한글') == 'hello\n123 🙂 한글'


def test_bounded_model_input(model):
    with pytest.raises(TashkeelUnavailable):
        model.complete('ع' * (MAX_INPUT_TOKENS + 1))


def test_spelling_restoration_is_not_applied():
    model = object.__new__(Vocalizer)
    model.input_ids = {'ا': 1}
    model.unknown_id = 0
    model.target_marks = {1: 'َ'}
    from threading import Lock
    model.lock = Lock()

    class Session:
        def run(self, names, feed):
            assert names == ['gated_cls']
            assert set(feed) == {'input'}
            return [np.array([[1]], dtype=np.int64)]

    model.session = Session()
    assert model.complete('أ') == 'أَ'


def test_long_context_accepts_complete_sentence(model):
    text = ('ذهب الطفل إلى المدرسة. ' * 30).strip()
    result = model.complete(text)
    assert [c for c, _ in split_marks(result)] == [c for c, _ in split_marks(text)]


def test_explicit_hamza_below_supplies_kasra_without_overriding_user_marks():
    from threading import Lock
    model = object.__new__(Vocalizer)
    model.input_ids = {'ا': 1}
    model.unknown_id = 0
    model.target_marks = {1: 'َ'}
    model.lock = Lock()
    class Session:
        def run(self, names, feed):
            return [np.array([[1]], dtype=np.int64)]
    model.session = Session()
    assert model.complete('إ') == 'إِ'
    assert model.complete('إَ') == 'إَ'
    assert model.complete('أ') == 'أَ'
