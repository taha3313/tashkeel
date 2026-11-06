"""Hosted Jais inference with source-preserving transfer of ordinary harakat."""

import json
import os
import re
from collections import defaultdict
from http.client import HTTPException, HTTPSConnection
from time import monotonic

from app.vocalizer import ARABIC_LETTER, MARKS, complete_text, split_marks

MODEL = "IFM/Jais-3-MoVA-36B-A4B"
PROMPT = (
    "أضف التشكيل العربي الكامل إلى النص، بما في ذلك حركات أواخر الكلمات. "
    "حافظ على كل حرف كما هو وعلى التشكيل الموجود والمسافات وعلامات الترقيم وفواصل الأسطر. "
    "أعد النص المشكول وحده دون أي شرح أو تنسيق."
)
REQUEST_BUDGET = 24
CHUNK_TIMEOUT = 12
MAX_RESPONSE_BYTES = 96 * 1024

WORD = re.compile(ARABIC_LETTER.pattern + "+")


def valid_marks(marks: str) -> bool:
    return (
        len(marks) == len(set(marks))
        and len(marks.replace("ّ", "")) <= 1
        and not ("ّ" in marks and "ْ" in marks)
    )


def apply_marks(char: str, existing: str, predicted: str) -> str:
    if not ARABIC_LETTER.fullmatch(char) or not valid_marks(predicted):
        return char + existing
    additions = "".join(mark for mark in predicted if mark not in existing)
    merged = existing + additions
    return char + (merged if valid_marks(merged) else existing)


def word_contexts(slots):
    words = list(WORD.finditer("".join(char for char, _ in slots)))
    contexts = defaultdict(list)
    for index, word in enumerate(words):
        before = words[index - 1][0] if index else None
        after = words[index + 1][0] if index + 1 < len(words) else None
        contexts[before, word[0], after].append(word.span())
    return contexts


def recover_harakat(text: str, prediction: str, fallback=complete_text) -> tuple[str, str]:
    source = split_marks(text)
    candidate = split_marks(prediction)
    source_indices = [i for i, (char, _) in enumerate(source) if not char.isspace()]
    candidate_letters = [(char, marks) for char, marks in candidate if not char.isspace()]
    if [source[i][0] for i in source_indices] == [char for char, _ in candidate_letters]:
        output = [char + marks for char, marks in source]
        for i, (_, predicted) in zip(source_indices, candidate_letters, strict=True):
            output[i] = apply_marks(*source[i], predicted)
        return "".join(output), "jais"

    local = split_marks(fallback(text))
    output = [char + marks for char, marks in local]
    contexts = word_contexts(candidate)
    applied = False
    for key, locations in word_contexts(source).items():
        matches = contexts.get(key, [])
        if len(locations) != 1 or len(matches) != 1:
            continue
        (start, end), (other_start, other_end) = locations[0], matches[0]
        for i, (_, predicted) in zip(range(start, end), candidate[other_start:other_end], strict=True):
            output[i] = apply_marks(*source[i], predicted)
        applied = True
    return "".join(output), "jais+rawi" if applied else "rawi"


def predict(text: str, key: str, timeout: float) -> str | None:
    payload = json.dumps({
        "model": MODEL,
        "temperature": 0,
        "max_tokens": 1600,
        "chat_template_kwargs": {"reasoning_effort": "low"},
        "messages": [
            {"role": "system", "content": PROMPT},
            {"role": "user", "content": text},
        ],
    }, ensure_ascii=False).encode()
    conn = HTTPSConnection("api.ifm.ai", timeout=timeout)
    try:
        conn.request("POST", "/v1/chat/completions", body=payload, headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
        })
        response = conn.getresponse()
        if response.status != 200:
            return None
        body = response.read(MAX_RESPONSE_BYTES + 1)
        if len(body) > MAX_RESPONSE_BYTES:
            return None
        choice = json.loads(body)["choices"][0]
        content = choice["message"]["content"]
        if choice["finish_reason"] == "stop" and isinstance(content, str) and content.strip():
            return content
    except (OSError, HTTPException, ValueError, KeyError, IndexError, TypeError):
        # Provider failures use Rawi. Avoid logging credentials or document text.
        return None
    finally:
        conn.close()
    return None


class JaisRequest:
    """Share one remote budget and fallback state across all chunks of a request."""

    def __init__(self, enabled: bool):
        self.key = os.getenv("IFM_API_KEY", "").strip() if enabled else ""
        self.deadline = monotonic() + REQUEST_BUDGET
        self.engines: set[str] = set()

    @property
    def engine(self) -> str:
        if "jais+rawi" in self.engines or self.engines == {"jais", "rawi"}:
            return "jais+rawi"
        return "jais" if "jais" in self.engines else "rawi"

    def complete(self, text: str) -> str:
        remaining = self.deadline - monotonic()
        if self.key and remaining > 0:
            prediction = predict(text, self.key, min(remaining, CHUNK_TIMEOUT))
            if prediction is not None:
                output, engine = recover_harakat(text, prediction)
                self.engines.add(engine)
                return output
            self.key = ""
        self.engines.add("rawi")
        return complete_text(text)
