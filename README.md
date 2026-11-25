# Mini Git

Git의 핵심 구조(커밋 그래프 DAG, 브랜치/HEAD, 그래프 탐색, 정렬, 역색인)를 직접 구현한 CLI 기반 Mini Git입니다.
외부 라이브러리 없이 Python 표준 라이브러리만 사용하며, `sorted()` / `list.sort()`와 그래프 라이브러리는 쓰지 않았습니다.

## 실행

```bash
python main.py            # Python 3.10 이상 (3.9에서도 동작 확인)
python -m unittest discover tests   # 테스트
```

## 명령어

명령어는 대소문자를 구분하지 않습니다. 공백이 들어간 인자는 따옴표로 감쌉니다. (예: `COMMIT "Add login feature"`)

| 명령 | 설명 |
| --- | --- |
| `INIT <user_name>` | 저장소 초기화, `main` 브랜치 생성 및 HEAD 설정, 현재 사용자 설정 |
| `BRANCH <branch_name>` | 현재 HEAD 커밋을 가리키는 새 브랜치 생성 |
| `SWITCH <branch_name>` | HEAD를 지정한 브랜치로 이동 |
| `COMMIT <message>` | 현재 HEAD를 부모로 하는 새 커밋 생성 (역색인 갱신) |
| `LOG` | 부모가 항상 자식보다 먼저 나오는 순서(위상 정렬)로 전체 커밋 출력 |
| `LOG --sort-by=date\|author` | 날짜 / 작성자 기준 정렬 (직접 구현한 병합 정렬) |
| `PATH <commit1> <commit2>` | 두 커밋 사이 최단 경로, 없으면 `No path` |
| `ANCESTORS <commit_hash>` | 도달 가능한 모든 조상 커밋 |
| `SEARCH <keyword>` | 메시지에 키워드가 포함된 커밋 (역색인) |
| `SEARCH --author=<name>` | 해당 작성자의 커밋 (역색인) |
| `HELP` / `EXIT` / `QUIT` | 도움말 / 종료 (Ctrl-D도 종료) |

- 커밋은 전체 hash 또는 **고유한 4자 이상의 접두사**로 지정할 수 있습니다.
- 에러 메시지: `Invalid args (usage: ...)`, `Unknown branch: <name>`, `Unknown commit: <hash>`,
  `Unknown command: <cmd>`, `Branch already exists: <name>`, `Ambiguous commit: <prefix>`,
  `Not a repository. Run INIT <user_name> first.`
- 다시 `INIT`을 하면 메모리 상의 저장소가 새로 초기화됩니다(이전 이력 삭제).

## 실행 예시

```
mini-git> init "Alice"
Initialized repository.
Current branch: main
Current user: Alice

mini-git> commit "Initial commit"
[main (root-commit) c49ea3e] Initial commit

mini-git> branch feature
Created branch: feature

mini-git> switch feature
Switched to branch: feature

mini-git> commit "Add login feature"
[feature e441586] Add login feature

mini-git> switch main
Switched to branch: main

mini-git> commit "Add payment feature"
[main 861fb7a] Add payment feature

mini-git> log
commit c49ea3e (Alice, 2026-11-25 17:49:50)
    Initial commit
commit e441586 (Alice, 2026-11-25 17:49:50) [feature]
    Add login feature
commit 861fb7a (Alice, 2026-11-25 17:49:50) [HEAD -> main]
    Add payment feature

mini-git> path e441586 861fb7a
Path: e441586 -> c49ea3e -> 861fb7a

mini-git> ancestors 861fb7a
Ancestors of 861fb7a (1 commit):
- c49ea3e (Alice, 2026-11-25 17:49:50): Initial commit

mini-git> search "login"
Found 1 commit:
- e441586 (Alice, 2026-11-25 17:49:50): Add login feature

mini-git> switch nope
Unknown branch: nope
```

`[...]` 안에는 그 커밋을 가리키는 브랜치가 표시되고, `HEAD ->`는 현재 브랜치입니다.

## 프로젝트 구조

```
main.py                 엔트리 포인트 (REPL 시작)
minigit/
  cli.py                REPL, 명령 파싱(shlex) -> 실행 -> 출력
  repository.py         저장소: 커밋 해시맵, 브랜치, HEAD, hash 생성
  models.py             Commit 노드 (hash, message, author, timestamp, parents)
  graph.py              위상 정렬, 최단 경로(BFS), 조상 탐색
  sorting.py            병합 정렬, 최소 힙 (직접 구현)
  index.py              역색인 (keyword -> hashes, author -> hashes)
tests/test_minigit.py   단위/시나리오 테스트
```

알고리즘(탐색/정렬/인덱싱)은 `Commit`이나 CLI에 의존하지 않는 독립 함수/클래스로 분리했습니다.
예를 들어 `graph.py`의 함수들은 `{노드: [부모, ...]}` 형태의 일반 dict만 받습니다.

## 설계 및 알고리즘 설명

### 1. 커밋 그래프는 왜 DAG인가

- 각 커밋은 0개 이상의 부모를 가집니다. 루트 커밋은 부모가 0개, 일반 커밋은 1개, 병합 커밋은 2개 이상입니다.
  부모가 여러 개일 수 있고 브랜치가 갈라질 수 있으므로 트리가 아니라 **그래프**입니다.
- 커밋은 **만들어지는 순간 이미 존재하는 커밋만 부모로 가리키고, 만들어진 뒤에는 바뀌지 않습니다.**
  간선(자식 → 부모)은 항상 "새 노드 → 옛 노드" 방향이므로, 따라가다가 자기 자신으로 돌아오는 사이클이 생길 수 없습니다.
  그래서 **방향성 비순환 그래프(DAG)** 입니다.
  실제 Git에서도 커밋 hash가 부모 hash를 포함한 내용으로 계산되기 때문에, 사이클을 만들려면 아직 존재하지 않는 hash를 미리 알아야 해서 불가능합니다.
- 저장소는 `dict[hash, Commit]` 해시맵이라 hash로 O(1)에 찾을 수 있습니다.
- **hash 유일성**: `증가 카운터 + 작성자 + 시각 + 부모 + 메시지`를 SHA-1로 해시한 뒤 앞 7자리를 씁니다.
  카운터가 매번 달라 입력이 겹치지 않고, 그래도 7자리가 기존 hash와 겹치면 자릿수를 늘리고, 40자 전체가 겹치면 카운터를 올려 다시 만듭니다.
  저장소에 없는 값만 반환하므로 세션 내 중복이 생기지 않습니다.

### 2. LOG: 부모가 먼저 나오는 출력 = 위상 정렬 (Kahn 알고리즘)

"최신순"이 아니라 "모든 부모가 자식보다 먼저"라는 조건은 DAG의 **위상 정렬** 그 자체입니다.

1. 각 커밋의 진입 차수 = 부모 수. 진입 차수 0인 커밋(루트)을 후보에 넣습니다.
2. 후보 하나를 꺼내 출력하고, 그 자식들의 진입 차수를 1 줄입니다. 0이 되면 후보에 넣습니다.
3. 모든 노드를 출력하면 끝. 출력 수가 노드 수보다 적으면 사이클이 있다는 뜻이므로 에러를 냅니다.

후보 집합을 **직접 구현한 최소 힙**(`(timestamp, 생성순번)` 기준)으로 관리하므로, 위상 순서를 지키는 범위에서 오래된 커밋이 먼저 나와 출력이 항상 같습니다.
시간복잡도는 O((V + E) log V)입니다. DFS 후위 순회 결과를 뒤집는 방식으로도 위상 정렬을 할 수 있지만, Kahn 방식은 "부모를 다 출력한 커밋만 출력 가능"이라는 조건이 코드에 그대로 드러나서 선택했습니다.

### 3. PATH: 무방향 최단 경로 + 사전순 최소 (BFS)

자식-부모 간선을 무방향으로 보면 가중치 없는 그래프이므로 **BFS**가 간선 수 기준 최단 경로를 줍니다.
최단 경로가 여러 개일 때 `hash1->hash2->...` 문자열이 사전순으로 가장 작은 경로를 고르기 위해 두 단계로 나눴습니다.

1. **도착점(goal)에서 BFS**를 돌려 모든 노드의 goal까지 거리 `dist`를 구합니다. start에 거리가 없으면 `No path`입니다.
2. start에서 출발해 매 단계 **`dist`가 정확히 1 줄어드는 이웃 중 hash가 가장 작은 이웃**을 고릅니다.

2번의 탐욕 선택이 옳은 이유: 후보 경로들은 모두 같은 노드에서 시작하므로 문자열 대소는 처음으로 달라지는 hash에서 결정됩니다.
그 자리에서 가장 작은 hash를 고르면 그보다 작은 경로는 없습니다. hash는 16진수 문자로만 이루어져 있고 구분자 `-`(0x2D)가 모든 16진수 문자보다 작으므로, hash 길이가 서로 달라도 이 성질이 유지됩니다.
`dist`가 1씩 줄어드는 이웃만 따라가므로 경로 길이는 항상 최단입니다.
시간복잡도는 O(V + E)입니다. (모든 최단 경로를 만들어 비교하면 경로 수가 지수적으로 늘 수 있습니다.)

예) 다이아몬드 `a ← b ← d`, `a ← c ← d`에서 `PATH a d` → `a -> b -> d` (b < c)

### 4. ANCESTORS: 조상 탐색 (BFS + visited)

커밋에서 부모 방향 간선만 따라가는 BFS입니다. 병합 커밋이 있으면 같은 조상에 여러 경로로 도달할 수 있으므로 `visited` 집합으로 **한 번씩만** 방문해 중복 없이, 빠짐없이 출력합니다.
가까운 조상부터 나열하며 시간복잡도는 O(V + E)입니다.

### 5. 정렬: 병합 정렬 직접 구현

`LOG --sort-by=date|author`는 `sorting.merge_sort(items, key=...)`를 씁니다. `key` 함수만 바꾸면 비교 기준이 바뀝니다.

| | 병합 정렬 |
| --- | --- |
| 평균 시간복잡도 | O(n log n) |
| 최악 시간복잡도 | O(n log n): 항상 절반으로 나누므로 깊이 log n, 각 깊이의 병합 비용 합 n |
| 공간복잡도 | O(n) |
| 안정 정렬 | **예**: 병합 시 오른쪽 원소가 *엄격히 작을 때만* 먼저 넣으므로 같은 키는 원래 순서 유지 |

- `date`: timestamp 오름차순. 동률이면 생성 순서 유지.
- `author`: 작성자 이름 오름차순(대소문자 무시). 같은 작성자 안에서는 생성 순서(=시간순) 유지.

안정 정렬이라 동률 처리 규칙을 따로 만들 필요 없이 "입력을 생성 순서로 넣는다"만으로 동률 순서가 정해집니다.
퀵 정렬은 평균 O(n log n)이지만 최악 O(n²)이고 일반적으로 불안정해서, 최악에도 O(n log n)이고 안정적인 병합 정렬을 골랐습니다.

LOG의 위상 정렬에는 직접 구현한 **이진 최소 힙**(`sorting.MinHeap`, push/pop O(log n))을 씁니다.

### 6. 역색인 (Inverted Index)

- 키워드 추출: 커밋 메시지를 공백으로 `split()`한 뒤 소문자(`lower()`)로 정규화합니다. 추가로 앞뒤 문장부호를 떼어 `"Login,"`도 `login`으로 찾을 수 있게 했습니다.
- 인덱스 2종: `keyword -> [commit_hash, ...]`, `author -> [commit_hash, ...]` (작성자는 대소문자 무시)
- COMMIT 시점에 두 인덱스를 갱신합니다. posting list는 생성 순서로 쌓이므로 검색 결과도 생성 순서입니다.
- 여러 단어로 검색하면(`SEARCH "add login"`) 모든 단어를 포함하는 커밋만 나옵니다(AND). 가장 짧은 posting list를 기준으로 나머지 단어의 집합에 있는지만 확인합니다.

**순회 검색보다 빠른 이유**: 순회 검색은 매번 N개 커밋의 메시지를 모두 훑어야 하므로 O(N × L) (L = 메시지 길이)입니다.
역색인은 커밋할 때 미리 "단어 → 커밋 목록"을 만들어 두므로 검색 시 해시맵 조회 O(1) + 결과 출력 O(K) (K = 결과 수)면 됩니다.
색인을 만드는 비용(커밋당 O(L))과 메모리를 미리 써서 검색 비용을 줄이는 방식입니다.

## 범위

- 보너스 과제(diff, merge, 정렬 성능 비교)는 구현하지 않았습니다. 다만 커밋 노드와 그래프 알고리즘은 부모가 2개 이상인 병합 커밋도 처리하도록 만들었고, 테스트에서 다이아몬드 구조로 확인합니다.
- 파일 내용 추적, 네트워크, 영속성 없이 메모리 상에서만 동작합니다.
