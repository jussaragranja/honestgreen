import json

from honestgreen import cli

TEST_V1 = '''
def test_total():
    assert total(166.65) == 149.99

def test_bonus():
    assert points(100) == 15
'''
CODE_V1 = "def total(x):\n    return x\n"


def setup(repo):
    repo.commit({"tests/test_shop.py": TEST_V1, "shop/core.py": CODE_V1}, "initial")
    repo.branch("feature")


def run(repo, *args, capsys=None):
    code = cli.main(["check", "--repo", str(repo.path), *args])
    out = capsys.readouterr().out if capsys else ""
    return code, out


def test_clean_change_passes(repo, capsys):
    setup(repo)
    repo.commit({"shop/core.py": "def total(x):\n    return round(x, 2)\n"})
    code, out = run(repo, capsys=capsys)
    assert code == 0 and "No test integrity findings" in out


def test_worktree_mode_sees_uncommitted_changes(repo, capsys):
    setup(repo)
    repo.write({"tests/test_shop.py": TEST_V1.replace("== 149.99", "== 149.98"),
                "shop/core.py": "def total(x):\n    return x - 0.01\n"})
    code, out = run(repo, capsys=capsys)
    assert code == 1 and "HG004" in out


def test_head_mode_ignores_worktree(repo, capsys):
    setup(repo)
    repo.write({"tests/test_shop.py": TEST_V1.replace("== 149.99", "== 149.98")})
    code, _ = run(repo, "--head", "HEAD", capsys=capsys)
    assert code == 0


def test_valid_justification_unblocks(repo, capsys):
    setup(repo)
    repo.commit({"tests/test_shop.py": TEST_V1.replace("== 15", "== 10"),
                 "shop/core.py": "x = 1\n"},
                "fix: points\n\nTest-Change: tests/test_shop.py | HG004 | PRODUCT-42 removed the "
                "welcome bonus; base rule is 1 point per R$ 10")
    code, out = run(repo, "--format", "json", capsys=capsys)
    data = json.loads(out)
    assert code == 0
    assert data["summary"]["justified"] == 1
    assert data["findings"][0]["justification"].startswith("PRODUCT-42")


def test_weak_justification_is_rejected(repo, capsys):
    setup(repo)
    repo.commit({"tests/test_shop.py": TEST_V1.replace("== 15", "== 10"), "shop/core.py": "x = 1\n"},
                "wip\n\nTest-Change: tests/test_shop.py | HG004 | test was failing")
    code, out = run(repo, "--format", "json", capsys=capsys)
    data = json.loads(out)
    assert code == 1
    assert data["rejected_justifications"][0]["problem"]


def test_justification_for_other_finding_does_not_apply(repo, capsys):
    setup(repo)
    repo.commit({"tests/test_shop.py": TEST_V1.replace("== 15", "== 10"), "shop/core.py": "x = 1\n"},
                "x\n\nTest-Change: tests/test_shop.py | HG002 | the welcome bonus rule is pending PRODUCT-42")
    code, _ = run(repo, capsys=capsys)
    assert code == 1


def test_fail_on_medium_and_never(repo, capsys):
    setup(repo)
    # expected value changed without production change -> medium
    repo.commit({"tests/test_shop.py": TEST_V1.replace("== 15", "== 10")})
    assert run(repo, capsys=capsys)[0] == 0
    assert run(repo, "--fail-on", "medium", capsys=capsys)[0] == 1
    assert run(repo, "--fail-on", "never", capsys=capsys)[0] == 0


def test_policy_protected_and_policy_change(repo, capsys):
    repo.commit({"tests/test_shop.py": TEST_V1, "shop/core.py": CODE_V1,
                 ".honestgreen.toml": 'protected = ["tests/test_shop.py"]\n'})
    repo.branch("feature")
    # a refactor inside a protected test (no assertion change) is still reported
    repo.commit({"tests/test_shop.py": TEST_V1.replace("def test_total():\n",
                                                       "def test_total():\n    x = 1\n")})
    code, out = run(repo, "--format", "json", capsys=capsys)
    data = json.loads(out)
    assert code == 1 and data["findings"][0]["id"] == "HG011"
    assert data["findings"][0]["protected"] is True

    repo.commit({".honestgreen.toml": "protected = []\n"})
    code, out = run(repo, "--format", "json", capsys=capsys)
    assert "HG010" in {f["id"] for f in json.loads(out)["findings"]}


def test_policy_detector_override(repo, capsys):
    repo.commit({"tests/test_shop.py": TEST_V1, "shop/core.py": CODE_V1,
                 ".honestgreen.toml": '[detectors.HG005]\nenabled = false\n'})
    repo.branch("feature")
    repo.commit({"tests/test_shop.py": "def test_total():\n    assert total(166.65) == 149.99\n"})
    code, out = run(repo, capsys=capsys)
    assert code == 0 and "HG005" not in out


def test_change_cannot_relax_its_own_policy(repo, capsys):
    setup(repo)
    repo.commit({"tests/test_shop.py": TEST_V1.replace("def test_bonus():\n    assert points(100) == 15\n", ""),
                 ".honestgreen.toml": 'fail_on = "never"\n'})
    code, out = run(repo, "--format", "json", capsys=capsys)
    found = {f["id"] for f in json.loads(out)["findings"]}
    assert code == 1 and {"HG005", "HG010"} <= found


def test_invalid_policy_is_an_error(repo, capsys):
    repo.commit({".honestgreen.toml": 'fail_on = "sometimes"\n'})
    assert run(repo, capsys=capsys)[0] == 2


def test_output_formats(repo, capsys, tmp_path):
    setup(repo)
    repo.commit({"tests/test_shop.py": TEST_V1.replace("def test_bonus():\n    assert points(100) == 15\n", ""),
                 "shop/core.py": "x = 2\n"})
    md = tmp_path / "r.md"
    run(repo, "--format", "md", "--output", str(md), capsys=capsys)
    assert "HG005" in md.read_text() and "| 🔴 |" in md.read_text()
    _, out = run(repo, "--format", "sarif", capsys=capsys)
    sarif = json.loads(out)
    assert sarif["runs"][0]["results"][0]["ruleId"] == "HG005"
    assert sarif["runs"][0]["results"][0]["level"] == "error"


def test_file_rename_is_followed(repo, capsys):
    setup(repo)
    repo.git("mv", "tests/test_shop.py", "tests/test_store.py")
    repo.commit({})
    code, out = run(repo, capsys=capsys)
    assert code == 0 and "No test integrity findings" in out


def test_policy_init(repo, capsys):
    assert cli.main(["policy", "init", "--repo", str(repo.path)]) == 0
    assert (repo.path / ".honestgreen.toml").exists()
    assert cli.main(["policy", "init", "--repo", str(repo.path)]) == 2


def test_unknown_base_is_an_error(repo, capsys):
    repo.commit({"a.txt": "x"})
    assert run(repo, "--base", "nope", capsys=capsys)[0] == 2
