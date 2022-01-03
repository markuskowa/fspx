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
Jobs are represented by [Nix](https://nixos.org) store paths. The input and output files are kept
in a content addressed storage and hashed with SHA256 checksum.


