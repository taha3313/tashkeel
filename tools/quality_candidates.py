"""Experimental rules for offline evaluation, never imported by the service."""
from tools.arabic_quality import preservation


def explicit_hamza_kasra(original, predicted):
    """An explicit إ suggests kasra; supplied marks always take precedence.

    This candidate is deliberately isolated from app/. Released references can
    omit this mark, so it must pass both linguistic review and regression checks.
    """
    if not preservation(original, predicted)[0]:
        raise ValueError('Cannot apply a rule to altered source text')
    def split(text):
        out = []
        for char in text:
            if char in 'ًٌٍَُِّْ' and out:
                out[-1][1] += char
            else:
                out.append([char, ''])
        return out
    source, output = split(original), split(predicted)
    for (char, supplied), slot in zip(source, output, strict=True):
        if char == 'إ' and not supplied:
            slot[1] = 'ِ'
    return ''.join(char + marks for char, marks in output)
