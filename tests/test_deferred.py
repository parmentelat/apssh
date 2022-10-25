import unittest

from asynciojobs import Scheduler, Sequence

from apssh import (
    SshNode, SshJob, Run, Service,
    CaptureFormatter, TerminalFormatter,
    Deferred, Variables, Capture
)

from .util import localuser, localhostname

class Tests(unittest.TestCase):

    def check_expansion(self, *deferred_expected_s):
        s = Scheduler()
        formatters = {}
        for deferred, _ in deferred_expected_s:
            formatters[deferred] = f = CaptureFormatter()
            f.start_capture()
            n = SshNode(localhostname(), username=localuser(), formatter=f)
            s.add( SshJob( node=n, commands=Run(deferred) ))
        s.run()
        for deferred, expected in deferred_expected_s:
            captured = formatters[deferred].get_capture()
            self.assertEqual(captured, expected)


    def test_deferred_1(self):
        "the ability of using a variable"

        env = Variables()
        env.fetched = 'a simple variable'
        # Warning this is a jinja template -- NOT an f-string !!
        deferred = Deferred("echo fetched = {{fetched}}", env)
        expected = f"fetched = a simple variable\n"
        self.check_expansion((deferred, expected))

    def test_deferred_2(self):
        "the ability of operations"

        env = Variables()
        env.x1 = 1
        env.x2 = 2.0
        # Warning this is a jinja template -- NOT an f-string !!
        d1 = Deferred("echo x1 = {{x1}}", env)
        e1 = f"x1 = 1\n"
        d2 = Deferred("echo x2 = {{x2}}", env)
        e2 = f"x2 = 2.0\n"
        d3 = Deferred("echo sum = {{x1+x2}}", env)
        e3 = f"sum = 3.0\n"
        self.check_expansion(
            (d1, e1), (d2, e2), (d3, e3))

    def test_deferred_chain(self):
        """
        one command computes a string that gets passed to another one

        this is analogous to

            run1=$(ssh localhost echo from-first-run)
            final=$(ssh localhost echo ${run1})

        the 'final' variable is only needed
        for checking everything went well
        """

        s = Scheduler()
        env = Variables()

        n = SshNode(localhostname(), username=localuser())
        Sequence(
            SshJob(n,
                   commands=Run("echo from-first-run",
                                capture=Capture('run1', env))),
            SshJob(n,
                   commands=Run(Deferred("echo {{run1}}", env),
                                capture=Capture('final', env))),
            scheduler=s)

        s.run()

        #print(f"env={env}")
        obtained = env.final
        expected = "from-first-run"
        self.assertEqual(obtained, expected)


    def test_deferred_service(self):
        """
        a service can be defined from a deferred instance
        rather than a plain string
        """
        s = Scheduler()
        env = Variables()
        echo_service = Service(
            Deferred("echo {{run1}}", env),
            service_id='echo',
            verbose=True)

        n = SshNode(localhostname(), username=localuser())
        Sequence(
            SshJob(n,
                   commands=Run("echo from-first-run",
                                capture=Capture('run1', env))),
            SshJob(n,
                   commands=Run(echo_service.start_command())),
            SshJob(n,
                   commands=Run(echo_service.journal_command(since="10 second ago"),
                                capture=Capture('journal', env))),
            scheduler=s)
        print('STARTING', 20*'-', echo_service.start_command())
        s.run()
        print('DONE', 20*'-', echo_service.start_command())

        #print(f"env={env}")
        obtained = env.journal
        expected = "from-first-run"
        found = expected in obtained
        self.assertTrue(found)
