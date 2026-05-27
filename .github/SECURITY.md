# Security policy

Spook takes security issues seriously. The full policy is documented at
[spook.boo/security](https://spook.boo/security).

## Reporting a vulnerability

Please report suspected vulnerabilities through GitHub's private vulnerability
reporting flow:

<https://github.com/frenck/spook/security/advisories/new>

Do not publish vulnerability details before there has been time to investigate
and release a fix.

## Supported versions

Spook follows the Home Assistant custom integration model. Security fixes are
made for the latest released version only.

| Version | Supported |
| ------- | --------- |
| Latest release | Yes |
| Older releases | No |

## Disclosure timeline

We aim to acknowledge valid reports within 7 days. Please allow at least 90 days
for investigation, mitigation, release, and coordinated disclosure unless there
is active exploitation or another clear reason to adjust that timeline.

## Out of scope

The following reports are generally out of scope for Spook itself:

- Issues in unsupported Spook versions.
- Issues that only affect unsupported Home Assistant or Python versions.
- Vulnerabilities in third-party dependencies, unless Spook uses them in a way
  that creates a Spook-specific security issue.
- Theoretical attacks without a practical proof of exploitability.

## More details

The project documentation contains the full policy, including severity scoring,
CVE handling, and bounty expectations:

<https://spook.boo/security>
