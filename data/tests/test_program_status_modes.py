"""모드 확장은 배선 판정을 깨지 않되 필수 모드 누락은 감지한다."""
import importlib.util
import sys
from pathlib import Path


def load_status_module():
    path = Path(__file__).resolve().parents[2] / "scripts/pppp_status.py"
    spec = importlib.util.spec_from_file_location("program_status_modes", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_extended_and_reordered_program_modes_keep_required_contract() -> None:
    status = load_status_module()
    required = {"popup", "soft_open", "mvp"}
    for source in (
        'ValidationMode = Literal["popup", "soft_open", "mvp"]',
        "ValidationMode = Literal[\n'actual_open', 'mvp', 'popup', 'soft_open'\n]",
    ):
        assert required.issubset(status._literal_options(source, "ValidationMode"))


def test_missing_program_mode_cannot_pass_through_comment_or_other_alias() -> None:
    status = load_status_module()
    source = '''
# ValidationMode = Literal["popup", "soft_open", "mvp"]
OtherMode = Literal["popup", "soft_open", "mvp"]
ValidationMode = Literal["popup", "actual_open"]
'''
    assert not {"popup", "soft_open", "mvp"}.issubset(
        status._literal_options(source, "ValidationMode"))
