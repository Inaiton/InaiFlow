# OmniRoute (opt-in local LLM gateway)

Optional. Nothing in this repo starts it, and it is **not** wired into Claude Code or any hook.

**Read first:** requests sent through OmniRoute go to whichever third-party providers you connect in its dashboard,
so any code or data in those prompts leaves your machine. Do not route this codebase through providers you would not
send it to directly. The project also advertises TLS-fingerprint spoofing to avoid provider bans; check each
provider's terms before connecting an account.

```powershell
cd tools/omniroute
copy .env.example .env        # then set OMNIROUTE_PASSWORD to a long random string
docker compose up -d          # http://127.0.0.1:20128 (loopback only)
docker compose down           # stop (data stays in the omniroute-data volume)
```

- Image: `diegosouzapw/omniroute`, pinned by version and digest in `docker-compose.yml` (published by the same
  maintainer as the npm package; upstream source is `cheaper-inference/OmniRoute`). Bump the pin by hand after checking
  the release; it is not part of the weekly `ai-tools-update` job.
- Dashboard: sign in with `OMNIROUTE_PASSWORD`, add providers (OAuth or API keys), then create a gateway key under
  Endpoints. API clients call `http://127.0.0.1:20128/v1` with that key; without one the API returns 401.
- Never publish the port beyond `127.0.0.1`, and do not enable its public tunnel without real auth.
