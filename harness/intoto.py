#!/usr/bin/env python3
"""in-toto eval-result records for quantcheck screens (standard library only).

A screen record is an in-toto Statement with the eval-result predicate proposed in
in-toto/attestation#575 (v0.1, discussed in #565). One Statement describes one screened
Ollama tag: the model file by digest, the 15-task suite, the verdict against the screen
threshold, and evidence files referenced by digest.

The chat template affects a screen result, so the run record is written before generation
starts. It holds the manifest, model and chat-template digests read from the local Ollama
store, checked against the blobs and against the manifest digest the running server reports
for the tag, plus the template the server serves, the runtime version and the decode settings.
The server must run on this machine, because the record hashes files in its store.

Subject names and blob URIs are derived from the tag. They resolve on the registry only for
tags pulled from it; a locally created model gets the same naming but no downloadable blob.
Records are unsigned. Sign them with in-toto or sigstore tooling if you need signatures.

Usage:
  intoto.py record --tag TAG --out run_record.json [--host URL] [--models-dir DIR] [--backend NAME]
  intoto.py statement --run-record R --generations G --scored S --evaluator-id URI --out OUT
                      [--suite smoke_suite_v1.json] [--base-url URL] [--dataset-url URL]
  intoto.py check STATEMENT [--fetch]
"""
import argparse, datetime, hashlib, ipaddress, json, os, platform, re, subprocess, sys
import urllib.parse, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

STATEMENT_TYPE = "https://in-toto.io/Statement/v1"
PREDICATE_TYPE = "https://in-toto.io/attestation/eval-result/v0.1"
COMPARATORS = (">=", ">", "<=", "<")
ASSURANCE_LEVELS = ("self_attested", "third_party", "reproduced", "enclave_attested")
SUBJECT_PROFILES = ("receipt", "public_model", "release_gate")

DEFAULT_REGISTRY = "registry.ollama.ai"
DEFAULT_PORT = 11434
SUITE_FILE = "smoke_suite_v1.json"
SUITE_NAME = "quantcheck HumanEval+ screen"
SUITE_VERSION = "smoke_suite_v1"
# The released suite file and where it is published (quantcheck v3.4.1).
SUITE_SHA256 = "0f50c6f29e2dfd2afe6153a60d9e806d7b8292bbebe23fe6276340a2180abf96"
SUITE_URL = "https://raw.githubusercontent.com/aditi-p31/quantcheck/v3.4.1/smoke_suite_v1.json"
# A tag passes the screen when it solves at least this many of the 15 tasks (60%).
SCREEN_THRESHOLD = 9
# Decode settings used by harness/audit.py (kept in sync by tests/test_intoto.py).
DECODE = {"api": "/api/chat", "temperature": 0.0, "seed": 42, "num_predict": 768, "num_ctx": 2048}

EVIDENCE_NAMES = {
    "run_record": "run record, written at run start (manifest, model and chat-template digests, runtime, decode settings)",
    "template": "chat template layer, digest recorded at run start",
    "served_template": "chat template served by the runtime (the tag has no template layer), digest recorded at run start",
    "generations": "generations",
    "scored": "per-task scores",
}
TIMESTAMP = re.compile(r"(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})(\.\d+)?(Z|[+-](\d{2}):(\d{2}))")
DECIMAL = re.compile(r"-?\d+(\.\d+)?")
SHA256_HEX = re.compile(r"[0-9a-f]{64}")
TYPE_URI = re.compile(r"[A-Za-z][A-Za-z0-9+.-]*:\S+")
TAG_PART = re.compile(r"[A-Za-z0-9._-]+")
REGISTRY_PART = re.compile(r"[A-Za-z0-9._-]+(:\d+)?")


# ---------------------------------------------------------------- helpers

def load_json(path):
    with open(path) as f:
        return json.load(f)


def read_text(path):
    with open(path) as f:
        return f.read()


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


def utc_now():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def valid_timestamp(value):
    """RFC 3339 date-time with a Z or +hh:mm offset and real calendar values."""
    m = TIMESTAMP.fullmatch(value) if isinstance(value, str) else None
    if not m:
        return False
    try:
        datetime.datetime.strptime(m.group(1), "%Y-%m-%dT%H:%M:%S")
    except ValueError:
        return False
    return m.group(3) == "Z" or (int(m.group(4)) < 24 and int(m.group(5)) < 60)


def normalize_host(host):
    """Return a scheme://host:port URL for the Ollama server.

    Accepts the forms OLLAMA_HOST takes. A missing port becomes 11434, and the bind-all
    addresses 0.0.0.0 and :: become 127.0.0.1. Raises ValueError for an unusable value.
    """
    host = host or os.environ.get("OLLAMA_HOST") or f"http://127.0.0.1:{DEFAULT_PORT}"
    if host.strip("[]") in ("0.0.0.0", "::"):
        host = "127.0.0.1"
    if not re.match(r"^https?://", host):
        host = "http://" + host
    u = urllib.parse.urlsplit(host)
    try:
        port = u.port or DEFAULT_PORT
    except ValueError:
        raise ValueError(f"not a usable Ollama host: {host!r}")
    name = u.hostname or "127.0.0.1"
    if name in ("0.0.0.0", "::"):          # a bind-all address; the server is reachable on loopback
        name = "127.0.0.1"
    netloc = f"[{name}]:{port}" if ":" in name else f"{name}:{port}"
    return f"{u.scheme}://{netloc}"


def is_loopback(host):
    name = urllib.parse.urlsplit(host).hostname or ""
    if name == "localhost":
        return True
    try:
        return ipaddress.ip_address(name).is_loopback
    except ValueError:
        return False


def ollama_api(host, path, payload=None, timeout=60):
    req = urllib.request.Request(
        host + path,
        data=json.dumps(payload).encode() if payload is not None else None,
        headers={"Content-Type": "application/json"},
        method="POST" if payload is not None else "GET",
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def default_models_dir():
    return os.environ.get("OLLAMA_MODELS") or os.path.join(os.path.expanduser("~"), ".ollama", "models")


def parse_tag(tag):
    """Split an Ollama tag into (registry, namespace, name, version).

    "qwen2.5-coder:3b"         -> ("registry.ollama.ai", "library", "qwen2.5-coder", "3b")
    "user/model"               -> ("registry.ollama.ai", "user", "model", "latest")
    "hf.co/org/repo:Q2_K"      -> ("hf.co", "org", "repo", "Q2_K")
    "localhost:5000/ns/m:v1"   -> ("localhost:5000", "ns", "m", "v1")
    """
    if not isinstance(tag, str) or not tag:
        raise ValueError(f"not an Ollama tag: {tag!r}")
    path, sep, version = tag.rpartition(":")
    if not sep or "/" in version:          # no version part (a colon, if any, belongs to a port)
        path, version = tag, "latest"
    parts = path.split("/")
    if len(parts) == 1:
        registry, namespace, model = DEFAULT_REGISTRY, "library", parts[0]
    elif len(parts) == 2:
        registry, namespace, model = DEFAULT_REGISTRY, parts[0], parts[1]
    elif len(parts) == 3:
        registry, namespace, model = parts
    else:
        raise ValueError(f"not an Ollama tag: {tag!r}")
    ok = (REGISTRY_PART.fullmatch(registry) and all(TAG_PART.fullmatch(x) for x in (namespace, model, version))
          and not any(x in (".", "..") for x in (registry, namespace, model, version)))
    if not ok:
        raise ValueError(f"not an Ollama tag: {tag!r}")
    return registry, namespace, model, version


def short_name(tag):
    """The name the Ollama server lists for a tag (registry and library prefix dropped)."""
    registry, namespace, model, version = parse_tag(tag)
    if registry == DEFAULT_REGISTRY:
        prefix = "" if namespace == "library" else namespace + "/"
    else:
        prefix = f"{registry}/{namespace}/"
    return f"{prefix}{model}:{version}"


def subject_name(tag):
    registry, namespace, model, version = parse_tag(tag)
    return f"{registry}/{namespace}/{model}:{version}"


def blob_uri(tag, digest_hex):
    registry, namespace, model, _ = parse_tag(tag)
    return f"https://{registry}/v2/{namespace}/{model}/blobs/sha256:{digest_hex}"


def read_manifest(models_dir, tag):
    registry, namespace, model, version = parse_tag(tag)
    path = os.path.join(models_dir, "manifests", registry, namespace, model, version)
    if not os.path.exists(path):
        raise FileNotFoundError(f"no local manifest for {tag} at {path}; pull the tag first")
    return path, load_json(path)


def layer_digests(manifest):
    """Map the last part of each layer media type (model, template, system, ...) to its hex digest."""
    out = {}
    for layer in manifest.get("layers", []):
        kind = layer["mediaType"].rsplit(".", 1)[-1]
        digest = layer["digest"]
        if not digest.startswith("sha256:"):
            raise ValueError(f"unexpected digest {digest!r}")
        out[kind] = digest.split(":", 1)[1]
    return out


def cpu_name():
    system = platform.system()
    try:
        if system == "Darwin":
            return subprocess.run(["sysctl", "-n", "machdep.cpu.brand_string"],
                                  capture_output=True, text=True, timeout=10).stdout.strip() or None
        if system == "Linux":
            for line in read_text("/proc/cpuinfo").splitlines():
                if line.lower().startswith("model name"):
                    return line.split(":", 1)[1].strip()
    except Exception:
        pass
    return platform.processor() or None


def harness_info():
    """quantcheck version (CITATION.cff), git commit, and whether the screen code differs from it."""
    version = None
    cff = os.path.join(ROOT, "CITATION.cff")
    if os.path.exists(cff):
        m = re.search(r'^version:\s*"?([^"\n]+)"?\s*$', read_text(cff), re.M)
        version = m.group(1).strip() if m else None
    commit, modified = None, None
    try:
        r = subprocess.run(["git", "-C", ROOT, "rev-parse", "HEAD"], capture_output=True, text=True, timeout=10)
        if r.returncode == 0:
            commit = r.stdout.strip()
            s = subprocess.run(["git", "-C", ROOT, "status", "--porcelain", "--", "harness", SUITE_FILE,
                                "rerun-2026-10/scripts"], capture_output=True, text=True, timeout=10)
            modified = bool(s.stdout.strip()) if s.returncode == 0 else None
    except Exception:
        pass
    return {"name": "quantcheck", "version": version, "gitCommit": commit, "screen_code_modified": modified,
            "audit_py_sha256": sha256_file(os.path.join(HERE, "audit.py"))}


# ---------------------------------------------------------------- run record

def server_state(tag, host, models_dir):
    """What the server and the store say about TAG right now: manifest file digest,
    the manifest digest the server lists, and the digest of the template it serves."""
    man_path, manifest = read_manifest(models_dir, tag)
    listed = {m.get("name"): m.get("digest") for m in ollama_api(host, "/api/tags").get("models", [])}
    show = ollama_api(host, "/api/show", {"model": tag})
    return {
        "manifest_path": man_path,
        "manifest": manifest,
        "manifest_sha256": sha256_file(man_path),
        "server_manifest_sha256": listed.get(short_name(tag)) or listed.get(tag),
        "served_template_sha256": sha256_bytes(show.get("template", "").encode("utf-8")),
    }


def record_run(tag, host=None, models_dir=None, backend=None, evalplus_version=None, suite_path=None,
               extra=None):
    """Build the run record for TAG. Call it before generation starts.

    Checks that the model and template blobs hash to their manifest digests and that the
    running server lists the same manifest, so the record describes the files the server
    will use. Raises ValueError or FileNotFoundError when any of that does not hold.
    """
    host = normalize_host(host)
    if not is_loopback(host):
        raise ValueError(f"{host} is not this machine: the run record hashes the local Ollama store, "
                         "so the server must run here")
    models_dir = models_dir or default_models_dir()
    suite_path = suite_path or os.path.join(ROOT, SUITE_FILE)
    recorded_at = utc_now()
    state = server_state(tag, host, models_dir)
    manifest = state["manifest"]
    if state["server_manifest_sha256"] is None:
        raise ValueError(f"{tag}: the server does not list this tag (as {short_name(tag)}); pull it into the "
                         f"server's store, or point --models-dir at the store the server uses")
    if state["server_manifest_sha256"] != state["manifest_sha256"]:
        raise ValueError(f"{tag}: the server lists manifest {state['server_manifest_sha256']}, the store at "
                         f"{models_dir} has {state['manifest_sha256']}; point --models-dir at the server's store")
    layers = layer_digests(manifest)
    if "model" not in layers:
        raise ValueError(f"{tag}: manifest has no model layer")
    blobs = os.path.join(models_dir, "blobs")
    model_sha = sha256_file(os.path.join(blobs, "sha256-" + layers["model"]))
    if model_sha != layers["model"]:
        raise ValueError(f"{tag}: model blob hashes to {model_sha}, manifest says {layers['model']}")
    template_sha = None
    if "template" in layers:
        template_sha = sha256_file(os.path.join(blobs, "sha256-" + layers["template"]))
        if template_sha != layers["template"]:
            raise ValueError(f"{tag}: template blob hashes to {template_sha}, manifest says {layers['template']}")
    version = ollama_api(host, "/api/version")["version"]
    runtime = {"ollama_version": version}
    if backend:
        runtime["backend"] = backend
    runtime.update({"machine": platform.machine(), "cpu": cpu_name(), "os": platform.platform()})
    rec = {
        "recorded_at_utc": recorded_at,
        "tag": tag,
        "manifest_sha256": state["manifest_sha256"],
        "manifest_listed_by_server": True,
        "model_sha256": model_sha,
        "template_sha256": template_sha,
        "system_sha256": layers.get("system"),
        "config_sha256": manifest.get("config", {}).get("digest", "").split(":", 1)[-1] or None,
        "template_served_by_runtime_sha256": state["served_template_sha256"],
        "template_matches_runtime": template_sha is not None and state["served_template_sha256"] == template_sha,
        "runtime": runtime,
        "decode": dict(DECODE),
        "suite": SUITE_FILE,
        "suite_sha256": sha256_file(suite_path),
        "harness": harness_info(),
        "evalplus_version": evalplus_version,
    }
    rec.update(extra or {})
    return rec


def changes_since(run_record, host=None, models_dir=None):
    """Compare the server and store with the run record; return a list of what changed."""
    host = normalize_host(host)
    state = server_state(run_record["tag"], host, models_dir or default_models_dir())
    out = []
    if state["manifest_sha256"] != run_record["manifest_sha256"]:
        out.append("the tag's manifest in the store changed")
    if state["server_manifest_sha256"] != run_record["manifest_sha256"]:
        out.append("the manifest the server lists changed")
    if state["served_template_sha256"] != run_record["template_served_by_runtime_sha256"]:
        out.append("the template the server serves changed")
    return out


def suite_tasks_digest(tasks, suite):
    """sha256 over the suite tasks as EvalPlus loads them (prompts, tests, inputs), key-sorted JSON."""
    blob = json.dumps({t: tasks[t] for t in suite}, sort_keys=True, default=repr)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def evalplus_info(tasks, suite):
    """Run-record fields that pin the HumanEval+ data and the EvalPlus memory setting."""
    from evalplus.data.humaneval import HUMANEVAL_PLUS_VERSION
    info = {"humaneval_plus_version": HUMANEVAL_PLUS_VERSION,
            "suite_tasks_sha256": suite_tasks_digest(tasks, suite),
            "evalplus_max_memory_bytes": os.environ.get(
                "EVALPLUS_MAX_MEMORY_BYTES", "unset (EvalPlus 0.3.1 default: 4 GiB, capped at total memory)")}
    if os.environ.get("HUMANEVAL_OVERRIDE_PATH"):
        info["humaneval_override_path"] = os.environ["HUMANEVAL_OVERRIDE_PATH"]
    return info


# ---------------------------------------------------------------- statement

def _descriptor(name, digest_hex, media_type, location=None, location_key="downloadLocation"):
    d = {"name": name, "digest": {"sha256": digest_hex}, "mediaType": media_type}
    if location:
        d[location_key] = location
    return d


def build_statement(run_record, run_record_path, generations_path, scored_path, evaluator_id,
                    suite_path=None, base_url=None, dataset_url=None, served_template_path=None):
    """Build the eval-result Statement for one screened tag.

    The scored file must cover exactly the suite's tasks for the recorded tag, at the screen
    threshold. base_url, when given, is where the three evidence files will be published (for
    example a raw.githubusercontent.com URL pinned to a commit); each file is then linked as
    base_url + its file name. Without it the evidence is referenced by digest only. For a tag
    without a template layer, served_template_path is the saved text of the template the
    server served; it is linked the same way and must match the digest in the run record.
    """
    if run_record.get("template_sha256") and run_record.get("template_matches_runtime") is False:
        raise ValueError("the run record shows the server served a different template than the tag's; "
                         "a statement would not describe what was run")
    if not evaluator_id or not TYPE_URI.fullmatch(str(evaluator_id)):
        raise ValueError("evaluator_id must be a URI for the party that ran the screen")
    suite_path = suite_path or os.path.join(ROOT, SUITE_FILE)
    suite_sha = sha256_file(suite_path)
    if suite_sha != run_record["suite_sha256"]:
        raise ValueError("suite file differs from the one recorded at run start")
    suite_tasks = load_json(suite_path)["suite_tasks"]
    tag = run_record["tag"]

    scored = load_json(scored_path)
    per_task = scored["per_task"]
    if sorted(per_task) != sorted(suite_tasks):
        raise ValueError("scored tasks are not exactly the suite's tasks")
    if scored.get("tag") is not None and scored["tag"] != tag:
        raise ValueError(f"scored file is for {scored['tag']}, run record for {tag}")
    if scored.get("threshold", SCREEN_THRESHOLD) != SCREEN_THRESHOLD:
        raise ValueError(f"scored threshold {scored['threshold']} is not the screen threshold {SCREEN_THRESHOLD}")
    n_tasks, n_pass = len(per_task), sum(1 for v in per_task.values() if v is True)
    passed = n_pass >= SCREEN_THRESHOLD
    for key, want in (("n_tasks", n_tasks), ("n_pass", n_pass), ("passed", passed)):
        if scored.get(key) is not None and scored[key] != want:
            raise ValueError(f"scored {key} {scored[key]!r} disagrees with its per-task results ({want!r})")
    gen_ids = [json.loads(l)["task_id"] for l in read_text(generations_path).splitlines() if l.strip()]
    if sorted(gen_ids) != sorted(suite_tasks):
        raise ValueError("generations are not exactly the suite's tasks")

    if dataset_url is None and suite_sha == SUITE_SHA256:
        dataset_url = SUITE_URL
    model_sha, template_sha = run_record["model_sha256"], run_record.get("template_sha256")
    base = base_url.rstrip("/") + "/" if base_url else None
    loc = (lambda p: base + os.path.basename(p)) if base else (lambda p: None)
    harness = {"name": run_record["harness"]["name"], "version": run_record["harness"]["version"]}
    # Pin the commit only when the screen code was known to be unmodified. Records written before
    # this field existed (the 17 Nov 2026 example) were made from a clean checkout.
    if run_record["harness"].get("gitCommit") and run_record["harness"].get("screen_code_modified", False) is False:
        harness["digest"] = {"gitCommit": run_record["harness"]["gitCommit"]}
    if template_sha:
        template_ev = _descriptor(EVIDENCE_NAMES["template"], template_sha, "application/vnd.ollama.image.template",
                                  blob_uri(tag, template_sha), location_key="uri")
    else:
        served = run_record["template_served_by_runtime_sha256"]
        if served_template_path and sha256_file(served_template_path) != served:
            raise ValueError("saved served template does not match the digest in the run record")
        template_ev = _descriptor(EVIDENCE_NAMES["served_template"], served, "text/plain",
                                  loc(served_template_path) if served_template_path else None)

    return {
        "_type": STATEMENT_TYPE,
        "subject": [{"name": subject_name(tag), "digest": {"sha256": model_sha}}],
        "predicateType": PREDICATE_TYPE,
        "predicate": {
            "evaluator": {"id": evaluator_id},
            "evaluatedAt": run_record["recorded_at_utc"],
            "suite": {"name": SUITE_NAME, "version": SUITE_VERSION},
            "claims": [{"metric": "tasks_solved", "comparator": ">=", "threshold": str(SCREEN_THRESHOLD),
                        "passed": passed}],
            "sampleSize": n_tasks,
            "model": _descriptor(tag, model_sha, "application/vnd.ollama.image.model",
                                 blob_uri(tag, model_sha), location_key="uri"),
            "dataset": _descriptor(os.path.basename(suite_path), suite_sha, "application/json", dataset_url),
            "assuranceLevel": "self_attested",
            "subjectProfile": "public_model",
            "evidence": [
                _descriptor(EVIDENCE_NAMES["run_record"], sha256_file(run_record_path), "application/json",
                            loc(run_record_path)),
                template_ev,
                _descriptor(EVIDENCE_NAMES["generations"], sha256_file(generations_path), "application/jsonl",
                            loc(generations_path)),
                _descriptor(EVIDENCE_NAMES["scored"], sha256_file(scored_path), "application/json",
                            loc(scored_path)),
            ],
            "harness": harness,
        },
    }


def dumps(statement):
    return json.dumps(statement, indent=2) + "\n"


# ---------------------------------------------------------------- checks

def _digest_problems(where, obj):
    d = obj.get("digest") if isinstance(obj, dict) else None
    if not isinstance(d, dict) or not d:
        return [f"{where}: missing digest"]
    if "sha256" in d and not SHA256_HEX.fullmatch(str(d["sha256"])):
        return [f"{where}: sha256 is not 64 lowercase hex characters"]
    return []


def check_statement(st):
    """Return a list of problems with STATEMENT against eval-result v0.1 (#575); empty means it conforms.

    This checks structure and field rules only. As the predicate says, the verdict in `passed`
    cannot be recomputed from the Statement alone, so it is not checked here. One quantcheck rule
    is added: for subjectProfile public_model, the subject digest must equal the model digest.
    """
    if not isinstance(st, dict):
        return ["statement is not a JSON object"]
    p = []
    if st.get("_type") != STATEMENT_TYPE:
        p.append("_type is not in-toto Statement v1")
    if st.get("predicateType") != PREDICATE_TYPE:
        p.append("predicateType is not eval-result v0.1")
    subj = st.get("subject")
    if not isinstance(subj, list) or not subj:
        p.append("subject must be a non-empty list")
        subj = []
    for i, s in enumerate(subj):
        p += _digest_problems(f"subject[{i}]", s)
    pr = st.get("predicate")
    if not isinstance(pr, dict):
        return p + ["predicate missing"]
    for key in ("evaluator", "evaluatedAt", "suite", "claims", "sampleSize", "assuranceLevel", "subjectProfile"):
        if key not in pr:
            p.append(f"predicate.{key} is required")
    ev = pr.get("evaluator")
    if not isinstance(ev, dict) or not isinstance(ev.get("id"), str) or not TYPE_URI.fullmatch(ev["id"]):
        p.append("predicate.evaluator.id must be a URI")
    if "evaluatedAt" in pr and not valid_timestamp(pr["evaluatedAt"]):
        p.append("predicate.evaluatedAt is not an RFC 3339 timestamp")
    suite = pr.get("suite")
    if not isinstance(suite, dict) or not suite.get("name") or not suite.get("version"):
        p.append("predicate.suite needs name and version")
    claims = pr.get("claims")
    if not isinstance(claims, list) or not claims:
        p.append("predicate.claims must be a non-empty list")
        claims = []
    for i, c in enumerate(claims):
        if not isinstance(c, dict):
            p.append(f"claims[{i}] is not an object")
            continue
        for key in ("metric", "comparator", "threshold", "passed"):
            if key not in c:
                p.append(f"claims[{i}].{key} is required")
        if c.get("comparator") not in COMPARATORS:
            p.append(f"claims[{i}].comparator must be one of {', '.join(COMPARATORS)}")
        if not isinstance(c.get("threshold"), str) or not DECIMAL.fullmatch(c["threshold"]):
            p.append(f"claims[{i}].threshold must be a decimal string")
        if not isinstance(c.get("passed"), bool):
            p.append(f"claims[{i}].passed must be a boolean")
    n = pr.get("sampleSize")
    if not isinstance(n, int) or isinstance(n, bool) or n <= 0:
        p.append("predicate.sampleSize must be a positive integer")
    commits = pr.get("commitments", {})
    if not isinstance(commits, dict):
        p.append("predicate.commitments must be an object")
        commits = {}
    for ident in ("model", "dataset"):
        if (ident in pr) == (ident in commits):
            p.append(f"exactly one of predicate.{ident} and commitments.{ident} must be present")
        if ident in pr:
            p += _digest_problems(f"predicate.{ident}", pr[ident])
        if ident in commits:
            cm = commits[ident]
            if not isinstance(cm, dict):
                p.append(f"commitments.{ident} is not an object")
                continue
            if cm.get("salted") is not True:
                p.append(f"commitments.{ident}.salted must be true")
            for key in ("alg", "value"):
                if not isinstance(cm.get(key), str) or not cm[key]:
                    p.append(f"commitments.{ident}.{key} is required")
    if pr.get("assuranceLevel") not in ASSURANCE_LEVELS:
        p.append("predicate.assuranceLevel is not a defined value")
    if pr.get("subjectProfile") not in SUBJECT_PROFILES:
        p.append("predicate.subjectProfile is not a defined value")
    evidence = pr.get("evidence", [])
    if not isinstance(evidence, list):
        p.append("predicate.evidence must be a list")
        evidence = []
    for i, e in enumerate(evidence):
        p += _digest_problems(f"evidence[{i}]", e)
    h = pr.get("harness")
    if h is not None and (not isinstance(h, dict) or not h.get("name") or not h.get("version")):
        p.append("predicate.harness needs name and version")
    # quantcheck rule
    if pr.get("subjectProfile") == "public_model" and subj and isinstance(pr.get("model"), dict):
        if isinstance(subj[0], dict) and subj[0].get("digest") != pr["model"].get("digest"):
            p.append("subject digest differs from the model descriptor digest")
    return p


def fetch_problems(st, timeout=120):
    """Download every linked descriptor except the model blob and compare its sha256."""
    pr = st.get("predicate", {}) if isinstance(st, dict) else {}
    items = [("dataset", pr.get("dataset"))] + [(f"evidence[{i}]", e) for i, e in enumerate(pr.get("evidence") or [])]
    p = []
    for where, d in items:
        if not isinstance(d, dict):
            continue
        url = d.get("downloadLocation") or d.get("uri")
        want = (d.get("digest") or {}).get("sha256")
        if not url or not want:
            continue
        try:
            with urllib.request.urlopen(url, timeout=timeout) as r:
                got = sha256_bytes(r.read())
        except Exception as e:
            p.append(f"{where}: could not fetch {url}: {e}")
            continue
        if got != want:
            p.append(f"{where}: {url} hashes to {got}, statement says {want}")
    return p


# ---------------------------------------------------------------- command line

def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("record", help="write the run record for a tag (before generation)")
    r.add_argument("--tag", required=True)
    r.add_argument("--out", required=True)
    r.add_argument("--host")
    r.add_argument("--models-dir")
    r.add_argument("--backend", help="inference backend, for example Metal or CUDA (recorded as given)")
    s = sub.add_parser("statement", help="build the eval-result Statement from a finished screen")
    s.add_argument("--run-record", required=True)
    s.add_argument("--generations", required=True)
    s.add_argument("--scored", required=True)
    s.add_argument("--evaluator-id", required=True, help="URI of whoever ran the screen")
    s.add_argument("--suite", default=os.path.join(ROOT, SUITE_FILE))
    s.add_argument("--base-url", help="where the evidence files will be published")
    s.add_argument("--dataset-url", help="download location of the suite file")
    s.add_argument("--out", required=True)
    c = sub.add_parser("check", help="check a Statement against eval-result v0.1")
    c.add_argument("statement")
    c.add_argument("--fetch", action="store_true", help="also download linked files and compare digests")
    a = ap.parse_args(argv)

    if a.cmd == "record":
        ev, extra = None, {}
        try:
            import evalplus
            from evalplus.data import get_human_eval_plus
            ev = evalplus.__version__
            extra = evalplus_info(get_human_eval_plus(), load_json(os.path.join(ROOT, SUITE_FILE))["suite_tasks"])
        except ImportError:
            pass
        rec = record_run(a.tag, a.host, a.models_dir, a.backend, ev, extra=extra)
        with open(a.out, "w") as f:
            json.dump(rec, f, indent=2)
            f.write("\n")
        print(f"run record written: {a.out} (template served by runtime "
              f"{'matches the tag' if rec['template_matches_runtime'] else 'DOES NOT match the tag'})")
        return 0
    if a.cmd == "statement":
        st = build_statement(load_json(a.run_record), a.run_record, a.generations, a.scored,
                             a.evaluator_id, a.suite, a.base_url, a.dataset_url)
        problems = check_statement(st)
        with open(a.out, "w") as f:
            f.write(dumps(st))
        claim = st["predicate"]["claims"][0]
        print(f"statement written: {a.out} (passed={claim['passed']}, threshold {claim['threshold']}, "
              f"sampleSize {st['predicate']['sampleSize']})")
        for prob in problems:
            print("PROBLEM:", prob)
        return 1 if problems else 0
    if a.cmd == "check":
        st = load_json(a.statement)
        problems = check_statement(st) + (fetch_problems(st) if a.fetch else [])
        for prob in problems:
            print("PROBLEM:", prob)
        print("conforms to eval-result v0.1" if not problems else f"{len(problems)} problem(s)")
        return 1 if problems else 0
    return 2


if __name__ == "__main__":
    sys.exit(main())
