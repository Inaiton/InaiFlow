#!/usr/bin/env node
// Keeps the AI tooling installed and fresh with no plugin activation:
//   graphify    -> local code knowledge graph in graphify-out/ (git-ignored, rebuilt per machine)
//   agent-skills -> vendored into .claude/ (committed, pinned in .claude/ai-tools.json)
// Commands: setup (install + build graph, idempotent) | hook (Claude SessionStart) | update (bump pins + re-vendor)
// Never fails the caller: pnpm install and Claude sessions must not break because of tooling.
import { spawn, spawnSync } from "node:child_process";
import {
  cpSync, existsSync, mkdirSync, mkdtempSync, openSync, readdirSync, readFileSync, rmSync, writeFileSync,
} from "node:fs";
import { createHash } from "node:crypto";
import { homedir, tmpdir } from "node:os";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const SELF = fileURLToPath(import.meta.url);
const ROOT = resolve(dirname(SELF), "..");
const CLAUDE = join(ROOT, ".claude");
const LOCK = join(CLAUDE, "ai-tools.json");
const OUT = join(ROOT, "graphify-out");
const STAMP = join(OUT, ".stamp");
const BUSY = join(OUT, ".busy");
const PY = ["python3", "python", "py"];

const lock = () => JSON.parse(readFileSync(LOCK, "utf8"));
const run = (cmd, args, opts = {}) =>
  spawnSync(cmd, args, { cwd: ROOT, encoding: "utf8", windowsHide: true, ...opts });
const ok = (r) => !r.error && r.status === 0;
const log = (m) => console.error(`[ai-tools] ${m}`);

// ---- graphify ---------------------------------------------------------------------------------
const home = homedir();
const BINS = ["graphify", join(home, ".local", "bin", "graphify"), join(home, ".local", "bin", "graphify.exe")];

function graphify() {
  for (const b of BINS) {
    const r = run(b, ["--version"]);
    if (ok(r)) return { bin: b, version: (r.stdout.match(/(\d+\.\d+\.\d+)/) || [])[1] };
  }
  return null;
}

function installGraphify(version) {
  const spec = `graphifyy==${version}`;
  const attempts = [
    ["uv", ["tool", "install", "--python", "3.12", "--force", spec]],
    ...PY.map((p) => [p, ["-m", "uv", "tool", "install", "--python", "3.12", "--force", spec]]),
    ["pipx", ["install", "--force", spec]],
    ...PY.map((p) => [p, ["-m", "pip", "install", "--user", "--upgrade", spec]]),
  ];
  for (const [cmd, args] of attempts) if (ok(run(cmd, args, { stdio: "inherit" }))) return true;
  log("could not install graphify (need uv, pipx or Python 3.11.5-3.14). Skipping.");
  return false;
}

function ensureGraphify() {
  const want = lock().graphify.version;
  const have = graphify();
  if (have?.version === want) return have;
  log(`installing graphifyy==${want}`);
  return installGraphify(want) ? graphify() : null;
}

const stampNow = () => {
  const git = (a) => run("git", a).stdout || "";
  const h = createHash("sha1").update(git(["rev-parse", "HEAD"])).update(git(["status", "--porcelain"]));
  return h.update(readFileSync(LOCK)).digest("hex");
};

const fresh = () => existsSync(join(OUT, "graph.json")) && existsSync(STAMP) && readFileSync(STAMP, "utf8") === stampNow();

function setup() {
  mkdirSync(OUT, { recursive: true });
  if (existsSync(BUSY) && Date.now() - Number(readFileSync(BUSY, "utf8")) < 15 * 60_000) return; // another run is active
  writeFileSync(BUSY, String(Date.now()));
  try {
    const g = ensureGraphify();
    if (!g) return;
    if (fresh()) return;
    // code-only: tree-sitter AST, no LLM, no API key, nothing leaves the machine. Cached, so reruns are incremental.
    run(g.bin, ["extract", ".", "--code-only"], { stdio: "inherit" });
    run(g.bin, ["cluster-only", ".", "--no-label"], { stdio: "inherit" });
    if (existsSync(join(OUT, "graph.json"))) writeFileSync(STAMP, stampNow());
  } finally {
    rmSync(BUSY, { force: true });
  }
}

function kick() {
  mkdirSync(OUT, { recursive: true });
  const fd = openSync(join(OUT, "setup.log"), "a");
  spawn(process.execPath, [SELF, "run"], { cwd: ROOT, detached: true, stdio: ["ignore", fd, fd], windowsHide: true }).unref();
}

function hook() {
  const have = existsSync(join(OUT, "graph.json"));
  if (!fresh()) kick();
  const context = have
    ? "graphify code graph is available (graphify-out/GRAPH_REPORT.md, auto-refreshed in the background). Before grepping or reading many files, read the report and use `graphify query \"...\"`, `graphify explain \"...\"` or `graphify path \"A\" \"B\"` (or /graphify). The graph is a map, not proof: open the cited source before relying on it."
    : "graphify is installing and building the code graph in the background (see graphify-out/setup.log). Until graphify-out/graph.json exists, search the repo normally.";
  console.log(JSON.stringify({ hookSpecificOutput: { hookEventName: "SessionStart", additionalContext: context } }));
}

// ---- update (pins + vendored files) ----------------------------------------------------------
const walk = (d) => readdirSync(d, { withFileTypes: true }).flatMap((e) => (e.isDirectory() ? walk(join(d, e.name)) : [join(d, e.name)]));
const retarget = (file) => {
  if (!file.endsWith(".md")) return;
  const t = readFileSync(file, "utf8");
  const n = t.replace(/\bagent-skills:([a-z][a-z0-9-]*)/g, "$1"); // plugin namespace does not exist once vendored
  if (n !== t) writeFileSync(file, n);
};

function syncGraphifySkill() {
  const bin = graphify()?.bin;
  if (!bin) return log("graphify missing; skill not refreshed");
  const tmp = mkdtempSync(join(tmpdir(), "gfy-"));
  try {
    const env = { ...process.env, HOME: tmp, USERPROFILE: tmp }; // keep the real ~/.claude untouched
    run(bin, ["install"], { env });
    const src = join(tmp, ".claude", "skills", "graphify");
    if (!existsSync(src)) return log("graphify skill not produced; skipped");
    const dst = join(CLAUDE, "skills", "graphify");
    rmSync(dst, { recursive: true, force: true });
    cpSync(src, dst, { recursive: true });
  } finally {
    rmSync(tmp, { recursive: true, force: true });
  }
}

function syncAgentSkills(cfg) {
  const tmp = mkdtempSync(join(tmpdir(), "agsk-"));
  try {
    const c = run("git", ["clone", "--depth", "1", cfg.repo, tmp], { stdio: "inherit" });
    if (!ok(c)) return log("clone of agent-skills failed; kept previous copy");
    const sha = run("git", ["rev-parse", "HEAD"], { cwd: tmp }).stdout.trim();
    const skillsDir = join(CLAUDE, "skills");
    for (const f of cfg.files || []) rmSync(join(ROOT, f), { recursive: true, force: true }); // drop what we vendored last time
    const files = [];
    const put = (from, to) => {
      if (!existsSync(from)) return;
      cpSync(from, join(ROOT, to), { recursive: true });
      files.push(to);
    };
    for (const d of readdirSync(join(tmp, "skills"))) {
      if (existsSync(join(skillsDir, d))) { log(`skill "${d}" already exists in the project; not overwritten`); continue; }
      put(join(tmp, "skills", d), `.claude/skills/${d}`);
    }
    for (const f of readdirSync(join(tmp, ".claude", "commands"))) {
      // /review would shadow the built-in, so it ships as /quality-review
      put(join(tmp, ".claude", "commands", f), `.claude/commands/${f === "review.md" ? "quality-review.md" : f}`);
    }
    put(join(tmp, "agents"), ".claude/agents-agent-skills"); // personas, kept apart from the project's own agents
    put(join(tmp, "references"), ".claude/agent-skills-references");
    put(join(tmp, "LICENSE"), ".claude/agent-skills-references/LICENSE");
    for (const f of files) {
      const p = join(ROOT, f);
      for (const x of existsSync(p) && !p.endsWith(".md") && !p.endsWith("LICENSE") ? walk(p) : [p]) if (x.endsWith(".md")) retarget(x);
    }
    return { ...cfg, sha, files };
  } finally {
    rmSync(tmp, { recursive: true, force: true });
  }
}

async function update() {
  const cfg = lock();
  const meta = await fetch("https://pypi.org/pypi/graphifyy/json").then((r) => r.json()).catch(() => null);
  if (meta?.info?.version) cfg.graphify.version = meta.info.version;
  writeFileSync(LOCK, JSON.stringify(cfg, null, 2) + "\n");
  if (ensureGraphify()) syncGraphifySkill();
  cfg.agentSkills = syncAgentSkills(cfg.agentSkills) ?? cfg.agentSkills;
  writeFileSync(LOCK, JSON.stringify(cfg, null, 2) + "\n");
  log(`graphify ${cfg.graphify.version}, agent-skills ${cfg.agentSkills.sha.slice(0, 7)}`);
}

// ---- main ------------------------------------------------------------------------------------
const cmd = process.argv[2] || "setup";
try {
  if (cmd === "hook") hook();
  else if (cmd === "update") await update();
  else if (cmd === "setup") {
    // Hosted builds (Vercel/CI) run `pnpm install` too; they never need the graph.
    if (process.env.CI || process.env.VERCEL || process.env.GITHUB_ACTIONS) process.exit(0);
    process.argv.includes("--wait") ? setup() : kick();
  } else if (cmd === "run") setup(); // internal: the detached worker
  else log(`unknown command "${cmd}" (setup | hook | update)`);
} catch (e) {
  log(String(e?.message || e));
}
