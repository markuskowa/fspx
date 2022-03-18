<!--
SPDX-FileCopyrightText: 2022 Markus Kowalewski

SPDX-License-Identifier: GPL-3.0-only
-->

# FSPX - Functional Scientific Project Execution
Scientific calculations are very often carried out in an iterative fashion.
However, in a more complex project it can become difficult to recreate all steps
that lead up to a result or to recalculate parts of the project with changed
parameters. FSPX is an experimental attempt to formalize the compute environment
and keep track of data input and output. This is done by means of cryptographic hashes,
which allow us to determine which jobs in a project need to be recalculated.


## Basic Concept
A project consists of one or more jobs. These jobs can depend on each other.
A job is a function that takes zero or more inputs (simple files) and produces one or more outputs (files).
Job scripts (i.e. the functions) are represented by [Nix](https://nixos.org) store paths. The input and output files are kept
in a content addressed storage and are hashed with a SHA256 checksum. If the function, an input, or an output
changes, all jobs and dependent jobs need to be recalculated.


## Usage
In the first step we need to create a config file for the project. The config makes
use of the nix module system:
```nix
{ pkgs, ... } :
{
  workdir = "/tmp/fspx";
  dstore = "./dstore";
  jobsets = {
    pre-run = {
      outputs = [ "data" ];
      jobScript = pkgs.writeShellScript "run"
      ''
	echo "1 2 3" > data
      '';
    };

    sum = {
      inputs = {
        ":data" = null;
      };
      outputs = [ "sum" ];
      env = pkgs.coreutils;
      jobScript = pkgs.writeShellScript "run"
        ''
          s=0;
          for i in $(cat inputs/data); do
            s=$(($s+$i))
          done;
          echo $s > sum
        '';
    };
  };
}
```

In this simple example we have a job named pre-run, which creates the data file named "data"
and second job named sum, which sums up the numbers in data. Note that the input name in
the job sum is prefix with ":". This means: take "data" from another job output.
The job sum thus depends on the job pre-run. If something in pre-run changes, sum and pre-run will be
automatically recalculated.

We can now build the project configuation with:
```
fspx build ./config.nix
```
This will create a directory `.fspx/cfg`, which points to the nix store and contains
the project configuration in `project.json`.

Next, we need to run all jobs:
```
fspx run
```
This now creates the outputs of each job, `outputs/data` and `outputs/sum` as well
as `.fspx/pre-run.manifest` and `.fspx/sum.manifest`, which record the state of inputs
outputs and all job scripts.

With
```
fspx check
```
one can verify, that all jobs in the project are valid.

