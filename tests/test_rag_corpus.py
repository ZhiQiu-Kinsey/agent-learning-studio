"""D 类（知识与检索）共享语料与检索模块的回归保护。

青石图书馆服务手册是 6 门检索课共用的固定资料集：中英两份逐段对应，gold 标注写在小节锚点上。
这里守住几件后续课程依赖的事实：两种语言结构一致、查询集指向真实锚点、片段能按路径和行号回到原文、
问题文件得到对应的加载异常记录，以及 BM25 在代表性查询上的命中与漏检和语料设计一致。
"""
import json
import re
import tempfile
import unittest
from collections import Counter
from pathlib import Path

from lessons.lesson_document_loading.chunking import (
    DEFAULT_PARAMS, ChunkingParams, chunk_corpus, chunk_document, default_chunks, params_for,
)
from lessons.lesson_document_loading.loader import (
    CORPUS_DIR, PROBLEM_DIR, ROOT, UNTRUSTED, corpus_version, load_corpus,
)
from lessons.lesson_embedding_retrieval.vector_index import VectorIndex, cosine, index_path
from lessons.lesson_hybrid_retrieval.fusion import apply_filter, rrf
from lessons.lesson_keyword_retrieval.bm25 import BM25Index, Hit, tokenize
from lessons.lesson_keyword_retrieval.query_set import KINDS, judge, load_queries, query_set_version

LOCALES = ("zh-CN", "en")
ANCHOR = re.compile(r"^## .*\{#([a-z0-9-]+)\}$", re.MULTILINE)
CJK = re.compile(r"[　-〿㐀-䶿一-鿿＀-￯]")


def anchors_of(doc):
    return ANCHOR.findall(doc.text)


def ranked(locale, preset="default"):
    """（片段表, BM25 索引）：按指定预设分块后建索引。"""
    documents, _ = load_corpus(locale)
    chunks = chunk_corpus(documents, params_for(locale, preset))
    return {chunk.chunk_id: chunk for chunk in chunks}, BM25Index(chunks, locale)


def outcome(locale, query_id, preset="default"):
    by_id, index = ranked(locale, preset)
    query = next(q for q in load_queries(locale) if q.id == query_id)
    hits = index.search(query.text, 5)
    return judge([by_id[hit.chunk_id] for hit in hits], query)


class CorpusStructureTests(unittest.TestCase):
    def test_both_languages_have_the_same_files_ids_and_anchors(self):
        files = {locale: sorted(p.name for p in (CORPUS_DIR / locale).iterdir()) for locale in LOCALES}
        self.assertEqual(files["zh-CN"], files["en"])
        problems = {locale: sorted(p.name for p in (PROBLEM_DIR / locale).iterdir()) for locale in LOCALES}
        self.assertEqual(problems["zh-CN"], problems["en"])
        loaded = {locale: {doc.doc_id: doc for doc in load_corpus(locale)[0]} for locale in LOCALES}
        self.assertEqual(loaded["zh-CN"].keys(), loaded["en"].keys())
        for doc_id, zh in loaded["zh-CN"].items():
            en = loaded["en"][doc_id]
            with self.subTest(doc_id=doc_id):
                self.assertEqual(anchors_of(zh), anchors_of(en))
                self.assertEqual(len(set(anchors_of(zh))), len(anchors_of(zh)), "锚点在一份文档内必须唯一")
                self.assertEqual((zh.version, zh.meta.get("supersedes")), (en.version, en.meta.get("supersedes")))
                # 逐行对应：同一行号在两种语言里是同一段，教学时可以并排对照。
                self.assertEqual(zh.text.count("\n"), en.text.count("\n"))

    def test_clean_corpus_size_and_trust(self):
        for locale in LOCALES:
            documents, issues = load_corpus(locale)
            with self.subTest(locale=locale):
                self.assertEqual(issues, [])
                self.assertTrue(8 <= len(documents) <= 10)
                for doc in documents:
                    self.assertEqual(doc.trust, UNTRUSTED)
                    self.assertTrue(3 <= len(anchors_of(doc)) <= 6, doc.doc_id)
                    self.assertTrue(doc.path.startswith("lessons/lesson_document_loading/corpus/"))

    def test_version_conflict_and_untrusted_instruction_are_present(self):
        for locale in LOCALES:
            docs = {doc.doc_id: doc for doc in load_corpus(locale)[0]}
            self.assertEqual(docs["hours"].meta["supersedes"], "hours-2025")
            self.assertGreater(docs["hours"].version, docs["hours-2025"].version)
            self.assertIn("#note-fees", "".join(f"#{a}" for a in anchors_of(docs["reader-notes"])))
        self.assertIn("ignore all previous instructions",
                      {d.doc_id: d for d in load_corpus("en")[0]}["reader-notes"].text)

    def test_english_files_contain_no_chinese(self):
        for folder in (CORPUS_DIR / "en", PROBLEM_DIR / "en"):
            for path in folder.iterdir():
                try:
                    text = path.read_text(encoding="utf-8")
                except UnicodeDecodeError:
                    text = path.read_bytes().decode("cp1252")  # 故意的非 UTF-8 样例
                with self.subTest(path=path.name):
                    self.assertIsNone(CJK.search(text))

    def test_corpus_version_is_a_stable_digest(self):
        for locale in LOCALES:
            version = corpus_version(locale)
            self.assertRegex(version, r"^[0-9a-f]{16}$")
            self.assertEqual(version, corpus_version(locale))
        self.assertNotEqual(corpus_version("zh-CN"), corpus_version("en"))


class ProblemFileTests(unittest.TestCase):
    def test_each_problem_file_gets_its_issue_kind(self):
        expected = {"empty-notice.md": "empty", "notice-board.md": "duplicate", "summer-hours.md": "parse_error",
                    "legacy-rules.md": "parse_error", "event-calendar.csv": "unsupported"}
        for locale in LOCALES:
            documents, issues = load_corpus(locale, include_problem_files=True)
            with self.subTest(locale=locale):
                self.assertEqual({Path(issue.path).name: issue.kind for issue in issues}, expected)
                # 重复段落要记录，但文档本身仍然载入，后面能看到它被检索两次。
                self.assertIn("notice-board", {doc.doc_id for doc in documents})
                duplicate = next(issue for issue in issues if issue.kind == "duplicate")
                self.assertIn("corpus/" + locale + "/borrowing.md", duplicate.detail)
                self.assertTrue(all(issue.detail for issue in issues))

    def test_unknown_locale_is_a_programming_error(self):
        with self.assertRaises(ValueError):
            load_corpus("fr")


class QuerySetTests(unittest.TestCase):
    def test_gold_points_at_real_anchors_and_every_kind_has_two_queries(self):
        real = {f"{doc.doc_id}#{anchor}" for doc in load_corpus("zh-CN")[0] for anchor in anchors_of(doc)}
        raw = json.loads((CORPUS_DIR / "queries.json").read_text(encoding="utf-8"))
        ids = [item["id"] for item in raw["queries"]]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertTrue(12 <= len(ids) <= 16)
        for locale in LOCALES:
            queries = load_queries(locale)
            counts = Counter(query.kind for query in queries)
            self.assertEqual(set(counts), set(KINDS))
            self.assertTrue(all(count >= 2 for count in counts.values()), counts)
            for query in queries:
                with self.subTest(locale=locale, query=query.id):
                    self.assertTrue(set(query.gold) <= real, set(query.gold) - real)
                    self.assertEqual(query.kind == "no_answer", not query.gold)
                    if query.kind in ("cross_section", "multi_hop", "conflict"):
                        self.assertGreaterEqual(len(query.gold), 2)
                    if query.kind == "multi_hop":
                        self.assertGreaterEqual(len({gold.split("#")[0] for gold in query.gold}), 2)
                    if locale == "en":
                        self.assertIsNone(CJK.search(query.text))

    def test_query_set_version_names_the_file_content(self):
        self.assertRegex(query_set_version(), r"^2026-10\+[0-9a-f]{8}$")

    def test_judge_no_answer_has_nothing_to_hit(self):
        by_id, index = ranked("zh-CN")
        query = next(q for q in load_queries("zh-CN") if q.kind == "no_answer")
        result = judge([by_id[hit.chunk_id] for hit in index.search(query.text)], query)
        self.assertIsNone(result["hit"])
        self.assertIsNone(result["complete"])


class ChunkingTests(unittest.TestCase):
    def test_default_chunks_point_back_to_the_original_lines(self):
        for locale in LOCALES:
            chunks = default_chunks(locale)
            with self.subTest(locale=locale):
                self.assertTrue(30 <= len(chunks) <= 50, len(chunks))
                self.assertEqual(len({chunk.chunk_id for chunk in chunks}), len(chunks))
                for chunk in chunks:
                    lines = (ROOT / chunk.path).read_text(encoding="utf-8").split("\n")
                    self.assertEqual(chunk.text, "\n".join(lines[chunk.start_line - 1:chunk.end_line]))
                    self.assertEqual(chunk.chunk_id, f"{chunk.doc_id}:{chunk.start_line}-{chunk.end_line}")
                    self.assertEqual(chunk.trust, UNTRUSTED)
                    self.assertTrue(chunk.anchors)

    def test_every_section_appears_in_some_chunk(self):
        for locale in LOCALES:
            documents, _ = load_corpus(locale)
            covered = {anchor for chunk in chunk_corpus(documents) for anchor in chunk.anchors}
            expected = {f"{doc.doc_id}#{anchor}" for doc in documents for anchor in anchors_of(doc)}
            self.assertEqual(covered, expected)

    def test_overlap_repeats_the_previous_last_line(self):
        doc = next(d for d in load_corpus("zh-CN")[0] if d.doc_id == "rooms")
        chunks = chunk_document(doc)
        for previous, current in zip(chunks, chunks[1:]):
            self.assertEqual(current.start_line, previous.end_line)
        narrow = chunk_document(doc, params_for("zh-CN", "narrow"))
        for previous, current in zip(narrow, narrow[1:]):
            self.assertGreater(current.start_line, previous.end_line)

    def test_superseding_document_is_carried_on_its_chunks(self):
        chunks = default_chunks("en")
        self.assertTrue(all(chunk.supersedes == ("hours-2025",) for chunk in chunks if chunk.doc_id == "hours"))
        self.assertTrue(all(chunk.supersedes == () for chunk in chunks if chunk.doc_id != "hours"))

    def test_params_are_validated(self):
        self.assertEqual(DEFAULT_PARAMS, params_for("zh-CN"))
        with self.assertRaises(ValueError):
            ChunkingParams(max_chars=0, overlap_lines=0)


class BM25DesignTests(unittest.TestCase):
    """语料设计的回归保护：改语料或分词时，这些结果应该保持不变。"""

    def test_exact_codes_rank_first(self):
        for locale in LOCALES:
            for query_id in ("q01", "q02", "q03"):
                with self.subTest(locale=locale, query=query_id):
                    self.assertEqual(outcome(locale, query_id)["first_rank"], 1)

    def test_synonym_queries_miss(self):
        for locale in LOCALES:
            for query_id in ("q04", "q05", "q06"):
                with self.subTest(locale=locale, query=query_id):
                    self.assertFalse(outcome(locale, query_id)["hit"])

    def test_cross_section_depends_on_chunking(self):
        for locale in LOCALES:
            for query_id in ("q09", "q10"):
                with self.subTest(locale=locale, query=query_id):
                    self.assertTrue(outcome(locale, query_id, "default")["complete"])
                    self.assertFalse(outcome(locale, query_id, "narrow")["complete"])

    def test_multi_hop_needs_a_second_search(self):
        for locale in LOCALES:
            for query_id in ("q11", "q12"):
                with self.subTest(locale=locale, query=query_id):
                    result = outcome(locale, query_id)
                    self.assertTrue(result["hit"])
                    self.assertFalse(result["complete"])

    def test_conflict_queries_retrieve_both_versions(self):
        for locale in LOCALES:
            for query_id in ("q13", "q14"):
                with self.subTest(locale=locale, query=query_id):
                    self.assertTrue(outcome(locale, query_id)["complete"])

    def test_fee_question_also_retrieves_the_disguised_instruction(self):
        # 信任边界实验依赖这一点：问逾期费用时，伪装成指令的读者留言会和真规定一起进入 top-5。
        for locale in LOCALES:
            by_id, index = ranked(locale)
            query = next(q for q in load_queries(locale) if q.id == "q03")
            anchors = {a for hit in index.search(query.text, 5) for a in by_id[hit.chunk_id].anchors}
            self.assertIn("reader-notes#note-fees", anchors, locale)

    def test_tokenizer_keeps_codes_and_drops_stop_words(self):
        self.assertEqual(tokenize("持 B2 证的读者 {#x}", "zh-CN"), ["持", "b2", "证", "读者"])
        self.assertEqual(tokenize("Is R-305 open at 20:00?", "en"), ["r-305", "open", "20:00"])

    def test_explain_adds_up_to_the_search_score(self):
        _, index = ranked("en")
        hit = index.search("maximum overdue charge per item")[0]
        explained = index.explain("maximum overdue charge per item", hit.chunk_id)
        self.assertAlmostEqual(explained["score"], hit.score, places=3)
        self.assertAlmostEqual(sum(t["contribution"] for t in explained["terms"]), hit.score, places=3)
        self.assertEqual(set(hit.detail["terms"]), {t["term"] for t in explained["terms"] if t["tf"]})
        with self.assertRaises(KeyError):
            index.explain("x", "missing:1-2")


class VectorAndFusionTests(unittest.TestCase):
    def test_cosine(self):
        self.assertAlmostEqual(cosine([1, 0], [2, 0]), 1.0)
        self.assertAlmostEqual(cosine([1, 0], [0, 3]), 0.0)
        self.assertEqual(cosine([0, 0], [1, 1]), 0.0)
        with self.assertRaises(ValueError):
            cosine([1], [1, 2])

    def test_index_round_trip_filter_and_staleness(self):
        index = VectorIndex("demo-embed", 2, "v1", ["a:1-2", "b:3-4", "c:5-6"], [[1, 0], [0.8, 0.6], [0, 1]])
        self.assertEqual([hit.chunk_id for hit in index.search([1, 0], 2)], ["a:1-2", "b:3-4"])
        self.assertEqual([hit.chunk_id for hit in index.search([1, 0], 2, where=lambda c: c != "a:1-2")],
                         ["b:3-4", "c:5-6"])
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "nested" / "index.json"
            index.save(path)
            loaded = VectorIndex.load(path)
        self.assertEqual(loaded, index)
        self.assertFalse(loaded.is_stale(model="demo-embed", dimensions=2, corpus_version="v1"))
        self.assertTrue(loaded.is_stale(model="demo-embed", dimensions=2, corpus_version="v2"))
        with self.assertRaises(ValueError):
            VectorIndex("m", 3, "v1", ["a"], [[1, 0]])
        path = index_path("en", "text-embedding-v4", 512)
        self.assertEqual(path.parts[-4:], (".runtime", "rag-index", "en", "text-embedding-v4-512.json"))

    def test_rrf_uses_ranks_only(self):
        keyword = [Hit("a", 12.0, 1, {}), Hit("b", 3.0, 2, {})]
        vector = [Hit("b", 0.9, 1, {}), Hit("c", 0.8, 2, {})]
        fused = rrf({"bm25": keyword, "vector": vector}, k=60)
        self.assertEqual(fused[0].chunk_id, "b")
        self.assertAlmostEqual(fused[0].score, round(1 / 62 + 1 / 61, 6))
        self.assertEqual(fused[0].detail["ranks"], {"bm25": 2, "vector": 1})
        self.assertEqual(fused[1].detail["ranks"], {"bm25": 1, "vector": None})

    def test_filter_drops_superseded_versions_and_records_why(self):
        chunks = default_chunks("zh-CN")
        kept, removed = apply_filter(chunks, newest_only=True)
        self.assertNotIn("hours-2025", {chunk.doc_id for chunk in kept})
        self.assertEqual({(item["reason"], item.get("by")) for item in removed}, {("superseded", "hours")})
        # 新版本被过滤掉时，旧版本不再被视为过期。
        kept, removed = apply_filter(chunks, doc_ids={"hours-2025"}, newest_only=True)
        self.assertEqual({chunk.doc_id for chunk in kept}, {"hours-2025"})
        self.assertEqual({item["reason"] for item in removed}, {"doc_id_filter"})


if __name__ == "__main__":
    unittest.main()
