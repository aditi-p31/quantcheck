"""Tests for harness/intoto.py and harness/screen_intoto.py.

Standard library only; no Ollama, model or EvalPlus needed (a fake Ollama server and a
stand-in generator and scorer are used). Run from the repository root:
    python3 -m unittest discover -s tests -v
"""
import contextlib, hashlib, http.server, io, json, os, sys, tempfile, threading, types, unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "harness"))
import intoto  # noqa: E402
import screen_intoto  # noqa: E402
from intoto import load_json, read_text  # noqa: E402

EX = os.path.join(ROOT, "examples", "intoto", "qwen2.5-coder-3b-instruct-q2_K")
EX_BASE = ("https://raw.githubusercontent.com/aditi-p31/quantcheck/01b3ae19c7601b143717c885853e7bd783c5d211/"
           "examples/intoto/qwen2.5-coder-3b-instruct-q2_K/")
SUITE = load_json(os.path.join(ROOT, intoto.SUITE_FILE))["suite_tasks"]


def write_json(path, obj):
    with open(path, "w") as f:
        json.dump(obj, f)


def write_text(path, text):
    with open(path, "w") as f:
        f.write(text)


def build_example(**kw):
    rr = load_json(os.path.join(EX, "run_record.json"))
    args = dict(run_record=rr, run_record_path=os.path.join(EX, "run_record.json"),
                generations_path=os.path.join(EX, "generations.jsonl"),
                scored_path=os.path.join(EX, "scored.json"), evaluator_id="https://github.com/aditi-p31",
                base_url=EX_BASE)
    args.update(kw)
    return intoto.build_statement(**args)


def example_statement():
    return load_json(os.path.join(EX, "statement.json"))


class ReproducesPostedExample(unittest.TestCase):
    """The record posted on in-toto/attestation#565 on 17 Nov 2026 must come out byte for byte."""

    def test_byte_identical(self):
        self.assertEqual(intoto.dumps(build_example()), read_text(os.path.join(EX, "statement.json")))

    def test_example_conforms(self):
        self.assertEqual(intoto.check_statement(example_statement()), [])

    def test_example_evidence_digests_match_files(self):
        files = {"run_record.json", "generations.jsonl", "scored.json"}
        seen = 0
        for e in example_statement()["predicate"]["evidence"]:
            name = e.get("downloadLocation", "").rsplit("/", 1)[-1]
            if name in files:
                seen += 1
                self.assertEqual(intoto.sha256_file(os.path.join(EX, name)), e["digest"]["sha256"], name)
        self.assertEqual(seen, 3)

    def test_without_base_url_has_no_evidence_links(self):
        st = build_example(base_url=None)
        for e in st["predicate"]["evidence"]:
            if e["mediaType"] != "application/vnd.ollama.image.template":
                self.assertNotIn("downloadLocation", e)
        self.assertEqual(intoto.check_statement(st), [])


class ChecksCatchProblems(unittest.TestCase):
    def problems(self, mutate):
        st = example_statement()
        mutate(st)
        return intoto.check_statement(st)

    def assertFlags(self, mutate, needle):
        probs = self.problems(mutate)
        self.assertTrue(any(needle in p for p in probs), f"expected {needle!r} in {probs}")

    def assertClean(self, mutate):
        self.assertEqual(self.problems(mutate), [])

    def test_float_threshold(self):
        self.assertFlags(lambda s: s["predicate"]["claims"][0].update(threshold=9), "decimal string")

    def test_threshold_with_newline(self):
        self.assertFlags(lambda s: s["predicate"]["claims"][0].update(threshold="9\n"), "decimal string")

    def test_bad_comparator(self):
        self.assertFlags(lambda s: s["predicate"]["claims"][0].update(comparator="=="), "comparator")

    def test_claim_not_an_object(self):
        self.assertFlags(lambda s: s["predicate"].update(claims=["x"]), "claims[0] is not an object")

    def test_model_and_commitment_both(self):
        self.assertFlags(lambda s: s["predicate"].update(
            commitments={"model": {"alg": "sha256-salted-v1", "value": "00", "salted": True}}), "exactly one")

    def test_commitments_only_is_valid(self):
        def m(s):
            pr = s["predicate"]
            pr.pop("model")
            pr.pop("dataset")
            pr["commitments"] = {"model": {"alg": "sha256-salted-v1", "value": "ab", "salted": True},
                                 "dataset": {"alg": "sha256-salted-v1", "value": "cd", "salted": True}}
            pr["subjectProfile"] = "receipt"
        self.assertClean(m)

    def test_commitment_without_alg(self):
        def m(s):
            pr = s["predicate"]
            pr.pop("model")
            pr["commitments"] = {"model": {"value": "ab", "salted": True}}
        self.assertFlags(m, "commitments.model.alg is required")

    def test_commitment_not_an_object(self):
        def m(s):
            s["predicate"].pop("model")
            s["predicate"]["commitments"] = {"model": "ab"}
        self.assertFlags(m, "commitments.model is not an object")

    def test_dataset_missing(self):
        self.assertFlags(lambda s: s["predicate"].pop("dataset"), "exactly one of predicate.dataset")

    def test_evidence_without_digest(self):
        self.assertFlags(lambda s: s["predicate"]["evidence"][0].pop("digest"), "evidence[0]: missing digest")

    def test_subject_model_mismatch_public_model(self):
        self.assertFlags(lambda s: s["subject"][0].update(digest={"sha256": "0" * 64}), "subject digest differs")

    def test_subject_model_mismatch_allowed_for_release_gate(self):
        def m(s):
            s["subject"][0]["digest"] = {"sha256": "0" * 64}
            s["predicate"]["subjectProfile"] = "release_gate"
        self.assertClean(m)

    def test_hyphenated_profile_rejected(self):
        self.assertFlags(lambda s: s["predicate"].update(subjectProfile="public-model"), "subjectProfile")

    def test_timestamps(self):
        self.assertClean(lambda s: s["predicate"].update(evaluatedAt="2026-11-17T17:36:13+00:00"))
        self.assertClean(lambda s: s["predicate"].update(evaluatedAt="2026-11-17T09:36:13.5-08:00"))
        for bad in ("2026-11-17 17:36:13", "2026-13-45T99:99:99Z", "2026-11-17T17:36:13", "2026-11-17T17:36:13+25:00"):
            self.assertFlags(lambda s, b=bad: s["predicate"].update(evaluatedAt=b), "RFC 3339")

    def test_evaluator_must_be_uri(self):
        for bad in (5, "not-a-uri", ""):
            self.assertFlags(lambda s, b=bad: s["predicate"]["evaluator"].update(id=b), "evaluator.id")
        self.assertFlags(lambda s: s["predicate"].pop("evaluator"), "evaluator")

    def test_sample_size_bool(self):
        self.assertFlags(lambda s: s["predicate"].update(sampleSize=True), "sampleSize")

    def test_not_an_object(self):
        self.assertEqual(intoto.check_statement([]), ["statement is not a JSON object"])


class BuildGuards(unittest.TestCase):
    def scored_variant(self, td, **changes):
        sc = load_json(os.path.join(EX, "scored.json"))
        sc.update(changes)
        p = os.path.join(td, "scored.json")
        write_json(p, sc)
        return p

    def test_evaluator_required(self):
        for bad in ("", "aditi"):
            with self.assertRaises(ValueError):
                build_example(evaluator_id=bad)

    def test_scored_disagreement(self):
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaises(ValueError):
                build_example(scored_path=self.scored_variant(td, n_pass=3))

    def test_foreign_tag(self):
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaises(ValueError):
                build_example(scored_path=self.scored_variant(td, tag="other:tag"))

    def test_partial_screen(self):
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaises(ValueError):
                build_example(scored_path=self.scored_variant(
                    td, per_task={SUITE[0]: True}, n_tasks=1, n_pass=1, threshold=1, passed=True))

    def test_other_threshold(self):
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaises(ValueError):
                build_example(scored_path=self.scored_variant(td, threshold=1, passed=False))

    def test_suite_mismatch(self):
        with tempfile.TemporaryDirectory() as td:
            p = os.path.join(td, intoto.SUITE_FILE)
            write_text(p, "{}")
            with self.assertRaises(ValueError):
                build_example(suite_path=p)

    def test_passing_screen(self):
        with tempfile.TemporaryDirectory() as td:
            per = {t: (i < 10) for i, t in enumerate(SUITE)}
            st = build_example(scored_path=self.scored_variant(td, per_task=per, n_pass=10, passed=True))
            claim = st["predicate"]["claims"][0]
            self.assertEqual((claim["threshold"], claim["passed"]), ("9", True))

    def test_commit_digest_only_for_known_clean_code(self):
        rr = load_json(os.path.join(EX, "run_record.json"))
        self.assertIn("digest", build_example(run_record=rr)["predicate"]["harness"])      # field absent (17 Nov)
        for value, pinned in ((True, False), (None, False), (False, True)):
            rr["harness"]["screen_code_modified"] = value
            self.assertEqual("digest" in build_example(run_record=rr)["predicate"]["harness"], pinned, value)

    def test_template_mismatch_record_refused(self):
        rr = load_json(os.path.join(EX, "run_record.json"))
        rr["template_matches_runtime"] = False
        with self.assertRaisesRegex(ValueError, "different template"):
            build_example(run_record=rr)


class ConstantsMatchRepository(unittest.TestCase):
    def test_suite_digest(self):
        self.assertEqual(intoto.sha256_file(os.path.join(ROOT, intoto.SUITE_FILE)), intoto.SUITE_SHA256)

    def test_threshold_matches_suite_rule(self):
        suite = load_json(os.path.join(ROOT, intoto.SUITE_FILE))
        self.assertEqual(len(suite["suite_tasks"]), 15)
        self.assertIn("60%", suite["criterion"])
        self.assertEqual(intoto.SCREEN_THRESHOLD, 9)   # 60% of 15

    def test_decode_settings_match_audit_py(self):
        src = read_text(os.path.join(ROOT, "harness", "audit.py"))
        self.assertIn(f'api("{intoto.DECODE["api"]}"', src)
        self.assertIn('"options": {"temperature": 0.0, "seed": 42, "num_predict": 768, "num_ctx": 2048}', src)


class TagsAndHosts(unittest.TestCase):
    def test_parse_forms(self):
        cases = {
            "qwen2.5-coder:3b-instruct-q2_K": ("registry.ollama.ai", "library", "qwen2.5-coder", "3b-instruct-q2_K"),
            "user/model": ("registry.ollama.ai", "user", "model", "latest"),
            "hf.co/org/repo:Q2_K": ("hf.co", "org", "repo", "Q2_K"),
            "localhost:5000/ns/m:v1": ("localhost:5000", "ns", "m", "v1"),
            "localhost:5000/ns/m": ("localhost:5000", "ns", "m", "latest"),
        }
        for tag, want in cases.items():
            self.assertEqual(intoto.parse_tag(tag), want, tag)

    def test_names(self):
        self.assertEqual(intoto.subject_name("qwen2.5-coder:3b-instruct-q2_K"),
                         "registry.ollama.ai/library/qwen2.5-coder:3b-instruct-q2_K")
        self.assertEqual(intoto.short_name("qwen2.5-coder:3b-instruct-q2_K"), "qwen2.5-coder:3b-instruct-q2_K")
        self.assertEqual(intoto.short_name("user/model"), "user/model:latest")
        self.assertEqual(intoto.short_name("hf.co/org/repo:Q2_K"), "hf.co/org/repo:Q2_K")
        self.assertEqual(intoto.blob_uri("phi3.5:x", "ab" * 32),
                         "https://registry.ollama.ai/v2/library/phi3.5/blobs/sha256:" + "ab" * 32)

    def test_rejects_garbage(self):
        for bad in ("", "a:b:c", "a/b/c/d:e", "a//b", "../../etc:x", "ns/..:x", "m:..", None):
            with self.assertRaises(ValueError, msg=repr(bad)):
                intoto.parse_tag(bad)

    def test_normalize_host(self):
        self.assertEqual(intoto.normalize_host("0.0.0.0"), "http://127.0.0.1:11434")
        self.assertEqual(intoto.normalize_host("::"), "http://127.0.0.1:11434")
        self.assertEqual(intoto.normalize_host("0.0.0.0:11500"), "http://127.0.0.1:11500")
        with self.assertRaises(ValueError):
            intoto.normalize_host("localhost:abc")
        self.assertEqual(intoto.normalize_host("localhost"), "http://localhost:11434")
        self.assertEqual(intoto.normalize_host("http://127.0.0.1:8080/"), "http://127.0.0.1:8080")
        self.assertEqual(intoto.normalize_host("[::1]:11434"), "http://[::1]:11434")

    def test_loopback(self):
        for h in ("http://127.0.0.1:11434", "http://localhost:1", "http://[::1]:11434"):
            self.assertTrue(intoto.is_loopback(h), h)
        for h in ("http://10.0.0.5:11434", "http://example.com:11434"):
            self.assertFalse(intoto.is_loopback(h), h)


class FakeOllama:
    """A temporary Ollama store plus an HTTP server answering /api/version, /api/tags and /api/show."""

    TEMPLATE = "{{ .System }}\n{{ .Prompt }}"

    def __init__(self, tag="fake:q2_K", with_template=True):
        self.td = tempfile.TemporaryDirectory()
        self.store = self.td.name
        self.tag = tag
        os.makedirs(os.path.join(self.store, "blobs"))
        self.model = self.blob(b"GGUF fake weights")
        layers = [{"mediaType": "application/vnd.ollama.image.model", "digest": "sha256:" + self.model}]
        self.template = None
        if with_template:
            self.template = self.blob(self.TEMPLATE.encode())
            layers.append({"mediaType": "application/vnd.ollama.image.template", "digest": "sha256:" + self.template})
        manifest = {"schemaVersion": 2, "config": {"digest": "sha256:" + self.blob(b"{}")}, "layers": layers}
        registry, namespace, model, version = intoto.parse_tag(tag)
        mdir = os.path.join(self.store, "manifests", registry, namespace, model)
        os.makedirs(mdir)
        self.manifest_path = os.path.join(mdir, version)
        write_json(self.manifest_path, manifest)
        self.state = {"template": self.TEMPLATE, "listed": None}
        fake = self

        class H(http.server.BaseHTTPRequestHandler):
            def _send(self, obj):
                body = json.dumps(obj).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def do_GET(self):
                if self.path == "/api/tags":
                    digest = fake.state["listed"] or intoto.sha256_file(fake.manifest_path)
                    name = fake.state.get("listed_name") or intoto.short_name(fake.tag)
                    self._send({"models": [{"name": name, "digest": digest}]})
                else:
                    self._send({"version": "0.0.0-test"})

            def do_POST(self):
                self.rfile.read(int(self.headers.get("Content-Length", 0)))
                self._send({"template": fake.state["template"]})

            def log_message(self, *a):
                pass

        self.srv = http.server.HTTPServer(("127.0.0.1", 0), H)
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()
        self.host = f"http://127.0.0.1:{self.srv.server_address[1]}"

    def blob(self, data):
        h = hashlib.sha256(data).hexdigest()
        with open(os.path.join(self.store, "blobs", "sha256-" + h), "wb") as f:
            f.write(data)
        return h

    def close(self):
        self.srv.shutdown()
        self.srv.server_close()
        self.td.cleanup()


class RecordRun(unittest.TestCase):
    def setUp(self):
        self.o = FakeOllama()

    def tearDown(self):
        self.o.close()

    def test_record(self):
        rec = intoto.record_run(self.o.tag, self.o.host, self.o.store, backend="Metal", evalplus_version="0.3.1",
                                extra={"humaneval_plus_version": "v0.1.10"})
        self.assertEqual(rec["model_sha256"], self.o.model)
        self.assertEqual(rec["template_sha256"], self.o.template)
        self.assertEqual(rec["manifest_sha256"], intoto.sha256_file(self.o.manifest_path))
        self.assertTrue(rec["manifest_listed_by_server"])
        self.assertTrue(rec["template_matches_runtime"])
        self.assertEqual(rec["runtime"]["ollama_version"], "0.0.0-test")
        self.assertEqual(rec["runtime"]["backend"], "Metal")
        self.assertEqual(rec["decode"], intoto.DECODE)
        self.assertEqual(rec["suite_sha256"], intoto.SUITE_SHA256)
        self.assertEqual(rec["humaneval_plus_version"], "v0.1.10")
        self.assertTrue(intoto.valid_timestamp(rec["recorded_at_utc"]))

    def test_template_drift_is_recorded(self):
        self.o.state["template"] = "something else"
        rec = intoto.record_run(self.o.tag, self.o.host, self.o.store)
        self.assertFalse(rec["template_matches_runtime"])
        self.assertNotIn("backend", rec["runtime"])

    def test_tag_not_listed_by_server(self):
        self.o.state["listed_name"] = "other:tag"
        with self.assertRaisesRegex(ValueError, "does not list this tag"):
            intoto.record_run(self.o.tag, self.o.host, self.o.store)

    def test_server_uses_another_store(self):
        self.o.state["listed"] = "f" * 64
        with self.assertRaisesRegex(ValueError, "server lists manifest"):
            intoto.record_run(self.o.tag, self.o.host, self.o.store)

    def test_remote_host_refused(self):
        with self.assertRaisesRegex(ValueError, "not this machine"):
            intoto.record_run(self.o.tag, "http://10.0.0.5:11434", self.o.store)

    def test_corrupt_blob_raises(self):
        with open(os.path.join(self.o.store, "blobs", "sha256-" + self.o.model), "wb") as f:
            f.write(b"tampered")
        with self.assertRaisesRegex(ValueError, "model blob"):
            intoto.record_run(self.o.tag, self.o.host, self.o.store)

    def test_missing_tag_raises(self):
        with self.assertRaises(FileNotFoundError):
            intoto.record_run("fake:q3_K_M", self.o.host, self.o.store)

    def test_changes_since(self):
        rec = intoto.record_run(self.o.tag, self.o.host, self.o.store)
        self.assertEqual(intoto.changes_since(rec, self.o.host, self.o.store), [])
        self.o.state["template"] = "swapped"
        self.assertEqual(intoto.changes_since(rec, self.o.host, self.o.store),
                         ["the template the server serves changed"])


class NoTemplateLayer(unittest.TestCase):
    def test_served_template_becomes_evidence(self):
        o = FakeOllama(with_template=False)
        try:
            rec = intoto.record_run(o.tag, o.host, o.store)
        finally:
            o.close()
        self.assertIsNone(rec["template_sha256"])
        self.assertFalse(rec["template_matches_runtime"])
        with tempfile.TemporaryDirectory() as td:
            rr, gen, sc = (os.path.join(td, n) for n in ("run_record.json", "generations.jsonl", "scored.json"))
            write_json(rr, rec)
            write_text(gen, "".join(json.dumps({"task_id": t, "solution": ""}) + "\n" for t in SUITE))
            write_json(sc, {"tag": o.tag, "per_task": {t: False for t in SUITE}})
            st = intoto.build_statement(rec, rr, gen, sc, "https://example.org/me")
        ev = st["predicate"]["evidence"][1]
        self.assertEqual(ev["digest"]["sha256"], rec["template_served_by_runtime_sha256"])
        self.assertEqual(ev["mediaType"], "text/plain")
        self.assertEqual(intoto.check_statement(st), [])


class FetchProblems(unittest.TestCase):
    def test_fetch(self):
        with tempfile.TemporaryDirectory() as td:
            write_text(os.path.join(td, "good.json"), "good")
            write_text(os.path.join(td, "bad.json"), "bad")

            class Quiet(http.server.SimpleHTTPRequestHandler):
                def __init__(self, *a, **k):
                    super().__init__(*a, directory=td, **k)

                def log_message(self, *a):
                    pass

            srv = http.server.HTTPServer(("127.0.0.1", 0), Quiet)
            threading.Thread(target=srv.serve_forever, daemon=True).start()
            base = f"http://127.0.0.1:{srv.server_address[1]}/"
            try:
                good = hashlib.sha256(b"good").hexdigest()
                st = {"predicate": {"evidence": [
                    {"name": "g", "digest": {"sha256": good}, "downloadLocation": base + "good.json"},
                    {"name": "b", "digest": {"sha256": good}, "downloadLocation": base + "bad.json"},
                    {"name": "m", "digest": {"sha256": good}, "downloadLocation": base + "missing.json"}]}}
                probs = intoto.fetch_problems(st, timeout=10)
            finally:
                srv.shutdown()
                srv.server_close()
        self.assertEqual(len(probs), 2, probs)
        self.assertTrue(any("evidence[1]" in p and "hashes to" in p for p in probs))
        self.assertTrue(any("evidence[2]" in p and "could not fetch" in p for p in probs))


class ScreenWrapper(unittest.TestCase):
    """run_screen with a fake server, a stand-in generator and a stand-in scorer."""

    def setUp(self):
        self.o = FakeOllama(tag="fake:q4_K_M")
        self.out = tempfile.TemporaryDirectory()
        self.calls = []

    def tearDown(self):
        self.o.close()
        self.out.cleanup()

    def fake_audit(self, mutate_during_run=None):
        test = self

        def audit_one(entry, tasks, keep=False):
            test.calls.append(("audit_one", entry, keep))
            test.assertTrue(os.path.exists(os.path.join(test.out.name, "run_record.json")),
                            "run record must exist before generation")
            os.makedirs(os.path.join(mod.RESULTS, "transcripts"))
            with open(os.path.join(mod.RESULTS, "transcripts", "t.jsonl"), "w") as f:
                for t in tasks:
                    f.write(json.dumps({"task_id": t, "solution": "def f(): pass"}) + "\n")
            if mutate_during_run:
                mutate_during_run()
            return {"tag": entry["tag"], "transcript": "t.jsonl", "trunc_frac": 0.0}

        mod = types.SimpleNamespace(SUITE=SUITE, OLLAMA_BIN="ollama", audit_one=audit_one)
        return mod

    def run_screen(self, audit, solved=10, scorer_works=True):
        def score(path, tasks):
            if os.path.basename(path) == "reference_solutions.jsonl":
                self.calls.append(("self_test", path))
                return {t: scorer_works for t in SUITE}
            self.calls.append(("score", path))
            return {t: (i < solved) for i, t in enumerate(SUITE)}
        tasks = {t: {"prompt": "def f():\n", "canonical_solution": "    return 1\n"} for t in SUITE}
        with contextlib.redirect_stdout(io.StringIO()):
            return screen_intoto.run_screen(self.o.tag, self.out.name, "https://example.org/me", self.o.host,
                                            self.o.store, "Metal", None, audit, score, tasks,
                                            "0.3.1", {"humaneval_plus_version": "v0.1.10"})

    def test_full_run(self):
        self.assertEqual(self.run_screen(self.fake_audit()), 0)
        self.assertEqual([c[0] for c in self.calls], ["self_test", "audit_one", "score"])
        self.assertEqual(self.calls[1], ("audit_one", {"tag": self.o.tag, "no_pull": True}, True))
        out = self.out.name
        self.assertFalse(os.path.exists(os.path.join(out, "work")), "work folder must be removed")
        st = load_json(os.path.join(out, "statement.json"))
        self.assertEqual(intoto.check_statement(st), [])
        self.assertTrue(st["predicate"]["claims"][0]["passed"])
        self.assertEqual(st["predicate"]["sampleSize"], 15)
        rr = load_json(os.path.join(out, "run_record.json"))
        self.assertEqual(st["predicate"]["evaluatedAt"], rr["recorded_at_utc"])
        sc = load_json(os.path.join(out, "scored.json"))
        self.assertEqual(sc["scorer_self_test"], "15 of 15 reference solutions passed")
        self.assertEqual(st["predicate"]["evidence"][0]["digest"]["sha256"],
                         intoto.sha256_file(os.path.join(out, "run_record.json")))

    def test_flagged_run(self):
        self.run_screen(self.fake_audit(), solved=8)
        st = load_json(os.path.join(self.out.name, "statement.json"))
        self.assertFalse(st["predicate"]["claims"][0]["passed"])

    def test_change_during_run_aborts(self):
        audit = self.fake_audit(mutate_during_run=lambda: self.o.state.update(template="swapped"))
        with self.assertRaisesRegex(screen_intoto.ScreenError, "template the server serves changed"):
            self.run_screen(audit)
        self.assertFalse(os.path.exists(os.path.join(self.out.name, "statement.json")))
        self.assertFalse(os.path.exists(os.path.join(self.out.name, "work")))

    def test_broken_scorer_stops_before_generation(self):
        with self.assertRaisesRegex(screen_intoto.ScreenError, "scorer self-test failed: 0 of 15"):
            self.run_screen(self.fake_audit(), scorer_works=False)
        self.assertEqual([c[0] for c in self.calls], ["self_test"])
        self.assertFalse(os.path.exists(os.path.join(self.out.name, "statement.json")))
        self.assertFalse(os.path.exists(os.path.join(self.out.name, "work")))

    def test_template_mismatch_stops_before_generation(self):
        self.o.state["template"] = "not the tag's template"
        with self.assertRaisesRegex(screen_intoto.ScreenError, "different chat template"):
            self.run_screen(self.fake_audit())
        self.assertEqual(self.calls, [])

    def test_refuses_existing_statement(self):
        write_text(os.path.join(self.out.name, "statement.json"), "{}")
        with self.assertRaisesRegex(screen_intoto.ScreenError, "already holds a statement"):
            self.run_screen(self.fake_audit())

    def test_tag_removed_during_run_aborts(self):
        audit = self.fake_audit(mutate_during_run=lambda: os.remove(self.o.manifest_path))
        with self.assertRaisesRegex(screen_intoto.ScreenError, "could not re-check"):
            self.run_screen(audit)
        self.assertFalse(os.path.exists(os.path.join(self.out.name, "statement.json")))

    def test_suite_tasks_digest_is_stable(self):
        tasks = {t: {"prompt": t, "base_input": [[1, 2]]} for t in SUITE}
        self.assertEqual(screen_intoto.suite_tasks_digest(tasks, SUITE),
                         screen_intoto.suite_tasks_digest(dict(reversed(list(tasks.items()))), SUITE))


class ScreenWithoutTemplateLayer(ScreenWrapper):
    def setUp(self):
        self.o = FakeOllama(tag="fake:q4_K_M", with_template=False)
        self.out = tempfile.TemporaryDirectory()
        self.calls = []

    def test_full_run(self):
        self.assertEqual(self.run_screen(self.fake_audit()), 0)
        out = self.out.name
        served = os.path.join(out, "served_template.txt")
        self.assertEqual(read_text(served), FakeOllama.TEMPLATE)
        st = load_json(os.path.join(out, "statement.json"))
        ev = st["predicate"]["evidence"][1]
        self.assertEqual(ev["mediaType"], "text/plain")
        self.assertEqual(ev["digest"]["sha256"], intoto.sha256_file(served))
        self.assertEqual(intoto.check_statement(st), [])

    # template-layer specific tests do not apply here
    test_template_mismatch_stops_before_generation = None
    test_change_during_run_aborts = None


if __name__ == "__main__":
    unittest.main()
