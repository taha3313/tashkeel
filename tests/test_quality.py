import csv
import json
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

import pytest

from tools.arabic_quality import (
    apply_review, evaluate, export_training, group_id, measure,
    partition, preservation, read_cases, write_jsonl,
)


def case(key='one', **changes):
    row = {'id': key, 'input': 'كتاب', 'expected': 'كِتَابٌ', 'baseline': 'كِتَابٍ',
           'split': 'development', 'categories': [], 'source': {'kind': 'original_example'},
           'review': {'status': 'pending', 'reviewer': None}, 'training_allowed': True}
    row.update(changes)
    return row


@pytest.mark.parametrize(('gold', 'predicted'), [
    ('عَلَّمَ', 'عَلَّمَ'),
    ('كِتَابًا', 'كِتَاباً'),
])
def test_equivalent_mark_order_and_fathatan_are_not_errors(gold, predicted):
    assert measure(gold, predicted)[0]['errors'] == 0


def test_separates_internal_vowels_endings_and_shadda():
    ending, mistakes = measure('كِتَابٌ', 'كِتَابٍ')
    assert ending['errors'] == ending['word_ending_errors'] == ending['tanwin_errors'] == 1
    assert ending['word_internal_errors'] == 0
    assert mistakes[0]['word'] == 'كتاب'
    internal, _ = measure('كِتَابٌ', 'كَتَابٌ')
    assert internal['word_internal_errors'] == 1
    assert internal['word_ending_errors'] == 0
    assert measure('عَلَّمَ', 'عَلَمَ')[0]['shadda_errors'] == 1


def test_preservation_checks_letters_whitespace_digits_and_supplied_marks():
    assert preservation('عَلْم 12\n', 'عَلْمٌ 12\n') == (True, True)
    assert preservation('عَلْم 12\n', 'عَلْمٌ 13\n') == (False, False)
    assert preservation('عَلْم 12\n', 'عَلْمٌ 12') == (False, False)
    assert preservation('عَلْم', 'عِلْم') == (True, False)
    # NFC equivalence for scoring does not grant permission to rewrite source.
    assert preservation('أحمد', 'أَحْمَدُ') == (False, False)


def test_missing_results_count_as_errors():
    result = evaluate([case()], {})
    assert result['samples'] == result['missing'] == 1
    assert result['scores']['candidate']['DER'] == 100
    assert result['source_violations'] == 1


def test_improvement_totals_do_not_hide_an_individual_regression():
    first = case('fixed')
    second = case('broken', input='قلم', expected='قَلَمٌ', baseline='قَلَمٌ')
    result = evaluate([first, second], {'fixed': 'كِتَابٌ', 'broken': 'قَلَمٍ'})
    assert result['scores']['baseline']['errors'] == result['scores']['candidate']['errors']
    assert result['outcomes'] == {'improved': 1, 'regressed': 1}


def test_duplicate_variants_cannot_leak_between_splits(tmp_path):
    assert group_id('كَتَبَ  الطالب') == group_id('كتب الطالب')
    assert partition('كَتَبَ  الطالب') == partition('كتب الطالب')
    path = tmp_path / 'cases.jsonl'
    write_jsonl(path, [case('a'), case('b', split='test')])
    with pytest.raises(ValueError, match='crosses splits'):
        read_cases(path)


def test_rejects_changed_reference_letters_and_duplicate_ids(tmp_path):
    path = tmp_path / 'cases.jsonl'
    write_jsonl(path, [case(expected='قَلَمٌ')])
    with pytest.raises(ValueError, match='changes source'):
        read_cases(path)
    write_jsonl(path, [case(), case()])
    with pytest.raises(ValueError, match='Duplicate case'):
        read_cases(path)


def test_training_export_excludes_benchmarks_test_data_and_unreviewed_rows(tmp_path):
    approved = case('approved', review={'status': 'approved', 'reviewer': 'Arabic reviewer'})
    benchmark = deepcopy(approved)
    benchmark.update(id='benchmark', source={'kind': 'published_benchmark'})
    heldout = deepcopy(approved)
    heldout.update(id='heldout', split='test')
    validation = deepcopy(approved)
    validation.update(id='validation', split='validation')
    denied = deepcopy(approved)
    denied.update(id='denied', training_allowed=False)
    out = tmp_path / 'training.jsonl'
    assert export_training([approved, benchmark, heldout, validation, denied, case()], out) == 1
    assert json.loads(out.read_text())['id'] == 'approved'
    out.unlink()
    with pytest.raises(ValueError, match='No approved'):
        export_training([benchmark, heldout, case()], out)
    assert not out.exists()


def test_review_import_requires_named_reviewer_and_keeps_audit_reference(tmp_path):
    source = tmp_path / 'cases.jsonl'
    write_jsonl(source, [case()])
    review = tmp_path / 'review.csv'
    row = {'id': 'one', 'split': 'development', 'input': 'كتاب', 'baseline': 'كِتَابٍ',
           'expected': 'كِتَابٌ', 'status': 'approved', 'reviewer': '', 'notes': 'checked'}
    def write():
        with review.open('w', newline='') as file:
            writer = csv.DictWriter(file, fieldnames=list(row))
            writer.writeheader()
            writer.writerow(row)
    args = SimpleNamespace(cases=source, csv=review, output=tmp_path / 'reviewed.jsonl')
    write()
    with pytest.raises(ValueError, match='reviewer name'):
        apply_review(args)
    row['reviewer'] = 'Arabic reviewer'
    write()
    apply_review(args)
    result = read_cases(args.output)[0]
    assert result['original_reference'] == 'كِتَابٌ'
    assert result['review']['reviewer'] == 'Arabic reviewer'
    row['input'] = 'قلم'
    write()
    with pytest.raises(ValueError, match='protected fields'):
        apply_review(args)


def test_frozen_quality_cases_have_isolated_groups_and_valid_manifest():
    import hashlib
    root = Path(__file__).resolve().parent.parent / 'quality'
    cases = read_cases(root / 'cases.jsonl')
    manifest = json.loads((root / 'cases.manifest.json').read_text())
    assert len(cases) == manifest['samples'] >= 150
    assert {row['split'] for row in cases} == {'development', 'validation', 'test'}
    assert hashlib.sha256((root / 'cases.jsonl').read_bytes()).hexdigest() == manifest['dataset_sha256']
    assert all(not c['training_allowed'] for c in cases if c['source']['kind'] == 'published_benchmark')


def test_ambiguous_references_do_not_count_as_candidate_failures():
    ambiguous = case('ambiguous', review={'status': 'ambiguous', 'reviewer': 'Arabic reviewer'})
    result = evaluate([case(), ambiguous], {'one': 'كِتَابٌ'})
    assert result['samples'] == result['review_excluded'] == 1
    assert result['missing'] == 0
    with pytest.raises(ValueError, match='No scorable'):
        evaluate([ambiguous], {})


def test_hamza_experiment_preserves_supplied_marks_and_source():
    from tools.quality_candidates import explicit_hamza_kasra
    assert explicit_hamza_kasra('إلى', 'إلَى') == 'إِلَى'
    assert explicit_hamza_kasra('إَلى', 'إَلَى') == 'إَلَى'
    assert explicit_hamza_kasra('إلى 12\n', 'إلَى 12\n') == 'إِلَى 12\n'
    with pytest.raises(ValueError, match='altered source'):
        explicit_hamza_kasra('إلى', 'إلّا')
