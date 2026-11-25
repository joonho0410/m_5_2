"""Mini Git 테스트. 실행: python -m unittest discover tests"""

import random
import unittest
from datetime import datetime, timedelta

from minigit import graph
from minigit.cli import MiniGitCLI
from minigit.index import CommitSearchIndex, tokenize
from minigit.repository import Repository
from minigit.sorting import MinHeap, merge_sort


def fake_clock(start=datetime(2024, 1, 15, 9, 0, 0), step=timedelta(minutes=15)):
    """호출할 때마다 step 만큼 증가하는 시각을 돌려주는 가짜 시계."""
    state = {"now": start - step}

    def clock():
        state["now"] += step
        return state["now"]

    return clock


class SortingTest(unittest.TestCase):
    def test_merge_sort_matches_expected_order(self):
        rng = random.Random(0)
        for size in range(0, 60):
            data = [rng.randint(-20, 20) for _ in range(size)]
            result = merge_sort(data)
            self.assertTrue(all(result[i] <= result[i + 1] for i in range(len(result) - 1)))
            self.assertEqual(len(result), size)
            for value in set(data):
                self.assertEqual(result.count(value), data.count(value))

    def test_merge_sort_is_stable_with_key(self):
        items = [("b", 1), ("a", 2), ("b", 3), ("a", 4), ("c", 5), ("a", 6)]
        result = merge_sort(items, key=lambda x: x[0])
        self.assertEqual(result, [("a", 2), ("a", 4), ("a", 6), ("b", 1), ("b", 3), ("c", 5)])

    def test_merge_sort_does_not_mutate_input(self):
        data = [3, 1, 2]
        merge_sort(data)
        self.assertEqual(data, [3, 1, 2])

    def test_min_heap(self):
        heap = MinHeap()
        for value in [5, 3, 8, 1, 9, 2, 7]:
            heap.push(value, str(value))
        self.assertEqual([heap.pop() for _ in range(len(heap))], ["1", "2", "3", "5", "7", "8", "9"])
        with self.assertRaises(IndexError):
            heap.pop()


class GraphTest(unittest.TestCase):
    #   a <- b <- d
    #   a <- c <- d   (d 는 병합 커밋: 부모 b, c)
    #   x            (연결되지 않은 별도 루트)
    DIAMOND = {"a": [], "b": ["a"], "c": ["a"], "d": ["b", "c"], "x": []}

    def test_topological_order_parents_first(self):
        order = graph.topological_order(self.DIAMOND, priority=lambda n: n)
        position = {node: i for i, node in enumerate(order)}
        for node, parents in self.DIAMOND.items():
            for parent in parents:
                self.assertLess(position[parent], position[node])
        self.assertEqual(sorted_copy(order), sorted_copy(self.DIAMOND))

    def test_topological_order_detects_cycle(self):
        with self.assertRaises(ValueError):
            graph.topological_order({"a": ["b"], "b": ["a"]}, priority=lambda n: n)

    def test_shortest_path_picks_lexicographically_smallest(self):
        # b -> d, c -> d 둘 다 길이 2 인 경로: a->b->d 가 사전순으로 더 작다.
        self.assertEqual(graph.shortest_path(self.DIAMOND, "a", "d"), ["a", "b", "d"])
        self.assertEqual(graph.shortest_path(self.DIAMOND, "d", "a"), ["d", "b", "a"])

    def test_shortest_path_through_common_ancestor(self):
        # 형제 b, c 는 공통 부모 a (또는 공통 자식 d) 를 통해 연결된다.
        self.assertEqual(graph.shortest_path(self.DIAMOND, "b", "c"), ["b", "a", "c"])

    def test_shortest_path_same_node_and_no_path(self):
        self.assertEqual(graph.shortest_path(self.DIAMOND, "a", "a"), ["a"])
        self.assertIsNone(graph.shortest_path(self.DIAMOND, "a", "x"))

    def test_shortest_path_prefers_shorter_over_lexicographic(self):
        g = {"s": [], "a": ["s"], "b": ["a"], "z": ["s"], "t": ["b", "z"]}
        # s->a->b->t (3) 보다 s->z->t (2) 가 짧다.
        self.assertEqual(graph.shortest_path(g, "s", "t"), ["s", "z", "t"])

    def test_ancestors_visits_each_once(self):
        self.assertEqual(graph.ancestors(self.DIAMOND, "d"), ["b", "c", "a"])
        self.assertEqual(graph.ancestors(self.DIAMOND, "a"), [])


def sorted_copy(iterable):
    return merge_sort(list(iterable))


class IndexTest(unittest.TestCase):
    def test_tokenize(self):
        self.assertEqual(tokenize("Fix: Login, login BUG"), ["fix", "login", "bug"])

    def test_keyword_and_author_index(self):
        index = CommitSearchIndex()
        index.add_commit("h1", "Add login feature", "Alice")
        index.add_commit("h2", "Fix login bug", "Bob")
        index.add_commit("h3", "Add payment", "alice")
        self.assertEqual(index.search_keyword("LOGIN"), ["h1", "h2"])
        self.assertEqual(index.search_keyword("add login"), ["h1"])
        self.assertEqual(index.search_keyword("nothing"), [])
        self.assertEqual(index.search_author("ALICE"), ["h1", "h3"])


class RepositoryTest(unittest.TestCase):
    def setUp(self):
        self.repo = Repository(clock=fake_clock())
        self.repo.init("Alice")

    def test_hashes_are_unique(self):
        hashes = {self.repo.commit(f"commit {i}").hash for i in range(500)}
        self.assertEqual(len(hashes), 500)

    def test_branch_points_to_head_commit(self):
        c1 = self.repo.commit("one")
        self.repo.create_branch("feature")
        self.assertEqual(self.repo.branches["feature"], c1.hash)
        self.repo.switch("feature")
        c2 = self.repo.commit("two")
        self.assertEqual(c2.parents, (c1.hash,))
        self.assertEqual(self.repo.branches["main"], c1.hash)

    def test_resolve_prefix(self):
        c1 = self.repo.commit("one")
        self.assertIs(self.repo.resolve(c1.hash[:4]), c1)


class CLITest(unittest.TestCase):
    def setUp(self):
        self.cli = MiniGitCLI(Repository(clock=fake_clock()))

    def run_cmd(self, line):
        return self.cli.execute(line)

    def commit_hash(self, line):
        # "[main abc1234] message" 또는 "[main (root-commit) abc1234] message"
        return self.run_cmd(line).split("]")[0].split()[-1]

    def test_requires_init(self):
        self.assertIn("INIT", self.run_cmd("commit hello"))

    def test_example_scenario(self):
        out = self.run_cmd('init "Alice"')
        self.assertIn("Current branch: main", out)
        self.assertIn("Current user: Alice", out)
        c1 = self.commit_hash('commit "Initial commit"')
        self.assertEqual(self.run_cmd("branch feature"), "Created branch: feature")
        self.assertEqual(self.run_cmd("SWITCH feature"), "Switched to branch: feature")
        c2 = self.commit_hash('Commit "Add login feature"')
        self.run_cmd("switch main")
        c3 = self.commit_hash('commit "Add payment feature"')

        log = self.run_cmd("log")
        self.assertLess(log.index(c1), log.index(c2))
        self.assertLess(log.index(c1), log.index(c3))
        self.assertIn("HEAD -> main", log)

        self.assertEqual(self.run_cmd(f"path {c1} {c3}"), f"Path: {c1} -> {c3}")
        self.assertEqual(self.run_cmd(f"path {c2} {c3}"), f"Path: {c2} -> {c1} -> {c3}")

        search = self.run_cmd('search "login"')
        self.assertTrue(search.startswith("Found 1 commit:"))
        self.assertIn(c2, search)
        self.assertIn("Found 3 commits", self.run_cmd("search --author=alice"))

        ancestors = self.run_cmd(f"ancestors {c3}")
        self.assertIn(c1, ancestors)
        self.assertNotIn(c2, ancestors)

    def test_log_sort_by_author_and_date(self):
        self.run_cmd("init Bob")
        self.run_cmd("commit first")
        self.run_cmd('init "Bob"')  # 재초기화하면 이력이 비워진다.
        self.assertEqual(self.run_cmd("log"), "No commits yet.")
        self.run_cmd("commit by-bob")
        self.cli.repo.user = "alice"  # 작성자 전환 (INIT 은 이력을 지우므로 직접 변경)
        self.run_cmd("commit by-alice")
        by_author = self.run_cmd("log --sort-by=author")
        self.assertLess(by_author.index("by-alice"), by_author.index("by-bob"))
        by_date = self.run_cmd("LOG --SORT-BY=DATE")
        self.assertLess(by_date.index("by-bob"), by_date.index("by-alice"))

    def test_errors(self):
        self.run_cmd("init Alice")
        self.assertEqual(self.run_cmd("switch nope"), "Unknown branch: nope")
        self.assertEqual(self.run_cmd("ancestors deadbeef"), "Unknown commit: deadbeef")
        self.assertTrue(self.run_cmd("commit").startswith("Invalid args"))
        self.assertTrue(self.run_cmd("log --sort-by=size").startswith("Invalid args"))
        self.assertTrue(self.run_cmd("branch a b").startswith("Invalid args"))
        self.assertEqual(self.run_cmd('commit "unclosed'), "Invalid args")
        self.assertTrue(self.run_cmd("frobnicate").startswith("Unknown command"))

    def test_no_path_between_unrelated_roots(self):
        self.run_cmd("init Alice")
        self.run_cmd("branch orphan")  # 커밋이 없을 때 만든 브랜치 -> 별도의 루트 커밋을 갖게 된다.
        c1 = self.commit_hash("commit one")
        self.run_cmd("switch orphan")
        c2 = self.commit_hash("commit two")
        self.assertEqual(self.run_cmd(f"path {c1} {c2}"), "No path")


if __name__ == "__main__":
    unittest.main()
