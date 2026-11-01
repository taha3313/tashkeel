"""CPU-only adapter for libtashkeel's bundled ONNX model (MIT licensed).

Token/hint layout follows mush42/libtashkeel, pinned in assets/PROVENANCE.json.
No network downloads, PyTorch, GPU libraries or meter-guided vowel search.
"""

import json
import re
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

ASSETS = Path(__file__).resolve().parent / "assets/libtashkeel"
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
            self.input_ids = json.loads((ASSETS / "input_id_map.json").read_text())
            self.hint_ids = json.loads((ASSETS / "hint_id_map.json").read_text())
            self.target_marks = {
                value: key
                for key, value in json.loads((ASSETS / "target_id_map.json").read_text()).items()
                if key != "_"
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
        except (OSError, ValueError, RuntimeError, *ORT_ERRORS) as exc:
            raise TashkeelUnavailable("تعذّر تحميل نموذج التشكيل المحلي.") from exc
        # Serialize inference to bound concurrent workspace memory on 512 MB hosts.
        self.lock = Lock()

    def complete(self, text: str) -> str:
        slots = split_marks(text)
        chars, hints, positions = [], [], []
        for index, (char, marks) in enumerate(slots):
            token = "#" if char.isdigit() else char
            if token not in self.input_ids:
                continue
            chars.append(self.input_ids[token])
            hints.append(self.hint_ids.get(normalize_marks(marks), 1))
            positions.append(index)
        if not chars:
            return text
        if len(chars) > 480:
            raise TashkeelUnavailable("النص أطول من الحد المتاح للتشكيل المحلي.")
        feed = {
            "char_inputs": np.array([chars], dtype=np.int64),
            "diac_inputs": np.array([hints], dtype=np.int64),
            "input_lengths": np.array([len(chars)], dtype=np.int64),
        }
        try:
            with self.lock:
                predictions = self.session.run(None, feed)[0].reshape(-1)
            if len(predictions) != len(positions):
                raise ValueError("Prediction length mismatch")
            output = list(slots)
            for index, prediction in zip(positions, predictions, strict=True):
                char, existing = slots[index]
                if ARABIC_LETTER.fullmatch(char):
                    predicted = self.target_marks.get(int(prediction), "")
                    output[index] = (char, merge_marks(existing, predicted))
            return "".join(char + marks for char, marks in output)
        except (RuntimeError, ValueError, *ORT_ERRORS) as exc:
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
