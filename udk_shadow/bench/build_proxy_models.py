"""Build RANDOM-WEIGHT proxy models with the live models' architectures and sizes, for the shadow interference
benchmark only (Hugging Face is not reachable from the benchmark environment, and the benchmark measures
compute/memory contention, not accuracy). Never used for detection; never shipped (not in the image whitelist).

  semantic  paraphrase-multilingual-MiniLM-L12-v2 shape: BERT, 12 layers, hidden 384, 12 heads, FFN 1536,
            vocab 250037, mean pooling -> loaded by the LIVE semantic.SentenceTransformerSemanticMatcher.
  intent    MoritzLaurer/mDeBERTa-v3-base-mnli-xnli shape (the live gate's base): DeBERTa-v2, 12 layers, hidden 768,
            12 heads, FFN 3072, vocab 250102, relative attention -> loaded by the LIVE intent_gate.IntentGate.
Tokenizers are a deterministic synthetic WordPiece vocabulary of the same size (token ids only drive
embedding lookups, so the vocabulary content does not change compute). Weights are seeded.

    python udk_shadow/bench/build_proxy_models.py <out_dir>
"""
from __future__ import annotations

import string
import sys
from pathlib import Path


def vocab(n: int) -> list[str]:
    base = ["[PAD]", "[UNK]", "[CLS]", "[SEP]", "[MASK]"] + list(string.ascii_lowercase + string.digits + string.punctuation)
    words = base + [f"##{c}" for c in string.ascii_lowercase]
    alpha = string.ascii_lowercase
    i = 0
    while len(words) < n:  # deterministic 2-4 letter pieces
        a, b, c = alpha[i % 26], alpha[(i // 26) % 26], alpha[(i // 676) % 26]
        words.append(a + b + (c if i >= 676 else "") + ("" if i < 17576 else str(i)))
        i += 1
    return words[:n]


def tokenizer(out: Path, n: int):
    from transformers import BertTokenizerFast
    out.mkdir(parents=True, exist_ok=True)
    (out / "vocab.txt").write_text("\n".join(vocab(n)) + "\n", encoding="utf-8")
    tok = BertTokenizerFast(vocab_file=str(out / "vocab.txt"), do_lower_case=True)
    tok.save_pretrained(out)
    return tok


def build(out_dir: str) -> None:
    import torch
    from sentence_transformers import SentenceTransformer, models
    from transformers import BertConfig, BertModel, DebertaV2Config, DebertaV2ForSequenceClassification

    out = Path(out_dir)
    torch.manual_seed(0)
    sem = out / "semantic_minilm_l12_proxy"
    tok = tokenizer(sem / "hf", 250037)
    BertModel(BertConfig(vocab_size=250037, hidden_size=384, num_hidden_layers=12, num_attention_heads=12,
                         intermediate_size=1536, max_position_embeddings=512)).save_pretrained(sem / "hf")
    word = models.Transformer(str(sem / "hf"), max_seq_length=128)
    SentenceTransformer(modules=[word, models.Pooling(word.get_word_embedding_dimension(), "mean")]).save(str(sem))

    torch.manual_seed(1)
    it = out / "intent_mdeberta_base_proxy"
    tok = tokenizer(it, 250102)
    cfg = DebertaV2Config(vocab_size=250102, hidden_size=768, num_hidden_layers=12, num_attention_heads=12,
                          intermediate_size=3072, max_position_embeddings=512, relative_attention=True, position_buckets=256,
                          norm_rel_ebd="layer_norm", share_att_key=True, pos_att_type=["p2c", "c2p"], max_relative_positions=-1,
                          type_vocab_size=0, num_labels=2)
    DebertaV2ForSequenceClassification(cfg).save_pretrained(it)
    print(f"proxy models written to {out}")


if __name__ == "__main__":
    build(sys.argv[1])
