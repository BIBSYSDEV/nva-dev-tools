from pathlib import Path

from conftest import Repo, bare_clone, commit_files, make_origin

from nva_dev_tools.common.git import git
from nva_dev_tools.repositories import versions
from nva_dev_tools.repositories.versions import (
    GRADLE,
    JAVA,
    NVA_COMMONS_VERSION,
    NVA_GRADLE_PLUGINS_VERSION,
    DeclaredVersion,
    RepositoryVersions,
)

WRAPPER_PROPERTIES = "gradle/wrapper/gradle-wrapper.properties"


def wrapper_properties(gradle_version: str) -> str:
    return f"distributionUrl=https\\://services.gradle.org/distributions/gradle-{gradle_version}-bin.zip\n"


def clone_with(tmp_path: Path, name: str, files: dict[str, str], *, tag: str | None = None) -> Repo:
    """A clone in tmp_path/clones whose origin has the files on its default branch, and optionally a tag on it."""
    origin = make_origin(tmp_path / "origins" / name)
    commit_files(origin, files)
    if tag is not None:
        git("tag", tag, cwd=origin)
    return bare_clone(origin, tmp_path / "clones" / name)


def read(clone: Path) -> RepositoryVersions:
    return versions.read_versions(clone, fetch=True)


def version_and_note(report: RepositoryVersions) -> dict[str, tuple[str | None, str | None]]:
    return {column.header: (declared.version, declared.note) for column, declared in report.versions.items()}


def test_reads_each_version_where_the_build_declares_it(tmp_path: Path) -> None:
    service = clone_with(
        tmp_path,
        "nva-nvi",
        {
            "gradlew": "",
            WRAPPER_PROPERTIES: wrapper_properties("9.8.2"),
            "gradle.properties": "nvaCommonsVersion=2.11.2\nnvaPluginsVersion=1.0.14\n",
            "build-logic/src/main/groovy/nva.java-conventions.gradle": "languageVersion = JavaLanguageVersion.of(25)\n",
        },
    )
    report = read(service.root)
    assert version_and_note(report) == {
        "Java": ("25", None),
        "Gradle": ("9.8.2", None),
        "nva-commons": ("2.11.2", None),
        "nva-gradle-plugins": ("1.0.14", None),
    }
    assert report.last_commit is not None and report.problem is None


def test_reads_origin_not_the_worktree(tmp_path: Path) -> None:
    service = clone_with(tmp_path, "nva-nvi", {"gradlew": "", WRAPPER_PROPERTIES: wrapper_properties("9.7.0")})
    (service.main / WRAPPER_PROPERTIES).write_text(wrapper_properties("8.4"))
    commit_files(service.origin, {WRAPPER_PROPERTIES: wrapper_properties("9.8.2")})
    assert read(service.root).versions[GRADLE].version == "9.8.2"


def test_reads_the_default_branch_of_an_ordinary_clone_with_a_feature_branch_checked_out(tmp_path: Path) -> None:
    origin = make_origin(tmp_path / "origins" / "nva-nvi")
    commit_files(origin, {"gradlew": "", WRAPPER_PROPERTIES: wrapper_properties("9.8.2")})
    ordinary = tmp_path / "clones" / "nva-nvi"
    git("clone", "-q", str(origin), str(ordinary), cwd=tmp_path)
    git("switch", "-q", "-c", "feature", cwd=ordinary)
    commit_files(ordinary, {WRAPPER_PROPERTIES: wrapper_properties("8.4")})
    assert read(ordinary).versions[GRADLE].version == "9.8.2"


def test_reads_the_plugin_coordinate_from_build_logic(tmp_path: Path) -> None:
    service = clone_with(
        tmp_path,
        "nva-uac",
        {
            "settings.gradle": "",
            "buildSrc/build.gradle": "implementation 'com.github.bibsysdev:nva-gradle-plugins:1.0.12'\n",
        },
    )
    assert read(service.root).versions[NVA_GRADLE_PLUGINS_VERSION] == DeclaredVersion("1.0.12")


def test_java_defaults_to_what_the_plugins_release_sets(tmp_path: Path) -> None:
    plugins = clone_with(
        tmp_path,
        "nva-gradle-plugins",
        {
            "gradlew": "",
            "build.gradle.kts": 'version = "1.0.14"\n',
            "src/main/resources/nva-plugin.properties": "java.version=21\n",
        },
        tag="v1.0.14",
    )
    released = clone_with(
        tmp_path, "nva-search-api", {"gradlew": "", "gradle.properties": "nvaPluginsVersion=1.0.14\n"}
    )
    unreleased = clone_with(tmp_path, "nva-uac", {"gradlew": "", "gradle.properties": "nvaPluginsVersion=1.0.99\n"})

    plugins_report = read(plugins.root)
    assert plugins_report.versions[NVA_GRADLE_PLUGINS_VERSION] == DeclaredVersion("1.0.14", "self")
    assert plugins_report.versions[JAVA] == DeclaredVersion()
    assert read(released.root).versions[JAVA] == DeclaredVersion("21")
    assert read(unreleased.root).versions[JAVA] == DeclaredVersion()


def test_nva_commons_reports_its_own_version(tmp_path: Path) -> None:
    commons = clone_with(tmp_path, "nva-commons", {"gradlew": "", "gradle.properties": "VERSION_NAME=2.11.2\n"})
    assert read(commons.root).versions[NVA_COMMONS_VERSION] == DeclaredVersion("2.11.2", "self")


def test_a_repository_without_gradle_has_only_a_last_commit(tmp_path: Path) -> None:
    frontend = clone_with(
        tmp_path, "NVA-Frontend", {"package.json": "{}\n", "gradle.properties": "nvaCommonsVersion=1\n"}
    )
    report = read(frontend.root)
    assert all(declared == DeclaredVersion() for declared in report.versions.values())
    assert report.last_commit is not None


def test_a_failed_fetch_is_a_problem_and_origin_as_last_fetched_is_reported(tmp_path: Path) -> None:
    service = clone_with(tmp_path, "nva-nvi", {"gradlew": "", WRAPPER_PROPERTIES: wrapper_properties("9.8.2")})
    git("remote", "set-url", "origin", str(tmp_path / "gone"), cwd=service.root)
    report = read(service.root)
    assert report.problem is not None and report.problem.startswith("fetch failed")
    assert report.versions[GRADLE].version == "9.8.2"


def test_mark_outdated_compares_versions_as_numbers_per_column() -> None:
    newest = RepositoryVersions("newest")
    newest.versions[JAVA] = DeclaredVersion("25")
    newest.versions[GRADLE] = DeclaredVersion("9.10.0")
    older = RepositoryVersions("older")
    older.versions[JAVA] = DeclaredVersion("21, 25")
    older.versions[GRADLE] = DeclaredVersion("9.9.0-rc-1")
    unknown = RepositoryVersions("unknown")
    unknown.versions[JAVA] = DeclaredVersion()

    assert versions.mark_outdated([newest, older, unknown]) == {JAVA: "25", GRADLE: "9.10.0"}
    assert [report.versions[JAVA].outdated for report in (newest, older, unknown)] == [False, True, False]
    assert [report.versions[GRADLE].outdated for report in (newest, older)] == [False, True]
