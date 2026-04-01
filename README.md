# autooptimize

Autonomous code optimization loop for [Claude Code](https://docs.anthropic.com/en/docs/claude-code). Inspired by Karpathy's [autoresearch](https://github.com/karpathy/autoresearch).

One metric, one loop, git-based rollback. Hypothesize, implement, benchmark, keep or discard, repeat.

## How it works

1. Read per-project config from `.claude/autooptimize.toml`
2. Establish a baseline measurement
3. For each experiment (default 5):
   - Generate optimization hypothesis from performance docs + past results
   - Create isolated branch, implement change
   - Run local gates (compile, lint, test, determinism)
   - Benchmark on VPS (or locally)
   - Keep if improvement exceeds threshold (default 2%), discard otherwise
   - Log result to experiment log
4. Stop after max experiments or N consecutive failures

## Usage

Copy `autooptimize-methodology.md` into your project's Claude Code directory:

```
.claude/reference/autooptimize-methodology.md
```

Add a reference in your project's `CLAUDE.md` so Claude loads it automatically:

```markdown
When asked to run the optimization loop, read `.claude/reference/autooptimize-methodology.md`.
```

Then start an optimization session by telling Claude:

```
Run the autooptimize loop.
```

```
Run the autooptimize loop, max 10 experiments.
```

```
Run a dry-run of the autooptimize loop - show hypotheses but don't execute.
```

Create a project config at `.claude/autooptimize.toml` in your target project. See the Config Reference section in `autooptimize-methodology.md` for the full schema.

## Requirements

- [Claude Code](https://docs.anthropic.com/en/docs/claude-code) CLI
- A project with a measurable performance metric
- A benchmark script that outputs parseable results
- Git (experiments use branch isolation)

## Config

Each project needs `.claude/autooptimize.toml` defining:

- **scope** - which files the optimizer can modify
- **build** - compile, test, lint, format commands
- **benchmark** - script, metric name, direction (higher/lower), runs per experiment
- **constraints** - determinism checks, improvement thresholds, experiment limits
- **context** - performance docs, experiment log path

VPS benchmarking is optional. Omit `[benchmark.vps]` to benchmark locally.

## License

MIT
