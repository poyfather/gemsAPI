// Writes the Lapidary Helper's allowlist from the console's own catalog:
// every component and toolbox entry that installs from winget or the PowerShell
// Gallery. The helper (desktop/helper/lapidary_helper.py) installs nothing else.
//
//   node scripts/allowlist.mjs ../build/lapidary-helper/allowlist.json
//
// LAPIDARY_PUBLISHER, when set, is the code-signing subject the helper requires
// on a console update before it runs it (see README, "Code signing").

import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { buildAllowlist } from "../lib/helper.js";

const here = dirname(fileURLToPath(import.meta.url));

const out = process.argv[2] || join(here, "..", "..", "build", "lapidary-helper", "allowlist.json");
const version = JSON.parse(readFileSync(join(here, "..", "package.json"), "utf8")).version;
const list = buildAllowlist({ version, publisher: process.env.LAPIDARY_PUBLISHER || "" });
mkdirSync(dirname(out), { recursive: true });
writeFileSync(out, JSON.stringify(list, null, 2) + "\n");
console.log(`wrote ${Object.keys(list.packages).length} packages to ${out}`);
