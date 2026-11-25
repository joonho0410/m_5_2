"""Mini Git 엔트리 포인트.

실행: python main.py
"""

from minigit.cli import MiniGitCLI


def main() -> None:
    """REPL 을 시작한다."""
    MiniGitCLI().run()


if __name__ == "__main__":
    main()
