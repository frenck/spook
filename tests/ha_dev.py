"""Let the test harness load on Home Assistant's development branch.

Home Assistant 2026.11 swaps httpx for httpx2 the moment it is imported,
and refuses when httpx is already loaded. The test harness of a released
Home Assistant imports respx, and so httpx, before it imports Home Assistant.
Loaded first with `-p tests.ha_dev`, this does the swap before either of them.
On a released Home Assistant there is no httpx2, and nothing to do.
"""

from contextlib import suppress

with suppress(ImportError):
    import httpx2

    httpx2.alias_httpx()
