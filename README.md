[![pre-commit](https://img.shields.io/badge/pre--commit-enabled-brightgreen?logo=pre-commit&logoColor=white)](https://github.com/pre-commit/pre-commit)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![uv](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/uv/main/assets/badge/v0.json)](https://github.com/astral-sh/uv)
[![Checked with pyright](https://microsoft.github.io/pyright/img/pyright_badge.svg)](https://microsoft.github.io/pyright/)
[![Actions status](https://github.com/LabAutomationAndScreening/lab-auto-pulumi/actions/workflows/ci.yaml/badge.svg?branch=main)](https://github.com/LabAutomationAndScreening/lab-auto-pulumi/actions)
[![Open in Dev Containers](https://img.shields.io/static/v1?label=Dev%20Containers&message=Open&color=blue)](https://vscode.dev/redirect?url=vscode://ms-vscode-remote.remote-containers/cloneInVolume?url=https://github.com/LabAutomationAndScreening/lab-auto-pulumi)
[![PyPI Version](https://img.shields.io/pypi/v/lab-auto-pulumi.svg)](https://pypi.org/project/lab-auto-pulumi/)
[![Downloads](https://pepy.tech/badge/lab-auto-pulumi)](https://pepy.tech/project/lab-auto-pulumi)
[![Python Versions](https://img.shields.io/pypi/pyversions/lab-auto-pulumi.svg)](https://pypi.org/project/lab-auto-pulumi/)
[![Codecov](https://codecov.io/gh/LabAutomationAndScreening/lab-auto-pulumi/branch/main/graph/badge.svg)](https://codecov.io/gh/LabAutomationAndScreening/lab-auto-pulumi)
[![OpenIssues](https://isitmaintained.com/badge/open/LabAutomationAndScreening/lab-auto-pulumi.svg)](https://isitmaintained.com/project/LabAutomationAndScreening/lab-auto-pulumi)

# Usage
Documentation is hosted on [ReadTheDocs](https://lab-auto-pulumi.readthedocs.io/en/latest/?badge=latest).

# Development

Multi-step workflows are defined as [Task](https://taskfile.dev) tasks. Run `task --list` to see them; the definitions live in `.config/taskfiles/`, and `Taskfile.yaml` in the repo root is only a shim that includes them.

This project has a dev container. If you already have VS Code and Docker installed, you can click the badge above or [here](https://vscode.dev/redirect?url=vscode://ms-vscode-remote.remote-containers/cloneInVolume?url=https://github.com/LabAutomationAndScreening/lab-auto-pulumi) to get started. Clicking these links will cause VS Code to automatically install the Dev Containers extension if needed, clone the source code into a container volume, and spin up a dev container for use.

To publish a new version of the repository, you can run the `Publish` workflow manually and publish to the staging registry from any branch, and you can check the 'Publish to Primary' option when on `main` to publish to the primary registry and create a git tag.

The `Release` workflow reuses the checks from CI instead of re-running them: it requires that the `CI` workflow has already completed successfully for the current commit (including the `workflow-summary` job) and reuses the artifacts CI built rather than rebuilding. Trigger it manually with `workflow_dispatch`; a real release must be run from `main`, while the `dry_run` option lets you exercise the workflow from any branch without tagging or releasing. A real run publishes the CI-built distribution to the staging registry and verifies a fresh install, then pushes the `v<version>` git tag, publishes to the primary registry, verifies the install again, and finally creates a GitHub Release with auto-generated notes.

<!-- TODO: migrate away from the `Publish` and `Publish to Staging` workflows and merge all of their functionality into the `Release` workflow. -->






## Updating from the template
This repository uses a copier template. To pull in the latest updates from the template, run `task copier-update`

<!--
============== WARNING ==============================================================================
File is managed by copier template: gh:LabAutomationAndScreening/copier-base-template.git
See .config/.copier-managed-files.json for details.

You are welcome to make changes to this file in your repo if they are custom to your project,
but if the change should be shared with other projects, please backport it to the template repo.
=====================================================================================================
-->
