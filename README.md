# StellarChain Directory

## What

A community-maintained directory of Stellar accounts, contracts, and assets. One CSV powers the public JSON API.

[Browse the CSV](directory.csv) · [Data sources and notices](NOTICE) · [Project license](LICENSE)

## How

### Query the API

| GET or HEAD | Result |
| --- | --- |
| [`/manifest.json`](https://directory.stellarchain.io/manifest.json) | Source commit, available networks, endpoints, counts, and download checksums |
| [`/schema.json`](https://directory.stellarchain.io/schema.json) | JSON Schema for the manifest, records, and bulk downloads |
| [`/mainnet/directory.json`](https://directory.stellarchain.io/mainnet/directory.json) | All mainnet address records |
| `/mainnet/addresses/{address}.json` | Look up one uppercase address. [Example lookup for the Burn Account](https://directory.stellarchain.io/mainnet/addresses/GALAXYVOIDAOPZTDLHILAJQKCVVFMD4IKLXLSZV5YHO7VY74IWZILUTO.json) |
| [`/mainnet/assets.json`](https://directory.stellarchain.io/mainnet/assets.json) | All mainnet classic asset records |
| `/mainnet/assets/{id}.json` | Look up `CODE-ISSUER` or [`native`](https://directory.stellarchain.io/mainnet/assets/native.json) for XLM |

Address types come from the Stellar address encoding. Soroban token contracts use their contract address. Classic assets use their code and issuer. [Stellar asset identities](https://developers.stellar.org/docs/learn/fundamentals/stellar-data-structures/assets)

An address with `role: "validator"` is a public Stellar consensus signing key. It may have no ledger account.

Each record has a `source` and a `verification` value for its label. A missing record returns `404`. In browsers, use ordinary `fetch(url)` and let the HTTP cache revalidate the response. Server clients can send the previous `ETag` as `If-None-Match` and reuse their saved response on `304`. Send a descriptive `User-Agent` from automated clients. [Browser cache behavior](https://developer.mozilla.org/en-US/docs/Web/API/Request/cache)

### Verification

| Value | What reviewers checked |
| --- | --- |
| `unverified` | No verification recorded |
| `first_party` | The project publishes the exact address or asset in its official documentation |
| `sep1_domain` | The account or issuer points to a domain whose `stellar.toml` lists the same account or exact asset |
| `stellarchain_verified` | StellarChain's published v4 account list marks the exact mainnet address and label as verified |

Verification describes the basis for the label. Contract build verification is defined separately by SEP-55. [SEP-1](https://github.com/stellar/stellar-protocol/blob/master/ecosystem/sep-0001.md) · [SEP-55](https://github.com/stellar/stellar-protocol/blob/master/ecosystem/sep-0055.md)

### Contribute an address

1. Open [directory.csv](directory.csv) and use GitHub's edit button.
2. Add or edit a row with `network,address,label,source,verification,asset_code,role`. Use `mainnet`, `testnet`, or `futurenet` and the full uppercase public address. For a community submission, use `community` and `unverified`. Put labels containing commas in double quotes.
3. Use `validator` in `role` for a published validator signing key. Leave `role` blank for other entries and `asset_code` blank for address records. For a classic asset, put the issuer in `address` and its code in `asset_code`. Use a blank issuer with `XLM` for the native asset.
4. Open a pull request using the [PR template](.github/PULL_REQUEST_TEMPLATE.md). Link to a public source that shows the exact identifier and supports the label. The checks summarize directory changes for reviewers. For SEP-1 verification changes, include the issuer's or account's public `stellar.toml` in [NOTICE](NOTICE) so the proof can be checked again.

Use an issue to [suggest a directory change](https://github.com/stellarchain/io.stellarchain.directory/issues/new?template=directory-change.yml) or [report an API problem](https://github.com/stellarchain/io.stellarchain.directory/issues/new?template=api-problem.yml).

## Why

Wallets, explorers, and researchers can look up a label without downloading the entire list. The CSV lets anyone inspect the entries and propose a correction.
