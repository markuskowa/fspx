# SPDX-FileCopyrightText: 2022 Markus Kowalewski
#
# SPDX-License-Identifier: GPL-3.0-only

{ pkgs, ... } :

let
  run = name: pkgs.writeShellScript "run"
  ''
    echo ${name} > ${name}
  '';

in {
  workdir = "/tmp/fspx";
  dstore = "./dstore";
  description = "A dummy test project";
  jobsets = {
    pes = {
      inputs = {
        ":data" = null;
        ":fixed-data" = "c568f5655f008414ea1e56416fefadf42f87608c1ba94a228de72f54bf504597";
      };
      outputs = [ "pes" ];
      env = pkgs.coreutils;
      jobScript = run "pes";

    };
    pre-run1 = {
      inputs = { "jobfile" = null; };
      outputs = [ "fixed-data" ];
      jobScript = run "fixed-data";
    };
    pre-run2 = {
      outputs = [ "data" ];
      jobScript = run "data";
    };
    dyn1 = {
      inputs = {
        ":pes" = null;
      };
      outputs = [ "dyn1.dat" ];
      env = pkgs.coreutils;
      jobScript = run "dyn1.dat";
    };
    dyn2 = {
      inputs = {
        ":pes" = null;
      };
      outputs = [ "dyn2.dat" ];
      env = pkgs.coreutils;
      jobScript = run "dyn2.dat";
    };

    job1 = {
      outputs = [ "job1.dat" ];
      env = pkgs.coreutils;
      jobScript = run "job1.dat";
    };

    job2 = {
      inputs = { ":job1.dat" = null; };
      outputs = [ "job2.dat" ];
      env = pkgs.coreutils;
      jobScript = run "job2.dat";
    };

    job3 = {
      inputs = { ":job2.dat" = null; };
      outputs = [ "job3.dat" ];
      env = pkgs.coreutils;
      jobScript = run "job3.dat";
    };
  };
}
