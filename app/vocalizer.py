"""CPU-only, source-preserving adapter for bundled Rawi Ensemble FP32 ONNX.

Upstream checkpoint and Apache-2.0 declaration are pinned in PROVENANCE.json.
No runtime downloads, spelling changes, PyTorch or GPU libraries.
"""

import json
import re
import unicodedata
from pathlib import Path
from threading import Lock

import numpy as np
import onnxruntime as ort

ORT_ERRORS = (
    ort.capi.onnxruntime_pybind11_state.Fail,
    ort.capi.onnxruntime_pybind11_state.NoSuchFile,
    ort.capi.onnxruntime_pybind11_state.InvalidArgument,
    ort.capi.onnxruntime_pybind11_state.InvalidGraph,
    ort.capi.onnxruntime_pybind11_state.RuntimeException,
)

ASSETS = Path(__file__).resolve().parent / "assets/rawi-ensemble"
MAX_INPUT_TOKENS = 1024
MARKS = frozenset("ًٌٍَُِّْ")
ARABIC_LETTER = re.compile(r"[ء-غف-ي]")


class TashkeelUnavailable(Exception):
    pass


def split_marks(text: str) -> list[tuple[str, str]]:
    slots: list[list[str]] = []
    for char in text:
        if char in MARKS:
            if slots:
                slots[-1][1] += char
        else:
            slots.append([char, ""])
    return [(char, marks) for char, marks in slots]


def normalize_marks(marks: str) -> str:
    return "".join(sorted(marks, key=lambda char: 0 if char == "ّ" else 1))


def merge_marks(existing: str, predicted: str) -> str:
    """Keep supplied vowels/sukun/shadda; allow predictions to fill missing marks."""
    if not existing:
        return predicted
    vowels = existing.replace("ّ", "")
    if not vowels:
        return "ّ" + predicted.replace("ّ", "")
    shadda = "ّ" if "ّ" in existing or ("ّ" in predicted and "ْ" not in existing) else ""
    return shadda + vowels


class Vocalizer:
    def __init__(self):
        try:
            vocab = json.loads((ASSETS / "vocab.json").read_text())
            self.input_ids = vocab["char_to_idx"]
            self.unknown_id = self.input_ids.get("<UNK>", 1)
            self.target_marks = {
                value: "".join(mark for mark in key if mark in MARKS)
                for key, value in vocab["diac_to_idx"].items()
            }
            options = ort.SessionOptions()
            options.intra_op_num_threads = 1
            options.inter_op_num_threads = 1
            options.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
            options.enable_cpu_mem_arena = False
            self.session = ort.InferenceSession(
                str(ASSETS / "model.onnx"),
                sess_options=options,
                providers=["CPUExecutionProvider"],
            )
        except (OSError, ValueError, KeyError, RuntimeError, *ORT_ERRORS) as exc:
            raise TashkeelUnavailable("تعذّر تحميل نموذج التشكيل المحلي.") from exc
        self.lock = Lock()

    def complete(self, text: str) -> str:
        slots = split_marks(text)
        chars, positions = [], []
        for index, (char, _) in enumerate(slots):
            # Rawi predicts rich NFD classes, including spelling-restoration marks.
            # Decompose only for inference; output always uses original characters.
            for token in unicodedata.normalize("NFD", char):
                if unicodedata.category(token) == "Mn":
                    continue
                chars.append(self.input_ids.get(token, self.unknown_id))
                positions.append(index)
        if not chars or not any(ARABIC_LETTER.fullmatch(c) for c, _ in slots):
            return text
        if len(chars) > MAX_INPUT_TOKENS:
            raise TashkeelUnavailable("النص أطول من الحد المتاح للتشكيل المحلي.")
        try:
            with self.lock:
                predictions = self.session.run(
                    ["gated_cls"], {"input": np.array([chars], dtype=np.int64)}
                )[0].reshape(-1)
            if len(predictions) != len(positions):
                raise ValueError("Prediction length mismatch")
            output = list(slots)
            for index, prediction in zip(positions, predictions, strict=True):
                char, existing = slots[index]
                if ARABIC_LETTER.fullmatch(char):
                    predicted = self.target_marks[int(prediction)]
                    # The explicitly written hamza-below already determines kasra.
                    # Supplied marks remain authoritative, even if contradictory.
                    if char == 'إ' and not existing:
                        predicted = 'ِ'
                    output[index] = (char, merge_marks(existing, predicted))
            return "".join(char + marks for char, marks in output)
        except (RuntimeError, ValueError, KeyError, *ORT_ERRORS) as exc:
            raise TashkeelUnavailable(
                "تعذّر إكمال التشكيل المحلي. يمكنك تعطيله وفحص النص الأصلي."
            ) from exc


_vocalizer: Vocalizer | None = None
_load_lock = Lock()


def get_vocalizer() -> Vocalizer:
    global _vocalizer
    # lru_cache alone allows multiple simultaneous cold initializations.
    with _load_lock:
        if _vocalizer is None:
            _vocalizer = Vocalizer()
        return _vocalizer


def complete_text(text: str) -> str:
    return get_vocalizer().complete(text)
