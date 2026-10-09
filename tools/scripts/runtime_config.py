"""Resolve BabblelabReel's machine-local runtime configuration.

The canonical config lives at ``<BABBLELABREEL_ROOT>/.babblelabreel/user.json`` and uses:

.. code-block:: json

    {
      "schemaVersion": 1,
      "alias": "user",
      "userHome": "/absolute/path/to/BabblelabReel"
    }

``userHome`` is one user's output root. ``usersRoot`` is the optional
multi-user container used by shared/CI checkouts. Legacy ``babblelabreelUserHome``,
``userRoot``, and ``usersDir`` keys remain readable.
"""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
import hashlib
import stat
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Mapping


CONFIG_SCHEMA_VERSION = 1
CONFIG_RELATIVE_PATH = Path(".babblelabreel/user.json")
SINGLE_HOME_KEYS = ("userHome", "babblelabreelUserHome", "userRoot")
USERS_ROOT_KEYS = ("usersRoot", "usersDir")
ONEDRIVE_ENV_KEYS = ("OneDriveCommercial", "OneDrive", "OneDriveConsumer")


class RuntimeConfigConflict(ValueError):
    """The configuration changed since the caller read its revision."""


@contextmanager
def _directory_handle(path: Path, *, create: bool = False):
    """Walk absolute directories without following links, including ancestors."""
    if os.name != "posix" or not hasattr(os, "O_NOFOLLOW"):
        raise ValueError("Changing USER_HOME requires POSIX no-follow filesystem support")
    fd = os.open(path.anchor, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        for part in path.parts[1:]:
            if create:
                try:
                    os.mkdir(part, mode=0o700, dir_fd=fd)
                except FileExistsError:
                    pass
            child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            os.close(fd)
            fd = child
        yield fd
    finally:
        os.close(fd)


def _config_snapshot(directory_fd: int) -> tuple[dict, str | None]:
    try:
        fd = os.open("user.json", os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory_fd)
    except FileNotFoundError:
        return {}, None
    with os.fdopen(fd, "rb") as stream:
        if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
            raise ValueError("Runtime configuration must be a regular JSON file")
        raw = stream.read(1024 * 1024 + 1)
    if len(raw) > 1024 * 1024:
        raise ValueError("Runtime configuration exceeds 1 MiB")
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError("Runtime configuration must be a JSON object")
    return data, hashlib.sha256(raw).hexdigest()


def runtime_config_snapshot(repo_root: Path | str) -> tuple[dict, str | None]:
    """Read configuration and its revision without creating any filesystem entry."""
    root = Path(repo_root).expanduser().absolute()
    try:
        with _directory_handle(root / CONFIG_RELATIVE_PATH.parent) as fd:
            return _config_snapshot(fd)
    except FileNotFoundError:
        return {}, None


def _is_emma_assets_root(path: Path) -> bool:
    return (
        (path / ".plugin/plugin.json").is_file()
        and (path / "tools/scripts/runtime_config.py").is_file()
    )


def _selected_user_home(repo_root: Path, user_home: Path | str) -> Path:
    if not isinstance(user_home, (str, Path)) or not str(user_home).strip():
        raise ValueError("USER_HOME must be an explicit absolute directory")
    text = str(user_home)
    target = Path(text)
    if (
        not target.is_absolute() or ".." in target.parts
        or text != text.strip() or any(ord(char) < 32 for char in text)
    ):
        raise ValueError("USER_HOME must be an explicit absolute directory without traversal")
    if (
        target == Path(target.anchor)
        or target == repo_root or target.is_relative_to(repo_root)
        or repo_root.is_relative_to(target)
    ):
        raise ValueError("USER_HOME must be outside BabblelabReel source and cannot contain BabblelabReel source")
    for ancestor in (target, *target.parents):
        if _is_emma_assets_root(ancestor):
            raise ValueError("USER_HOME cannot be inside BabblelabReel source or installed plugin assets")
    # Check all existing components before creating anything; missing children are OK.
    current = Path(target.anchor)
    for part in target.parts[1:]:
        current /= part
        try:
            mode = current.lstat().st_mode
        except FileNotFoundError:
            break
        if not stat.S_ISDIR(mode):
            raise ValueError("USER_HOME must be a directory with no symbolic-link components")
    return target


def set_user_home(
    repo_root: Path | str,
    user_home: Path | str,
    *,
    expected_revision: str | None,
) -> dict:
    """Save an explicit selection without changing environment/CLI precedence.

    This is an explicit-write API for a writable BabblelabReel source checkout, not a
    startup operation. Existing user files are never copied, moved or deleted.
    Unknown configuration fields and aliases are retained.
    """
    import fcntl

    root = Path(repo_root).expanduser().absolute()
    if not (root / ".git").exists():
        raise ValueError("Changing USER_HOME requires a writable BabblelabReel source checkout, not installed assets")
    target = _selected_user_home(root, user_home)
    _, revision = runtime_config_snapshot(root)
    if revision != expected_revision:
        raise RuntimeConfigConflict("Storage settings changed; reload before saving")
    with _directory_handle(root / CONFIG_RELATIVE_PATH.parent, create=True) as config_fd:
        fcntl.flock(config_fd, fcntl.LOCK_EX)
        try:
            data, revision = _config_snapshot(config_fd)
            if revision != expected_revision:
                raise RuntimeConfigConflict("Storage settings changed; reload before saving")
            with _directory_handle(target, create=True) as home_fd:
                probe = f".babblelabreel-write-check-{uuid.uuid4().hex}"
                probe_fd = os.open(probe, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=home_fd)
                os.close(probe_fd)
                os.unlink(probe, dir_fd=home_fd)
            data.update({"schemaVersion": CONFIG_SCHEMA_VERSION, "userHome": str(target)})
            raw = (json.dumps(data, indent=2, allow_nan=False) + "\n").encode("utf-8")
            temporary = f".user.json.{uuid.uuid4().hex}.tmp"
            try:
                fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=config_fd)
                with os.fdopen(fd, "wb") as stream:
                    stream.write(raw)
                    stream.flush()
                    os.fsync(stream.fileno())
                # Catch changes made by older, non-locking config writers too.
                if _config_snapshot(config_fd)[1] != expected_revision:
                    raise RuntimeConfigConflict("Storage settings changed; reload before saving")
                os.replace(temporary, "user.json", src_dir_fd=config_fd, dst_dir_fd=config_fd)
                os.fsync(config_fd)
            finally:
                try:
                    os.unlink(temporary, dir_fd=config_fd)
                except FileNotFoundError:
                    pass
        finally:
            fcntl.flock(config_fd, fcntl.LOCK_UN)
    return {
        "configuredHome": str(target),
        "configPath": str(root / CONFIG_RELATIVE_PATH),
        "revision": hashlib.sha256(raw).hexdigest(),
        "selectionSaved": True,
    }


@dataclass(frozen=True)
class RuntimeConfig:
    schema_version: int
    repo_root: Path
    config_path: Path
    alias: str
    user_home: Path
    user_home_source: str
    state_home: Path


@dataclass(frozen=True)
class UserWorkspace:
    alias: str
    home: Path
    source: str


def _validate_alias(alias: str) -> str:
    value = alias.strip()
    if (
        not value
        or value in {".", ".."}
        or Path(value).is_absolute()
        or "/" in value
        or "\\" in value
        or "\x00" in value
    ):
        raise ValueError(f"Invalid user alias: {alias!r}")
    return value


def _workspace_home(users_root: Path, alias: str) -> Path:
    root = users_root.expanduser().resolve()
    safe_alias = _validate_alias(alias)
    home = (root / safe_alias).resolve()
    try:
        home.relative_to(root)
    except ValueError as error:
        raise ValueError(
            f"User workspace for alias {safe_alias!r} escapes users root {root}"
        ) from error
    return home


def load_runtime_config(repo_root: Path | str) -> dict:
    path = Path(repo_root) / CONFIG_RELATIVE_PATH
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {}
    return data if isinstance(data, dict) else {}


def resolve_alias(
    repo_root: Path | str,
    explicit: str | None = None,
    *,
    config: Mapping[str, object] | None = None,
    environ: Mapping[str, str] | None = None,
) -> str:
    if explicit and explicit.strip():
        return _validate_alias(explicit)

    repo_root = Path(repo_root)
    config = config if config is not None else load_runtime_config(repo_root)
    configured = str(config.get("alias", "")).strip()
    if configured:
        return _validate_alias(configured)

    environ = environ if environ is not None else os.environ
    for key in ("BABBLELABREEL_USER_ALIAS", "USER_ALIAS"):
        value = environ.get(key, "").strip()
        if value:
            return _validate_alias(value)

    try:
        completed = subprocess.run(
            ["git", "config", "--get", "user.email"],
            cwd=str(repo_root),
            text=True,
            capture_output=True,
            timeout=5,
            check=False,
        )
        email = completed.stdout.strip()
        if "@" in email:
            return _validate_alias(email.split("@", 1)[0])
    except (OSError, subprocess.SubprocessError):
        pass

    return _validate_alias(
        environ.get("USER")
        or environ.get("USERNAME")
        or Path.home().name
        or "default"
    )


def _configured_path(config: Mapping[str, object], keys: Iterable[str]) -> tuple[Path | None, str]:
    for key in keys:
        value = str(config.get(key, "")).strip()
        if value:
            return Path(value).expanduser(), f"config:{key}"
    return None, ""


def _state_home(environ: Mapping[str, str]) -> Path:
    explicit = environ.get("BABBLELABREEL_STATE_HOME", "").strip()
    if explicit:
        return Path(explicit).expanduser()
    xdg = environ.get("XDG_STATE_HOME", "").strip()
    if xdg:
        return Path(xdg).expanduser() / "babblelabreel"
    home = environ.get("HOME", "").strip()
    if home:
        return Path(home).expanduser() / ".local" / "state" / "babblelabreel"
    return Path(tempfile.gettempdir()) / "babblelabreel"


def default_local_user_home(
    *,
    environ: Mapping[str, str] | None = None,
    home: Path | str | None = None,
) -> Path:
    """Return ``<OneDrive>/BabblelabReel`` when available, otherwise ``~/BabblelabReel``."""
    environ = environ if environ is not None else os.environ
    user_home = Path(home).expanduser() if home is not None else Path.home()
    candidates: list[Path] = []
    for key in ONEDRIVE_ENV_KEYS:
        value = environ.get(key, "").strip()
        if value:
            candidates.append(Path(value).expanduser())

    cloud_storage = user_home / "Library" / "CloudStorage"
    if cloud_storage.is_dir():
        candidates.extend(sorted(cloud_storage.glob("OneDrive-*")))
    candidates.extend(sorted(user_home.glob("OneDrive*")))

    seen: set[str] = set()
    for candidate in candidates:
        resolved = candidate.resolve()
        key = str(resolved).casefold()
        if key not in seen and resolved.is_dir():
            seen.add(key)
            return resolved / "BabblelabReel"
    return user_home.resolve() / "BabblelabReel"


def resolve_runtime_config(
    repo_root: Path | str,
    alias: str | None = None,
    *,
    explicit_user_home: Path | str | None = None,
    environ: Mapping[str, str] | None = None,
) -> RuntimeConfig:
    repo_root = Path(repo_root).expanduser().resolve()
    config_path = repo_root / CONFIG_RELATIVE_PATH
    config = load_runtime_config(repo_root)
    environ = environ if environ is not None else os.environ
    resolved_alias = resolve_alias(repo_root, alias, config=config, environ=environ)

    if explicit_user_home is not None:
        user_home = Path(explicit_user_home).expanduser()
        source = "cli:user-home"
    elif environ.get("BABBLELABREEL_USER_HOME", "").strip():
        user_home = Path(environ["BABBLELABREEL_USER_HOME"]).expanduser()
        source = "env:BABBLELABREEL_USER_HOME"
    else:
        user_home, source = _configured_path(config, SINGLE_HOME_KEYS)
        if user_home is None:
            users_root, root_source = _configured_path(config, USERS_ROOT_KEYS)
            if users_root is None:
                user_home = default_local_user_home(environ=environ)
                source = "default:local-user-home"
            if users_root is not None:
                user_home = _workspace_home(users_root, resolved_alias)
                source = root_source

    configured_version = config.get("schemaVersion", CONFIG_SCHEMA_VERSION)
    try:
        schema_version = int(configured_version)
    except (TypeError, ValueError):
        schema_version = 0

    return RuntimeConfig(
        schema_version=schema_version,
        repo_root=repo_root,
        config_path=config_path,
        alias=resolved_alias,
        user_home=user_home.resolve(),
        user_home_source=source,
        state_home=_state_home(environ).resolve(),
    )


def ensure_runtime_user_home(
    repo_root: Path | str,
    alias: str | None = None,
    *,
    explicit_user_home: Path | str | None = None,
    environ: Mapping[str, str] | None = None,
) -> RuntimeConfig:
    """Resolve USER_HOME, reject non-directory targets, and create it if absent."""
    runtime = resolve_runtime_config(
        repo_root,
        alias,
        explicit_user_home=explicit_user_home,
        environ=environ,
    )
    environment = environ if environ is not None else os.environ
    environment_home = environment.get("BABBLELABREEL_USER_HOME", "").strip()
    if environment_home and not Path(environment_home).expanduser().is_absolute():
        raise ValueError(f"BABBLELABREEL_USER_HOME must be an absolute path: {environment_home}")
    if runtime.user_home.exists() and not runtime.user_home.is_dir():
        raise ValueError(f"BABBLELABREEL_USER_HOME must be a directory: {runtime.user_home}")
    runtime.user_home.mkdir(parents=True, exist_ok=True)
    return runtime


def _aliases_in_root(users_root: Path, excluded_aliases: set[str]) -> list[str]:
    if not users_root.is_dir():
        return []
    return [
        child.name
        for child in sorted(users_root.iterdir())
        if child.is_dir()
        and not child.name.startswith(".")
        and child.name not in excluded_aliases
    ]


def resolve_user_workspaces(
    repo_root: Path | str,
    *,
    cli_user_home: Path | str | None = None,
    cli_users_dir: Path | str | None = None,
    cli_aliases: Iterable[str] | None = None,
    excluded_aliases: set[str] | None = None,
    environ: Mapping[str, str] | None = None,
) -> list[UserWorkspace]:
    """Resolve concrete user workspaces for scanners such as Rehydrate.

    ``--user-home`` and a configured/env ``userHome`` represent one workspace
    directly. Only explicit ``--users-dir`` or configured
    ``usersRoot``/legacy ``usersDir`` values enable multi-user mode.
    """

    if cli_user_home is not None and cli_users_dir is not None:
        raise ValueError("--user-home and --users-dir are mutually exclusive")

    repo_root = Path(repo_root).expanduser().resolve()
    config = load_runtime_config(repo_root)
    environ = environ if environ is not None else os.environ
    excluded_aliases = excluded_aliases or set()
    aliases = [
        _validate_alias(alias)
        for alias in (cli_aliases or [])
        if alias.strip()
    ]
    configured_alias_value = str(config.get("alias", "")).strip()
    configured_alias = (
        _validate_alias(configured_alias_value) if configured_alias_value else None
    )

    if cli_user_home is not None:
        if len(aliases) > 1:
            raise ValueError("--user-home accepts at most one --alias")
        runtime = resolve_runtime_config(
            repo_root,
            aliases[0] if aliases else None,
            explicit_user_home=cli_user_home,
            environ=environ,
        )
        return [UserWorkspace(runtime.alias, runtime.user_home, runtime.user_home_source)]

    if cli_users_dir is not None:
        users_root = Path(cli_users_dir).expanduser().resolve()
        selected = aliases or _aliases_in_root(users_root, excluded_aliases)
        return [
            UserWorkspace(alias, _workspace_home(users_root, alias), "cli:users-dir")
            for alias in selected
            if alias not in excluded_aliases
        ]

    env_home = environ.get("BABBLELABREEL_USER_HOME", "").strip()
    configured_home, configured_source = _configured_path(config, SINGLE_HOME_KEYS)
    if env_home or configured_home is not None:
        if len(aliases) > 1:
            raise ValueError("Configured userHome supports only one alias; use --users-dir for a multi-user scan")
        if (
            not env_home
            and configured_alias is not None
            and aliases
            and aliases[0] != configured_alias
        ):
            raise ValueError(
                f"Configured userHome belongs to alias '{configured_alias}'; "
                "use --users-dir for a multi-user scan"
            )
        runtime = resolve_runtime_config(
            repo_root,
            aliases[0] if aliases else None,
            environ=environ,
        )
        source = "env:BABBLELABREEL_USER_HOME" if env_home else configured_source
        return [UserWorkspace(runtime.alias, runtime.user_home, source)]

    users_root, source = _configured_path(config, USERS_ROOT_KEYS)
    if users_root is None:
        if len(aliases) > 1:
            raise ValueError("The local USER_HOME default supports one alias; use --users-dir for a multi-user scan")
        runtime = resolve_runtime_config(
            repo_root,
            aliases[0] if aliases else None,
            environ=environ,
        )
        if runtime.alias in excluded_aliases:
            return []
        return [UserWorkspace(runtime.alias, runtime.user_home, runtime.user_home_source)]
    users_root = users_root.resolve()
    env_alias = next(
        (
            _validate_alias(environ[key])
            for key in ("BABBLELABREEL_USER_ALIAS", "USER_ALIAS")
            if environ.get(key, "").strip()
        ),
        None,
    )
    selected = (
        aliases
        or ([configured_alias] if configured_alias else [])
        or ([env_alias] if env_alias else [])
        or _aliases_in_root(users_root, excluded_aliases)
    )
    return [
        UserWorkspace(alias, _workspace_home(users_root, alias), source)
        for alias in selected
        if alias not in excluded_aliases
    ]


def write_runtime_config(
    repo_root: Path | str,
    *,
    alias: str,
    user_home: Path | str,
) -> Path:
    """Atomically persist the canonical versioned runtime config."""

    repo_root = Path(repo_root).expanduser().resolve()
    path = repo_root / CONFIG_RELATIVE_PATH
    data = load_runtime_config(repo_root)
    alias = _validate_alias(alias)
    data.update(
        {
            "schemaVersion": CONFIG_SCHEMA_VERSION,
            "alias": alias,
            "userHome": str(Path(user_home).expanduser().resolve()),
        }
    )

    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        path.parent.chmod(0o700)
    except OSError:
        pass
    temp_path = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temp_path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    try:
        temp_path.chmod(0o600)
        os.replace(temp_path, path)
        path.chmod(0o600)
    finally:
        if temp_path.exists():
            temp_path.unlink()
    return path
