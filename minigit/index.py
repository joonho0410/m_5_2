"""역색인(Inverted Index).

"문서 -> 단어" 가 아니라 "단어 -> 문서 목록(posting list)" 으로 저장해 두면,
검색할 때 모든 커밋을 순회(O(N x 메시지 길이))하지 않고 해시맵 조회 O(1) 로
후보 커밋 목록을 바로 가져올 수 있다. (결과 출력 비용은 O(결과 수))
"""

from __future__ import annotations

import string
from typing import Dict, List, Set

_PUNCTUATION = string.punctuation


def normalize_token(token: str) -> str:
    """토큰을 소문자로 정규화하고 앞뒤 문장부호를 제거한다.

    예: "Login," -> "login", "Fix:" -> "fix". 문장부호만으로 된 토큰은 그대로 둔다.
    """
    lowered = token.lower()
    stripped = lowered.strip(_PUNCTUATION)
    return stripped or lowered


def tokenize(text: str) -> List[str]:
    """텍스트를 공백 기준으로 split 하고 정규화한 키워드 목록을 반환한다 (중복 제거, 순서 유지)."""
    seen: Set[str] = set()
    tokens: List[str] = []
    for raw in text.split():
        token = normalize_token(raw)
        if token not in seen:
            seen.add(token)
            tokens.append(token)
    return tokens


def normalize_author(name: str) -> str:
    """작성자 이름을 색인 키로 정규화한다 (앞뒤 공백 제거, 소문자)."""
    return " ".join(name.split()).lower()


class InvertedIndex:
    """term -> 문서 id 목록 을 저장하는 역색인.

    문서 id 는 추가된 순서대로(=커밋 생성 순서) 저장되며 같은 term 에 중복 저장하지 않는다.
    """

    def __init__(self) -> None:
        self._postings: Dict[str, List[str]] = {}
        self._members: Dict[str, Set[str]] = {}

    def add(self, term: str, doc_id: str) -> None:
        """term 의 posting list 에 doc_id 를 추가한다. O(1)."""
        members = self._members.setdefault(term, set())
        if doc_id in members:
            return
        members.add(doc_id)
        self._postings.setdefault(term, []).append(doc_id)

    def lookup(self, term: str) -> List[str]:
        """term 을 포함하는 문서 id 목록을 반환한다. O(1) 조회 + O(결과 수) 복사."""
        return list(self._postings.get(term, []))

    def lookup_all(self, terms: List[str]) -> List[str]:
        """모든 term 을 포함하는 문서 id 목록(AND 검색)을 반환한다.

        가장 짧은 posting list 를 기준으로 나머지 term 의 멤버 집합에 있는지만 확인하므로
        O(가장 짧은 posting list 길이 x term 수) 이다.
        """
        if not terms:
            return []
        shortest = terms[0]
        for term in terms[1:]:
            if len(self._postings.get(term, [])) < len(self._postings.get(shortest, [])):
                shortest = term
        others = [self._members.get(term, set()) for term in terms if term != shortest]
        return [doc for doc in self._postings.get(shortest, []) if all(doc in m for m in others)]


class CommitSearchIndex:
    """커밋 검색용 역색인 2종(keyword, author)을 묶어 관리한다."""

    def __init__(self) -> None:
        self.keyword_index = InvertedIndex()
        self.author_index = InvertedIndex()

    def add_commit(self, commit_hash: str, message: str, author: str) -> None:
        """새 커밋의 메시지 키워드와 작성자를 색인에 반영한다."""
        for token in tokenize(message):
            self.keyword_index.add(token, commit_hash)
        self.author_index.add(normalize_author(author), commit_hash)

    def search_keyword(self, query: str) -> List[str]:
        """키워드를 포함하는 커밋 hash 목록. 여러 단어면 모두 포함하는 커밋만(AND)."""
        return self.keyword_index.lookup_all(tokenize(query))

    def search_author(self, name: str) -> List[str]:
        """해당 작성자의 커밋 hash 목록 (대소문자 무시)."""
        return self.author_index.lookup(normalize_author(name))
