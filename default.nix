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

