# SPDX-FileCopyrightText: 2022 Markus Kowalewski
#
# SPDX-License-Identifier: GPL-3.0-only

{ config }:

let
  pkgs = config.nixpkgs or import <nixpkgs> {};
  inherit (pkgs) lib;

  evaluatedModule = lib.evalModules {
    modules = [
      ./module.nix
      config
    ];
  };

in
  evaluatedModule.config.outPath

