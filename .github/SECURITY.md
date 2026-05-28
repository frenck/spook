# Security policy

The full security policy of Spook is documented at
[spook.boo/security](https://spook.boo/security). This file mirrors the same
policy for GitHub's security policy detection.

So, you have found a security vulnerability in Spook? Please, be sure to
**responsibly** disclose it to us by
[reporting a vulnerability using GitHub's Security Advisory](https://github.com/frenck/spook/security/advisories/new).

**DO NOT MAKE A PUBLIC ISSUE FOR SECURITY VULNERABILITIES!**

For the sake of the security of our users, please do not make vulnerabilities
public without notifying us and giving us at least 90 days to release a fixed
version. We will do our best to respond to your report within 7 days and also to
keep you informed of the progress of our efforts to resolve the issue, but
understand that Spook, like many Open Source projects, is primarily a volunteer
project with no full-time resources. We may not be able to respond as quickly as
you would like due to other responsibilities.

If you are going to write about Spook's security, please get in touch, so we can
ensure that all claims are correct.

## Supported versions

We only accept reports against the latest stable and official version of Spook or
any versions beyond that currently in development. The latest version can be
found [here](https://github.com/frenck/spook/releases/latest).

We do not accept reports against forks of Spook.

## Non-qualifying vulnerabilities

We will not accept reports of vulnerabilities of the following types:

- Reports from automated tools or scanners.
- Theoretical attacks without proof of exploitability.
- Attacks that are the result of a third-party application or library (these
  should instead be reported to the library maintainers).
- Social engineering.
- Attacks involving physical access to a user's device, or involving a device or
  network that's already seriously compromised (like, man-in-the-middle).
- Attacks that require the user to install a malicious other Home Assistant
  integration or add-on.
- Attacks that the user can only perform on themselves.

## Severity scoring

If you are familiar with
[CVSS3.1](https://www.first.org/cvss/v3.1/specification-document), please provide
the vulnerability score in your report in the shape of a vector string. There's a
calculator [here](https://www.first.org/cvss/calculator/3.1). If you are unsure
how or unable to score a vulnerability, state that in your report, and we will
look into it.

If you intend to provide a score, please familiarize yourself with CVSS first (we
strongly recommend reading the
[Specification](https://www.first.org/cvss/v3.1/specification-document) and
[Scoring Guide](https://www.first.org/cvss/v3.1/user-guide#Scoring-Guide)), as
we will not accept reports that use it incorrectly.

## Public disclosure & CVE assignment

We will publish GitHub Security Advisories and through those, will also request
CVEs, for valid vulnerabilities that meet the following criteria:

- The vulnerability is in Spook itself, not a third-party library.
- The vulnerability is not already known to us.
- The vulnerability is not already known to the public.
- CVEs will only be requested for vulnerabilities with a severity of Medium or
  higher.

## Bounties

As a crowd-funded community project, Spook cannot offer bounties for security
vulnerabilities. However, if so desired, we will credit the discoverer of a
vulnerability in our release notes.
