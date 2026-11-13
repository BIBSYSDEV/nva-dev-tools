"""Build versions on origin's default branch of each clone. No Click, no output.

Read through git rather than from a worktree, so a worktree that is behind, busy with other work, or missing
does not change the answer.

Where each version comes from (first match wins):
  Java                toolchain languageVersion in build.gradle(.kts), or in the convention plugins under
                      build-logic/src or buildSrc/src; otherwise the default of the nva-gradle-plugins version
                      in use, read from the nva-gradle-plugins clone next to this one
  Gradle              gradle/wrapper/gradle-wrapper.properties
  nva-commons         nvaCommonsVersion in gradle.properties
  nva-gradle-plugins  nvaPluginsVersion in gradle.properties, or the plugin coordinate in build-logic/ or
                      buildSrc/ build.gradle(.kts)
nva-commons and nva-gradle-plugins report their own version with the note "self".
"""

import re
from dataclasses import dataclass, field
from datetime import datetime
from functools import cache
from pathlib import Path, PurePosixPath

from nva_dev_tools.common import git
from nva_dev_tools.common.run import CommandError
from nva_dev_tools.repositories.actions import fetch_origin

NVA_COMMONS = "nva-commons"
NVA_GRADLE_PLUGINS = "nva-gradle-plugins"
BUILD_LOGIC_FOLDERS = ("build-logic", "buildSrc")
BUILD_FILES = ("build.gradle", "build.gradle.kts")
GRADLE_PROJECT_MARKERS = ("gradlew", "settings.gradle", "settings.gradle.kts")
PLUGINS_DEFAULTS_FILE = "src/main/resources/nva-plugin.properties"

GRADLE_DISTRIBUTION = re.compile(r"^distributionUrl=.*gradle-([\w.-]+?)-(?:bin|all)\.zip", re.MULTILINE)
PLUGINS_COORDINATE = re.compile(r"com\.github\.bibsysdev:nva-gradle-plugins:(\d[\w.-]*)['\"]")
PLUGINS_OWN_VERSION = re.compile(r'^version\s*=\s*"([^"]+)"', re.MULTILINE)
DEFAULT_JAVA_VERSION = re.compile(r"^java\.version\s*=\s*(\d+)", re.MULTILINE)
DECLARED_JAVA_VERSIONS = (
    re.compile(r"languageVersion\s*=\s*(\d+)"),
    re.compile(r"JavaLanguageVersion\.of\((\d+)\)"),
    re.compile(r"JavaVersion\.VERSION_(\d+)"),
)

SELF = "self"


@dataclass(frozen=True)
class Column:
    key: str
    """The JSON key."""
    header: str


JAVA = Column("java", "Java")
GRADLE = Column("gradle", "Gradle")
NVA_COMMONS_VERSION = Column("nvaCommons", "nva-commons")
NVA_GRADLE_PLUGINS_VERSION = Column("nvaGradlePlugins", "nva-gradle-plugins")
COLUMNS = (JAVA, GRADLE, NVA_COMMONS_VERSION, NVA_GRADLE_PLUGINS_VERSION)


@dataclass
class DeclaredVersion:
    version: str | None = None
    note: str | None = None
    """SELF when nva-commons or nva-gradle-plugins reports its own version."""
    outdated: bool = False
    """Older than the newest version of the same column in the report; set by mark_outdated()."""


@dataclass
class RepositoryVersions:
    repository: str
    last_commit: datetime | None = None
    """When the newest commit on origin's default branch was made."""
    versions: dict[Column, DeclaredVersion] = field(
        default_factory=lambda: {column: DeclaredVersion() for column in COLUMNS}
    )
    problem: str | None = None
    """Why the versions may be missing or out of date, such as a failed fetch."""


class DefaultBranchFiles:
    """The files on origin's default branch of a clone, read through git."""

    def __init__(self, clone: Path, default_ref: str) -> None:
        self.clone = clone
        self.default_ref = default_ref
        self.paths = set(git.git("ls-tree", "-r", "--name-only", default_ref, cwd=clone).splitlines())

    def exists(self, path: str) -> bool:
        return path in self.paths

    def read(self, path: str) -> str:
        """The file's text, or an empty string when there is no such file."""
        return git.git("show", f"{self.default_ref}:{path}", cwd=self.clone) if self.exists(path) else ""

    def under(self, folder: str) -> list[str]:
        return sorted(path for path in self.paths if path.startswith(f"{folder}/"))


def read_versions(clone: Path, *, fetch: bool) -> RepositoryVersions:
    """The versions on origin's default branch. A failure is a problem on the result, not an exception."""
    report = RepositoryVersions(clone.name)
    try:
        _read(clone, report, fetch=fetch)
    except CommandError as failure:
        report.problem = str(failure)
    return report


def _read(clone: Path, report: RepositoryVersions, *, fetch: bool) -> None:
    if fetch:
        fetch_failure = fetch_origin(clone)
        if fetch_failure is not None:
            report.problem = f"fetch failed, showing origin as of the last fetch: {fetch_failure}"
    default_ref = git.default_ref(clone)
    if not git.remote_branch_exists(default_ref.removeprefix("origin/"), clone):
        report.problem = f"{default_ref} not found"
        return
    report.last_commit = datetime.fromisoformat(git.git("log", "-1", "--format=%cI", default_ref, cwd=clone))

    files = DefaultBranchFiles(clone, default_ref)
    if not any(files.exists(marker) for marker in GRADLE_PROJECT_MARKERS):
        return
    plugins_version = _nva_gradle_plugins_version(files, clone.name)
    report.versions[NVA_GRADLE_PLUGINS_VERSION] = plugins_version
    report.versions[NVA_COMMONS_VERSION] = _nva_commons_version(files, clone.name)
    report.versions[GRADLE] = DeclaredVersion(
        _first_match(GRADLE_DISTRIBUTION, files, "gradle/wrapper/gradle-wrapper.properties")
    )
    report.versions[JAVA] = _java_version(files, clone, plugins_version.version)


def _nva_gradle_plugins_version(files: DefaultBranchFiles, repository: str) -> DeclaredVersion:
    if repository == NVA_GRADLE_PLUGINS:
        return DeclaredVersion(_first_match(PLUGINS_OWN_VERSION, files, "build.gradle.kts"), note=SELF)
    declared = _property(files.read("gradle.properties"), "nvaPluginsVersion")
    if declared is not None:
        return DeclaredVersion(declared)
    build_files = [f"{folder}/{build_file}" for folder in BUILD_LOGIC_FOLDERS for build_file in BUILD_FILES]
    return DeclaredVersion(_first_match(PLUGINS_COORDINATE, files, *build_files, *BUILD_FILES))


def _nva_commons_version(files: DefaultBranchFiles, repository: str) -> DeclaredVersion:
    properties = files.read("gradle.properties")
    if repository == NVA_COMMONS:
        return DeclaredVersion(_property(properties, "VERSION_NAME"), note=SELF)
    return DeclaredVersion(_property(properties, "nvaCommonsVersion"))


def _java_version(files: DefaultBranchFiles, clone: Path, plugins_version: str | None) -> DeclaredVersion:
    if clone.name == NVA_GRADLE_PLUGINS:
        return DeclaredVersion()
    declared = sorted(
        {version for path in _java_build_files(files) for version in _declared_java_versions(files.read(path))},
        key=int,
    )
    if declared:
        return DeclaredVersion(", ".join(declared))
    if plugins_version is None:
        return DeclaredVersion()
    return DeclaredVersion(_default_java_version(clone.parent / NVA_GRADLE_PLUGINS, plugins_version))


def _java_build_files(files: DefaultBranchFiles) -> list[str]:
    convention_plugins = [
        path
        for folder in BUILD_LOGIC_FOLDERS
        for path in files.under(f"{folder}/src")
        if PurePosixPath(path).suffix in (".gradle", ".kts")
    ]
    return [*BUILD_FILES, *convention_plugins]


def _declared_java_versions(text: str) -> set[str]:
    return {version for pattern in DECLARED_JAVA_VERSIONS for version in pattern.findall(text)}


@cache
def _default_java_version(plugins_clone: Path, plugins_version: str) -> str | None:
    """The Java version nva-gradle-plugins sets when a build does not, at the release tag of that version."""
    if not (plugins_clone / ".git").exists():
        return None
    defaults = git.git("show", f"v{plugins_version}:{PLUGINS_DEFAULTS_FILE}", cwd=plugins_clone, check=False)
    match = DEFAULT_JAVA_VERSION.search(defaults)
    return match.group(1) if match else None


def _first_match(pattern: re.Pattern[str], files: DefaultBranchFiles, *paths: str) -> str | None:
    for path in paths:
        match = pattern.search(files.read(path))
        if match:
            return match.group(1)
    return None


def _property(properties: str, key: str) -> str | None:
    match = re.search(rf"^\s*{re.escape(key)}\s*=\s*(\S+)", properties, re.MULTILINE)
    return match.group(1) if match else None


def mark_outdated(reports: list[RepositoryVersions]) -> dict[Column, str]:
    """Mark each version older than the newest one of its column in the reports. Returns the newest per column.

    A declaration of several versions ("21, 25") is outdated when its oldest one is.
    """
    newest_by_column: dict[Column, str] = {}
    for column in COLUMNS:
        declared_versions = [
            report.versions[column] for report in reports if _numeric_versions(report.versions[column].version)
        ]
        if not declared_versions:
            continue
        newest = max(numbers for declared in declared_versions for numbers in _numeric_versions(declared.version))
        newest_by_column[column] = ".".join(str(number) for number in newest)
        for declared in declared_versions:
            declared.outdated = min(_numeric_versions(declared.version)) < newest
    return newest_by_column


def _numeric_versions(version: str | None) -> list[tuple[int, ...]]:
    """Versions as tuples of numbers, so 9.10 sorts after 9.9.

    "21, 25" gives [(21,), (25,)] and "9.7.0-rc-1" gives [(9, 7, 0)].
    """
    numeric_versions = []
    for single_version in (version or "").split(","):
        numeric_prefix = re.match(r"[\d.]*\d", single_version.strip())
        if numeric_prefix:
            numeric_versions.append(tuple(int(number) for number in numeric_prefix.group().split(".")))
    return numeric_versions
