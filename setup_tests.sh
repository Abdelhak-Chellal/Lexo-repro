#!/bin/bash
mkdir -p tests

declare -A REPOS=(
  ["is-number"]="https://github.com/jonschlinkert/is-number"
  ["arr-diff"]="https://github.com/jonschlinkert/arr-diff"
  ["is-odd"]="https://github.com/jonschlinkert/is-odd"
  ["is-even"]="https://github.com/jonschlinkert/is-even"
  ["is-object"]="https://github.com/jonschlinkert/isobject"
  ["left-pad"]="https://github.com/left-pad/left-pad"
  ["concat-map"]="https://github.com/ljharb/concat-map"
  ["replace-ext"]="https://github.com/gulpjs/replace-ext"
  ["array-ify"]="https://github.com/stevemao/array-ify"
  ["just-pick"]="https://github.com/angus-c/just"
  ["just-filter-object"]="https://github.com/angus-c/just"
  ["primality"]="https://github.com/nbcl/primality"
)

for pkg in "${!REPOS[@]}"; do
  if [ ! -d "tests/$pkg" ]; then
    echo "Cloning $pkg..."
    git clone --depth 1 "${REPOS[$pkg]}" tests/$pkg 2>/dev/null || echo "Failed: $pkg"
  else
    echo "Already exists: $pkg"
  fi
done

echo "Done."
