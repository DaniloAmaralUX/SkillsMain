"""Stage a delivery on the destination volume and recover an interrupted replacement."""
from contextlib import contextmanager
import os
from pathlib import Path
import re
import shutil
import tempfile
import uuid


@contextmanager
def locked_output(project):
    state = project / ".viewer-build"
    state.mkdir(exist_ok=True)
    try:
        with (state / ".gitignore").open("x", encoding="ascii") as ignored:
            ignored.write("*\n")
    except FileExistsError:
        pass
    output = project / "dist"
    output.mkdir(exist_ok=True)
    # OS locks are released when the process exits, including abnormal termination.
    with (state / "lock").open("a+b") as handle:
        try:
            if os.name == "nt":
                import msvcrt
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            raise ValueError("Outra geração está usando este projeto. Aguarde e tente novamente.") from exc
        pending = state / "pending"
        if pending.exists():
            recover(output, pending)
        draft_pending = state / "draft-transaction/pending"
        if draft_pending.exists():
            recover(state / "draft", draft_pending)
        yield output


def check_name(name):
    if not re.fullmatch(r"[A-Za-z0-9_-]+(?:\.html|-SPEC\.md)|resultado\.json", name):
        raise ValueError("Nome inesperado na revisão do viewer.")


def recover(output, pending):
    """A consumed 'next' file identifies a replacement executed before interruption."""
    for item in pending.iterdir():
        check_name(item.name)
        if (item / "next").exists():
            continue
        target = output / item.name
        original = item / "original"
        if original.exists():
            original.replace(target)
        elif (item / "absent").exists():
            target.unlink(missing_ok=True)
    with tempfile.TemporaryDirectory(dir=pending.parent) as trash:
        pending.rename(Path(trash) / "resolved")


@contextmanager
def destination_file(directory):
    """Create with the same inherited permissions as a normal file in the target folder."""
    temporary = directory / f".viewer-{uuid.uuid4().hex}.tmp"
    with temporary.open("xb"):
        pass
    try:
        yield temporary
    finally:
        temporary.unlink(missing_ok=True)


def stage_entry(stage, target, text):
    check_name(target.name)
    if target.is_symlink():
        raise ValueError(f"O destino {target.name} é um link simbólico.")
    item = stage / target.name
    item.mkdir()
    # Renames on NTFS keep a file's ACL. Files created inside TemporaryDirectory
    # can only be read by the building account, even after moving them to dist.
    with destination_file(target.parent) as candidate:
        candidate.replace(item / "next")
    (item / "next").write_text(text, encoding="utf-8", newline="\n")
    if target.exists():
        try:
            os.link(target, item / "original")
        except OSError:
            # File systems without hard links still stage a readable rollback copy.
            with destination_file(target.parent) as backup:
                backup.replace(item / "original")
            shutil.copy2(target, item / "original")
    else:
        (item / "absent").touch()


def publish(output, contents, state=None):
    """Caller holds locked_output. HTML, SPEC and the report belong to one revision."""
    if state is None:
        state = output.parent / ".viewer-build"
    state.mkdir(exist_ok=True)
    pending = state / "pending"
    with tempfile.TemporaryDirectory(dir=state) as staging:
        stage = Path(staging) / "revision"
        stage.mkdir()
        for name, text in contents.items():
            stage_entry(stage, output / name, text)
        stage.rename(pending)
        try:
            for name in contents:
                (pending / name / "next").replace(output / name)
            pending.rename(stage)
        except OSError:
            recover(output, pending)
            raise
