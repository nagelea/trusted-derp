# Trusted DERP build

Build Tailscale's DERP relay and its userspace identity client together from pinned official source. Images are built and tested **in GitHub Actions**, then published to GHCR. The target architecture is Linux amd64.

This repository is independent of Tailscale. The word trusted describes the auditable build process; it is not a guarantee that the upstream software has no vulnerabilities.

## Build inputs and publication

- `source-lock.json` records the exact upstream commit, Go base image digest and GitHub Action commits.
- All three programs (`derper`, `tailscaled`, `tailscale`) come from the same source checkout.
- Go verifies downloaded modules against the upstream dependency lock files and checksum database.
- The final image uses `scratch`, contains no shell or package manager, and runs as UID/GID 65532.
- Builds include upstream revision, Go build information, module inventory and binary hashes under `/usr/share/derp/`.
- PRs and pushes to `main` build and test. A manual Actions run or `v*` release tag publishes **the exact tested image**.
- Publication uses the workflow's short-lived `GITHUB_TOKEN`. No personal access token is stored in this repository.
- The workflow creates GitHub artifact provenance for the published digest. Deploy by `ghcr.io/nagelea/trusted-derp@sha256:...`, not a floating `latest` tag.

In Actions, open **Build, test and publish DERP**, select **Run workflow**, then inspect the summary for the deployment digest. First publication can be private even when the repository is public; set the GHCR package visibility to public if anonymous pulls are intended.

Example provenance check with a locally authenticated GitHub CLI:

```bash
gh attestation verify oci://ghcr.io/nagelea/trusted-derp@sha256:ACTUAL_DIGEST \
  --repo nagelea/trusted-derp
```

The build is pinned and auditable. Bit-for-bit repeatability across independent builds has not been established.

## Deploy on a new Linux server

Install Docker Engine, Compose, Python 3 and OpenSSL. Open TCP443 and UDP3478 for DERP/STUN. Restrict SSH separately. A cloud provider's public IPv4 may be NAT-mapped to the host, so binding Docker to `0.0.0.0` is intentional.

1. Download this repository and verify the desired GHCR digest and its attestation.
2. Prepare per-instance data, using the real public IPv4 and actual image digest:

   ```bash
   sudo python3 scripts/prepare_host.py \
     --ip YOUR_PUBLIC_IPV4 \
     --image ghcr.io/nagelea/trusted-derp@sha256:ACTUAL_DIGEST
   docker compose pull
   docker compose up -d identity
   ```

3. Enroll the identity interactively in your existing Headscale server:

   ```bash
   docker compose exec identity /usr/local/bin/tailscale \
     --socket=/run/tailscale/tailscaled.sock up \
     --login-server=https://YOUR_HEADSCALE_SERVER \
     --hostname=your-derp-node --accept-dns=false --accept-routes=false --shields-up
   ```

   Follow the registration link and approve the new node on your Headscale host. No authorization key belongs in an image or in this repository. If automating enrollment, use a short-lived single-use key supplied through a temporary protected file and remove it afterwards.

4. Start DERP only after identity enrollment:

   ```bash
   docker compose up -d derper
   ```

5. Add the public IPv4 to the Headscale DERP map, using the exact `sha256-raw:` certificate pin printed by `prepare_host.py`, external DERP port443 and STUN port3478. Keep an existing fallback region while testing.
6. Verify real peer traffic, not just the root HTTPS page: use `tailscale ping`, application requests, and a negative test with an unregistered client. This deployment enables `-verify-clients` and uses the paired identity socket; an unenrolled identity must not be treated as a ready relay.

The public-IP certificate is generated on the server and is valid for30 days. Renew it deliberately before expiry, restart DERP and update the certificate pin in Headscale. A newly assigned IP requires the corresponding new certificate and map configuration.

## Runtime files

`prepare_host.py` creates `.env`, `certs/`, `data/` and `run/` with restrictive permissions. These contain per-server secrets or state and are ignored by Git. The Docker build context is an allowlist containing only the Dockerfile and dockerignore; those runtime directories cannot enter the build context.

The identity and DERP containers share a local Unix socket and run without additional Linux capabilities. Container listeners use unprivileged ports8443/13478, mapped to host443/3478, avoiding executable file capabilities. State is mounted separately from the read-only root filesystems.

## Tests and limits

The CI smoke test checks the runtime user, the paired client executable, pinned upstream build metadata, certificate-verified HTTPS204, the DERP101 protocol upgrade and server key frame, a real UDP STUN binding response, and Compose syntax. All temporary test ports bind to localhost.

The smoke test is a transport check and does not enroll a device into your production Headscale network. Authenticated forwarding and denial of unknown devices must also be checked when deploying to a real network. A successful build does not establish a particular cloud provider's route quality or guarantee GHCR download speed from that provider.

## Stop, rebuild and update

- Stop a deployment with `docker compose down`; this does not delete the retained data directories or cloud resources.
- For temporary cloud nodes, withdraw the map first and release the instance, disks and public IPs after use; Docker stop alone is not a complete cost stop.
- Retain the public image digest, repository and deployment method between trials. Generate per-instance secrets again on a new node.
- For an upstream upgrade, update the source commit/version and Go base digest together, refresh Action pins deliberately, then let Actions rebuild and run tests. Do not silently build upstream `latest` on every temporary server.

References: [official DERP source and pairing requirement](https://github.com/tailscale/tailscale/tree/main/cmd/derper), [GitHub container publication](https://docs.github.com/en/actions/tutorials/publish-packages/publish-docker-images), [artifact attestations](https://docs.github.com/en/actions/how-tos/secure-your-work/use-artifact-attestations).
