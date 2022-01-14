# SPDX-FileCopyrightText: 2022 Markus Kowalewski
#
# SPDX-License-Identifier: GPL-3.0-only

{ pkgs ? import <nixpkgs> { }
, config
}:

let
  cfg = (pkgs.lib.evalModules {
    modules = [ ./module.nix config ];
    args = { inherit pkgs; inherit (pkgs) lib; };
  }).config;
in
  cfg.outPath

