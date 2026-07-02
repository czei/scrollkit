"""
System utilities for hardware and system operations.
Copyright (c) 2024-2026 Michael Czeiszperger

Time-setting is deliberately resilient rather than precise: for these displays
"close enough" is fine, but the clock must get set even on hostile networks.
``set_system_clock`` cascades through independent sources:

  1. NTP across several reliable servers (the gold standard) — but a single shot
     at pool.ntp.org is unreliable (random dead/slow pool members) and NTP needs
     outbound UDP/123, which guest wifi / captive portals / some ISPs block.
  2. The HTTP ``Date`` response header from a reachable host — works wherever
     HTTPS works, i.e. exactly the networks that block NTP. Accurate to ~1s.
"""
import sys  # noqa: F401  (kept for parity with the embedded build)
import time
import asyncio  # noqa: F401

# Import hardware-specific modules or mock them
try:
    import rtc
    import microcontroller  # noqa: F401
    HAS_HARDWARE = True
except ModuleNotFoundError:
    # Mocking the unavailable modules in non-embedded environments
    from adafruit_datetime import datetime

    class rtc:
        class RTC:
            def __init__(self):
                self.datetime = datetime()

    HAS_HARDWARE = False

# Try to import adafruit_ntp, with fallback if not available
try:
    import adafruit_ntp
    HAS_NTP = True
except Exception:
    HAS_NTP = False


# NTP servers tried in order. A single query to pool.ntp.org is unreliable in the
# field: it resolves to a RANDOM pool member, many of which are dead, slow
# (10-20s), or rate-limiting ("aggressive denial"). So we lead with single-operator
# anycast servers that don't have that problem and fall through to the pool last.
# Override via the `servers` argument.
DEFAULT_NTP_SERVERS = ("time.cloudflare.com", "time.google.com", "pool.ntp.org")

# HTTPS hosts to read the 'Date' response header from when NTP is unreachable.
# Any HTTPS host returns a Date header; these are highly available. If your app
# already fetches from a reliable host, pass it via `http_date_hosts` to avoid an
# extra dependency.
DEFAULT_HTTP_DATE_HOSTS = ("https://time.cloudflare.com", "https://www.google.com")

_MONTHS = {"Jan": 1, "Feb": 2, "Mar": 3, "Apr": 4, "May": 5, "Jun": 6,
           "Jul": 7, "Aug": 8, "Sep": 9, "Oct": 10, "Nov": 11, "Dec": 12}


__all__ = ['set_system_clock', 'set_system_clock_ntp', 'DEFAULT_NTP_SERVERS', 'DEFAULT_HTTP_DATE_HOSTS']

async def set_system_clock_ntp(socket_pool, tz_offset=None, servers=None,
                               socket_timeout=5):
    """
    Set device time using NTP, trying several servers until one responds.

    NTP is the right technique for these devices, but a single shot at
    pool.ntp.org fails often in the field (random dead/slow pool members). This
    tries a list of independent, reliable servers and uses the first that answers,
    with a short per-server timeout so a dead server fails fast.

    Args:
        socket_pool: SocketPool instance for NTP (must have getaddrinfo).
        tz_offset: Timezone offset in hours (defaults to US Eastern, -5).
        servers: Iterable of NTP server hostnames to try in order
            (defaults to DEFAULT_NTP_SERVERS).
        socket_timeout: Per-server timeout in seconds (default 5).

    Returns:
        True if any server set the clock, False if every server failed.
    """
    from scrollkit.utils.error_handler import ErrorHandler
    logger = ErrorHandler("error_log")

    if not HAS_NTP or not HAS_HARDWARE:
        logger.info("NTP module not available or hardware not supported")
        return False

    # Validate socket_pool is a proper socket pool object
    if socket_pool is None or not hasattr(socket_pool, 'getaddrinfo'):
        logger.error(None, "Invalid socket pool provided for NTP, socket pool must have getaddrinfo")
        return False

    # Timezone offset: default to EST (-5 hours)
    if tz_offset is None:
        tz_offset = -5

    for server in (servers if servers is not None else DEFAULT_NTP_SERVERS):
        try:
            logger.info(f"Getting time from NTP server {server} (tz_offset {tz_offset})")
            ntp = adafruit_ntp.NTP(socket_pool, server=server, tz_offset=tz_offset,
                                   socket_timeout=socket_timeout)
            current_time = ntp.datetime

            # Convert to a tuple for the RTC module
            datetime_tuple = (
                current_time.tm_year,    # Year
                current_time.tm_mon,     # Month
                current_time.tm_mday,    # Day
                current_time.tm_hour,    # Hour
                current_time.tm_min,     # Minute
                current_time.tm_sec,     # Second
                current_time.tm_wday,    # Day of week (0-6)
                -1,                      # Day of year (not necessary)
                -1                       # DST flag (not necessary)
            )

            rtc.RTC().datetime = datetime_tuple
            logger.info(f"System clock set to {datetime_tuple} via NTP ({server})")
            return True

        except Exception as e:
            logger.error(e, f"NTP server {server} failed, trying next")
            # Reclaim the failed NTP object (and any socket/SSL allocations it
            # held) before trying the next server. On the RAM-constrained ESP32-S3
            # this curbs heap fragmentation across the failover loop — cheap
            # insurance on a once-at-boot path. No-op cost on desktop.
            import gc
            gc.collect()
            continue

    logger.error(None, "All NTP servers failed to respond")
    return False


def _parse_http_date(date_header):
    """Parse an RFC 1123 HTTP 'Date' header (always UTC) into a UTC time tuple.

    e.g. 'Wed, 21 Oct 2025 07:28:00 GMT' -> (2025, 10, 21, 7, 28, 0).
    Returns None if it can't be parsed.
    """
    try:
        parts = date_header.split(" ")
        # ['Wed,', '21', 'Oct', '2025', '07:28:00', 'GMT']
        day = int(parts[1])
        month = _MONTHS[parts[2]]
        year = int(parts[3])
        hour, minute, second = (int(x) for x in parts[4].split(":"))
        return (year, month, day, hour, minute, second)
    except (ValueError, KeyError, IndexError):
        return None


def _utc_to_local_tuple(utc, tz_offset):
    """Shift a (Y, M, D, h, m, s) UTC tuple by tz_offset hours into an RTC tuple.

    Uses time.mktime/localtime, which on CircuitPython operate in UTC (no timezone
    database), so this yields the correct local wall-clock for the given offset and
    normalizes any day/month rollover. Returns None on overflow/parse error.
    """
    try:
        year, month, day, hour, minute, second = utc
        epoch = time.mktime((year, month, day, hour, minute, second, 0, -1, -1))
        lt = time.localtime(epoch + int(tz_offset * 3600))
        return (lt.tm_year, lt.tm_mon, lt.tm_mday, lt.tm_hour,
                lt.tm_min, lt.tm_sec, lt.tm_wday, -1, -1)
    except (OverflowError, OSError, ValueError):
        return None


async def _set_clock_from_http_date(http_client, tz_offset, hosts, logger):
    """Set the RTC from the HTTP 'Date' response header of a reachable host.

    Works on networks that block NTP (UDP/123) but allow HTTPS. ~1s accurate.
    Returns the datetime tuple that was set, or None if no host answered.
    """
    for url in hosts:
        try:
            resp = await http_client.get(url)
            headers = getattr(resp, "headers", None) or {}
            date_hdr = headers.get("Date") or headers.get("date")
            if not date_hdr:
                logger.info(f"No Date header from {url}")
                continue
            utc = _parse_http_date(date_hdr)
            if utc is None:
                logger.error(None, f"Could not parse Date header from {url}: {date_hdr}")
                continue
            dt = _utc_to_local_tuple(utc, tz_offset)
            if dt is None:
                continue
            if HAS_HARDWARE:
                rtc.RTC().datetime = dt
            logger.info(f"System clock set to {dt} via HTTP Date header ({url})")
            return dt
        except Exception as e:
            logger.error(e, f"HTTP time from {url} failed")
            continue
    return None


async def set_system_clock(http_client, socket_pool=None, tz_offset=None,
                           http_date_hosts=None):
    """
    Set the device clock as reliably as possible (accuracy is not critical).

    Cascades through independent sources, first that answers wins:
      1. NTP across several reliable servers (needs UDP/123 open).
      2. The HTTP 'Date' response header (works where NTP is blocked).

    Args:
        http_client: HTTP client used for the Date-header fallback.
        socket_pool: Optional socket pool for NTP.
        tz_offset: Timezone offset in hours (defaults to US Eastern, -5).
        http_date_hosts: Optional list of HTTPS hosts for the Date-header
            fallback (defaults to DEFAULT_HTTP_DATE_HOSTS). Prefer a host you
            already fetch from.

    Returns:
        The datetime tuple that was set, or None if every source failed.
    """
    from scrollkit.utils.error_handler import ErrorHandler
    logger = ErrorHandler("error_log")

    if tz_offset is None:
        tz_offset = -5

    # 1. NTP (multi-server failover) — accurate, but needs UDP/123 open.
    if HAS_NTP and socket_pool is not None:
        logger.info("Setting time via NTP...")
        try:
            if await set_system_clock_ntp(socket_pool, tz_offset=tz_offset):
                logger.info("System clock set via NTP")
                return rtc.RTC().datetime
        except Exception as e:
            logger.error(e, "NTP failed; falling back to the HTTP Date header")

    # 2. HTTP 'Date' header — survives networks that block NTP.
    logger.info("Setting time via the HTTP Date header...")
    hosts = http_date_hosts if http_date_hosts is not None else DEFAULT_HTTP_DATE_HOSTS
    dt = await _set_clock_from_http_date(http_client, tz_offset, hosts, logger)
    if dt is None:
        logger.error(None, "Failed to set system clock - no time source reachable "
                           "(NTP and HTTP Date both failed)")
    return dt
