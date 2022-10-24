"""
the Targets class
"""

from pathlib import Path
from collections import namedtuple

from .util import print_stderr
from .sshproxy import SshProxy
from .config import local_config_dir

# note explicit-direct
# if we call apssh -t None->box -g gateway it means we want to
# to go direct to box and bypass gateway
# in that case we will use Endpoint(None, None) to describe the
# gateway part of the Hop2 instance that goes with the None->box target
Endpoint = namedtuple('Endpoint', ['hostname', 'username'])
Hop2 = namedtuple('Hop2', ['final', 'gateway'])


class Targets:
    """
    This internal class is in charge of dealing with the scope of a apssh session

    From the main CLI options, and notably --target --gateway --exclude and --login,
    this class can build a collection of the SshProxy (SshNode actually)
    instances that are targetted

    * in its most simple form, a target is just a hostname

    * when needed it can also be extended and use a syntax like this one
    gwuser@gateway->user@hostname
    which means reach account user on host hostname but in 2 hops, passing through
    account gwuser on gateway

    * there are also mechanisms that let define scopes in files (that contain targets)
    or directories (whose simple files represent targets)
    for deciding if a target is a hostname or a filename or a dirname, we simply search
    for a file or directory with that name, either from ., or if it is a relative filename
    it is also searched in ``~/.apssh``.

    this feature with directories is notably for use together
    with the ``--mark`` option, so that one can easily select
    reachable nodes only, or just as easily exclude failing nodes.


    """

    def __init__(self, target_strs, gateway_str, *, login, excludes,
                 private_keys, formatter,
                 timeout, debug, dry_run):
        self.target_strs = target_strs
        self.gateway_str = gateway_str
        self.login = login
        self.excludes = excludes
        self.private_keys = private_keys
        self.formatter = formatter
        self.timeout = timeout
        self.debug = debug
        self.dry_run = dry_run
        #
        self.proxies = []

        self.gateway_endpoint = None
        if gateway_str:
            self.gateway_endpoint = self.parse_endpoint(gateway_str)


    # create a EndPoint (parse something like username@hostname)
    # use the username if already present in the target,
    # otherwise the one specified with --login
    def parse_endpoint(self, target):                   # pylint: disable=C0111
        if target == "None":
            # explicit-direct
            # this is how we mark that there is an explicit choice
            # to go direct
            return Endpoint(None, None)
        try:
            username, hostname = target.split('@')
            return Endpoint(hostname, username)
        except ValueError:
            return Endpoint(target, self.login)

    # create a Hop2 (parse something like gwuser@gwhostname->username@hostname)
    def parse_hop2(self, target):
        left, middle, right = target.partition('->')
        if not middle:
            left, middle, right = target.partition('→')
        if not middle:
            return Hop2(self.parse_endpoint(target), None)
        else:
            return Hop2(self.parse_endpoint(right), self.parse_endpoint(left))


    @staticmethod
    def split(text):
        """
        split along spaces or commas
        """
        return [x for commas in text.split(' ') for x in commas.split(',')]


    # returns a valid Path object, or None
    @staticmethod
    def locate_file(file):                              # pylint: disable=C0111
        path = Path(file)
        if path.exists():
            return path
        if not path.is_absolute():
            in_home = local_config_dir / path
            # somehow pylints figured in_home is a PurePath
            if in_home.exists():                        # pylint: disable=E1101
                return in_home
        return None


    def analyze_target(self, target):
        """
        This function is used to guess the meaning of all the targets passed
        to the ``apssh`` command through its ``-t/--target`` option.

        Parameters:
          target: a string passed to ``--target``

        Returns:
          a list of Hop2 tuples
          an empty list means something went wrong, and the target
          could not be resolved

          for example, this is the case when the file exists
          but cannot be parsed - in which case it is probably not a hostname.

        """
        targets = []
        # located is a Path object - or None
        located = self.locate_file(target)
        if located:
            if located.is_dir():
                # directory
                onlyfiles = [str(f.name) for f in located.iterdir() if f.is_file()]
                return [Hop2(Endpoint(filename, self.login),
                             self.gateway_endpoint)
                        for filename in onlyfiles]
            else:
                # file
                try:
                    with located.open() as inputfile: # pylint: disable=unspecified-encoding
                        for line in inputfile:
                            line = line.strip()
                            if line.startswith('#'):
                                continue
                            line = line.split()
                            for token in line:
                                targets += token.split()
                    return [self.parse_hop2(target) for target in targets]
                except FileNotFoundError:
                    return []
                except Exception as exc:                     # pylint: disable=broad-except
                    print_stderr(f"Unexpected exception when parsing file {target}, {exc}")
                    if self.debug:
                        import traceback          # pylint: disable=import-outside-toplevel
                        traceback.print_exc()
                    return []
        else:
            # string
            return [self.parse_hop2(x) for x in self.split(target)]


    def create_proxies(self):                           # pylint: disable=C0111
        # a set of endpoints (disregard gateways in the exclusion lists)
        excludes = set()
        for exclude in self.excludes:
            excluded_endpoints = {hop2.final for hop2 in self.analyze_target(exclude)}
            excludes.update(excluded_endpoints)
        if self.dry_run:
            print(f"========== {len(excludes)} excludes found:")
            for exclude in excludes:
                print(exclude)

        # gather targets as mentioned in -t -x args
        hop2_s = []
        actually_excluded = 0
        # read input file(s)
        for target in self.target_strs:
            target_hop2_s = self.analyze_target(target)
            if not target_hop2_s:
                print(f"WARNING: ignoring target {target}")
                continue
            for hop2 in target_hop2_s:
                if hop2.final not in excludes:
                    hop2_s.append(hop2)
                else:
                    actually_excluded += 1
        if not hop2_s:
            raise ValueError("empty targets")

        if self.dry_run:
            print(f"========== {len(hop2_s)} hostnames selected"
                  f" ({actually_excluded} excluded):")
            for hop2 in hop2_s:
                print(hop2)
            exit(0)

        # lazily create gateways
        # explicit-direct
        cache = {}

        def lazy_create_gateway(endpoint):
            hostname, username = endpoint
            # explicit-direct
            if hostname is None and username is None:
                return None
            cached = cache.get((hostname, username), None)
            if cached:
                return cached
            gateway = SshProxy(
                hostname=hostname, username=username,
                keys=self.private_keys, formatter=self.formatter,
                timeout=self.timeout, debug=self.debug)
            cache[(hostname, username)] = gateway
            return gateway


        # create proxies
        self.proxies = []

        for hop2 in hop2_s:
            # print(f"dealing with {hop2=}")
            hostname, username = hop2.final
            gateway = None
            if hop2.gateway:
                gateway = lazy_create_gateway(hop2.gateway)
            elif self.gateway_endpoint:
                gateway = lazy_create_gateway(self.gateway_endpoint)
            # xxx still buggy at this point:
            # if there is a default gateway provided with -g
            # and then one of the targets actually wants to override this
            # and use a direct connection, then we're screwed

            self.proxies.append(
                SshProxy(hostname, username=username,
                         keys=self.private_keys,
                         gateway=gateway,
                         formatter=self.formatter,
                         timeout=self.timeout,
                         debug=self.debug))

        return self.proxies
