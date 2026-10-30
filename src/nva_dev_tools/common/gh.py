import json
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from nva_dev_tools.common.output import warn
from nva_dev_tools.common.run import CommandError, run

PULL_REQUESTS_PER_BRANCH = 10
"""Enough that a fork's pull request from a branch of the same name does not hide the repository's own."""


@dataclass(frozen=True)
class PullRequest:
    number: int
    state: str
    """open, closed or merged."""
    head_sha: str


def latest_pull_requests(branches: Sequence[str], cwd: Path) -> dict[str, PullRequest | None] | None:
    """The most recent pull request of every branch, in any state, in one GraphQL request.

    None after a warning when gh fails (not installed, not logged in, repo not on GitHub, offline), so that
    the caller leaves the pull request state out instead of reporting every branch as having none.
    """
    if not branches:
        return {}
    # gh fills in {owner} and {repo} from the repository at cwd
    command = ["gh", "api", "graphql", "-F", "owner={owner}", "-F", "name={repo}"]
    command += ["-f", f"query={pull_request_query(len(branches))}"]
    for index, branch in enumerate(branches):
        command += ["-f", f"branch{index}={branch}"]
    try:
        completed = run(command, cwd=cwd, check=False)
    except CommandError as failure:
        return _not_checked(str(failure))
    if completed.returncode != 0:
        return _not_checked(completed.stderr.strip())
    return parse_pull_requests(branches, json.loads(completed.stdout))


def _not_checked(reason: str) -> None:
    warn(f"PR state not checked, so squash-merged branches will not show as stale; gh failed: {reason}")
    return None


def pull_request_query(branch_count: int) -> str:
    """One aliased pullRequests field per branch variable (branch0, branch1, ...), newest pull request first."""
    variables = "".join(f", $branch{index}: String!" for index in range(branch_count))
    fields = " ".join(
        f"branch{index}: pullRequests(headRefName: $branch{index}, first: {PULL_REQUESTS_PER_BRANCH}, "
        "orderBy: {field: CREATED_AT, direction: DESC}) "
        "{ nodes { number state headRefOid headRepository { nameWithOwner } } }"
        for index in range(branch_count)
    )
    selection = f"repository(owner: $owner, name: $name) {{ nameWithOwner {fields} }}"
    return f"query($owner: String!, $name: String!{variables}) {{ {selection} }}"


def parse_pull_requests(branches: Sequence[str], response: dict[str, Any]) -> dict[str, PullRequest | None]:
    """Map the aliased fields of a pull_request_query response back to their branches, ignoring fork pull requests."""
    repository = response["data"]["repository"]
    pull_requests: dict[str, PullRequest | None] = {}
    for index, branch in enumerate(branches):
        nodes = repository[f"branch{index}"]["nodes"]
        own_nodes = (node for node in nodes if _head_repository(node) == repository["nameWithOwner"])
        pull_requests[branch] = next((_pull_request(node) for node in own_nodes), None)
    return pull_requests


def _head_repository(node: dict[str, Any]) -> str | None:
    """None when the fork the pull request came from has been deleted."""
    head_repository = node.get("headRepository")
    return head_repository["nameWithOwner"] if head_repository else None


def _pull_request(node: dict[str, Any]) -> PullRequest:
    return PullRequest(number=int(node["number"]), state=str(node["state"]).lower(), head_sha=str(node["headRefOid"]))
