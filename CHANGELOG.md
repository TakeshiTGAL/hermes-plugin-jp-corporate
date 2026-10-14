# Changelog

## 0.1.1

`GBIZINFO_API_TOKEN` was read from `os.environ` on each request and when checking whether a token is configured. One Hermes process can serve more than one profile, so that read can use another profile's token. Each call now reads it with `agent.secret_scope.get_secret`. An HTTP proxy set in the environment is not used for gBizINFO requests, so a machine that can reach the network only through that proxy can no longer reach the API. Each profile needs its own `GBIZINFO_API_TOKEN` in that profile's `.env` (`~/.hermes/.env` for the default profile, `~/.hermes/profiles/<name>/.env` for a named profile). Tool results and error text do not include the token value. `plugin.yaml` now declares `requires_hermes: >=0.21.4`, the floor the catalog entry already had. Installing this repository on Hermes older than 0.21.4 now fails that check; catalog installs were already held to the same floor. This version is tested on Hermes 0.21.4 and later.
