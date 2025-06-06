#!@PYTHON@

# cli.in
#
# Copyright 2020 brombinmirko <send@mirko.pm>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.


import argparse
import os
import signal
import sys
import uuid
import warnings

import gi

warnings.filterwarnings("ignore")  # suppress GTK warnings
gi.require_version("Gtk", "4.0")

APP_VERSION = "@APP_VERSION@"
pkgdatadir = "@pkgdatadir@"
# noinspection DuplicatedCode
gresource_path = f"{pkgdatadir}/bottles.gresource"
sys.path.insert(1, pkgdatadir)

signal.signal(signal.SIGINT, signal.SIG_DFL)

# ruff: noqa: E402
from gi.repository import Gio

from bottles.frontend.params import APP_ID
from bottles.backend.globals import Paths
from bottles.backend.health import HealthChecker
from bottles.backend.managers.manager import Manager
from bottles.backend.models.config import BottleConfig
from bottles.backend.wine.cmd import CMD
from bottles.backend.wine.control import Control
from bottles.backend.wine.executor import WineExecutor
from bottles.backend.wine.winecommand import WineCommand
from bottles.backend.wine.reg import Reg
from bottles.backend.wine.winepath import WinePath
from bottles.backend.wine.regedit import Regedit
from bottles.backend.wine.taskmgr import Taskmgr
from bottles.backend.wine.uninstaller import Uninstaller
from bottles.backend.wine.winecfg import WineCfg
from bottles.backend.wine.explorer import Explorer
from bottles.backend.wine.regkeys import RegKeys
from bottles.backend.runner import Runner
from bottles.backend.utils import json
from bottles.backend.utils.manager import ManagerUtils


# noinspection DuplicatedCode
class CLI:
    settings = Gio.Settings.new(APP_ID)

    def __init__(self):
        # self.__clear()

        self.parser = argparse.ArgumentParser(
            description="Bottles is a tool to manage your bottles"
        )
        self.parser.add_argument(
            "-v", "--version", action="version", version=f"Bottles {APP_VERSION}"
        )
        self.parser.add_argument(
            "-j", "--json", action="store_true", help="Outputs in JSON format"
        )

        subparsers = self.parser.add_subparsers(dest="command", help="sub-command help")

        info_parser = subparsers.add_parser(
            "info", help="Show information about Bottles"
        )
        info_parser.add_argument(
            "type", choices=["bottles-path", "health-check"], help="Type of information"
        )

        list_parser = subparsers.add_parser("list", help="List entities")
        list_parser.add_argument(
            "type", choices=["bottles", "components"], help="Type of entity"
        )
        list_parser.add_argument(
            "-f",
            "--filter",
            help="Filter bottles and components (e.g. '-f 'environment:gaming')",
        )

        programs_parser = subparsers.add_parser("programs", help="List programs")
        programs_parser.add_argument(
            "-b", "--bottle", help="Bottle name", required=True
        )

        add_parser = subparsers.add_parser("add", help="Add program")
        add_parser.add_argument("-b", "--bottle", help="Bottle name", required=True)
        add_parser.add_argument("-n", "--name", help="Program name", required=True)
        add_parser.add_argument("-p", "--path", help="Program path", required=True)
        add_parser.add_argument("-l", "--launch-options", help="Program launch options")
        add_parser.add_argument(
            "--no-dxvk", action="store_true", help="Disable DXVK for the program"
        )
        add_parser.add_argument(
            "--no-vkd3d", action="store_true", help="Disable VKD3D for the program"
        )
        add_parser.add_argument(
            "--no-dxvk-nvapi",
            action="store_true",
            help="Disable DXVK Nvapi for the program",
        )

        tools_parser = subparsers.add_parser("tools", help="Launch Wine tools")
        tools_parser.add_argument(
            "tool",
            choices=[
                "cmd",
                "winecfg",
                "uninstaller",
                "regedit",
                "taskmgr",
                "control",
                "explorer",
            ],
            help="Tool to launch",
        )
        tools_parser.add_argument("-b", "--bottle", help="Bottle name", required=True)

        reg_parser = subparsers.add_parser("reg", help="Manage registry")
        reg_parser.add_argument(
            "action", choices=["add", "edit", "del"], help="Action to perform"
        )
        reg_parser.add_argument("-b", "--bottle", help="Bottle name", required=True)
        reg_parser.add_argument("-k", "--key", help="Registry key", required=True)
        reg_parser.add_argument("-v", "--value", help="Registry value", required=True)
        reg_parser.add_argument("-d", "--data", help="Data to be set")
        reg_parser.add_argument(
            "-t",
            "--key-type",
            help="Data type",
            choices=["REG_DWORD", "REG_SZ", "REG_BINARY", "REG_MULTI_SZ"],
        )

        edit_parser = subparsers.add_parser("edit", help="Edit a bottle configuration")
        edit_parser.add_argument("-b", "--bottle", help="Bottle name", required=True)
        edit_parser.add_argument(
            "--params", help="Set parameters (e.g. '-p dxvk:true')"
        )
        edit_parser.add_argument(
            "--env-var",
            help="Add new environment variable (e.g. '-env-var WINEDEBUG=-all')",
        )
        edit_parser.add_argument(
            "--win", help="Change Windows version (e.g. '--win win7')"
        )
        edit_parser.add_argument(
            "--runner", help="Change Runner (e.g. '--runner caffe-7.2')"
        )
        edit_parser.add_argument(
            "--dxvk", help="Change DXVK (e.g. '--dxvk dxvk-1.9.0')"
        )
        edit_parser.add_argument(
            "--vkd3d", help="Change VKD3D (e.g. '--vkd3d vkd3d-proton-2.6')"
        )
        edit_parser.add_argument(
            "--nvapi", help="Change DXVK-Nvapi (e.g. '--nvapi dxvk-nvapi-1.9.0')"
        )
        edit_parser.add_argument(
            "--latencyflex",
            help="Change LatencyFleX (e.g. '--latencyflex latencyflex-v0.1.0')",
        )

        new_parser = subparsers.add_parser("new", help="Create a new bottle")
        new_parser.add_argument("--bottle-name", help="Bottle name", required=True)
        new_parser.add_argument(
            "--environment",
            help="Environment to apply (gaming|application|custom)",
            required=True,
        )
        new_parser.add_argument(
            "--custom-environment", help="Path to a custom environment.yml file"
        )
        new_parser.add_argument("--arch", help="Architecture (win32|win64)")
        new_parser.add_argument("--runner", help="Name of the runner to be used")
        new_parser.add_argument("--dxvk", help="Name of the dxvk to be used")
        new_parser.add_argument("--vkd3d", help="Name of the vkd3d to be used")
        new_parser.add_argument("--nvapi", help="Name of the dxvk-nvapi to be used")
        new_parser.add_argument(
            "--latencyflex", help="Name of the latencyflex to be used"
        )

        run_parser = subparsers.add_parser("run", help="Run a program")
        run_parser.add_argument("-b", "--bottle", help="Bottle name", required=True)
        run_parser.add_argument("-e", "--executable", help="Path to the executable")
        run_parser.add_argument("-p", "--program", help="Program to run")
        run_parser.add_argument(
            "--args-replace",
            action="store_false",
            dest="keep_args",
            help="Replace current program arguments, instead of append",
        )
        run_parser.add_argument(
            "args",
            nargs="*",
            action="extend",
            help="Arguments to pass to the executable",
        )

        standalone_parser = subparsers.add_parser(
            "standalone",
            help="Generate a standalone script to launch commands "
            "without passing trough Bottles",
        )
        standalone_parser.add_argument(
            "-b", "--bottle", help="Bottle name", required=True
        )

        shell_parser = subparsers.add_parser(
            "shell", help="Launch commands in a Wine shell"
        )
        shell_parser.add_argument("-b", "--bottle", help="Bottle name", required=True)
        shell_parser.add_argument(
            "-i", "--input", help="Command to execute", required=True
        )

        self.__process_args()

    @staticmethod
    def __clear():
        os.system("clear")

    def __process_args(self):
        self.args = self.parser.parse_args()

        # INFO parser
        if self.args.command == "info":
            self.show_info()

        # LIST parser
        elif self.args.command == "list":
            _filter = None if self.args.filter is None else self.args.filter
            _type = self.args.type

            if _type == "bottles":
                self.list_bottles(c_filter=_filter)
            elif _type == "components":
                self.list_components(c_filter=_filter)

        # PROGRAMS parser
        elif self.args.command == "programs":
            self.list_programs()

        # TOOLS parser
        elif self.args.command == "tools":
            self.launch_tool()

        # ADD parser
        elif self.args.command == "add":
            self.add_program()

        # REG parser
        elif self.args.command == "reg":
            self.manage_reg()

        # EDIT parser
        elif self.args.command == "edit":
            self.edit_bottle()

        # NEW parser
        elif self.args.command == "new":
            self.new_bottle()

        # RUN parser
        elif self.args.command == "run":
            self.run_program()

        # SHELL parser
        elif self.args.command == "shell":
            self.run_shell()

        # STANDALONE parser
        elif self.args.command == "standalone":
            self.generate_standalone()

        else:
            self.parser.print_help()

    # region INFO
    def show_info(self):
        _type = self.args.type
        if _type == "bottles-path":
            res = Paths.bottles
            sys.stdout.write(res)
            exit(0)
        elif _type == "health-check":
            hc = HealthChecker()
            if self.args.json:
                sys.stdout.write(json.dumps(hc.get_results()) + "\n")
                exit(0)
            sys.stdout.write(hc.get_results(plain=True))

    # endregion

    # region LIST
    def list_bottles(self, c_filter=None):
        mng = Manager(g_settings=self.settings, is_cli=True)
        mng.check_bottles()
        bottles = mng.local_bottles

        if c_filter and c_filter.startswith("environment:"):
            environment = c_filter.split(":")[1].lower()
            bottles = [
                name
                for name, bottle in bottles.items()
                if bottle.Environment.lower() == environment
            ]

        if self.args.json:
            sys.stdout.write(json.dumps(bottles))
            exit(0)

        if len(bottles) > 0:
            sys.stdout.write(f"Found {len(bottles)} bottles:\n")
            for b in bottles:
                sys.stdout.write(f"- {b}\n")

    def list_components(self, c_filter=None):
        mng = Manager(g_settings=self.settings, is_cli=True)
        mng.check_runners(False)
        mng.check_dxvk(False)
        mng.check_vkd3d(False)
        mng.check_nvapi(False)
        mng.check_latencyflex(False)

        components = {
            "runners": mng.runners_available,
            "dxvk": mng.dxvk_available,
            "vkd3d": mng.vkd3d_available,
            "nvapi": mng.nvapi_available,
            "latencyflex": mng.latencyflex_available,
        }

        if c_filter and c_filter.startswith("category:"):
            category = c_filter.split(":")[1].lower()
            if category in components:
                components = {category: components[category]}

        if self.args.json:
            sys.stdout.write(json.dumps(components))
            exit(0)

        for c in components:
            sys.stdout.write(f"Found {len(components[c])} {c}\n")
            for i in components[c]:
                sys.stdout.write(f"- {i}\n")

    # endregion

    # region PROGRAMS
    def list_programs(self):
        mng = Manager(g_settings=self.settings, is_cli=True)
        mng.check_bottles()
        _bottle = self.args.bottle

        if _bottle not in mng.local_bottles:
            sys.stderr.write(f"Bottle {_bottle} not found\n")
            exit(1)

        bottle = mng.local_bottles[_bottle]
        programs = mng.get_programs(bottle)
        programs = [p for p in programs if not p.get("removed", False)]

        if self.args.json:
            sys.stdout.write(json.dumps(programs))
            exit(0)

        if len(programs) > 0:
            sys.stdout.write(f"Found {len(programs)} programs:\n")
            for p in programs:
                sys.stdout.write(f"- {p['name']}\n")

    # endregion

    # region TOOLS
    def launch_tool(self):
        _bottle = self.args.bottle
        _tool = self.args.tool
        mng = Manager(g_settings=self.settings, is_cli=True)
        mng.check_bottles()

        if _bottle not in mng.local_bottles:
            sys.stderr.write(f"Bottle {_bottle} not found\n")
            exit(1)

        bottle = mng.local_bottles[_bottle]

        if _tool == "cmd":
            CMD(bottle).launch()
        elif _tool == "winecfg":
            WineCfg(bottle).launch()
        elif _tool == "uninstaller":
            Uninstaller(bottle).launch()
        elif _tool == "regedit":
            Regedit(bottle).launch()
        elif _tool == "taskmgr":
            Taskmgr(bottle).launch()
        elif _tool == "control":
            Control(bottle).launch()
        elif _tool == "explorer":
            Explorer(bottle).launch()

    # endregion

    # region ADD
    def add_program(self):
        _bottle = self.args.bottle
        _name = self.args.name
        _path = self.args.path
        _launch_options = self.args.launch_options
        _no_dxvk = self.args.no_dxvk
        _no_vkd3d = self.args.no_vkd3d
        _no_dxvk_nvapi = self.args.no_dxvk_nvapi
        _executable = ""
        _folder = ""
        _uuid = str(uuid.uuid4())
        mng = Manager(g_settings=self.settings, is_cli=True)
        mng.check_bottles()

        if _bottle not in mng.local_bottles:
            sys.stderr.write(f"Bottle {_bottle} not found\n")
            exit(1)

        bottle = mng.local_bottles[_bottle]
        winepath = WinePath(bottle)

        if winepath.is_unix(_path):
            if not os.path.exists(_path):
                sys.stderr.write(f"Path doesn't exists or is unreachable: {_path}")
                exit(1)
            _executable = os.path.basename(_path)
            _folder = os.path.dirname(_path)
        elif winepath.is_windows(_path):
            _executable = _path.split("\\")[-1]
            _folder = ManagerUtils.get_exe_parent_dir(bottle, _path)
        else:
            sys.stderr.write(f"Unsupported path type: {_path}")
            exit(1)

        _program = {
            "arguments": _launch_options if _launch_options else "",
            "executable": _executable,
            "name": _name,
            "folder": _folder,
            "icon": "",
            "id": _uuid,
            "path": _path,
            "dxvk": not _no_dxvk if _no_dxvk else bottle.Parameters.dxvk,
            "vkd3d": not _no_vkd3d if _no_vkd3d else bottle.Parameters.vkd3d,
            "dxvk_nvapi": (
                not _no_dxvk_nvapi if _no_dxvk_nvapi else bottle.Parameters.dxvk_nvapi
            ),
        }
        mng.update_config(bottle, _uuid, _program, scope="External_Programs")
        sys.stdout.write(f"'{_name}' added to '{bottle.Name}'!")

    # endregion

    # region REG
    def manage_reg(self):
        _bottle = self.args.bottle
        _action = self.args.action
        _key = self.args.key
        _value = self.args.value
        _data = self.args.data
        _key_type = self.args.key_type
        mng = Manager(g_settings=self.settings, is_cli=True)
        mng.check_bottles()

        if _bottle not in mng.local_bottles:
            sys.stderr.write(f"Bottle {_bottle} not found\n")
            exit(1)

        bottle = mng.local_bottles[_bottle]
        allowed_types = ["REG_SZ", "REG_DWORD", "REG_BINARY", "REG_MULTI_SZ"]
        _key_type = "REG_SZ" if _key_type is None else _key_type.upper()

        if _action in ["add", "edit"]:
            if _data is None or _key_type not in allowed_types:
                sys.stderr.write("Missing or invalid data or key type\n")
                exit(1)
            Reg(bottle).add(_key, _value, _data, _key_type)
        elif _action == "del":
            Reg(bottle).remove(_key, _value)

    # endregion

    # region EDIT
    def edit_bottle(self):
        _bottle = self.args.bottle
        _params = self.args.params
        _env_var = self.args.env_var
        _win = self.args.win
        _runner = self.args.runner
        _dxvk = self.args.dxvk
        _vkd3d = self.args.vkd3d
        _nvapi = self.args.nvapi
        _latencyflex = self.args.latencyflex
        mng = Manager(g_settings=self.settings, is_cli=True)
        mng.check_bottles()

        valid_parameters = BottleConfig().Parameters.keys()

        if _bottle not in mng.local_bottles:
            sys.stderr.write(f"Bottle {_bottle} not found\n")
            exit(1)

        bottle = mng.local_bottles[_bottle]

        if _params is not None:
            _params = _params.split(",")
            _params = [p.split(":") for p in _params]
            for k, v in _params:
                if k not in valid_parameters:
                    sys.stderr.write(f"Invalid parameter {k}\n")
                    exit(1)

                if v.lower() == "true":
                    v = True
                elif v.lower() == "false":
                    v = False
                else:
                    try:
                        v = int(v)
                    except ValueError:
                        pass

                mng.update_config(bottle, k, v, scope="Parameters")

        if _env_var is not None and "=" in _env_var:
            k, v = _env_var.split("=", 1)
            mng.update_config(bottle, k, v, scope="Environment_Variables")

        if _win is not None:
            RegKeys(bottle).lg_set_windows(_win)

        if _runner is not None:
            Runner.runner_update(bottle, mng, _runner)

        if _dxvk is not None:
            mng.check_dxvk(False)

            if _dxvk not in mng.dxvk_available:
                sys.stderr.write(f"DXVK version {_dxvk} not available\n")
                exit(1)

            if mng.install_dll_component(bottle, "dxvk", version=_dxvk):
                mng.update_config(bottle, "DXVK", _dxvk)

        if _vkd3d is not None:
            mng.check_vkd3d(False)

            if _vkd3d not in mng.vkd3d_available:
                sys.stderr.write(f"VKD3D version {_vkd3d} not available\n")
                exit(1)

            if mng.install_dll_component(bottle, "vkd3d", version=_vkd3d):
                mng.update_config(bottle, "VKD3D", _vkd3d)

        if _nvapi is not None:
            mng.check_nvapi(False)

            if _nvapi not in mng.nvapi_available:
                sys.stderr.write(f"NVAPI version {_nvapi} not available\n")
                exit(1)

            if mng.install_dll_component(bottle, "nvapi", version=_nvapi):
                mng.update_config(bottle, "NVAPI", _nvapi)

        if _latencyflex is not None:
            mng.check_latencyflex(False)

            if _latencyflex not in mng.latencyflex_available:
                sys.stderr.write(f"LatencyFlex version {_latencyflex} not available\n")
                exit(1)

            if mng.install_dll_component(bottle, "latencyflex", version=_latencyflex):
                mng.update_config(bottle, "LatencyFlex", _latencyflex)

    # endregion

    # region NEW
    def new_bottle(self):
        _name = self.args.bottle_name
        _environment = self.args.environment
        _custom_environment = self.args.custom_environment
        _arch = "win64" if self.args.arch is None else self.args.arch
        _runner = self.args.runner
        _dxvk = self.args.dxvk
        _vkd3d = self.args.vkd3d
        _nvapi = self.args.nvapi
        _latencyflex = self.args.latencyflex
        mng = Manager(g_settings=self.settings, is_cli=True)
        mng.checks()

        mng.create_bottle(
            name=_name,
            environment=_environment,
            runner=_runner,
            dxvk=_dxvk,
            vkd3d=_vkd3d,
            nvapi=_nvapi,
            latencyflex=_latencyflex,
            arch=_arch,
            custom_environment=_custom_environment,
        )

    # endregion

    # region RUN
    def run_program(self):
        _bottle = self.args.bottle
        _program = self.args.program
        _keep = self.args.keep_args
        _args = " ".join(self.args.args)
        _executable = self.args.executable

        mng = Manager(g_settings=self.settings, is_cli=True)
        mng.checks()

        if _bottle.startswith('"') and _bottle.endswith('"'):
            _bottle = _bottle[1:-1]
        elif _bottle.startswith("'") and _bottle.endswith("'"):
            _bottle = _bottle[1:-1]

        for b in mng.local_bottles.keys():
            if b == _bottle:
                break
        else:
            sys.stderr.write(f"Bottle {_bottle} not found\n")
            exit(1)

        bottle = mng.local_bottles[_bottle]
        programs = mng.get_programs(bottle)

        if _program is not None:
            if _executable is not None:
                sys.stderr.write("Cannot specify both --program and --executable\n")
                exit(1)

            if _program not in [p["name"] for p in programs]:
                sys.stderr.write(f"Program {_program} not found\n")
                exit(1)

            program = [p for p in programs if p["name"] == _program][0]
            _executable = program.get("path", "")
            _program_args = program.get("arguments")
            if _keep and _program_args:
                _args = _program_args + " " + _args
            program.get("pre_script", None)
            program.get("post_script", None)
            program.get("folder", None)
            program.get("midi_soundfont", None)

            program.get("dxvk")
            program.get("vkd3d")
            program.get("dxvk_nvapi")
            program.get("fsr")
            program.get("gamescope")
            program.get("virtual_desktop")

            WineExecutor.run_program(bottle, program | {"arguments": _args})

        elif _executable:
            _executable = _executable.replace("file://", "")
            if _executable.startswith('"') and _executable.endswith('"'):
                _executable = _executable[1:-1]
            elif _executable.startswith("'") and _executable.endswith("'"):
                _executable = _executable[1:-1]

            WineExecutor(
                bottle,
                exec_path=_executable,
                args=_args,
            ).run_cli()
        else:
            sys.stderr.write(
                "No program or executable specified, you must use either --program or --executable\n"
            )
            exit(1)

    # endregion

    # region SHELL
    def run_shell(self):
        _bottle = self.args.bottle
        _input = self.args.input
        mng = Manager(g_settings=self.settings, is_cli=True)
        mng.checks()

        if _bottle not in mng.local_bottles:
            sys.stderr.write(f"Bottle {_bottle} not found\n")
            exit(1)

        bottle = mng.local_bottles[_bottle]
        winecommand = WineCommand(config=bottle, command=_input, communicate=True)
        res = winecommand.run()
        if not res.ok:
            sys.stdout.write(res.message)
        sys.stdout.write(res.data)

    # endregion

    # region STANDALONE
    def generate_standalone(self):
        _bottle = self.args.bottle
        mng = Manager(g_settings=self.settings, is_cli=True)
        mng.checks()

        if _bottle not in mng.local_bottles:
            sys.stderr.write(f"Bottle {_bottle} not found\n")
            exit(1)

        bottle = mng.local_bottles[_bottle]
        path = ManagerUtils.get_bottle_path(bottle)
        standalone_path = os.path.join(path, "standalone")
        winecommand = WineCommand(config=bottle, command='"$@"')
        env = winecommand.get_env(return_clean_env=True)
        cmd = winecommand.get_cmd('"$@"', return_clean_cmd=True)
        winecommand.command.replace(
            "/usr/lib/extensions/vulkan/MangoHud/bin/mangohud", ""
        )

        if os.path.isfile(standalone_path):
            os.remove(standalone_path)

        with open(standalone_path, "w") as f:
            f.write("#!/bin/bash\n")
            for k, v in env.items():
                f.write(f"export {k}='{v}'\n")
            f.write(f"{cmd}\n")

        os.chmod(os.path.join(path, "standalone"), 0o755)
        sys.stdout.write(f"Standalone generated in {path}\n")
        sys.stdout.write("Re-generate after every bottle change.\n")


if __name__ == "__main__":
    cli = CLI()
