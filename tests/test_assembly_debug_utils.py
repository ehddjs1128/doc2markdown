import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from tests import _helpers  # noqa: F401

from modules.assembly.ir import AssemblyMeta, AssemblyResult


SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import _assembly_debug_utils as debug_utils


class AssemblyDebugUtilsTests(unittest.TestCase):
    def test_build_stage_results_delegates_to_trace_api(self):
        layout_output = {"pages": []}
        table_output = []
        validated_result = AssemblyResult(metadata=AssemblyMeta(stage="validated"))
        trace = SimpleNamespace(stages={"validated": validated_result})

        with patch.object(
            debug_utils.DocumentAssembler,
            "build_from_outputs_with_trace",
            return_value=trace,
        ) as build_with_trace:
            stage_results = debug_utils.build_stage_results_from_outputs(layout_output, table_output)

        self.assertIs(stage_results["validated"], validated_result)
        build_with_trace.assert_called_once_with(layout_output, table_output)


if __name__ == "__main__":
    unittest.main()
