"""``protocol_stubs``：``@protocol`` AST 推导与 ``ir.PROTOCOL_*`` 一致。"""
from __future__ import annotations

import unittest

from src.analysis.ir import (
  PROTOCOL_IMPL_ASSOC_RECEIVER,
  PROTOCOL_PARAM_ERASE,
  PROTOCOL_PARAMETRIC_RECEIVER,
)
from src.analysis.stubs.protocol_stubs import (
  load_protocol_impl_assoc_receiver,
  load_protocol_param_erase,
  load_protocol_parametric_receiver,
)


class ProtocolStubTests(unittest.TestCase):
  def test_ir_aliases_match_loaders(self):
    self.assertEqual(PROTOCOL_PARAM_ERASE, load_protocol_param_erase())
    self.assertEqual(PROTOCOL_PARAMETRIC_RECEIVER, load_protocol_parametric_receiver())
    self.assertEqual(PROTOCOL_IMPL_ASSOC_RECEIVER, load_protocol_impl_assoc_receiver())

  def test_param_erase_excludes_equatable_and_runtime_erased_protocols(self):
    erase = load_protocol_param_erase()
    self.assertNotIn("EquatableType", erase)
    self.assertIn("ComparableType", erase)
    self.assertNotIn("NavigatableType", erase)
    self.assertNotIn("EncoderType", erase)

  def test_parametric_receiver_navigatable_only(self):
    self.assertEqual(load_protocol_parametric_receiver(), frozenset({"NavigatableType"}))

  def test_impl_assoc_receiver_collection_abc(self):
    assoc = load_protocol_impl_assoc_receiver()
    self.assertEqual(
      assoc,
      frozenset({
        "IterableType",
        "IteratorType",
        "CollectionType",
        "ContainerType",
        "AppendableType",
        "ReversibleType",
        "AsyncIterableType",
        "AsyncIteratorType",
        "AsyncGeneratorType",
      }),
    )


if __name__ == "__main__":
  unittest.main()
