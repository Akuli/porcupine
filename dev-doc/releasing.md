# Releasing Porcupine

These instructions are meant for Porcupine maintainers.
Other people shouldn't need them.

1. Update `CHANGELOG.md` based on Git logs (e.g. `git log --all --oneline --graph`).
    You should add a new section to the beginning with `Unreleased` instead of a version number.
    Don't split the text to multiple lines any more than is necessary,
    as that won't show up correctly on GitHub's releases page.
2. Make a pull request of your changelog edits. Review carefully:
    changing the changelog afterwards is difficult, as the text gets copied into the releases page.
    It also goes to email notifications when releasing.
3. Merge the pull request and pull the merge commit to your local `main` branch.
4. Run `python3 scripts/release.py` from the `main` branch.
    The script pushes a tag named e.g. `v2022.08.28`,
    which triggers the parts of `.github/workflows/release-builds.yml`
    that have `if: startsWith(github.ref, 'refs/tags/v')` in them.
    They create a release whose description comes from `CHANGELOG.md`.

If you want, you can also do a release from a branch named `bugfix-release` instead of `main`.
This is useful if you fixed a bug that made Porcupine unusable for someone,
but the new features on `main` aren't ready for releasing yet.
