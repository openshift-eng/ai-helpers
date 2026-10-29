# Sourced by Go stubs. Native metadata identity is covered with real Go; these
# fixtures model graph/update outcomes while accepting Go's binding flags.
_binding_arg_count=$#
while [ "$_binding_arg_count" -gt 0 ]; do
  case "$1" in
    -modfile=*|-overlay=) shift ;;
    *) set -- "$@" "$1"; shift ;;
  esac
  _binding_arg_count=$((_binding_arg_count - 1))
done
unset _binding_arg_count
# Workspace ownership must use an actual read-only parse, not a stub verdict.
if [ "${1:-}" = work ] && [ "${2:-}" = edit ]; then
  exec "$CVE_FIX_TEST_REAL_GO" "$@"
fi
