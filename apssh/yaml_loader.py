"""
the YamlLoader class - how to create objects in YAML
"""

from pathlib import Path

import yaml

from jinja2 import Template, DebugUndefined


from asynciojobs import Scheduler
import apssh
from apssh import SshJob, formatters # , Run, RunScript, RunString, Push, Pull
from apssh.nodes import SshNode, LocalNode


WARNING = """
# WARNING: this file was produced automatically - DO NOT EDIT !
# see {original} instead
#
"""

class YamlLoader:

    """
    The `YamlLoader` class builds a Scheduler object from a yaml file

    In addition to using the regular YAML syntax
    (current implementation uses pyyaml, which supports YAML v1.1)
    the input can optionnally pass through Jinja2 templating;
    to that end, provide a non-empty `env` parameter, that will specify
    templating variables

    Parameters:
      filename(str): the input file (can be a Path as well)
    """

    def __init__(self, filename):
        self.path = Path(filename)


    def load(self, env=None, *, save_intermediate=None) -> Scheduler:
        """
        parse input filename and returns a `Scheduler` object; a shortcut to using
        `load_with_maps()` and trashing the intermediary maps

        same parameters as `load_with_maps`

        """
        _nodes_map, _jobs_map, scheduler = self.load_with_maps(
            env, save_intermediate=save_intermediate)
        return scheduler


    def load_with_maps(self, env=None, *, save_intermediate=None):
        """
        parse input filename

        Parameters:
          env(dict): if not empty, a Jinja2 pass is performed on the input
          save_intermediate: defaults to None, meaning do nothing; if provided,
            this parameter means to save the output of the jinja templating phase,
            typically for debugging purposes; if set to `True`, the output filename
            is computed from the object's filename as provided at constructor-time;
            alternatively you may also pass a string, or a Path instance.
            If env is None, this parameter is ignored.

        Returns:
          a tuple containing:
            (*) nodes_map, a dictionary linking ids to SshNode instantes
            (*) jobs_map, a dictionary linking ids to Job instances
            (*) the resulting scheduler
        """
        with self.path.open() as feed:
            yaml_input = feed.read()

        if env:
            template = Template(yaml_input, undefined=DebugUndefined)
            yaml_input = template.render(**env)
            yaml_input = WARNING.format(original=self.path) + yaml_input

            # save this intermediate form for debugging or documentation
            if save_intermediate is None or save_intermediate is False:
                pass
            elif isinstance(save_intermediate, (str, Path)):
                if isinstance(save_intermediate, str):
                    save_intermediate = Path(save_intermediate)
                with save_intermediate.open('w') as writer:
                    writer.write(yaml_input)
                    print(f"save_intermediate: (over)wrote plain YAML {save_intermediate}")
            else:
                # compute a filename
                if self.path.suffix == ".j2":
                    # simply remove the .j2
                    intermediate_path = self.path.with_suffix("")
                else:
                    # add a .tmp
                    intermediate_path = self.path.parent / (self.path.name + ".tmp")
                with intermediate_path.open('w') as writer:
                    writer.write(yaml_input)
                    print(f"save_intermediate: (over)wrote plain YAML {intermediate_path}")


        D = yaml.safe_load(yaml_input)           # pylint: disable=invalid-name

        if 'nodes' not in D:
            raise ValueError(f"file {self.path} has no 'nodes' key")
        if 'jobs' not in D:
            raise ValueError(f"file {self.path} has no 'jobs' key")

        nodes_map = self._load_nodes(D['nodes'])

        jobs_map, scheduler = self._load_jobs(D['jobs'], nodes_map)
        return nodes_map, jobs_map, scheduler


    @staticmethod
    def _dict_to_class(D, cls, mandatories, optionals): # pylint: disable=invalid-name
        """
        translate a dict to a class object

        the 'id' field is always mandatory

        mandatories and optionals are both expected to be a dictionary that maps
        fieldname to a transformer function that is applied to the corresponding
        value; if None, no transformation is performed

        mandatory values are passed to the constructor

        as far as optionals, the result is then assigned right into object.key

        returns a tuple (id, obj)
        """
        assert 'id' in D

        # check for mandatories
        for key in mandatories:
            if key not in D:
                raise ValueError(f"dict {D} misses the `{key}` field")

        # check for unexpected keys
        for key in D:
            if key == 'id':
                continue
            if key not in mandatories and key not in optionals:
                raise ValueError(f"{D} contains unexpected key {key}")
        # build object from mandatories
        constructor_args = {}
        for key, transformer in mandatories.items():
            value = D[key]
            if transformer:
                value = transformer(value)
            constructor_args[key] = value
        obj = cls(**constructor_args)
        # assign optionals
        for key, transformer in optionals.items():
            if key not in D:
                continue
            value = D[key]
            if transformer:
                value = transformer(value)
            setattr(obj, key, value)

        return (D['id'], obj)


    def _load_nodes(self, nodes_list):
        """
        returns a dict:
        - keys are the ids defined in each node (mandatory)
        - values are SshNode objects
        """
        nodes_map = {}

        def locate_node_from_id(node_id):
            return nodes_map[node_id]

        def locate_formatter(clsname):
            # formatters is the apssh.formatters module
            cls = getattr(formatters, clsname)
            return cls()

        node_mandatories = {
            'hostname': None,
        }
        node_optionals = {
            # the gateway field refers to an id defined beforehand
            'gateway': locate_node_from_id,
            'username': None,
            'critical': None,
            'formatter': locate_formatter,
            'verbose': None,
        }
        local_mandatories = {
        }
        local_optionals = {
            'formatter': locate_formatter,
            'verbose': None,
        }
        for node_dict in nodes_list:
            if 'localnode' in node_dict:
                del node_dict['localnode']
                node_id, node = self._dict_to_class(node_dict, LocalNode,
                                                    local_mandatories, local_optionals)
            else:
                node_id, node = self._dict_to_class(node_dict, SshNode,
                                                    node_mandatories, node_optionals)
            nodes_map[node_id] = node

        return nodes_map

    def _load_jobs(self, jobs_list, nodes_map):

        jobs_map = {}

        def locate_node_from_id(node_id):
            return nodes_map[node_id]

        def locate_requirement(req_id_s):
            # search instance or instances of job in the current map
            if isinstance(req_id_s, str):
                return {jobs_map[req_id_s]}
            else:
                return {jobs_map[req_id] for req_id in req_id_s}

        def create_commands(commands_list):
            def get_and_delete_key(D, k, default=None): # pylint: disable=invalid-name
                if k in D:
                    result = D[k]
                    del D[k]
                    return result
                if default is None:
                    raise ValueError(f"missing key {k}")
                return default

            result = []
            for command_dict in commands_list:
                # locate the class
                classname = command_dict['type']
                del command_dict['type']
                cls = getattr(apssh, classname)

                if 'Run' in classname:
                    # the 'usual' shorthand is to simply define 'command'
                    if 'command' in command_dict:
                        argv = command_dict['command'].split()
                        del command_dict['command']
                        command_instance = cls(*argv, **command_dict)
                    # however in some cases the 'split' approach may not work
                    # as desired
                    elif classname == 'Run':
                        argv = get_and_delete_key(command_dict, 'argv')
                        command_instance = cls(*argv, **command_dict)
                    elif classname == 'RunScript':
                        text = get_and_delete_key(command_dict, 'local_script')
                        args = get_and_delete_key(command_dict, 'args', [])
                        command_instance = cls(text, *args, **command_dict)
                    elif classname == 'RunString':
                        text = get_and_delete_key(command_dict, 'script_body')
                        args = get_and_delete_key(command_dict, 'args', [])
                        command_instance = cls(text, *args, **command_dict)
                elif classname in ('Push, Pull'):
                    command_instance = cls(**command_dict)

                result.append(command_instance)
            return result

        def strip_label(label):
            return label.strip()

        mandatories = {
            'node': locate_node_from_id,
            'commands': create_commands,
        }
        optionals = {
            'required': locate_requirement,
            'critical': None,
            'verbose': None,
            'label': strip_label,
        }

        for job_dict in jobs_list:
            job_id, job = self._dict_to_class(job_dict, SshJob, mandatories, optionals)
            jobs_map[job_id] = job

        scheduler = Scheduler()
        # insert jobs in scheduler
        scheduler.update(jobs_map.values())

        return jobs_map, scheduler
