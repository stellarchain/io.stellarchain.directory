import csv
import hashlib
import json
import sys
import tempfile
import unittest
from base64 import b32encode
from binascii import crc_hqx
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from build import build, collect
from strkey import address_type


ACCOUNT = "GA7QYNF7SOWQ3GLR2BGMZEHXAVIRZA4KVWLTJJFC7MGXUA74P7UJVSGZ"
CONTRACT = "CA7QYNF7SOWQ3GLR2BGMZEHXAVIRZA4KVWLTJJFC7MGXUA74P7UJUWDA"
MUXED_ACCOUNT = "MA7QYNF7SOWQ3GLR2BGMZEHXAVIRZA4KVWLTJJFC7MGXUA74P7UJVAAAAAAAAAAAAAJLK"
MUXED_CONTRACT = "WA7QYNF7SOWQ3GLR2BGMZEHXAVIRZA4KVWLTJJFC7MGXUA74P7UJUAAAAAAAAAAAAAWWC"


class DirectoryTest(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)

    def put(self, rows):
        path = self.root / "directory.csv"
        with path.open("w", encoding="utf-8", newline="") as output:
            writer = csv.writer(output)
            writer.writerow(("network", "address", "label", "source", "verification", "asset_code"))
            writer.writerows(rows)
        return path

    def test_strkey_types_and_rejections(self):
        for address, kind in (
            (ACCOUNT, "account"), (CONTRACT, "contract"),
            (MUXED_ACCOUNT, "muxed_account"), (MUXED_CONTRACT, "muxed_contract"),
        ):
            self.assertEqual(address_type(address), kind)

        synthetic_seed = bytes([18 << 3]) + bytes(32)
        seed = b32encode(synthetic_seed + crc_hqx(synthetic_seed, 0).to_bytes(2, "little")).decode("ascii")
        for address in (ACCOUNT[:-1] + "A", ACCOUNT.lower(), MUXED_CONTRACT[:-1] + "D", seed):
            with self.assertRaises(ValueError):
                address_type(address)

    def test_csv_lookup_and_bulk_integrity(self):
        source = self.put([
            ("mainnet", ACCOUNT, "Example, Inc.", "community", "unverified", ""),
            ("mainnet", CONTRACT, "", "stellar-expert", "unverified", ""),
            ("testnet", ACCOUNT, "Testnet label", "community", "sep1_domain", ""),
        ])
        dist = self.root / "dist"
        build(source, dist)
        self.assertTrue((dist / "manifest.json").is_file())
        manifest = json.loads((dist / "manifest.json").read_bytes())
        bulk = (dist / "mainnet/directory.json").read_bytes()
        lookup = json.loads((dist / f"mainnet/addresses/{ACCOUNT}.json").read_bytes())
        mainnet = manifest["networks"]["mainnet"]
        self.assertEqual(set(manifest), {"networks"})
        self.assertEqual(mainnet["directory"], "/mainnet/directory.json")
        self.assertEqual(mainnet["lookup"], "/mainnet/addresses/{address}.json")
        self.assertEqual(mainnet["sha256"], hashlib.sha256(bulk).hexdigest())
        self.assertEqual(mainnet["bytes"], len(bulk))
        self.assertEqual(mainnet["count"], 2)
        self.assertEqual(json.loads(bulk)[1], lookup)
        self.assertEqual(lookup["label"], "Example, Inc.")
        self.assertEqual(lookup["source"], "community")
        self.assertEqual(lookup["verification"], "unverified")
        self.assertEqual(set(lookup), {"network", "address", "type", "label", "source", "verification"})
        self.assertNotIn("label", json.loads(bulk)[0])
        self.assertEqual(manifest["networks"]["testnet"]["count"], 1)

        self.put([("testnet", ACCOUNT, "Testnet label", "community", "sep1_domain", "")])
        build(source, dist)
        self.assertFalse((dist / "mainnet").exists())

    def test_rejects_duplicate_addresses_and_nonpublic_fields(self):
        row = ("mainnet", ACCOUNT, "Example", "community", "unverified", "")
        source = self.put([row, row])
        with self.assertRaisesRegex(ValueError, "duplicate address"):
            collect(source)
        self.put([row + ("unexpected field",)])
        with self.assertRaisesRegex(ValueError, "expected 6 columns"):
            collect(source)

    def test_classic_assets_keep_their_own_identity(self):
        source = self.put([
            ("mainnet", ACCOUNT, "Example issuer", "community", "sep1_domain", ""),
            ("mainnet", ACCOUNT, "Example asset", "community", "sep1_domain", "USD"),
            ("mainnet", "", "Stellar Lumen", "stellar", "first_party", "XLM"),
        ])
        dist = self.root / "dist"
        build(source, dist)
        root = dist / "mainnet"
        manifest = json.loads((dist / "manifest.json").read_bytes())["networks"]["mainnet"]
        payload = (root / "assets.json").read_bytes()
        asset, native = json.loads(payload)
        self.assertEqual(manifest["count"], 1)
        self.assertEqual(manifest["assets"]["count"], 2)
        self.assertEqual(manifest["assets"]["sha256"], hashlib.sha256(payload).hexdigest())
        self.assertEqual(asset["id"], "USD-" + ACCOUNT)
        self.assertEqual(asset["issuer"], ACCOUNT)
        self.assertEqual(asset["type"], "asset")
        self.assertEqual(native["id"], "native")
        self.assertIsNone(native["issuer"])
        self.assertEqual(json.loads((root / "assets" / f"{asset['id']}.json").read_bytes()), asset)
        self.assertTrue((root / "addresses" / f"{ACCOUNT}.json").is_file())

    def test_rejects_invalid_asset_and_verification_combinations(self):
        source = self.put([("mainnet", CONTRACT, "Bad issuer", "community", "unverified", "USD")])
        with self.assertRaisesRegex(ValueError, "asset issuer must be an account"):
            collect(source)
        self.put([("mainnet", CONTRACT, "Bad proof", "community", "sep1_domain", "")])
        with self.assertRaisesRegex(ValueError, "SEP-1 domain verification requires an account or asset issuer"):
            collect(source)
        self.put([("mainnet", ACCOUNT, "", "community", "first_party", "")])
        with self.assertRaisesRegex(ValueError, "verification requires a label"):
            collect(source)
        self.put([("mainnet", ACCOUNT, "Example", "private-screening", "unverified", "")])
        with self.assertRaisesRegex(ValueError, "unknown public source"):
            collect(source)
