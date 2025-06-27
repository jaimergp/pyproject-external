# pyproject-external

This is a proof of concept of a library and CLI to interact with
[PEP 725](https://peps.python.org/pep-0725/) `[external]` metadata.

The library offers several classes importable from `pyproject_external`.
The high-level API is provided by the `External` class. All the other
objects are considered low-level API to interact with the data
provided by [`external-metadata-mappings`](https://github.com/jaimergp/external-metadata-mappings).

The CLI interface available as `python -m pyproject_external` allows you to
take a sdist or a local directory to parse and present the `[external]`
metadata in different ways: as is, normalized, mapped to the desired ecosystem
and package manager, or as a command you can run in your machine.

*Note: all of this is currently experimental, and under the hood doesn't look
anything like a production-ready version would. Please don't use this for
anything beyond experimenting.*

## Related projects

- [`external-deps-build`](https://github.com/rgommers/external-deps-build): CI workflows to
  build popular PyPI packages patched with the necessary `[external]` metadata.
- [`external-metadata-mappings`](https://github.com/jaimergp/external-metadata-mappings):
  Schemas, registries and mappings to support `[external]` metadata for different ecosystems
  and package managers.

## Contributing

Refer to [`CONTRIBUTING`](./CONTRIBUTING).
