# pyproject-external

This is a proof of concept CLI (plus a Python API) to interact with
[PEP 725](https://peps.python.org/pep-0725/) `[external]` metadata.

*Note: all of this is currently experimental, and under the hood doesn't look
anything like a production-ready version would. Please don't use this for
anything beyond experimenting.*

## CLI usage

The CLI interface available as `python -m pyproject_external` provides several subcommands:

- `show`: Query `[external]` metadata from pyproject.toml or source distributions. It can render it as is, normalized, mapped to your package manager names, or as a ready-to-run install command.
- `prepare`: Prepare a package for building with user-provided `[external]` metadata by downloading and patching its most recent sdist.
- `build`: Build a wheel for the given sdist or project. External dependencies are installed before the build starts.
- `install`: Install a project in the given location. Wheels will be built as needed. External dependencies are installed before the build starts too.

### Example

Let's build `cryptography` from source! You'll need `git` and [`pixi`](https://pixi.sh/latest/installation/).

#### Install

First, let's install `pyproject-external`:

```bash
# Clone the repository
git clone https://github.com/jaimergp/pyproject-external.git
cd pyproject-external/
# Enter a new pixi shell, this shall stay open in the rest of the example
pixi shell
```

> You can also use `pixi run` directly instead of `pixi shell`, like `pixi run python -m pyproject_external`, but in this example we'll assume you are inside a `pixi shell`.

In this shell, `pyproject_external` is installed and available as:

```
# Run the CLI help
python -m pyproject_external
```

If you don't want to use `pixi` at all, you can also use `uv run -m pyproject_external` directly. Note that in this case the package manager auto-detection will fallback to a system package manager (and not Pixi), so it will likely make changes to your system installation.

#### Prepare sdist

Now, let's prepare the `cryptography` sdist for building. Checking their install instructions,
it would require this `[external]` table:

```toml
[external]
build-requires = [
  "dep:virtual/compiler/c",
  "dep:virtual/compiler/rust",
  "dep:generic/pkg-config",
]
host-requires = [
  "dep:generic/openssl",
  "dep:generic/libffi",
]
```

Save it as `cryptography.toml` in a `external-metadata` directory and then run this command:

```bash
python -m pyproject_external prepare cryptography --external-metadata-dir=external-metadata/
```

You'll find a patched `cryptography-*.tar.gz` file under the `sdist/` directory.

#### Inspect patched sdist

What happened during `prepare`? We simply amended the sdist `pyproject.toml` to include the `[external]` table and put it back in the tarball. We can now inspect it with the `show` subcommand:

Show the `[external]` table as is:

```bash
$ python -m pyproject_external show sdist/cryptography-*.tar.gz
[external]
build-requires = [
    "dep:virtual/compiler/c",
    "dep:virtual/compiler/rust",
    "dep:generic/pkg-config",
]
host-requires = [
    "dep:generic/openssl",
    "dep:generic/libffi",
]
```

Map the `dep:` URLs to conda-forge packages (auto-detected because we are in a Pixi shell):

```bash
$ python -m pyproject_external show sdist/cryptography-*.tar.gz --output=mapped
[external]
build_requires = [
    "c-compiler",
    "rust",
    "pkg-config",
    "python",
]
host_requires = [
    "openssl",
    "libffi",
]
```

Write the command needed to install these dependencies (again, Pixi auto-detected because of `pixi shell`):

```bash
$ python -m pyproject_external show sdist/cryptography-*.tar.gz --output=command
pixi add c-compiler rust pkg-config openssl libffi python
```

If you want a different package manager, use `--package-manager`. Notice how the package names are also different, since they are mapped to the correct ecosystem (Debian), instead of the auto-detected conda-forge.

```bash
$ python -m pyproject_external show sdist/cryptography-*.tar.gz --output=command --package-manager=apt
sudo apt install --yes gcc rustc pkgconf openssl libffi8 libffi-dev python3
```

#### Build wheel

Now you can take the patched sdist and turn it into a wheel with:

```bash
python -m pyproject_external build sdist/cryptography-*.tar.gz
```

This will fail if you run it locally! That's intentional. We need to install external dependencies with your system package manager, which might be a surprising side effect, specially if there are tons of dependencies to install (e.g. compilers, heavy librariers, etc). By default, it will auto-detect the system package manager for your distribution (e.g. `apt` for Ubuntu), but here you can also provide a different one with `--package-manager`.

If you understand the risks, proceed with:

```bash
CI=1 python -m pyproject_external build sdist/cryptography-*.tar.gz
```

A `cryptography-*.whl` file will show up in your working directory. You can install it with `pip install` or distribute it in your preferred way.

#### Install wheel directly

If you don't want to keep the wheel file around, you can build it and install it in a single step with:

```bash
CI=1 python -m pyproject_external install sdist/cryptography-*.tar.gz
```

Same warnings apply about the `CI=1` guards!

## Python API

The library offers several classes importable from `pyproject_external`.
The high-level API is provided by the `External` class. All the other
objects are considered low-level API to interact with the data
provided by [`external-metadata-mappings`](https://github.com/jaimergp/external-metadata-mappings).

## Related projects

- [`external-deps-build`](https://github.com/rgommers/external-deps-build): CI workflows to
  build popular PyPI packages patched with the necessary `[external]` metadata.
- [`external-metadata-mappings`](https://github.com/jaimergp/external-metadata-mappings):
  Schemas, registries and mappings to support `[external]` metadata for different ecosystems
  and package managers.

## Contributing

Refer to [`CONTRIBUTING`](./CONTRIBUTING).
