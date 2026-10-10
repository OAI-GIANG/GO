#!/usr/bin/env bash
set -u
set -a; . /etc/go/go-runtime.env; set +a
echo "provenance_match=$([ "${HG_TOOL_AUTHORITY_PROVENANCE:-}" = "${HG_TOOL_AUTHORITY_PROVENANCE_EXPECTED:-}" ] && echo yes || echo no)"
case "${HG_TOOL_AUTHORITY_SUBJECT:-}" in HG_SESSION_*) echo subject_prefix_ok=yes;; *) echo subject_prefix_ok=no;; esac
echo "provenance_len=${#HG_TOOL_AUTHORITY_PROVENANCE}  subject_len=${#HG_TOOL_AUTHORITY_SUBJECT}"
echo "root_key_env_set=$([ -n "${HG_AUTHORITY_ROOT_KEY_FILE:-}" ] && echo yes || echo no)"
echo "default_root_path_exists=$([ -s /etc/hg/authority/root.key ] && echo yes || echo no)"
echo "== default path the code will use =="
echo "${HG_AUTHORITY_ROOT_KEY_FILE:-/etc/hg/authority/root.key}"
echo DONE
