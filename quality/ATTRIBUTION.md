# Dataset attribution and scope

The 150 `published_benchmark` rows in `cases.jsonl`, their supplied references,
and adaptations come from **Misraj/SadeedDiac-25**, observed revision
`aa311213e44e4cab6cc3f2848daacd753adc1ce1`.

Authors: Zeina Aldallal, Sara Chrouf, Khalil Hennara, Mohamed Motaism Hamed,
Muhammad Hreden and Safwan AlModhayan. *Sadeed: Advancing Arabic Diacritization
Through Small Language Model*, 2025.

- Dataset: https://huggingface.co/datasets/Misraj/SadeedDiac-25
- Paper: https://arxiv.org/abs/2504.21635
- Dataset license: **CC BY-NC-SA 4.0**
- License text: https://creativecommons.org/licenses/by-nc-sa/4.0/legalcode.en

Changes: NFC normalization; regenerate bare input from reference output;
exclude 217 previously evaluated normalized text groups; deterministic
hash-ranked selection of 50 Rawi/reference disagreements from each source;
append baseline predictions, diagnostic categories, deterministic split ids,
and pending review metadata. The cache and resulting dataset hashes are in
`cases.manifest.json`. Model-training overlap is unknown.

The 12 `original_example` diagnostics were authored by the assistant during this
task. They have no independent human review and are clearly distinguished from
the released references. This notice does not assign a new project-wide license.

The benchmark subset is for noncommercial evaluation and review. Its rows are
never exported for fine-tuning by this workflow, including if a reviewer later
approves a reference. Approval of Arabic labels is separate from permission to
use source text for training. User/private examples and training exports belong
in ignored `quality/local/`, never in this published seed set.
