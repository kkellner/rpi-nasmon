#!/bin/bash
#
# Get disk usage info and output in json - values are in bytes
#


df -Ph --block-size=1 | \
  jq -R -s '
    [
      split("\n") |
      .[] |
      if test("^/") then
        gsub(" +"; " ") | split(" ") | {dev: .[0], mount: .[5], spacetotal: .[1], spaceused: .[2], spaceavail: .[3]}
      else
        empty
      end
    ]'