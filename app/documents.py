"""Change text nodes only: retain runs, tables, links, images, and section formatting."""
from io import BytesIO
import re
import unicodedata
from zipfile import BadZipFile, ZipFile
from lxml import etree
from app.vocalizer import MAX_INPUT_TOKENS, split_marks

MAX_TEXT = 20_000
MAX_FILE = 5 * 1024 * 1024
W = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
PART = re.compile(r'word/(document|header\d+|footer\d+|footnotes|endnotes)\.xml$')
ARABIC = re.compile(r'[ء-غف-ي]')


def chunks(text, limit=MAX_INPUT_TOKENS):
    """Split at whitespace when possible without dropping any input characters."""
    slots = split_marks(text)
    start = 0
    while start < len(slots):
        # Match the model's NFD token budget, including mixed-script text.
        end, tokens = start, 0
        while end < len(slots):
            cost = sum(unicodedata.category(c) != 'Mn'
                       for c in unicodedata.normalize('NFD', slots[end][0]))
            if tokens + cost > limit:
                break
            tokens += cost
            end += 1
        if end == start:
            raise ValueError('Chunk limit is smaller than one source character.')
        if end < len(slots):
            boundary = next((i + 1 for i in range(end - 1, start, -1)
                             if slots[i][0].isspace() or slots[i][0] in '.!?؟؛،'), None)
            if boundary is not None:
                end = boundary
        yield ''.join(char + marks for char, marks in slots[start:end])
        start = end


def vocalize(text, complete):
    return ''.join(complete(piece) if ARABIC.search(piece) else piece for piece in chunks(text))


def process_docx(data, complete):
    if len(data) > MAX_FILE:
        raise ValueError('الحد الأقصى لحجم الملف ٥ ميغابايت.')
    try:
        source = ZipFile(BytesIO(data))
        entries = source.infolist()
        if (len(entries) > 1000 or len({e.filename for e in entries}) != len(entries)
                or sum(e.file_size for e in entries) > 30 * 1024 * 1024):
            raise ValueError('الملف كبير بعد فك الضغط. جرّب مستندًا أصغر.')
        if 'word/document.xml' not in source.namelist() or '[Content_Types].xml' not in source.namelist():
            raise ValueError('يرجى اختيار مستند Word صالح بصيغة .docx.')
        parts = {}
        groups = []
        total = 0
        for entry in entries:
            if not PART.fullmatch(entry.filename):
                continue
            root = etree.fromstring(source.read(entry), etree.XMLParser(resolve_entities=False, no_network=True))
            if root.getroottree().docinfo.doctype:
                raise ValueError('هذا المستند غير مدعوم.')
            parts[entry.filename] = root
            for paragraph in root.iter(W + 'p'):
                nodes = []
                for node in paragraph.iter(W + 't'):
                    parent = node.getparent()
                    while parent is not None and parent.tag != W + 'p':
                        parent = parent.getparent()
                    if parent is paragraph:
                        nodes.append(node)
                text = ''.join(node.text or '' for node in nodes)
                total += len(text)
                if total > MAX_TEXT:
                    raise ValueError('الحد الأقصى للنص داخل المستند ٢٠٬٠٠٠ حرف.')
                if ARABIC.search(text):
                    groups.append((nodes, text))
        if not groups:
            raise ValueError('لم نعثر على نص عربي في المستند.')
        for nodes, text in groups:
            result = split_marks(vocalize(text, complete))
            original = split_marks(text)
            if [c for c, _ in result] != [c for c, _ in original]:
                raise ValueError('تعذّر الحفاظ على النص الأصلي. لم يتم إنشاء ملف معدّل.')
            # Assign newly predicted marks to the run containing their base letter.
            # Existing marks may sit in a different run; keep those in place.
            predicted = []
            for (_, before), (_, after) in zip(original, result, strict=True):
                remaining = list(after)
                for mark in before:
                    if mark in remaining:
                        remaining.remove(mark)
                predicted.append(''.join(remaining))
            position = -1
            for node in nodes:
                output = []
                for char in node.text or '':
                    if char not in 'ًٌٍَُِّْ':
                        position += 1
                        output.append(char + predicted[position])
                    else:
                        output.append(char)
                node.text = ''.join(output)
        output = BytesIO()
        with ZipFile(output, 'w') as target:
            for entry in entries:
                content = (etree.tostring(parts[entry.filename], xml_declaration=True, encoding='UTF-8', standalone=True)
                           if entry.filename in parts else source.read(entry))
                target.writestr(entry, content)
        return output.getvalue()
    except (BadZipFile, etree.XMLSyntaxError, KeyError, RuntimeError, NotImplementedError) as exc:
        raise ValueError('تعذّر قراءة المستند. احفظه بصيغة .docx غير محمية ثم أعد المحاولة.') from exc
