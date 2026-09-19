# Contributing to Alignment Engine

Thank you for your interest in contributing to the Alignment Engine! 

## Code of Conduct

Please be respectful and constructive in issues and pull requests.

## Development Workflow

1. Fork the repository.
2. Create a new branch for your feature or bugfix (`git checkout -b feature-name`).
3. Make your changes following the coding standards.
4. Run tests and ensure they pass.
5. Submit a Pull Request.

## Coding Standards

As mandated by our architecture:
1. **No Placeholders**: Never use `pass` or `# TODO` in production code. Ensure robust implementations.
2. **Type Safety**: Maintain strong typing across boundaries. Use Pydantic for Python and strict TS for Frontend.
3. **Tests**: Include unit tests for every new branch of logic. Coverage must remain above 90% for frontend and high for backend.
4. **Performance**: If modifying the `analyzer` or `trajectory_optimizer`, open a PR with detailed benchmarks.
