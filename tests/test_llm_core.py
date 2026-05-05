import sys
import unittest
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from modules.llm_core import LLMConfig, LocalTransformersLLMClient


class FakeTensor:
    def __init__(self, shape=(1, 3)):
        self.shape = shape
        self.device = None

    def to(self, device):
        self.device = device
        return self


class FakeBatchEncoding:
    def __init__(self):
        self.input_ids = FakeTensor()
        self.attention_mask = FakeTensor()

    def items(self):
        return {
            "input_ids": self.input_ids,
            "attention_mask": self.attention_mask,
        }.items()


class FakeGeneratedRow:
    def __getitem__(self, key):
        return ["generated"]


class FakeGeneratedOutput:
    def __getitem__(self, key):
        return FakeGeneratedRow()


class FakeTokenizer:
    eos_token_id = 0

    def __init__(self):
        self.batch_encoding = FakeBatchEncoding()

    def apply_chat_template(self, messages, add_generation_prompt, return_tensors, enable_thinking=False):
        return self.batch_encoding

    def decode(self, generated, skip_special_tokens):
        return '{"ok": true}'


class FakeModel:
    device = "cuda:0"

    def __init__(self):
        self.generate_kwargs = None

    def generate(self, **kwargs):
        self.generate_kwargs = kwargs
        return FakeGeneratedOutput()


class LocalTransformersLLMClientTests(unittest.TestCase):
    def test_generate_json_accepts_batch_encoding_inputs(self):
        tokenizer = FakeTokenizer()
        model = FakeModel()
        client = LocalTransformersLLMClient(LLMConfig(model_id="fake-local-llm", max_new_tokens=7))
        client._tokenizer = tokenizer
        client._model = model

        response = client.generate_json("content_repair", {"items": []})

        self.assertEqual(response, {"ok": True})
        self.assertIs(model.generate_kwargs["input_ids"], tokenizer.batch_encoding.input_ids)
        self.assertIs(model.generate_kwargs["attention_mask"], tokenizer.batch_encoding.attention_mask)
        self.assertEqual(model.generate_kwargs["input_ids"].device, "cuda:0")
        self.assertEqual(model.generate_kwargs["attention_mask"].device, "cuda:0")
        self.assertEqual(model.generate_kwargs["max_new_tokens"], 7)


if __name__ == "__main__":
    unittest.main()
