#!/usr/bin/env bash
# Long-running relay: poll the branch for a new task id, run ci/task.sh, push base64 log back.
set -u
BR="arena/725ba00e-cft22"
last=""
mkdir -p ci/out
while true; do
  if git fetch -q origin "$BR" && git reset -q --hard FETCH_HEAD; then :; else sleep 5; continue; fi
  id="$(cat ci/task.id 2>/dev/null | tr -d '[:space:]')"
  if [ -n "$id" ] && [ "$id" != "$last" ]; then
    echo "== running task $id ==" >&2
    ( cd ci && bash task.sh ) 2>&1 | tee /tmp/task.out | base64 -w0 > "ci/out/$id.log"
    echo "exit=$?" >> /tmp/task.out
    printf '%s\n' "EXITCODE:${PIPESTATUS[0]}" > /tmp/ex
    cat /tmp/ex | base64 -w0 >> "ci/out/$id.log"
    last="$id"
    ok=0
    for i in 1 2 3 4 5 6; do
      git add -A ci/out >/dev/null 2>&1
      git commit -q -m "out $id" >/dev/null 2>&1 || true
      git pull -q --rebase origin "$BR" >/dev/null 2>&1 || true
      if git push -q origin "HEAD:$BR" >/dev/null 2>&1; then ok=1; break; fi
      sleep 3
    done
    echo "== task $id done push_ok=$ok ==" >&2
  fi
  sleep 4
done
