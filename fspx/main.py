# SPDX-FileCopyrightText: 2022 Markus Kowalewski
#
# SPDX-License-Identifier: GPL-3.0-only

import os
import argparse
import subprocess
import json

from . import utils
from . import fspx
from . import cas

# Default path for project files
cfgPath = fspx.cfgPath

# Path nix module files
instDir = "nix/"


def cmd_build(cfgnix: str) -> int:
    '''Build the project configuration from nix configuration file
    '''

    if not os.path.exists(cfgPath):
        raise Exception("Build needs to be called from the top level directory of the project.\nRun 'fspx init' before first use.")


    print("Build {}".format(cfgnix))
    if not cfgnix[0] in ['.', '/']:
        cfgnix = "./" + cfgnix

    try:
        os.mkdir(cfgPath)
    except FileExistsError:
        None
    ret = os.system("nix-build {}/project.nix --arg config {} --out-link {}/cfg --show-trace".format(instDir, cfgnix, cfgPath))
    return os.waitstatus_to_exitcode(ret)


def cmd_list(config) -> None:
    '''List all jobs in project
    '''
    for name, _ in config['jobsets'].items():
        print(name)

def cmd_check(config) -> tuple[list[str], bool]:
    '''Check if job results are valid
    '''

    jobs, valid = fspx.check_jobset(config['deps'], config['dstore'], recalc=[])

    if not valid:
        print("The following jobs need to be re-run:")

        for j in jobs:
            print(j)

    return jobs, valid

def cmd_shell(config, jobname: str, dstore: str) -> None:
    '''Start a shell in a job environment
    '''
    job = config['jobsets'][jobname]

    #workdir = os.path.expandvars(job['workdir'])
    workdir = job['workdir']

    # Import inputs
    print("Import and link inputs...")
    inputs = fspx.import_input_paths(job, jobname, dstore)
    fspx.link_inputs_to_dir(inputs, workdir, dstore)

    print("Run nix-shell...")
    os.system("cd {0}; nix-shell -p {1}".format(workdir, job['env']))


def cmd_export(config, toDir: str, targetStore: str) -> None:
    '''Export the project
    '''

    # Copy config file and update hashes
    jobsets = {}
    for name, job in config['jobsets'].items():
        jobsets[name] = fspx.package_job(name, job)

    config['jobsets'] = jobsets

    # Remove workdir (not needed in archive)
    config.pop("workdir")
    # Are not needed, can be recalculated, when needed.
    config.pop("deps")

    # Copy inputs and outputs to archive
    print("Copying files to archive...")
    os.makedirs(toDir)

    os.mkdir("{}/inputs".format(toDir))
    os.mkdir("{}/outputs".format(toDir))

    try:
        os.makedirs(targetStore)
    except FileExistsError:
        None

    fspx.copy_files_to_external(config['jobsets'], toDir, targetStore, config['dstore'])

    # Fix dstore
    config['dstore'] = os.path.relpath(targetStore, toDir)

    cas.link_to_store(
            os.path.join(toDir, "config.json"),
            cas.import_data(json.dumps(config, indent=2).encode(), targetStore),
            targetStore,
            gcroot = True)

    # Create NAR
    print("Save job scripts to NAR archive...")
    allJobScripts = fspx.collect_job_scripts(config['jobsets'])
    nar_dir = "{}/nar".format(toDir)
    os.mkdir(nar_dir)

    out_paths = os.popen("nix-store -qR {}".format(" ".join(allJobScripts), toDir), 'r').read()

    for path in out_paths.split('\n'):
        process = subprocess.Popen(['nix-store', '--export', path],
                     stdout=subprocess.PIPE,
                     stderr=subprocess.PIPE)
        nar_data, _ = process.communicate()
        hash = cas.import_data(nar_data, targetStore)
        cas.link_to_store("{}/{}.nar".format(nar_dir, os.path.basename(path)), hash, targetStore, gcroot = True)


def cmd_init() -> None:

    # create directories
    dirs = [ 'inputs', 'src', '.fspx'];

    for d in dirs:
        try:
            os.makedirs(d)
        except FileExistsError:
            None

def cmd_run(config, job: str = None, launcher: str = None) -> None:
    if job == None:
        jobs, valid = fspx.check_jobset(config['deps'], config['dstore'])
        if not valid:
            fspx.run_jobs(config['jobsets'], jobs, config['dstore'], global_launcher = launcher)
    else:
        fspx.run_jobs(config['jobsets'], [ job ], config['dstore'], global_launcher = launcher)

def cmd_validate(config, job: str = None, launcher: str = None) -> None:

    # make sure we have a valid job set by attempting to run all jobs
    cmd_run(config, launcher = launcher)

    if job == None:
        all_jobs = fspx.find_all_jobs(config['deps'])
        fspx.validate_jobs(config['jobsets'], map(lambda j: j["name"], all_jobs), config['dstore'], global_launcher = launcher)
    else:
        fspx.validate_jobs(config['jobsets'], [ job ], config['dstore'], global_launcher = launcher)

#
# Main
#

def main():
    argsMain = argparse.ArgumentParser(
            prog = "fspx",
            description = "Functional Scientific Project Execution.")

    cmdArgs = argsMain.add_subparsers(dest="command", help='sub-command help')

    cmdArgs.add_parser("init", help="Setup directories and templates.")

    argsBuild = cmdArgs.add_parser("build", help="Build the project description from Nix config file.")
    argsBuild.add_argument("config_file", nargs='?', default = './config.nix', help="Project configuration file.")

    cmdArgs.add_parser("list", help="List job names.")

    cmdArgs.add_parser("check", help="Check project and list invalidated jobs.")

    argsRun = cmdArgs.add_parser("run", help="Run jobs")
    argsRun.add_argument("job", nargs='?', help="Job to run. If ommited all invalidated jobs be run.")
    argsRun.add_argument("-l", "--launcher", help="Override job launcher.")

    argsValidate = cmdArgs.add_parser("validate", help="Validate jobs by re-running them")
    argsValidate.add_argument("job", nargs='?', help="Jobs to run. If ommited all jobs will be run.")
    argsValidate.add_argument("-l", "--launcher", help="Override job launcher.")

    argsShell = cmdArgs.add_parser("shell", help="Enter an interactive job shell environment.")
    argsShell.add_argument("job", help="Job to pick shell from.")

    argsExport = cmdArgs.add_parser("export", help="Export a finished project.")
    argsExport.add_argument("target_dir", help="Target directory. Must be empty.")
    argsExport.add_argument("target_store", help="Target data store directory.")

    argsImport = cmdArgs.add_parser("store-import", help="Import files into data store manually.")
    argsImport.add_argument("file_name", help="File to import.")
    argsImport.add_argument("link_name", help="Link name to create")

    argsCheckCAS = cmdArgs.add_parser("store-check", help="Check if store entries are valid")
    argsCheckCAS.add_argument("dstore", help="Path to data store")

    argsGC = cmdArgs.add_parser("store-gc", help="garbage collect unlinked entries from data store")
    argsGC.add_argument("dstore", help="Path to data store")

    args = argsMain.parse_args()

    if args.command == None:
        argsMain.print_help()
        exit(1)

    elif args.command == "init":
        cmd_init()
        exit(0)

    elif args.command == "build":
        ret = cmd_build(args.config_file)
        exit(ret)

    elif args.command == "store-check":
        if not cas.verify_store(args.dstore):
            exit(1)

        print("Store in {} is OK.".format(args.dstore))
        exit(0)

    elif args.command == "store-gc":
        n = cas.clean_garbage(args.dstore)
        print("Removed {} files from data store".format(n))
        exit(0)

    # Read the config. Every command from here on will need it
    config = utils.read_json("{}/cfg/project.json".format(cfgPath))

    if args.command == "list":
        cmd_list(config)

    elif args.command == "check":
        _, valid = cmd_check(config)
        if not valid:
            exit(1)

    elif args.command == "run":
        cmd_run(config, args.job, args.launcher)

    elif args.command == "validate":
        cmd_validate(config, args.job, args.launcher)

    elif args.command == "shell":
        cmd_shell(config, args.job, config['dstore'])

    elif args.command == "export":
        if not cmd_check(config):
            print("Project data is not valid. Can not export project.")
            exit(1)

        cmd_export(config, args.target_dir, args.target_store)

    elif args.command == "store-import":
        paths = cas.import_paths([ args.file_name ], config['dstore'])
        cas.link_to_store(args.link_name, paths[args.file_name], config['dstore'], gcroot = True)


    exit(0)

if __name__ == '__main__':
    main()
