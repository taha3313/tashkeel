"""Offline Arabic quality dataset, regression scoring, and reviewed-data export."""
import argparse
import collections
import csv
import difflib
import hashlib
import json
import re
import subprocess
import sys
import unicodedata
from pathlib import Path

MARKS = frozenset('ًٌٍَُِّْ')
ARABIC = re.compile('[ء-غف-ي]')
WORDS = re.compile('[ء-غف-ي]+')
ROOT = Path(__file__).resolve().parent.parent


def slots(text):
    out = []
    for char in unicodedata.normalize('NFC', text):
        if char == 'ٰ':
            continue
        if char in MARKS:
            if out:
                out[-1][1] += char
        else:
            out.append([char, ''])
    # Both common fathatan placements before a final silent alef are equivalent.
    for i, (char, marks) in enumerate(out):
        if (i and char == 'ا' and marks == 'ً' and not out[i - 1][1]
                and ARABIC.fullmatch(out[i - 1][0])
                and (i + 1 == len(out) or not ARABIC.fullmatch(out[i + 1][0]))):
            out[i][1] = ''
            out[i - 1][1] = 'ً'
    return [(char, ''.join(sorted(marks))) for char, marks in out]


def bare(text):
    return ''.join(char for char, _ in slots(text))


def group_id(text):
    # Whitespace variants and differently vocalized copies cannot cross splits.
    normalized = ' '.join(bare(text).split())
    return hashlib.sha256(normalized.encode()).hexdigest()


def partition(text):
    bucket = int(group_id(text)[:8], 16) % 100
    return 'development' if bucket < 70 else 'validation' if bucket < 85 else 'test'


def measure(reference, prediction):
    gold, pred = slots(reference), slots(prediction)
    gb, pb = bare(reference), bare(prediction)
    mapping = {}
    for tag, a, b, x, _ in difflib.SequenceMatcher(a=gb, b=pb, autojunk=False).get_opcodes():
        if tag == 'equal':
            mapping.update({a + i: x + i for i in range(b - a)})
    words = [list(range(m.start(), m.end())) for m in WORDS.finditer(gb)]
    endings = {word[-1] for word in words}
    for word in words:
        if len(word) > 1 and gold[word[-1]][0] == 'ا' and gold[word[-2]][1] == 'ً':
            endings.add(word[-2])
    counts = collections.Counter(samples=1, words=len(words), source_changes=int(gb != pb))
    mistakes = []
    wrong = set()
    for i, (char, expected) in enumerate(gold):
        if not ARABIC.fullmatch(char):
            continue
        counts['letters'] += 1
        counts['ending_letters' if i in endings else 'internal_letters'] += 1
        actual = pred[mapping[i]][1] if i in mapping else None
        if actual == expected:
            continue
        wrong.add(i)
        counts['errors'] += 1
        kind = 'word_ending' if i in endings else 'word_internal'
        counts[kind + '_errors'] += 1
        if ('ّ' in expected) != ('ّ' in (actual or '')):
            counts['shadda_errors'] += 1
        if set('ًٌٍ') & set(expected + (actual or '')):
            counts['tanwin_errors'] += 1
        word = next((w for w in words if i in w), [i])
        mistakes.append({'position': i, 'word': gb[word[0]:word[-1] + 1],
                         'letter': char, 'expected': expected, 'predicted': actual,
                         'kind': kind})
    counts['word_errors'] = sum(bool(wrong.intersection(word)) for word in words)
    counts['invalid_marks'] = sum(len(m) != len(set(m)) or len(m.replace('ّ', '')) > 1
                                  or ('ّ' in m and 'ْ' in m) for _, m in pred)
    return counts, mistakes


def preservation(original, prediction):
    # Stricter than metric normalization: retain exact supplied source characters.
    def original_slots(text):
        result = []
        for char in text:
            if char in MARKS and result:
                result[-1][1] += char
            else:
                result.append([char, ''])
        return result
    before, after = original_slots(original), original_slots(prediction)
    if [c for c, _ in before] != [c for c, _ in after]:
        return False, False
    return True, all(set(supplied) <= set(actual)
                     for (_, supplied), (_, actual) in zip(before, after, strict=True))


def percentages(counts):
    result = dict(counts)
    for name, num, den in [('DER', 'errors', 'letters'), ('WER', 'word_errors', 'words'),
                           ('ending_DER_proxy', 'word_ending_errors', 'ending_letters'),
                           ('internal_DER', 'word_internal_errors', 'internal_letters')]:
        result[name] = 100 * counts[num] / counts[den] if counts[den] else None
    return result


def read_cases(path):
    cases = [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]
    ids, groups = set(), {}
    for case in cases:
        if case['id'] in ids:
            raise ValueError('Duplicate case id: ' + case['id'])
        ids.add(case['id'])
        if bare(case['input']) != bare(case['expected']):
            raise ValueError('Reference changes source: ' + case['id'])
        group = group_id(case['input'])
        if case.get('group_id', group) != group:
            raise ValueError('Incorrect group id: ' + case['id'])
        if groups.setdefault(group, case['split']) != case['split']:
            raise ValueError('Duplicate text crosses splits: ' + case['id'])
        if case['split'] not in {'development', 'validation', 'test'}:
            raise ValueError('Unknown split: ' + case['id'])
    return cases


def write_jsonl(path, rows):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows))



def write_report(path, report):
    # Keep per-case records on one line so data changes remain reviewable in Git.
    summary = {k: v for k, v in report.items() if k != 'details'}
    prefix = json.dumps(summary, ensure_ascii=False, indent=2).rstrip()[:-1].rstrip()
    details = ',\n'.join('    ' + json.dumps(row, ensure_ascii=False, separators=(',', ':'))
                         for row in report.get('details', []))
    Path(path).write_text(prefix + ',\n  "details": [\n' + details + '\n  ]\n}\n')


def baseline_predict(text):
    sys.path.insert(0, str(ROOT))
    from app.documents import vocalize
    from app.vocalizer import complete_text
    return vocalize(text, complete_text)


def evaluate(cases, predictions):
    excluded = sum(c['review']['status'] in {'ambiguous', 'rejected'} for c in cases)
    cases = [c for c in cases if c['review']['status'] not in {'ambiguous', 'rejected'}]
    if not cases:
        raise ValueError('No scorable cases after review exclusions')
    totals = {name: collections.Counter() for name in ['baseline', 'candidate']}
    details = []
    for case in cases:
        output = predictions.get(case['id'])
        # An absent prediction is scored as omitted output, never as a fallback win.
        expected = case['expected']
        old, _ = measure(expected, case['baseline'])
        new, mistakes = measure(expected, output or '')
        for name, counts in [('baseline', old), ('candidate', new)]:
            totals[name].update(counts)
        source_ok, marks_ok = preservation(case['input'], output or '')
        details.append({'id': case['id'], 'split': case['split'],
                        'baseline_errors': old['errors'], 'candidate_errors': new['errors'],
                        'outcome': 'improved' if new['errors'] < old['errors'] else
                                   'regressed' if new['errors'] > old['errors'] else 'unchanged',
                        'missing': output is None, 'source_preserved': source_ok,
                        'supplied_marks_preserved': marks_ok, 'mistakes': mistakes})
    return {'samples': len(cases), 'review_excluded': excluded, 'scores': {k: percentages(v) for k, v in totals.items()},
            'outcomes': dict(collections.Counter(r['outcome'] for r in details)),
            'missing': sum(r['missing'] for r in details),
            'source_violations': sum(not r['source_preserved'] for r in details),
            'supplied_mark_violations': sum(not r['supplied_marks_preserved'] for r in details),
            'reviewed_cases': sum(c['review']['status'] == 'approved' for c in cases),
            'details': details}


def build(args):
    raw = Path(args.source).read_bytes()
    rows = json.loads(raw)
    excluded = set()
    for file in args.exclude:
        for row in json.loads(Path(file).read_text()):
            excluded.add(group_id(row['input']))
    if args.exclude_groups:
        excluded.update(json.loads(Path(args.exclude_groups).read_text()))
    groups = collections.defaultdict(list)
    for entry in rows:
        row = entry['row']
        expected = unicodedata.normalize('NFC', row['output'])
        text = bare(expected)
        if not text.strip() or group_id(text) in excluded:
            continue
        groups[row['filename']].append((entry['row_idx'], text, expected))
    cases, seen = [], set()
    for filename, rows in sorted(groups.items()):
        selected = 0
        ordered = sorted(rows, key=lambda r: hashlib.sha256(('error-set-v1:' + str(r[0])).encode()).hexdigest())
        for index, text, expected in ordered:
            group = group_id(text)
            if group in seen:
                continue
            output = baseline_predict(text)
            counts, mistakes = measure(expected, output)
            if not counts['errors']:
                continue
            seen.add(group)
            cases.append({'id': 'sadeed-' + str(index), 'group_id': group,
                          'split': partition(text), 'input': text, 'baseline': output,
                          'expected': expected, 'baseline_errors': counts['errors'],
                          'categories': sorted({m['kind'] for m in mistakes} |
                                               ({'shadda'} if counts['shadda_errors'] else set()) |
                                               ({'tanwin'} if counts['tanwin_errors'] else set())),
                          'source': {'kind': 'published_benchmark', 'dataset': 'Misraj/SadeedDiac-25',
                                     'revision': args.revision, 'filename': filename, 'row': index,
                                     'license': 'CC-BY-NC-SA-4.0'},
                          'review': {'status': 'pending', 'reviewer': None},
                          'training_allowed': False})
            selected += 1
            if selected == args.per_source:
                break
        if selected != args.per_source:
            raise ValueError(f'Only {selected} failure cases available from {filename}')
        print(f'{filename}: {selected} reference mismatches', flush=True)
    if args.seed:
        for seed in json.loads(Path(args.seed).read_text()):
            group = group_id(seed['input'])
            if group in seen or group in excluded:
                raise ValueError('Duplicate or excluded seed: ' + seed['id'])
            seen.add(group)
            output = baseline_predict(seed['input'])
            counts, _ = measure(seed['expected'], output)
            cases.append({**seed, 'group_id': group, 'split': partition(seed['input']),
                          'baseline': output, 'baseline_errors': counts['errors'],
                          'review': {'status': 'pending', 'reviewer': None}})
    write_jsonl(args.output, cases)
    read_cases(args.output)
    manifest = {'schema_version': 1, 'selection': 'error-set-v1; hash-ranked per source; first reference mismatches',
                'selection_bias': 'failure-enriched challenge set, not a general accuracy benchmark',
                'source_sha256': hashlib.sha256(raw).hexdigest(),
                'dataset_sha256': hashlib.sha256(Path(args.output).read_bytes()).hexdigest(),
                'samples': len(cases), 'splits': dict(collections.Counter(c['split'] for c in cases)),
                'failure_cases': sum(c['baseline_errors'] > 0 for c in cases),
                'correct_controls': sum(c['baseline_errors'] == 0 for c in cases),
                'excluded_groups': len(excluded), 'reviewed_cases': 0}
    from app.vocalizer import ASSETS
    manifest['baseline_commit'] = subprocess.check_output(
        ['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    manifest['baseline_code_sha256'] = {
        name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
        for name in ['app/vocalizer.py', 'app/documents.py']}
    manifest['baseline_model_sha256'] = hashlib.sha256((ASSETS / 'model.onnx').read_bytes()).hexdigest()
    Path(args.output).with_suffix('.manifest.json').write_text(json.dumps(manifest, indent=2))


def review_csv(args):
    cases = read_cases(args.cases)
    with Path(args.output).open('w', newline='', encoding='utf-8-sig') as file:
        fields = ['id', 'split', 'input', 'baseline', 'expected', 'categories', 'status', 'reviewer', 'notes', 'provenance']
        writer = csv.DictWriter(file, fieldnames=fields)
        writer.writeheader()
        for case in cases:
            writer.writerow({**{k: case[k] for k in fields[:5]},
                             'categories': ', '.join(case['categories']),
                             'status': case['review']['status'],
                             'reviewer': case['review'].get('reviewer') or '', 'notes': '',
                             'provenance': json.dumps(case['source'], ensure_ascii=False)})



def apply_review(args):
    cases = read_cases(args.cases)
    known = {case['id']: case for case in cases}
    seen = set()
    with Path(args.csv).open(newline='', encoding='utf-8-sig') as file:
        for row in csv.DictReader(file):
            key = row['id']
            if key not in known or key in seen:
                raise ValueError('Unknown or duplicate review id: ' + key)
            seen.add(key)
            case = known[key]
            if any(row[field] != case[field] for field in ['input', 'baseline', 'split']):
                raise ValueError('Review changed protected fields: ' + key)
            status = row['status'].strip()
            reviewer = row['reviewer'].strip()
            if status not in {'pending', 'approved', 'rejected', 'ambiguous'}:
                raise ValueError('Unknown review status: ' + key)
            if status != 'pending' and not reviewer:
                raise ValueError('A reviewed decision needs a reviewer name: ' + key)
            if row['expected'] != case['expected'] and status != 'approved':
                raise ValueError('An edited reference needs approval: ' + key)
            source_ok, marks_ok = preservation(case['input'], row['expected'])
            if not source_ok or not marks_ok:
                raise ValueError('Review changes source or supplied marks: ' + key)
            case.setdefault('original_reference', case['expected'])
            case['expected'] = row['expected']
            case['review'] = {'status': status, 'reviewer': reviewer or None,
                              'notes': row.get('notes', '')}
    write_jsonl(args.output, cases)
    read_cases(args.output)
    print('Imported reviews:', len(seen))


def add_case(args):
    cases = read_cases(args.cases)
    row = json.loads(Path(args.example).read_text())
    source_ok, marks_ok = preservation(row['input'], row['expected'])
    if not source_ok or not marks_ok:
        raise ValueError('Expected correction must preserve source and supplied marks')
    group = group_id(row['input'])
    if any(group_id(case['input']) == group for case in cases):
        raise ValueError('This text is already present; review its existing case')
    if row['source']['kind'] not in {'user_example', 'original_example'}:
        raise ValueError('Use build for published benchmarks')
    cases.append({'id': 'example-' + group[:16], 'group_id': group,
                  'split': partition(row['input']), 'input': row['input'],
                  'baseline': baseline_predict(row['input']), 'expected': row['expected'],
                  'categories': row.get('categories', []), 'source': row['source'],
                  'review': {'status': 'pending', 'reviewer': None},
                  'training_allowed': row.get('training_allowed') is True})
    write_jsonl(args.output, cases)
    read_cases(args.output)
    print('Added', cases[-1]['id'], 'to', cases[-1]['split'])


def export_training(cases, output):
    eligible = [c for c in cases if c['split'] == 'development'
                and c['source']['kind'] != 'published_benchmark'
                and c.get('training_allowed') is True
                and c['review']['status'] == 'approved' and c['review'].get('reviewer')]
    if not eligible:
        raise ValueError('No approved, training-eligible development cases. No export written.')
    write_jsonl(output, [{'id': c['id'], 'input': c['input'], 'output': c['expected'],
                          'source': c['source'], 'reviewer': c['review']['reviewer']} for c in eligible])
    return len(eligible)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    p = sub.add_parser('build')
    p.add_argument('--source', required=True)
    p.add_argument('--revision', required=True)
    p.add_argument('--exclude', action='append', default=[])
    p.add_argument('--exclude-groups', help='Frozen normalized text group ids to reserve')
    p.add_argument('--seed', help='Task-authored diagnostic JSON array')
    p.add_argument('--per-source', type=int, default=50)
    p.add_argument('--output', required=True)
    p = sub.add_parser('review-csv')
    p.add_argument('--cases', required=True)
    p.add_argument('--output', required=True)
    p = sub.add_parser('apply-review')
    p.add_argument('--cases', required=True)
    p.add_argument('--csv', required=True)
    p.add_argument('--output', required=True)
    p = sub.add_parser('add')
    p.add_argument('--cases', required=True)
    p.add_argument('--example', required=True, help='Local JSON: input, expected, source, training_allowed')
    p.add_argument('--output', required=True)
    p = sub.add_parser('evaluate')
    p.add_argument('--cases', required=True)
    p.add_argument('--split', choices=['development', 'validation', 'test', 'all'], default='validation')
    p.add_argument('--candidate', choices=['explicit-hamza'], help='Offline experimental rule; not production')
    p.add_argument('--predictions', help='JSONL with id/output; absent means current local Rawi')
    p.add_argument('--output', required=True)
    p.add_argument('--check', action='store_true', help='Fail on missing output, source/mark changes, invalid marks, or any regression')
    p = sub.add_parser('export-training')
    p.add_argument('--cases', required=True)
    p.add_argument('--output', required=True)
    args = parser.parse_args()
    try:
        if args.command == 'build':
            build(args)
        elif args.command == 'review-csv':
            review_csv(args)
        elif args.command == 'apply-review':
            apply_review(args)
        elif args.command == 'add':
            add_case(args)
        elif args.command == 'export-training':
            print('Exported', export_training(read_cases(args.cases), args.output), 'reviewed cases')
        else:
            cases = [c for c in read_cases(args.cases) if args.split == 'all' or c['split'] == args.split]
            if not cases:
                raise ValueError('Selected split contains no cases')
            if args.predictions:
                pairs = [json.loads(l) for l in Path(args.predictions).read_text().splitlines() if l.strip()]
                if len({p['id'] for p in pairs}) != len(pairs):
                    raise ValueError('Duplicate prediction ids')
                predictions = {p['id']: p['output'] for p in pairs}
            else:
                predictions = {c['id']: baseline_predict(c['input']) for c in cases}
            if args.candidate:
                sys.path.insert(0, str(ROOT))
                from tools.quality_candidates import explicit_hamza_kasra
                predictions = {c['id']: explicit_hamza_kasra(c['input'], predictions[c['id']])
                               for c in cases if c['id'] in predictions}
            result = evaluate(cases, predictions)
            write_report(args.output, result)
            print(json.dumps({k: v for k, v in result.items() if k != 'details'}, ensure_ascii=False))
            if args.check and (result['missing'] or result['source_violations'] or result['supplied_mark_violations']
                              or result['outcomes'].get('regressed') or result['scores']['candidate'].get('invalid_marks')):
                raise ValueError('Candidate failed regression/preservation checks; see the report')
    except (ValueError, KeyError) as error:
        parser.exit(2, str(error) + '\n')


if __name__ == '__main__':
    main()
