/**
 * A bridge between the integration tests and the frontend.
 *
 * The tests do not talk to the chain themselves when they check the frontend.
 * They call this script, which uses the very same read layer the pages use
 * (`src/lib/cite.ts`), and compare what comes back with what the contract
 * says. If the interface renames a field, drops a conversion or changes a
 * number into a string, this is where it shows up.
 *
 *   npx tsx scripts/contract-read.ts market 0
 *   npx tsx scripts/contract-read.ts odds 0
 *   npx tsx scripts/contract-read.ts citations 0
 *   npx tsx scripts/contract-read.ts accounting
 *   npx tsx scripts/contract-read.ts count
 *
 * The contract and the network come from the environment, so the same script
 * reads Studionet and a local network.
 */
import { existsSync } from "node:fs"
import { join } from "node:path"

// Next.js loads `.env.local` for the pages. This script runs outside Next, so
// it loads the same file itself. Variables already in the environment win, so
// the tests can point the script at a local network without touching a file.
const envFile = join(process.cwd(), ".env.local")
if (existsSync(envFile)) {
  process.loadEnvFile(envFile)
}

function serialise(value: unknown): string {
  return JSON.stringify(value, (_key, item) =>
    typeof item === "bigint" ? item.toString() : item
  )
}

async function main() {
  const {
    getAccounting,
    getCitations,
    getMarket,
    getMarketCount,
    getMarketOdds,
    getPendingPayouts,
  } = await import("../src/lib/cite")

  const [command, argument] = process.argv.slice(2)

  switch (command) {
    case "market": {
      const market = await getMarket(Number(argument))
      return serialise(market)
    }
    case "odds": {
      const odds = await getMarketOdds(Number(argument))
      return serialise(odds)
    }
    case "citations": {
      const trail = await getCitations(Number(argument))
      return serialise(trail)
    }
    case "accounting": {
      const accounting = await getAccounting()
      return serialise(accounting)
    }
    case "count": {
      return serialise(await getMarketCount())
    }
    case "pending": {
      return serialise(await getPendingPayouts())
    }
    default: {
      process.stderr.write(
        "usage: contract-read <market|odds|citations|accounting|count|pending> [market_id]\n"
      )
      process.exitCode = 2
      return ""
    }
  }
}

main().then(
  (output) => {
    process.stdout.write(output)
  },
  (error) => {
    process.stderr.write(
      `${error instanceof Error ? error.stack ?? error.message : String(error)}\n`
    )
    process.exitCode = 1
  }
)
