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
        gsub(" +"; " ") | split(" ") | {mount: .[0], spacetotal: .[1], spaceused: .[2], spaceavail: .[3], spaceusedpercent: .[4]}
      else
        empty
      end
    ]'