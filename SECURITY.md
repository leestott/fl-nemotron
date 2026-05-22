# Security Policy

## Supported Versions

This project is currently maintained on the main branch.

## Reporting a Vulnerability

Please do not open public issues for security vulnerabilities.

Report security concerns privately to the maintainer with:
- A clear description of the issue
- Steps to reproduce
- Potential impact
- Any suggested remediation

If contact details are not yet published for this repository, open a minimal issue requesting a private contact channel and avoid including exploit details.

## Security Practices in This Repository

- Secrets are managed via environment files and .env is gitignored.
- The application is designed for local execution and does not require cloud API keys.
- Generated artifacts and local logs should not be committed.

## Disclosure Process

After triage, fixes will be prioritized based on severity and a coordinated disclosure timeline will be used where appropriate.
