"""REPL 기반 CLI: 명령 파싱 -> 실행 -> 결과 출력."""

from __future__ import annotations

import shlex
from typing import Callable, Dict, List, Optional

from .models import Commit
from .repository import SORT_KEYS, MiniGitError, Repository

PROMPT = "mini-git> "
EXIT_COMMANDS = ("exit", "quit")

USAGE = {
    "init": "INIT <user_name>",
    "branch": "BRANCH <branch_name>",
    "switch": "SWITCH <branch_name>",
    "commit": "COMMIT <message>",
    "log": "LOG [--sort-by=date|author]",
    "path": "PATH <commit1> <commit2>",
    "ancestors": "ANCESTORS <commit_hash>",
    "search": "SEARCH <keyword> | SEARCH --author=<name>",
    "help": "HELP",
}

HELP_TEXT = "\n".join(
    ["Commands (case-insensitive):"]
    + [f"  {usage}" for usage in USAGE.values()]
    + ["  EXIT | QUIT", 'Wrap arguments that contain spaces in quotes, e.g. COMMIT "Add login".']
)


class InvalidArgs(Exception):
    """명령 인자 형식이 잘못되었음을 나타낸다."""


def parse_line(line: str) -> List[str]:
    """한 줄을 토큰으로 나눈다. 따옴표로 감싼 문자열은 공백을 포함한 하나의 토큰이 된다.

    Raises:
        InvalidArgs: 따옴표가 닫히지 않은 경우.
    """
    try:
        return shlex.split(line)
    except ValueError as exc:
        raise InvalidArgs from exc


def _join_text(args: List[str]) -> str:
    """문자열 인자를 하나로 합친다. 따옴표 없이 여러 단어를 입력해도 허용한다."""
    if not args:
        raise InvalidArgs
    text = " ".join(args).strip()
    if not text:
        raise InvalidArgs
    return text


def _single(args: List[str]) -> str:
    if len(args) != 1:
        raise InvalidArgs
    return args[0]


def _plural(count: int, word: str) -> str:
    return f"{count} {word}" if count == 1 else f"{count} {word}s"


class MiniGitCLI:
    """명령어 문자열을 받아 Repository 를 조작하고 출력 문자열을 돌려준다."""

    def __init__(self, repo: Optional[Repository] = None) -> None:
        self.repo = repo if repo is not None else Repository()
        self._handlers: Dict[str, Callable[[List[str]], str]] = {
            "init": self._cmd_init,
            "branch": self._cmd_branch,
            "switch": self._cmd_switch,
            "commit": self._cmd_commit,
            "log": self._cmd_log,
            "path": self._cmd_path,
            "ancestors": self._cmd_ancestors,
            "search": self._cmd_search,
            "help": self._cmd_help,
        }

    def execute(self, line: str) -> str:
        """명령 한 줄을 실행하고 출력할 문자열을 반환한다 (빈 줄이면 빈 문자열)."""
        try:
            tokens = parse_line(line)
        except InvalidArgs:
            return "Invalid args"
        if not tokens:
            return ""
        name, args = tokens[0].lower(), tokens[1:]
        handler = self._handlers.get(name)
        if handler is None:
            return f"Unknown command: {tokens[0]} (type HELP to see commands)"
        try:
            return handler(args)
        except InvalidArgs:
            return f"Invalid args (usage: {USAGE[name]})"
        except MiniGitError as exc:
            return str(exc)

    # ------------------------------------------------------------------ 출력 형식
    def _describe(self, commit: Commit) -> str:
        """LOG 한 항목: hash / author / timestamp / 브랜치 표시 + 메시지."""
        header = f"commit {commit.hash} ({commit.author}, {commit.time_str})"
        refs = self.repo.branches_at(commit.hash)
        if refs:
            labels = [f"HEAD -> {r}" if r == self.repo.head else r for r in refs]
            header += f" [{', '.join(labels)}]"
        if len(commit.parents) > 1:
            header += f"\nMerge: {' '.join(commit.parents)}"
        return f"{header}\n    {commit.message}"

    @staticmethod
    def _summary(commit: Commit) -> str:
        return f"- {commit.hash} ({commit.author}, {commit.time_str}): {commit.message}"

    # ------------------------------------------------------------------ 명령 처리
    def _cmd_init(self, args: List[str]) -> str:
        reinit = self.repo.init(_join_text(args))
        first = "Reinitialized repository (previous history cleared)." if reinit else "Initialized repository."
        return f"{first}\nCurrent branch: {self.repo.head}\nCurrent user: {self.repo.user}"

    def _cmd_branch(self, args: List[str]) -> str:
        name = _single(args)
        self.repo.create_branch(name)
        return f"Created branch: {name}"

    def _cmd_switch(self, args: List[str]) -> str:
        name = _single(args)
        self.repo.switch(name)
        return f"Switched to branch: {name}"

    def _cmd_commit(self, args: List[str]) -> str:
        commit = self.repo.commit(_join_text(args))
        root = " (root-commit)" if not commit.parents else ""
        return f"[{self.repo.head}{root} {commit.hash}] {commit.message}"

    def _cmd_log(self, args: List[str]) -> str:
        sort_by: Optional[str] = None
        if len(args) == 1 and args[0].lower().startswith("--sort-by="):
            sort_by = args[0].split("=", 1)[1].lower()
            if sort_by not in SORT_KEYS:
                raise InvalidArgs
        elif args:
            raise InvalidArgs
        commits = self.repo.log(sort_by)
        if not commits:
            return "No commits yet."
        return "\n".join(self._describe(c) for c in commits)

    def _cmd_path(self, args: List[str]) -> str:
        if len(args) != 2:
            raise InvalidArgs
        found = self.repo.path(args[0], args[1])
        if found is None:
            return "No path"
        return "Path: " + " -> ".join(c.hash for c in found)

    def _cmd_ancestors(self, args: List[str]) -> str:
        target = self.repo.resolve(_single(args))
        found = self.repo.ancestors(target.hash)
        if not found:
            return f"No ancestors: {target.hash} is a root commit."
        lines = [f"Ancestors of {target.hash} ({_plural(len(found), 'commit')}):"]
        lines.extend(self._summary(c) for c in found)
        return "\n".join(lines)

    def _cmd_search(self, args: List[str]) -> str:
        if len(args) == 1 and args[0].lower().startswith("--author="):
            found = self.repo.search_author(args[0].split("=", 1)[1])
        elif args and args[0].startswith("--"):
            raise InvalidArgs
        else:
            found = self.repo.search(_join_text(args))
        if not found:
            return "No commits found."
        lines = [f"Found {_plural(len(found), 'commit')}:"]
        lines.extend(self._summary(c) for c in found)
        return "\n".join(lines)

    def _cmd_help(self, args: List[str]) -> str:
        return HELP_TEXT

    # ------------------------------------------------------------------ REPL
    def run(self) -> None:
        """mini-git> 프롬프트에서 명령을 반복 입력받는다. exit/quit 또는 EOF(Ctrl-D)로 종료."""
        print('Mini Git. Type HELP for commands, EXIT to quit.')
        while True:
            try:
                line = input(PROMPT)
            except (EOFError, KeyboardInterrupt):
                print()
                break
            if line.strip().lower() in EXIT_COMMANDS:
                break
            output = self.execute(line)
            if output:
                print(output)
            print()
        print("Bye.")
