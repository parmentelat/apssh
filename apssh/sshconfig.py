"""
Resolving target names through an OpenSSH-style client config file
(by default ``~/.ssh/config``), so that short names, users, ports,
identity files and ``ProxyJump`` / ``ProxyCommand`` are honoured.

The parsing itself is delegated to asyncssh, so semantics
(``Host`` / ``Match``, ``Include``, ``%h`` tokens, first-value-wins)
are those of ``asyncssh.connect()``.
"""

import getpass
from dataclasses import dataclass, field
from pathlib import Path

from asyncssh.config import SSHClientConfig

DEFAULT_CONFIG_FILE = Path.home() / ".ssh" / "config"

# guard against ProxyJump loops
MAX_HOPS = 8


@dataclass(frozen=True)
class Hop:
    """
    One ProxyJump hop, as written in the config: ``[user@]host[:port]``.
    Fields left to None are to be filled from the config entry for ``host``.
    """
    host: str
    user: str = None
    port: int = None


@dataclass
class ResolvedHost:                              # pylint: disable=r0902
    """
    What the ssh config says about one name.
    All fields but ``alias`` and ``address`` may be None / empty.
    """
    alias: str
    address: str
    user: str = None
    port: int = None
    identity_files: list = field(default_factory=list)
    identities_only: bool = False
    proxy_jump: list = field(default_factory=list)       # of Hop
    proxy_command: str = None


def parse_hop(text):
    """
    ``[user@]host[:port]`` -> Hop
    """
    user = None
    if '@' in text:
        user, text = text.rsplit('@', 1)
    port = None
    if text.count(':') == 1:
        text, port_text = text.split(':')
        port = int(port_text)
    return Hop(text, user, port)


class SshConfig:
    """
    Lookup facility on top of an ssh client config file.

    Parameters:
      path: the config file; defaults to ``~/.ssh/config``
      enabled: when False, :meth:`resolve` returns the bare name
        untouched, i.e. the pre-config behaviour of apssh
    """

    def __init__(self, path=None, enabled=True):
        self.path = Path(path).expanduser() if path else DEFAULT_CONFIG_FILE
        self.enabled = enabled and self.path.exists()
        self._local_user = getpass.getuser()
        self._cache = {}

    def resolve(self, alias):
        """
        Returns:
          a :class:`ResolvedHost`
        """
        if alias in self._cache:
            return self._cache[alias]
        if not self.enabled:
            resolved = ResolvedHost(alias, alias)
        else:
            resolved = self._lookup(alias)
        self._cache[alias] = resolved
        return resolved

    def _lookup(self, alias):
        config = SSHClientConfig.load(
            None, self.path, False, False, False,
            self._local_user, (), alias, ())
        jump = config.get('ProxyJump')
        hops = []
        if jump and str(jump).lower() != 'none':
            hops = [parse_hop(h) for h in str(jump).split(',')]
        identities = [str(Path(f).expanduser())
                      for f in (config.get('IdentityFile') or [])]
        return ResolvedHost(
            alias=alias,
            address=config.get('Hostname') or alias,
            user=config.get('User'),
            port=config.get('Port'),
            identity_files=identities,
            identities_only=bool(config.get('IdentitiesOnly')),
            proxy_jump=hops,
            proxy_command=config.get('ProxyCommand') or None,
        )

    def jump_chain(self, resolved):
        """
        The ProxyJump hops of a resolved host, outermost first, each one
        resolved in turn through the config (so that a hop can be a ``Host``
        alias, and can itself be behind jumps).

        Returns:
          list of (ResolvedHost, user, port) – with user and port taking the
          explicit values of the Hop if any, else the config's
        """
        return self._nested(resolved, depth=0)

    def _nested(self, resolved, depth):
        if depth > MAX_HOPS:
            raise ValueError(
                f"ssh config: ProxyJump chain too deep (loop?) at {resolved.alias}")
        result = []
        for hop in resolved.proxy_jump:
            sub = self.resolve(hop.host)
            result += self._nested(sub, depth + 1)
            result.append((sub, hop.user or sub.user, hop.port or sub.port))
        return result
