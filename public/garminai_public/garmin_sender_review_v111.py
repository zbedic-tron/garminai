"""v1.1.1 offline-only source attribution review (not a live authenticator).

The partner-provided IP ranges are CONFIDENTIAL and are intentionally not
committed to the repository. Socket addresses on Render are proxy addresses;
X-Forwarded-For and CF-Connecting-IP are NOT self-authenticating. This module
NEVER returns an authorization decision usable to enable real push delivery.
"""
from __future__ import annotations

import ipaddress
from dataclasses import dataclass
from typing import Iterable

PROXY_IP_HEADERS = frozenset({
    'x-forwarded-for', 'x-real-ip', 'forwarded', 'cf-connecting-ip',
    'true-client-ip',
})

@dataclass(frozen=True)
class SourceReview:
    observed_peer: str | None
    matches_reference_range: bool
    proxy_headers_present: bool
    sender_authenticated: bool
    reason: str


def review_asgi_source(scope: dict, headers: Iterable[tuple[bytes, bytes]],
                       reference_ranges: Iterable[str] = ()) -> SourceReview:
    """Review *socket peer* only; never trust client-controlled forwarded IPs.

    A CIDR match is not sender authentication. A trusted ingress contract and
    provenance validation are necessary before integrating any live handler.
    """
    peer = scope.get('client') if isinstance(scope, dict) else None
    names = set()
    for key, value in headers:
        if not isinstance(key, bytes) or not isinstance(value, bytes):
            raise ValueError('Invalid header pair')
        names.add(key.decode('ascii', 'ignore').lower())
    via_proxy = bool(names & PROXY_IP_HEADERS)
    try:
        addr = ipaddress.ip_address(peer[0]) if isinstance(peer, (tuple, list)) and peer else None
    except ValueError:
        addr = None
    # CIDRs are injected locally, never published in repository source files.
    matches = bool(addr is not None and any(addr in ipaddress.ip_network(net, strict=True)
                                             for net in reference_ranges))
    reason = ('NO_VALID_SOCKET_PEER' if addr is None else
              'PROXY_PROVENANCE_UNVERIFIED' if via_proxy else
              'SOCKET_CIDR_MATCH_IS_NOT_AUTHENTICATION' if matches else
              'SOCKET_PEER_NOT_IN_REFERENCE_RANGES')
    return SourceReview(str(addr) if addr is not None else None,
                        matches, via_proxy, False, reason)


def offline_acknowledgement_candidate(*, verified_ingress: bool,
                                      verified_owner: bool,
                                      durable_commit: bool,
                                      payload_validated: bool) -> int:
    """Model HTTP ACK preconditions ONLY. Never wired into public routes.

    200 implies durable *enqueue*, not full downstream activity processing.
    An exception or rolled back transaction may never produce a success ACK.
    """
    return 200 if all(x is True for x in (verified_ingress, verified_owner,
                                         durable_commit, payload_validated)) else 503
