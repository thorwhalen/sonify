"""Guards on the CI workflow's own wiring.

These tests exist because of a failure mode that no amount of testing the
*package* can catch: CI configuration that reads as if it were live but is
inert. ``[tool.wads.ci.publish].enabled`` sat in ``pyproject.toml`` looking
like an on/off switch while the publish job's ``if:`` never consulted it, so
the only way to discover the switch did nothing was to merge and watch the
default branch go red.

GitHub makes this class of bug quiet on purpose: referencing
``needs.<job>.outputs.<name>`` for an output the upstream job never declared
is not an error, it evaluates to the empty string. A gate written against a
misspelled or undeclared output therefore does not fail loudly -- it just
stops gating, and the job it was supposed to guard runs every time.

So the assertions here are about the workflow file as a document. They are
cheap, they need no network and no GitHub, and each one corresponds to a
specific way this repo's CI has actually been wrong.
"""

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_PATH = REPO_ROOT / ".github" / "workflows" / "ci.yml"

pytestmark = pytest.mark.requires_repo_checkout


def _workflow_text() -> str:
    return WORKFLOW_PATH.read_text(encoding="utf-8")


def _job_block(text: str, job_name: str) -> str:
    """Return the YAML lines belonging to one job.

    Jobs are the two-space-indented keys under ``jobs:``. A job's block runs
    until the next line that starts at indent 2 or less with a non-space
    character, which is either the next job or a new top-level key.
    """
    lines = text.splitlines()
    header = re.compile(rf"^  {re.escape(job_name)}:\s*$")
    start = next((i for i, line in enumerate(lines) if header.match(line)), None)
    assert start is not None, f"no job named {job_name!r} in {WORKFLOW_PATH.name}"

    block = [lines[start]]
    for line in lines[start + 1 :]:
        if line.strip() and not line.startswith("   "):
            break
        block.append(line)
    return "\n".join(block)


def _declared_setup_outputs(text: str) -> set:
    """The output names the setup job actually exposes to downstream jobs."""
    setup = _job_block(text, "setup").splitlines()
    outputs_at = next(
        (i for i, line in enumerate(setup) if line.rstrip() == "    outputs:"), None
    )
    assert outputs_at is not None, "the setup job declares no outputs: block"

    declared = set()
    for line in setup[outputs_at + 1 :]:
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        entry = re.match(r"^      ([A-Za-z0-9_-]+):", line)
        if entry is None:
            break  # dedented out of the outputs mapping
        declared.add(entry.group(1))
    return declared


def _without_comments(text: str) -> str:
    """Drop whole-line YAML comments.

    Only executable YAML can gate a job, and comments here legitimately discuss
    output names in prose -- scanning them would flag documentation as a bug.
    """
    return "\n".join(
        line for line in text.splitlines() if not line.lstrip().startswith("#")
    )


def _job_if_expression(text: str, job_name: str) -> str:
    match = re.search(r"^    if: (.+)$", _job_block(text, job_name), re.MULTILINE)
    assert match is not None, f"job {job_name!r} has no if: condition"
    return match.group(1)


def test_every_referenced_setup_output_is_declared():
    """A gate reading an undeclared output is not a gate -- it is a no-op.

    This is the general form of the bug: ``needs.setup.outputs.publish-enabled``
    was consulted nowhere, and had it been consulted without being declared it
    would have expanded to "" and gated nothing.
    """
    text = _workflow_text()
    referenced = set(
        re.findall(r"needs\.setup\.outputs\.([A-Za-z0-9_-]+)", _without_comments(text))
    )
    declared = _declared_setup_outputs(text)

    assert referenced, "no setup outputs are referenced at all -- parser broken?"

    undeclared = referenced - declared
    assert not undeclared, (
        "these outputs are used in the workflow but never declared by the "
        f"setup job, so they silently expand to an empty string: {sorted(undeclared)}"
    )


def test_publish_job_is_gated_on_the_pyproject_publish_flag():
    """``[tool.wads.ci.publish].enabled`` must be able to turn publishing off.

    Without this the flag is decoration: the job runs on every push to the
    default branch regardless, and a repo with no PYPI_PASSWORD secret has no
    way to express "do not try to publish yet" short of deleting the job.
    """
    condition = _job_if_expression(_workflow_text(), "publish")
    assert "needs.setup.outputs.publish-enabled" in condition, (
        "the publish job does not consult publish-enabled, so "
        "[tool.wads.ci.publish].enabled in pyproject.toml is dead config"
    )


def test_publish_job_pushes_back_over_https_not_ssh():
    """The version push-back must not require a per-repo SSH deploy key.

    ``actions/checkout`` leaves GITHUB_TOKEN credentials configured for the
    HTTPS remote, which -- with the job's ``contents: write`` permission -- is
    all the push-back needs. Rewriting origin to an SSH URL overrides those
    credentials, and ``wads/actions/git-commit`` only starts an ssh-agent when
    it is handed a key, so on a repo without SSH_PRIVATE_KEY the push fails and
    the version bump is never recorded.
    """
    publish = _job_block(_workflow_text(), "publish")

    assert "git remote set-url" not in publish, (
        "publish rewrites the git remote; if that makes it SSH, push-back "
        "breaks on every repo without an SSH_PRIVATE_KEY deploy key"
    )
    assert "ssh-private-key:" not in publish, (
        "publish asks git-commit for an SSH key; the push-back is supposed to "
        "ride on GITHUB_TOKEN instead"
    )
    assert "contents: write" in publish, (
        "publish pushes commits and tags back, which needs contents: write"
    )


def test_docs_job_does_not_depend_on_publish():
    """Turning publishing off must not silently take the docs down with it.

    A job whose dependency is skipped is itself skipped, so ``needs: publish``
    would couple GitHub Pages to PyPI releases -- two things with no real
    relationship and separate enable flags.
    """
    docs_job = _job_block(_workflow_text(), "github-pages")
    needs = re.search(r"^    needs: (.+)$", docs_job, re.MULTILINE)
    assert needs is not None, "the github-pages job declares no needs:"
    assert "publish" not in needs.group(1), (
        "github-pages depends on publish, so disabling publishing also "
        f"disables docs: needs: {needs.group(1)}"
    )


def test_publish_marker_is_matched_with_startswith_not_contains():
    """Naming the one-off publish marker must not TRIGGER it.

    A squash-merge folds the whole PR body into the commit message. With a
    ``contains`` match, a PR body that merely explains the escape hatch -- in a
    sentence carrying the literal marker -- forces a publish, overriding
    ``[tool.wads.ci.publish] enabled``. That happened on 9851229: the publish job
    ran against ``enabled = false``, failed on the absent token, and reddened the
    first green main this repo had had in a year.

    ``startsWith`` keeps the hatch usable (a message that BEGINS with the marker
    is deliberate) while leaving prose that names it inert.
    """
    publish = _job_block(_workflow_text(), "publish")
    gate = re.search(r"^    if: (.+)$", publish, re.MULTILINE)
    assert gate is not None, "the publish job declares no if: gate"
    condition = gate.group(1)

    assert "startsWith(github.event.head_commit.message, needs.setup.outputs.publish-marker)" in condition, (
        "the publish marker is not matched with startsWith; a PR body that "
        f"merely mentions the marker would force a release. gate: {condition}"
    )
    assert "contains(github.event.head_commit.message, needs.setup.outputs.publish-marker)" not in condition, (
        "the publish marker is still matched with contains somewhere in the "
        f"gate, which is the bug this test exists to prevent. gate: {condition}"
    )
