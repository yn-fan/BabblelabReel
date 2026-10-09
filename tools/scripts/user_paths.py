"""Compatibility helpers for BabblelabReel user output paths.

New code should import :mod:`runtime_config` directly. These functions remain
for existing skills and tools that only need a resolved ``USER_HOME``.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path

from runtime_config import resolve_alias, resolve_runtime_config


USER_HOME_SUBDIRS = (
    "cache",
    "docs",
    "grounding",
    "knowledge",
    "memory",
    "outputs",
    "presentations",
    "private",
    "profile",
    "reports",
)

NONCANONICAL_USER_ROOTS = {
    "groundings": "grounding",
    "presentation": "presentations",
    "reviews": "reports",
}

ARTIFACT_ROOTS = {
    "cache": "cache",
    "grounding": "grounding",
    "output": "outputs",
    "presentation": "presentations",
    "private": "private",
    "report": "reports",
    "state": "profile",
}


def resolve_user_home(repo_root: Path | str, alias: str | None = None) -> Path:
    """Return the absolute USER_HOME from the canonical RuntimeConfig."""
    return resolve_runtime_config(repo_root, alias).user_home


def user_home_health(user_home: Path | str) -> list[dict[str, str]]:
    """Report top-level taxonomy drift without changing existing user data."""
    home = Path(user_home).expanduser().resolve()
    if not home.is_dir():
        return [{"path": str(home), "kind": "missing-user-home", "message": "USER_HOME does not exist"}]

    findings: list[dict[str, str]] = []
    for child in sorted(home.iterdir()):
        if child.name.startswith(".") or child.name in USER_HOME_SUBDIRS:
            continue
        replacement = NONCANONICAL_USER_ROOTS.get(child.name)
        if replacement:
            kind = "noncanonical-root"
            message = f"noncanonical top-level root; new artifacts belong under {replacement}/"
        else:
            kind = "unknown-root"
            message = "unknown top-level entry; keep generated artifacts in a canonical binding"
        findings.append({"path": str(child), "kind": kind, "message": message})

    nested_users = home / "users"
    if nested_users.is_dir() and any(nested_users.iterdir()):
        findings.append({
            "path": str(nested_users),
            "kind": "nested-user-home",
            "message": "resolved USER_HOME must not contain another users/{alias} workspace",
        })
    return findings


def user_subdir(repo_root: Path | str, *parts: str, alias: str | None = None) -> Path:
    """Convenience: resolve_user_home(...) joined with sub-path parts."""
    return resolve_user_home(repo_root, alias).joinpath(*parts)


def user_subdir_from_home(user_home: Path | str, *parts: str) -> Path:
    """Join canonical subdirectories to an already RuntimeConfig-resolved home.

    This performs no discovery, filesystem access, symlink resolution or writes.
    Callers handling untrusted files must enforce filesystem containment too.
    """
    home = Path(user_home)
    if not home.is_absolute() or ".." in home.parts:
        raise ValueError("USER_HOME must be an absolute, already resolved path")
    if not parts or parts[0] not in USER_HOME_SUBDIRS:
        raise ValueError("Expected a canonical USER_HOME subdirectory")
    for part in parts:
        if (
            not isinstance(part, str) or not part or part.startswith(".")
            or part != part.strip() or part.endswith(".")
            or any(char in part for char in "/\\%:")
            or any(ord(char) < 32 or ord(char) == 127 for char in part)
        ):
            raise ValueError("Invalid USER_HOME subdirectory component")
    return home.joinpath(*parts)


def report_dir_from_home(
    user_home: Path | str,
    skill_name: str,
    run_id: str | None = None,
    *,
    feature_name: str | None = None,
) -> Path:
    """Return a report path when RuntimeConfig supplied an explicit user home."""
    path = Path(user_home).expanduser().resolve() / "reports" / _validated_name(skill_name, "skill name")
    if feature_name:
        path /= _validated_name(feature_name, "feature name")
    return path / _validated_name(run_id, "run id") if run_id else path


def _validated_name(value: str, label: str) -> str:
    name = value.strip()
    if not name or name in {".", ".."} or Path(name).name != name:
        raise ValueError(f"Invalid {label}: {value!r}")
    return name


def ensure_user_path(repo_root: Path | str, path: Path | str, alias: str | None = None) -> Path:
    """Return an absolute path after proving it is contained by USER_HOME."""
    user_home = resolve_user_home(repo_root, alias)
    resolved = Path(path).expanduser().resolve()
    if not resolved.is_relative_to(user_home):
        raise ValueError(f"User file must be stored under USER_HOME ({user_home}): {resolved}")
    return resolved


def ensure_artifact_path(
    repo_root: Path | str,
    path: Path | str,
    artifact_class: str,
    alias: str | None = None,
) -> Path:
    """Prove that a generated file is inside its canonical artifact root."""
    try:
        root_name = ARTIFACT_ROOTS[artifact_class]
    except KeyError as error:
        choices = ", ".join(sorted(ARTIFACT_ROOTS))
        raise ValueError(f"Unknown artifact class {artifact_class!r}; expected one of: {choices}") from error

    resolved = ensure_user_path(repo_root, path, alias)
    artifact_root = user_subdir(repo_root, root_name, alias=alias)
    if not resolved.is_relative_to(artifact_root):
        raise ValueError(
            f"{artifact_class} artifact must be stored under {artifact_root}: {resolved}"
        )
    return resolved


def output_dir(repo_root: Path | str, skill_name: str, alias: str | None = None) -> Path:
    """Return ``USER_HOME/outputs/{skill_name}`` for final non-report artifacts."""
    return user_subdir(repo_root, "outputs", _validated_name(skill_name, "skill name"), alias=alias)


def report_dir(
    repo_root: Path | str,
    skill_name: str,
    run_id: str | None = None,
    *,
    feature_name: str | None = None,
    alias: str | None = None,
) -> Path:
    """Return ``USER_HOME/reports/{skill_name}[/{feature_name}][/{run_id}]``."""
    return report_dir_from_home(
        resolve_user_home(repo_root, alias),
        skill_name,
        run_id,
        feature_name=feature_name,
    )


def meeting_report_dir(
    repo_root: Path | str,
    meeting_slug: str,
    occurrence_date: str,
    alias: str | None = None,
) -> Path:
    """Return the occurrence-owned report directory for Get Review Context."""
    return user_subdir(
        repo_root,
        "reports",
        _validated_name(meeting_slug, "meeting slug"),
        _validated_name(occurrence_date, "occurrence date"),
        alias=alias,
    )


def child_report_dir(
    repo_root: Path | str,
    master_run_dir: Path | str,
    child_skill_name: str,
    *,
    alias: str | None = None,
) -> Path:
    """Nest an invoked skill's files beneath its master's report run."""
    master = ensure_user_path(repo_root, master_run_dir, alias)
    reports_root = user_subdir(repo_root, "reports", alias=alias)
    if not master.is_relative_to(reports_root):
        raise ValueError(f"Master run must be stored under {reports_root}: {master}")
    return master / _validated_name(child_skill_name, "child skill name")


def presentation_dir(repo_root: Path | str, deck_slug: str, alias: str | None = None) -> Path:
    """Return ``USER_HOME/presentations/{deck_slug}``."""
    return user_subdir(repo_root, "presentations", _validated_name(deck_slug, "deck slug"), alias=alias)


def state_dir(repo_root: Path | str, skill_name: str, alias: str | None = None) -> Path:
    """Return ``USER_HOME/profile/{skill_name}`` for durable skill configuration."""
    name = _validated_name(skill_name, "skill name")
    return user_subdir(repo_root, "profile", alias=alias) if name == "profile" else user_subdir(
        repo_root, "profile", name, alias=alias
    )


def state_dir_from_home(user_home: Path | str, skill_name: str) -> Path:
    """Return ``USER_HOME/profile/{skill_name}`` from an explicit user home."""
    return Path(user_home).expanduser().resolve() / "profile" / _validated_name(skill_name, "skill name")


def cache_dir(repo_root: Path | str, skill_name: str, alias: str | None = None) -> Path:
    """Return ``USER_HOME/cache/{skill_name}`` for regenerable files."""
    return user_subdir(repo_root, "cache", _validated_name(skill_name, "skill name"), alias=alias)


def grounding_dir(repo_root: Path | str, *parts: str, alias: str | None = None) -> Path:
    """Return a path below the canonical ``USER_HOME/grounding`` root."""
    clean_parts = tuple(_validated_name(part, "grounding path part") for part in parts)
    return user_subdir(repo_root, "grounding", *clean_parts, alias=alias)


def private_dir(repo_root: Path | str, *parts: str, alias: str | None = None) -> Path:
    """Return a path below USER_HOME/private for credentials and auth state."""
    clean_parts = tuple(_validated_name(part, "private path part") for part in parts)
    return user_subdir(repo_root, "private", *clean_parts, alias=alias)


@dataclass(frozen=True)
class ArtifactContext:
    """Resolve logical artifact classes without exposing layout to a skill."""

    repo_root: Path | str
    skill_name: str
    run_id: str
    alias: str | None = None
    feature_name: str | None = None
    master_skill: str | None = None
    master_run_id: str | None = None
    master_feature_name: str | None = None
    playground_project: Path | str | None = None
    review_project: Path | str | None = None

    @property
    def design_project(self) -> Path | None:
        """Validate a host-selected project; artifact data cannot supply this grant."""
        if self.playground_project is None:
            return None
        design_child_of_review = (
            self.master_skill == "review" and self.skill_name in {"design", "design-canvas"}
        )
        if (self.master_skill or self.skill_name) not in {"design", "design-canvas"} and not design_child_of_review:
            raise ValueError("Playground output binding requires a Design owner")
        supplied = Path(self.playground_project).expanduser()
        if not supplied.is_absolute():
            raise ValueError("Playground project must be an absolute existing project path")
        if supplied.is_symlink():
            raise ValueError("Playground project must be a real directory, not a symlink")
        try:
            project = supplied.resolve(strict=True)
        except (OSError, RuntimeError) as error:
            raise ValueError("Playground project must be an existing real directory") from error
        if not project.is_dir():
            raise ValueError("Playground project must be an existing directory")
        if project.is_relative_to(Path(self.repo_root).expanduser().resolve()):
            raise ValueError("Playground project cannot be inside the BabblelabReel runtime/source root")
        if any(path.is_symlink() for path in supplied.parents):
            raise ValueError("Playground project must not use symlink ancestors")
        return project

    @staticmethod
    def _design_directory(destination: Path, project: Path) -> Path:
        for path in (destination, *destination.parents):
            if path.is_symlink() or (path.exists() and not path.is_dir()):
                raise ValueError("Playground output directories must be real directories, not symlinks")
            if path == project:
                break
        if not destination.resolve().is_relative_to(project):
            raise ValueError("Playground output escapes its selected project")
        return destination

    def _design_output(self, area: str) -> Path:
        project = self.design_project
        assert project is not None
        return self._design_directory(project / "design" / area, project)

    def _design_report(self) -> Path:
        """Keep a bound Design run and its child records inside the owned stage."""
        project = self.design_project
        assert project is not None
        run = (self.master_run_id or self.run_id) if self.master_skill else self.run_id
        for value, label in ((run, "Design run id"), (self.skill_name, "Design skill name")):
            if (
                not isinstance(value, str) or not value.strip()
                or value != value.strip() or value in {".", ".."}
                or "/" in value or "\\" in value or ":" in value or "\0" in value
                or Path(value).is_absolute()
            ):
                raise ValueError(f"Invalid {label}: expected a nonempty path segment, got {value!r}")
        destination = project / "design" / "runs" / run
        if self.master_skill:
            destination /= self.skill_name
        return self._design_directory(destination, project)

    @property
    def review_output(self) -> Path:
        """Resolve the public Review root without changing internal report ownership."""
        if (self.master_skill or self.skill_name) != "review" and not (
                self.review_project is None and self.skill_name == "review"):
            raise ValueError("Review output binding requires a Review owner")
        self._review_identity()
        if self.review_project is None:
            destination = (
                self.report / "outputs" if self.master_skill
                else output_dir(self.repo_root, "review", self.alias)
            )
            root = self.report if self.master_skill and self.playground_project is not None else self.user_home
            return self._review_directory(destination, root)
        supplied = Path(self.review_project)
        if not supplied.is_absolute():
            raise ValueError("Review project must be an absolute existing project path")
        if supplied.is_symlink():
            raise ValueError("Review project must be a real directory, not a symlink")
        try:
            project = supplied.resolve(strict=True)
        except (OSError, RuntimeError) as error:
            raise ValueError("Review project must be an existing real directory") from error
        if not project.is_dir():
            raise ValueError("Review project must be an existing directory")
        if project.is_relative_to(Path(self.repo_root).expanduser().resolve()):
            raise ValueError("Review project cannot be inside the BabblelabReel runtime/source root")
        if any(path.is_symlink() for path in supplied.parents):
            raise ValueError("Review project must not use symlink ancestors")

        return self._review_directory(project / "review", supplied)

    def _review_identity(self) -> tuple[str, str]:
        topic = (self.master_feature_name or self.feature_name) if self.master_skill else self.feature_name
        cycle = (self.master_run_id or self.run_id) if self.master_skill else self.run_id
        for value, label in ((topic, "Review topic"), (cycle, "Review cycle")):
            if (
                not isinstance(value, str) or not value.strip()
                or value != value.strip() or value in {".", ".."}
                or "/" in value or "\\" in value or ":" in value or "\0" in value
                or Path(value).is_absolute()
            ):
                raise ValueError(f"Invalid {label}: expected a nonempty path segment, got {value!r}")
        return topic, cycle

    @staticmethod
    def _review_directory(destination: Path, root: Path) -> Path:
        for path in (destination, *destination.parents):
            if path.is_symlink() or (path.exists() and not path.is_dir()):
                raise ValueError("Review output directories must be real directories, not symlinks")
            if path == root:
                break
        if not destination.resolve().is_relative_to(root.resolve()):
            raise ValueError("Review output escapes its binding")
        return destination

    @property
    def review_cycle_output(self) -> Path:
        """Scope new Review publications by topic and cycle under the output binding."""
        root = self.review_output
        topic, cycle = self._review_identity()
        return self._review_directory(root / topic / cycle, root)

    @property
    def user_home(self) -> Path:
        return resolve_user_home(self.repo_root, self.alias)

    @property
    def report(self) -> Path:
        if self.playground_project is not None:
            return self._design_report()
        if self.master_skill:
            master_run = report_dir(
                self.repo_root,
                self.master_skill,
                self.master_run_id or self.run_id,
                feature_name=self.master_feature_name or self.feature_name,
                alias=self.alias,
            )
            return child_report_dir(
                self.repo_root,
                master_run,
                self.skill_name,
                alias=self.alias,
            )
        return report_dir(
            self.repo_root,
            self.skill_name,
            self.run_id,
            feature_name=self.feature_name,
            alias=self.alias,
        )

    @property
    def output(self) -> Path:
        if self.playground_project is not None:
            return self._design_output("deliverables")
        return self.report / "outputs" if self.master_skill else output_dir(self.repo_root, self.skill_name, self.alias)

    @property
    def working_output(self) -> Path:
        """Mutable-source previews stay distinct from saved deliverables."""
        return self._design_output("working") if self.playground_project is not None else self.output

    @property
    def cache(self) -> Path:
        return cache_dir(self.repo_root, self.skill_name, self.alias)

    @property
    def state(self) -> Path:
        return state_dir(self.repo_root, self.skill_name, self.alias)

    @property
    def grounding(self) -> Path:
        owner = self.master_skill or self.skill_name
        return grounding_dir(self.repo_root, owner, self.run_id, alias=self.alias)

    @property
    def private(self) -> Path:
        return private_dir(self.repo_root, self.skill_name, alias=self.alias)

    def presentation(self, deck_slug: str) -> Path:
        return presentation_dir(self.repo_root, deck_slug, self.alias)


def main() -> int:
    parser = argparse.ArgumentParser(description="Resolve an BabblelabReel artifact destination.")
    parser.add_argument("kind", choices=("home", "output", "working-output", "review-output", "review-cycle-output", "report", "presentation", "state", "cache", "grounding", "private"))
    parser.add_argument("skill", nargs="?")
    parser.add_argument("--run-id")
    parser.add_argument("--feature-name")
    parser.add_argument("--master-skill")
    parser.add_argument("--master-run-id")
    parser.add_argument("--master-feature-name")
    parser.add_argument("--playground-project", type=Path, help="Host-verified existing Design project container; binds report, output and working-output to its Design stage.")
    parser.add_argument("--review-project", type=Path, help="Host-verified existing Review project; affects review-output only.")
    parser.add_argument("--alias")
    parser.add_argument("--repo-root", default=str(Path(__file__).resolve().parents[2]))
    args = parser.parse_args()

    if args.kind == "home":
        path = resolve_user_home(args.repo_root, args.alias)
    else:
        if not args.skill:
            parser.error(f"{args.kind} requires a skill or deck name")
        if args.kind in {"review-output", "review-cycle-output"} and not args.run_id and not (args.master_skill and args.master_run_id):
            parser.error(f"{args.kind} requires an explicit --run-id (or bound --master-run-id)")
        context = ArtifactContext(
            args.repo_root,
            args.skill,
            args.run_id or "latest",
            alias=args.alias,
            master_feature_name=args.master_feature_name,
            feature_name=args.feature_name,
            master_skill=args.master_skill,
            master_run_id=args.master_run_id,
            playground_project=args.playground_project,
            review_project=args.review_project,
        )
        if args.kind == "output":
            path = context.output
        elif args.kind == "working-output":
            path = context.working_output
        elif args.kind == "review-output":
            path = context.review_output
        elif args.kind == "review-cycle-output":
            path = context.review_cycle_output
        elif args.kind == "report":
            path = context.report
        elif args.kind == "presentation":
            path = context.presentation(args.skill)
        elif args.kind == "state":
            path = context.state
        elif args.kind == "cache":
            path = context.cache
        elif args.kind == "private":
            path = context.private
        else:
            path = context.grounding

    print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
