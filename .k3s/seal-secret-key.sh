#!/usr/bin/env bash
# Seals a fresh SECRET_KEY twice and writes both into .k3s/values.yaml:
# once for the "relay" namespace (production), once --scope cluster-wide with a
# different, throwaway key (previews run in relay-pr-N and cannot read the first).
#
# Needs kubectl pointed at the k3s cluster, kubeseal and yq (mikefarah, v4).
# Without them installed: nix shell nixpkgs#kubectl nixpkgs#kubeseal nixpkgs#yq-go
#
# The first SECRET_KEY line in values.yaml is production's, the second the previews'.
#
# Rerunning rotates both keys, which logs everyone out. Restart afterwards:
#   kubectl rollout restart statefulset/relay -n relay
set -euo pipefail

cd "$(dirname "$0")"
values=values.yaml

for tool in kubectl kubeseal yq openssl; do
  command -v "$tool" >/dev/null || { echo "missing: $tool" >&2; exit 1; }
done

echo "kubectl context: $(kubectl config current-context)"
kubectl get deploy -n kube-system sealed-secrets-controller >/dev/null \
  || { echo "no sealed-secrets-controller in kube-system: wrong cluster?" >&2; exit 1; }

seal() { # namespace, extra kubeseal args...
  local ns=$1; shift
  kubectl create secret generic relay-secrets -n "$ns" \
    --from-literal=SECRET_KEY="$(openssl rand -hex 32)" \
    --dry-run=client -o yaml \
  | kubeseal --controller-name sealed-secrets-controller --controller-namespace kube-system \
      --format yaml "$@" \
  | yq '.spec.encryptedData.SECRET_KEY'
}

prod=$(seal relay)
preview=$(seal placeholder --scope cluster-wide)

# Line by line rather than yq -i, which would reflow the rest of the file.
[ "$(grep -c '^ *SECRET_KEY: ' "$values")" = 2 ] \
  || { echo "expected exactly two SECRET_KEY lines in $values" >&2; exit 1; }
PROD="$prod" PREVIEW="$preview" awk '
  /^ *SECRET_KEY: / { n++; sub(/SECRET_KEY: .*/, "SECRET_KEY: " (n == 1 ? ENVIRON["PROD"] : ENVIRON["PREVIEW"])) }
  { print }
' "$values" > "$values.tmp" && mv "$values.tmp" "$values"

echo "sealed both SECRET_KEY values into $values; commit and push it"
