"""Spook - Your homie. Remembering what somebody said to leave alone."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING

from homeassistant.core import callback
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.storage import Store
from homeassistant.util.hass_dict import HassKey

from .const import DOMAIN, LOGGER

if TYPE_CHECKING:
    from collections.abc import Iterable

    from homeassistant.core import CALLBACK_TYPE, Event, HomeAssistant

STORAGE_KEY = f"{DOMAIN}.dismissals"
STORAGE_VERSION = 1

# Not much rides on writing this the instant it changes, and pressing ignore
# on a handful of issues in a row is one write rather than a handful.
_SAVE_DELAY = 5

DATA_DISMISSALS: HassKey[Dismissals] = HassKey("spook_dismissals")

# Where the orphaned statistics repair kept these before there was one place
# for all of them. Its single issue is filed under its own name.
_LEGACY_KEPT_STATISTICS_KEY = f"{DOMAIN}.kept_statistics"
_LEGACY_KEPT_STATISTICS_VERSION = 1
_ORPHANED_STATISTICS = "orphaned_statistics"


@dataclass(frozen=True)
class _Offered:
    """What an issue Spook raised was about."""

    repair: str
    owner: str
    references: frozenset[str]


def _read_dismissed(stored: object) -> dict[str, dict[str, set[str]]]:
    """Return what was ignored, read back from disk, minus what makes no sense.

    The file can be edited by hand, or come back from an old backup. Whatever
    is in it, Spook sets up.
    """
    if not isinstance(stored, Mapping):
        if stored is not None:
            LOGGER.debug("Spook could not read its dismissals, starting over")
        return {}

    dismissed: dict[str, dict[str, set[str]]] = {}
    dropped = 0
    for repair, owners in stored.items():
        if not isinstance(repair, str) or not isinstance(owners, Mapping):
            dropped += 1
            continue

        dismissed[repair] = {}
        for owner, references in owners.items():
            # A string would pass for a list of its letters.
            if not isinstance(owner, str) or not isinstance(references, list):
                dropped += 1
                continue

            dismissed[repair][owner] = {
                reference for reference in references if isinstance(reference, str)
            }

    if dropped:
        LOGGER.debug("Spook dropped %s dismissals it could not read", dropped)

    return dismissed


class Dismissals:
    """The findings somebody ignored, per repair and per thing they were in.

    Home Assistant remembers that an issue was ignored, but it remembers it on
    the issue, and only for as long as that issue exists. Spook files an issue
    under its findings, so one finding more or less is a different issue, and
    an issue that goes for a moment is gone with its mark: an automation being
    reloaded, a dashboard that would not load, a restart before everything has
    arrived. Every one of those put an ignored finding back up as new. #1699,
    #1702.

    So the decision is written down here instead, where it outlasts the issue
    it was made on.
    """

    def __init__(
        self,
        hass: HomeAssistant,
        store: Store[dict[str, dict[str, list[str]]]] | None = None,
        dismissed: dict[str, dict[str, list[str]]] | None = None,
    ) -> None:
        """Hold what was loaded."""
        self._hass = hass
        self._store = store
        self._dismissed = _read_dismissed(dismissed)
        self._offered: dict[str, _Offered] = {}

        # Which issues are ignored right now, so that a change can be told
        # from an update. Home Assistant says "update" for both somebody
        # ignoring an issue and a dashboard being renamed in its text.
        self._ignored = {
            issue_id
            for (domain, issue_id), issue in ir.async_get(hass).issues.items()
            if domain == DOMAIN and issue.dismissed_version is not None
        }

        # Issues somebody stopped ignoring before Spook had said again what
        # they were about, as happens in the minutes after a start. Taken
        # back for real once it does.
        self._taken_back: set[str] = set()

    @property
    def is_written_down(self) -> bool:
        """Return whether this is the copy that goes to disk."""
        return self._store is not None

    @callback
    def async_dismissed(self, repair: str, owner: str) -> set[str]:
        """Return what somebody ignored in this one, for this repair."""
        return set(self._dismissed.get(repair, {}).get(owner, ()))

    @callback
    def async_offer(
        self,
        issue_id: str,
        repair: str,
        owner: str,
        references: Iterable[str],
    ) -> None:
        """Remember what an issue is about, so ignoring it can be written down."""
        self._offered[issue_id] = _Offered(repair, owner, frozenset(references))

        if issue_id in self._taken_back:
            self._taken_back.discard(issue_id)
            self.async_undismiss_offered(issue_id)

    @callback
    def async_dismiss_offered(self, issue_id: str) -> None:
        """Write down that the findings of this issue are to be left alone."""
        if (offered := self._offered.get(issue_id)) is None:
            return

        self.async_dismiss(offered.repair, offered.owner, offered.references)

    @callback
    def async_dismiss(
        self,
        repair: str,
        owner: str,
        references: Iterable[str],
    ) -> None:
        """Write down that these findings are to be left alone."""
        references = set(references)
        dismissed = self._dismissed.setdefault(repair, {}).setdefault(owner, set())
        if references <= dismissed:
            return

        dismissed |= references
        self._async_schedule_save()

    @callback
    def async_undismiss_offered(self, issue_id: str) -> None:
        """Take back ignoring the findings of this issue."""
        if (offered := self._offered.get(issue_id)) is None:
            return

        owners = self._dismissed.get(offered.repair, {})
        if not (dismissed := owners.get(offered.owner)) or not (
            offered.references & dismissed
        ):
            return

        dismissed -= offered.references
        if not dismissed:
            del owners[offered.owner]
        self._async_schedule_save()

    @callback
    def async_issue_registry_updated(
        self,
        event: Event[ir.EventIssueRegistryUpdatedData],
    ) -> None:
        """Follow somebody ignoring an issue, or taking that back.

        Only a change in whether it is ignored counts. Any other update is
        Spook rewriting the text, and reading that as somebody's choice would
        throw away what they ignored the first time a name in it changed.
        """
        if event.data["domain"] != DOMAIN:
            return

        issue_id = event.data["issue_id"]
        if event.data["action"] == "remove":
            self._ignored.discard(issue_id)
            return

        if (
            issue := ir.async_get(self._hass).async_get_issue(DOMAIN, issue_id)
        ) is None:
            return

        ignored = issue.dismissed_version is not None
        if ignored == (issue_id in self._ignored):
            return

        if ignored:
            self._ignored.add(issue_id)
            self.async_dismiss_offered(issue_id)
            return

        self._ignored.discard(issue_id)
        if issue_id in self._offered:
            self.async_undismiss_offered(issue_id)
        else:
            self._taken_back.add(issue_id)

    async def async_remove(self) -> None:
        """Remove what is on disk, and never write it again.

        A save still waiting would put the file back, a few seconds later or
        on the way down. Removing through the same store calls that off.
        """
        store, self._store = self._store, None
        if store is None:
            return

        # Saving waits for a write that is under way, and leaves none behind.
        # Not every Home Assistant that Spook runs on waits for one before it
        # removes the file, and a write landing after would put the file back.
        await store.async_save(self._data_to_save())
        await store.async_remove()

    async def async_write_now(self) -> None:
        """Write it down without waiting."""
        if self._store is not None:
            await self._store.async_save(self._data_to_save())

    @callback
    def _async_schedule_save(self) -> None:
        """Write it down, soon."""
        if self._store is not None:
            self._store.async_delay_save(self._data_to_save, _SAVE_DELAY)

    @callback
    def _data_to_save(self) -> dict[str, dict[str, list[str]]]:
        """Return what goes on disk."""
        return {
            repair: {owner: sorted(references) for owner, references in owners.items()}
            for repair, owners in self._dismissed.items()
            if owners
        }


@callback
def async_get_dismissals(hass: HomeAssistant) -> Dismissals:
    """Return the dismissals, or an empty set that is never written down.

    The empty set is for a repair asked to look without Spook having been set
    up around it, which is a test and not a house.
    """
    if (dismissals := hass.data.get(DATA_DISMISSALS)) is None:
        dismissals = hass.data[DATA_DISMISSALS] = Dismissals(hass)

    return dismissals


async def _async_take_over_kept_statistics(
    hass: HomeAssistant,
    dismissals: Dismissals,
) -> None:
    """Carry over the statistics kept the way the orphaned statistics repair used to.

    It wrote them down in a store of its own, and then let the issue go, so
    nothing but that file still knows somebody said to keep them.
    """
    legacy: Store[dict[str, list[str]]] = Store(
        hass, _LEGACY_KEPT_STATISTICS_VERSION, _LEGACY_KEPT_STATISTICS_KEY
    )
    if (stored := await legacy.async_load()) is None:
        return

    # Damaged, it holds nothing to carry over, and goes like an empty one.
    listed = stored.get("statistic_ids") if isinstance(stored, Mapping) else None
    if not isinstance(listed, list):
        listed = []

    statistic_ids = {
        statistic_id for statistic_id in listed if isinstance(statistic_id, str)
    }
    if statistic_ids:
        dismissals.async_dismiss(
            _ORPHANED_STATISTICS, _ORPHANED_STATISTICS, statistic_ids
        )

        # On disk before the old file goes, so there is no moment where
        # neither holds it. Home Assistant logs a failed write rather than
        # raising it, so what landed is read back rather than assumed, and
        # the old file stays for another try if it is not all there.
        await dismissals.async_write_now()
        written = await Store[dict[str, dict[str, list[str]]]](
            hass, STORAGE_VERSION, STORAGE_KEY
        ).async_load()
        landed = _read_dismissed(written).get(_ORPHANED_STATISTICS, {})
        if not statistic_ids <= landed.get(_ORPHANED_STATISTICS, set()):
            return

    await legacy.async_remove()


async def async_setup_dismissals(hass: HomeAssistant) -> CALLBACK_TYPE:
    """Load what was ignored before, and follow what gets ignored from now on.

    Before any repair looks, because the first thing a repair does with a
    finding is ask whether somebody already said to leave it alone.

    Loaded once and then kept, reloads included. Writing is put off for a few
    seconds, and a reload inside that window that read the disk again would
    start from before the latest ignore. Worse, the old and the new copy
    would each write their own idea of it later, and whichever went last
    would quietly throw away the other's.
    """
    dismissals = hass.data.get(DATA_DISMISSALS)
    if dismissals is None or not dismissals.is_written_down:
        store: Store[dict[str, dict[str, list[str]]]] = Store(
            hass, STORAGE_VERSION, STORAGE_KEY
        )
        dismissals = hass.data[DATA_DISMISSALS] = Dismissals(
            hass, store, await store.async_load()
        )
        await _async_take_over_kept_statistics(hass, dismissals)

    return hass.bus.async_listen(
        ir.EVENT_REPAIRS_ISSUE_REGISTRY_UPDATED,
        dismissals.async_issue_registry_updated,
    )


async def async_remove_dismissals(hass: HomeAssistant) -> None:
    """Remove what was ignored, on disk too, for Spook being removed.

    Out of `hass.data` as well, so Spook added again in the same run starts
    from nothing rather than from what was kept across reloads.
    """
    # Carried over at the next setup otherwise, Spook added again or not.
    await Store(
        hass, _LEGACY_KEPT_STATISTICS_VERSION, _LEGACY_KEPT_STATISTICS_KEY
    ).async_remove()

    dismissals = hass.data.pop(DATA_DISMISSALS, None)
    if dismissals is not None and dismissals.is_written_down:
        await dismissals.async_remove()
        return

    # Not loaded in this run, like Spook disabled before the restart. The
    # file is still there.
    await Store(hass, STORAGE_VERSION, STORAGE_KEY).async_remove()
