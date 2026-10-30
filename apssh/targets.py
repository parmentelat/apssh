"""
the Targets class
"""

# we need an instance to add parser options, but at that point
# we do not yet have the values to initialize this object
# so it's kind of a 2-step init
# pylint: disable=attribute-defined-outside-init

import sys
from pathlib import Path
from collections import namedtuple

from .config import default_username

from .util import print_stderr
from .sshproxy import SshProxy
from .sshconfig import SshConfig
from .keys import import_private_key
from .config import local_config_dir

# note explicit-direct
# if we call apssh -t None->box -g gateway it means we want to
# to go direct to box and bypass gateway
# in that case we will use Endpoint(None, None) to describe the
# gateway part of the Hop2 instance that goes with the None->box target
Endpoint = namedtuple('Endpoint', ['hostname', 'username'])
Hop2 = namedtuple('Hop2', ['final', 'gateway'])


class Targets:                   # pylint: disable=too-many-instance-attributes
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

    def __init__(self):
        self.proxies = []

    def __iter__(self):
        return iter(self.proxies)


    def add_target_options(self, parser): # pylint: disable=missing-function-docstring
        parser.add_argument(
            "-t", "--target", dest='targets', action='append', default=[],
            help="""
            specify targets (additive); at least one is required

            a basic target can be either
            * hostname
            * username@hostname
            * gwuser@gwhost->username@hostname

            complex targets can be
            * a space- or comma- separated list of targets
            * the name of a file containing targets
            * the name of a directory containing files named after hostnames;
            see e.g. the --mark option
            """)
        parser.add_argument(
            "-l", "--login", default=None,
            help=f"""remote user name; when not specified, the user
            is taken from the ssh config if applicable,
            or else defaults to {default_username}""")
        parser.add_argument(
            "-g", "--gateway", default=None,
            help="""
            specify a gateway for 2-hops ssh
            - either hostname or username@hostname;
            takes precedence over any ProxyJump in the ssh config
            """)
        parser.add_argument(
            "-F", "--config-file", dest='ssh_config_file', default=None,
            help="""use this ssh client config file
            instead of ~/.ssh/config""")
        parser.add_argument(
            "--no-config", dest='use_ssh_config', action='store_false',
            default=True,
            help="""do not read any ssh config file; targets are then used
            as-is, without name, user, port, key or ProxyJump resolution""")
        parser.add_argument(
            "-x", "--exclude", dest='excludes', action='append', default=[],
            help="""
            like --target, but for specifying exclusions;
            for now no wildcard mechanism is supported here;
            also the order in which --target and --exclude options
            are mentioned does not matter;
            use --dry-run to only check for the list of applicable hosts
            """)


    # args is the output of a parser.parse_args()
    def init_from_args(self, args, private_keys, formatter):
        """
        actual initialization, once parser.parse_args has been called
        """
        self.args = args
        self.private_keys = private_keys
        self.formatter = formatter
        self.timeout = args.timeout
        self.debug = args.debug
        self.dry_run = args.dry_run
        self.ssh_config = SshConfig(args.ssh_config_file,
                                    enabled=args.use_ssh_config)
        if args.ssh_config_file and not self.ssh_config.path.exists():
            print_stderr(f"WARNING: ssh config file {args.ssh_config_file} not found")
        self._identity_keys = {}
        #

        self.gateway_endpoint = None
        if self.args.gateway:
            self.gateway_endpoint = self.parse_endpoint(self.args.gateway)


    # create an EndPoint (parse something like [username@]hostname)
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
            return Endpoint(target, self.args.login)

    # create a Hop2 (parse something like [[gwuser@]gwhostname->][username@]hostname)
    def parse_hop2(self, target):                       # pylint: disable=C0111
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
        return [x for commas in text.split() for x in commas.split(',')]


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
                return [Hop2(Endpoint(filename, self.args.login),
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


    def create_proxies(self):               # pylint: disable=too-many-branches
        """
        build the proxies associated with that set of targets
        """
        # a set of endpoints (disregard gateways in the exclusion lists)
        excludes = set()
        for exclude in self.args.excludes:
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
        for target in self.args.targets:
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

        # lazily create gateways
        # explicit-direct
        cache = {}

        def host_keys(resolved):
            """keys for IdentityFile entries of the ssh config, then the global ones"""
            keys = []
            for filename in resolved.identity_files:
                if filename not in self._identity_keys:
                    self._identity_keys[filename] = import_private_key(filename)
                if self._identity_keys[filename]:
                    keys.append(self._identity_keys[filename])
            if resolved.identities_only and keys:
                return keys
            return keys + list(self.private_keys)

        def create_proxy(label, resolved, user, port, gateway):
            """
            one SshProxy; label is what shows up in outputs,
            while the actual connection uses resolved.address
            """
            return SshProxy(
                label,
                address=resolved.address,
                username=user or resolved.user or default_username,
                port=port or resolved.port or 22,
                proxy_command=None if gateway else resolved.proxy_command,
                keys=host_keys(resolved),
                gateway=gateway,
                formatter=self.formatter,
                timeout=self.timeout, debug=self.debug)

        def gateway_from_chain(chain):
            """
            chain is a list of (resolved, user, port), outermost first;
            returns the innermost gateway, or None if chain is empty
            """
            gateway = None
            for resolved, user, port in chain:
                user = user or default_username
                key = (resolved.address, user, port or resolved.port, gateway)
                if key not in cache:
                    cache[key] = create_proxy(
                        resolved.alias, resolved, user, port, gateway)
                gateway = cache[key]
            return gateway

        def lazy_create_gateway(endpoint):
            hostname, username = endpoint
            # explicit-direct
            if hostname is None and username is None:
                return None
            resolved = self.ssh_config.resolve(hostname)
            chain = self.ssh_config.jump_chain(resolved)
            chain.append((resolved, username, None))
            return gateway_from_chain(chain)

        # create proxies
        self.proxies = []

        for hop2 in hop2_s:
            hostname, username = hop2.final
            resolved = self.ssh_config.resolve(hostname)
            if hop2.gateway:
                gateway = lazy_create_gateway(hop2.gateway)
            elif self.gateway_endpoint:
                gateway = lazy_create_gateway(self.gateway_endpoint)
            else:
                gateway = gateway_from_chain(self.ssh_config.jump_chain(resolved))

            self.proxies.append(
                create_proxy(hostname, resolved, username, None, gateway))

        if self.dry_run:
            print(f"========== {len(hop2_s)} hostnames selected"
                  f" ({actually_excluded} excluded):")
            def hop(proxy):
                port = f":{proxy.port}" if proxy.port != 22 else ""
                return f"{proxy.username}@{proxy.address}{port}"

            for proxy in self.proxies:
                chain, gateway = [hop(proxy)], proxy.gateway
                while gateway:
                    chain.insert(0, hop(gateway))
                    gateway = gateway.gateway
                line = f"{proxy.hostname} -> " + " -> ".join(chain)
                if proxy.proxy_command:
                    line += f"  (ProxyCommand: {proxy.proxy_command})"
                print(line)
            sys.exit(0)

        return self.proxies
