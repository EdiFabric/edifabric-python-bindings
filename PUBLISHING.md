# Publishing to PyPI

The PyPI package `edifabric-x12` is published as four platform wheels. Each wheel holds the
`edifabric_x12` package plus the ediFabric Native library for one platform:

| Wheel tag | Library | Requires |
| --- | --- | --- |
| `win_amd64` | `edifabric-x12-tools.dll` | Windows x64 |
| `manylinux_2_34_x86_64` | `edifabric-x12-tools.so` | Linux x64, glibc 2.34+ |
| `manylinux_2_34_aarch64` | `edifabric-x12-tools.so` | Linux arm64, glibc 2.34+ |
| `macosx_12_0_arm64` | `edifabric-x12-tools.dylib` | macOS 12+ on Apple silicon |

The libraries come from the public downloads at `https://www.edifabric.com/download/`, so
publish a release only after the native build for that version is uploaded there. There is no
source distribution, because a package without the native library would not work.

| File | Purpose |
| --- | --- |
| `pyproject.toml` | package metadata and version |
| `scripts/fetch-natives.ps1`, `.sh` | download the four libraries into `natives/<rid>/` |
| `scripts/build_wheels.py` | build and tag one wheel per platform into `dist/` |
| `scripts/smoke_test.py` | check that an installed wheel loads its bundled library |
| `scripts/release.ps1`, `.sh` | fetch, build, check, smoke-test, and upload from your machine |
| `.github/workflows/publish-pypi.yml` | the same pipeline in GitHub Actions, with a smoke test on every platform |

## One-time setup

1. Create the `edifabric-x12` project on [PyPI](https://pypi.org) and [TestPyPI](https://test.pypi.org)
   with the EdiFabric account (the first upload creates it; a
   [pending trusted publisher](https://docs.pypi.org/trusted-publishers/creating-a-project-through-oidc/)
   lets GitHub Actions create it).
2. On both sites, add a trusted publisher under **Your projects > edifabric-x12 > Publishing**:
   - Owner `EdiFabric`, repository `edifabric-python-bindings`
   - Workflow `publish-pypi.yml`
   - Environment `pypi` on PyPI, `testpypi` on TestPyPI
3. In the GitHub repository, create the environments `pypi` and `testpypi`
   (**Settings > Environments**). Add required reviewers to `pypi` if releases need approval.
4. For uploads from your machine only: create API tokens on PyPI and TestPyPI and keep them in
   `~/.pypirc` or set `TWINE_USERNAME=__token__` and `TWINE_PASSWORD=<token>`.

## Release

1. Upload the new native build to `https://www.edifabric.com/download/`.
2. Set `version` in `pyproject.toml` to the native library version, for example `1.1.1`, and
   commit.
3. Publish to TestPyPI and check the install:
   - GitHub: **Actions > Publish to PyPI > Run workflow**, repository `testpypi`
   - or locally: `./scripts/release.ps1 -TestPyPI` (Windows) or `scripts/release.sh --testpypi`

   ```bash
   pip install --index-url https://test.pypi.org/simple/ edifabric-x12
   ```

4. Create a GitHub release with the tag `v<version>`, for example `v1.1.1`. Publishing the
   release runs the workflow against PyPI; the workflow fails if the tag and the version differ.
   Locally, the equivalent is `./scripts/release.ps1` or `scripts/release.sh`.

To build without uploading, run `./scripts/release.ps1 -DryRun` or `scripts/release.sh --dry-run`.
PyPI never accepts the same version twice, so a fix needs a new version, such as `1.1.1.post1`
for a packaging-only change.
