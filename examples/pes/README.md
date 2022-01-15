<!--
SPDX-FileCopyrightText: 2022 Markus Kowalewski

SPDX-License-Identifier: GPL-3.0-only
-->

This is a simple, linear three-step quantum chemistry job.

The first step does a geometry optimization, the second calculates
a pontential energy surface, and the third step interpolates the surface.

The first two are molpro jobs and use slurm (sbatch) as a launcher.
The third jobs runs an octave script.
