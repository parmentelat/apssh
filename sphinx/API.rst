The apssh API
========================================

Most symbols can be imported directly from the ``apssh`` package, e.g.

    ``from apssh import SshJob``

No need to import module ``apssh.sshjob`` here.

The SshProxy class
------------------------------

.. automodule:: apssh.sshproxy
		:members:

-----

Commands classes
------------------------------

.. automodule:: apssh.commands
		:members:

		-----

		Formatters classes
		------------------------------

		.. automodule:: apssh.formatters
				:members:
				:member-order: bysource
				:exclude-members: VerboseFormatter

-----

The Service class
------------------------------

.. automodule:: apssh.service
		:members:

-----

Utilities
------------------------------

.. automodule:: apssh.topology
		:members: close_ssh_in_scheduler, co_close_ssh_in_scheduler, topology_graph, topology_dot, topology_as_dotfile, topology_as_pngfile

-----

``nepi-ng`` node classes
-------------------------------------

.. automodule:: apssh.nodes
		:members:

``nepi-ng`` job classes
-------------------------------------

.. automodule:: apssh.sshjob
		:members:

-----

Tools to deal with keys
------------------------------

.. automodule:: apssh.keys
		:members:

-----

The apssh binary implementation
----------------------------------------

.. automodule:: apssh.apssh
		:members:
