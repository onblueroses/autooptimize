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
   - Log result to TSV experiment log
4. Stop after max experiments or N consecutive failures

## Installation

Copy `SKILL.md` and `references/` into your Claude Code skills directory:

```
.claude/skills/autooptimize/
  SKILL.md
  references/
    hypothesis-strategy.md
```

Create a project config at `.claude/autooptimize.toml` in your target project. See the Config Reference section in SKILL.md for the full schema.

## Usage

```
/autooptimize              # Run with defaults from config
/autooptimize --max 10     # Override max experiments
/autooptimize --dry-run    # Show what would be tried, don't execute
```

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
