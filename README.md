# StellarChain Directory

## What

A community-maintained directory of public Stellar addresses and their labels. The list lives in one CSV file and is available through a public JSON API.

[Browse the CSV](directory.csv) · [Data sources and notices](NOTICE) · [Project license](LICENSE)

## How

### Query the API

| GET or HEAD | Result |
| --- | --- |
| [`/manifest.json`](https://stellarchain-directory.stellarchain.workers.dev/manifest.json) | Available networks, endpoints, counts, and download checksums |
| [`/mainnet/directory.json`](https://stellarchain-directory.stellarchain.workers.dev/mainnet/directory.json) | All mainnet records as a JSON array |
| `/mainnet/addresses/{address}.json` | Look up one uppercase address. [Example lookup for the Burn Account](https://stellarchain-directory.stellarchain.workers.dev/mainnet/addresses/GALAXYVOIDAOPZTDLHILAJQKCVVFMD4IKLXLSZV5YHO7VY74IWZILUTO.json) |

Each record has `network`, `address`, `type`, and a `label` when available. A missing address returns `404`. Use `ETag` with `If-None-Match` to revalidate cached responses. Automated clients should send a descriptive `User-Agent`. [Cloudflare client guidance](https://developers.cloudflare.com/support/troubleshooting/http-status-codes/cloudflare-1xxx-errors/error-1010/)

### Contribute an address

1. Open [directory.csv](directory.csv) and use GitHub's edit button.
2. Add or edit a row with `network,address,label`. Use `mainnet`, `testnet`, or `futurenet` and the full uppercase public address. Use one row per address per network. Put labels containing commas in double quotes.
3. Open a pull request using the [PR template](.github/PULL_REQUEST_TEMPLATE.md). Link to a public source that shows the address and supports the label. For corrections or removals, explain the change.

Use an issue to [suggest a directory change](https://github.com/stellarchain/io.stellarchain.directory/issues/new?template=directory-change.yml) or [report an API problem](https://github.com/stellarchain/io.stellarchain.directory/issues/new?template=api-problem.yml).

## Why

Wallets, explorers, and researchers can look up a label without downloading the entire list. The CSV lets anyone inspect the entries and propose a correction.
