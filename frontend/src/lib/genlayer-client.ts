import { createClient } from "genlayer-js"
import { studionet } from "genlayer-js/chains"

const CONTRACT_ADDRESS =
  (process.env.NEXT_PUBLIC_CONTRACT_ADDRESS as `0x${string}`) || undefined

const RPC = process.env.NEXT_PUBLIC_RPC_URL || "https://studio.genlayer.com/api"

const CHAIN_ID = Number(process.env.NEXT_PUBLIC_CHAIN_ID || 61999)

/**
 * The chain the reads and writes are pointed at. The default is Studionet. A
 * local network, or another chain, only needs a different RPC url and id.
 */
function chainConfig() {
  return {
    ...studionet,
    chainId: CHAIN_ID,
    rpcUrls: { default: { http: [RPC] } },
  } as any
}

let readClient: ReturnType<typeof createClient> | null = null

/**
 * A client for reads. It never holds an account, so it can be created on the
 * server as well.
 */
export function getReadClient() {
  if (!readClient) {
    const client = createClient({
      chain: chainConfig(),
    })

    // Studionet allows thirty requests a minute. A burst of page reads can
    // cross that line, so a throttled read waits and tries again instead of
    // failing the page.
    const original = client.readContract.bind(client)
    client.readContract = async (args: any) => {
      let lastError: unknown
      for (let attempt = 0; attempt < 4; attempt++) {
        try {
          return await original(args)
        } catch (error) {
          lastError = error
          if (!isRateLimited(error) || attempt === 3) throw error
          const hinted = Number(
            (error as any)?.cause?.data?.retry_after_seconds ?? 0
          )
          const waitMs =
            (hinted > 0 ? hinted + 1 : 2 ** attempt * 5) * 1000
          await new Promise((resolve) => setTimeout(resolve, waitMs))
        }
      }
      throw lastError
    }

    readClient = client
  }
  return readClient
}

function isRateLimited(error: unknown): boolean {
  const message = String((error as any)?.message ?? error)
  const cause = String((error as any)?.cause?.message ?? "")
  return (
    message.includes("Rate limit") ||
    message.includes("-32029") ||
    cause.includes("Rate limit")
  )
}

/**
 * A client for writes. It signs with the browser wallet, so it needs both the
 * address and the injected provider.
 */
export function getWriteClient(address: `0x${string}`, provider: any) {
  return createClient({
    chain: chainConfig(),
    account: address,
    provider: wrapProvider(provider),
  })
}

/**
 * GenLayer does not use the EIP 1559 fee fields, and the injected providers
 * insist on filling them in. This strips them before the transaction is sent.
 */
function wrapProvider(provider: any) {
  if (!provider || provider.__glPatched) return provider
  const original = provider.request.bind(provider)

  provider.request = async (request: any) => {
    if (
      request?.method === "eth_sendTransaction" &&
      Array.isArray(request.params) &&
      request.params[0]
    ) {
      const transaction = { ...request.params[0] }
      transaction.type = "0x0"
      transaction.gasPrice = "0x0"
      delete transaction.maxFeePerGas
      delete transaction.maxPriorityFeePerGas
      if (!transaction.gas) transaction.gas = "0x100000"
      return original({ method: "eth_sendTransaction", params: [transaction] })
    }
    return original(request)
  }

  provider.__glPatched = true
  return provider
}

export function getContractAddress() {
  return CONTRACT_ADDRESS
}

export const CHAIN_CONFIG = {
  chainId: CHAIN_ID,
  name: RPC === "https://studio.genlayer.com/api" ? "Studionet" : "Local network",
  rpcUrl: RPC,
  currency: "GEN",
  explorerUrl: "https://explorer-studio.genlayer.com",
}
