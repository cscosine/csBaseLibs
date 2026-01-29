# Agent Guide: csBaseLibs (quick reference)

This file gives focused, actionable guidance for AI coding agents working in this repository.

**Big picture**
- `csBaseLibs` is a meta-project that orchestrates multiple C++ subprojects as separate repositories: `csCore/`, `csLie/`, `csCamera/`, `csVisOpenGL/` (each contains its own `CMakePresets.json` and `projectConfig.toml`).
- Top-level orchestration is done by `project.py` which delegates checkout and build workflows to `csProjectManager` (`csProjectManager/projectManager.py`).
- The meta-project downloads some precompiled 3rd-party bundles into `libs/<preset>/` and places build artifacts in `build/<preset>/<repo>/` and installs in `install/<preset>/`.

**How builds and workflows are driven (concrete)**
- Install Python requirements used by the orchestrator: `csProjectManager/requirements.txt` (requires `keyring`, `requests`, `GitPython`, etc.).
- Prerequisite script for Linux: `installRequirements-linux.sh` (called by `project.py` during checkout).  Run it manually if needed.
- Typical orchestration commands (run from repo root):

```
python3 -m pip install -r csProjectManager/requirements.txt
python3 project.py -u -b         # clone/update subrepos (-u) and build them (-b)
python3 project.py -gw           # generate GitHub Actions full-build workflow
python3 project.py -b -bo csCore -po linux-ninja  # build only csCore using a preset
python3 project.py -cb -ci      # clear build and install folders (use with -y to skip confirmation)
```

- `project.py` uses `csWorkflow()` to generate commands like `cmake --workflow <preset>`; the `csCMake` repository contains presets and helper tooling (`csCMake/presets/` and `csCMake.cmake`). If `cmake --workflow` fails, inspect the printed commands in the `projectManager` output and run the corresponding `cmake --preset` or the exact command shown.

**Important files & locations to inspect**
- `project.py` — top-level entry; defines `checkout_func()` and `build_func()` used by `csProjectManager`. Example: `checkout_func` calls `csGetRepository()` and `csGetPrecompiledLib()`.
- `csProjectManager/projectManager.py` — core orchestration: argument parsing, `csSetupProject()`, generation/execution of build commands, pre-commit handling, and GitHub workflow generation.
- `csCMake/` — custom presets and CMake helper code used across subprojects.
- Per-subproject: each subdir (`csCore/`, `csLie/`, `csCamera/`, `csVisOpenGL/`) contains `CMakePresets.json` and `projectConfig.toml` which drive per-repo builds.
- `installRequirements-linux.sh` — distro-level prerequisites installer used on Linux.
- `csProjectManager/requirements.txt` — Python deps required to run `project.py` and `csProjectManager`.

**Project-specific conventions & patterns**
- Meta-project model: this repo is not a single build — it clones and manages multiple independent repositories; changes to one subrepo usually require re-running the meta `project.py` flow to reproduce CI-like builds.
- Build presets are named and sometimes composed (e.g., `linux-ninja{debug|release|relWithDebInfo|paranoid}`) — `csProjectManager` expands these into concrete `cmake --workflow` commands.
- Precompiled 3rd-party bundles (release assets) are fetched using GitHub API and extracted into `libs/<preset>/`. Access requires a GitHub token kept in system keyring under service `github` and account `csCosineGithubToken`.

**Tokens / secrets**
- `csProjectManager` expects a GitHub token retrieved via `keyring.get_password("github", "csCosineGithubToken")`. To set it locally:

```
python3 -m pip install keyring
python3 -c "import keyring; keyring.set_password('github','csCosineGithubToken','<YOUR_TOKEN>')"
```

**Pre-commit and hooks**
- `csProjectManager` will check for pre-commit and can install/run hooks. Use `--install-hooks` or `--run-hooks` flags when invoking `project.py` (see `python3 project.py --help`).

**If you need to modify or debug builds**
- Run `python3 project.py -u` to ensure all subrepos are present, then re-run `python3 project.py -b` to build. When failures occur, inspect `projectManager` printed commands — it prints exact commands it will run for each repo and preset. You can re-run those commands manually in the subrepo directory.

**Good examples to cite while coding**
- `project.py` uses `csGetRepository()` and `csGetPrecompiledLib()` — follow those call sites when you need to add new repos or bundled libs.
- `csProjectManager/projectManager.py` shows how CLI flags map to behavior (`--build`, `--update`, `--build-only`, `--preset-only`, `--generate-workflow`). Use the same flags for automation logic.

If anything above is unclear or you want a shorter/longer form (or to include extra examples like exact CMake preset names), tell me which sections to expand and I will iterate.
