"use client"

/**
 * Finding the wallet, without a fight.
 *
 * Several extensions inject into the same `window.ethereum`. Whoever injected
 * last wins the global, so a page that reads `window.ethereum` on every call
 * can end up talking to a different wallet than the one the user picked.
 *
 * The rules here:
 *
 * 1. Collect every provider we can find, from `window.ethereum.providers`,
 *    from the EIP 6963 announcements and from the well known globals.
 * 2. Ask EIP 6963 providers to identify themselves, and listen for the
 *    announcements that arrive after page load.
 * 3. Once the user picks one, lock that exact provider object. Every later
 *    signing call uses the locked object, never `window.ethereum` again.
 * 4. React to `accountsChanged` and `chainChanged` on the locked provider only.
 */

export interface DetectedWallet {
  id: string
  name: string
  provider: any
}

declare global {
  interface Window {
    ethereum?: any
    rabby?: any
  }
}

const announced = new Map<string, any>()

/** EIP 6963: wallets announce themselves, they do not fight over a global. */
function listenForAnnouncements() {
  if (typeof window === "undefined") return
  const onAnnounce = (event: any) => {
    const info = event?.detail
    if (!info?.provider || !info?.uuid) return
    announced.set(info.uuid, info)
  }
  window.addEventListener?.("eip6963:announceProvider", onAnnounce)
  window.dispatchEvent?.(new Event("eip6963:requestProvider"))
}

function labelFor(provider: any): string {
  if (provider?.isRabby) return "Rabby"
  if (provider?.isCoinbaseWallet) return "Coinbase Wallet"
  if (provider?.isMetaMask) return "MetaMask"
  if (provider?.isBraveWallet) return "Brave Wallet"
  if (provider?.isTrust) return "Trust Wallet"
  if (provider?.isPhantom) return "Phantom"
  if (provider?.isOKXWallet) return "OKX Wallet"
  return "Browser Wallet"
}

function identityFor(provider: any): string {
  if (provider?.isRabby) return "Rabby"
  if (provider?.isCoinbaseWallet) return "Coinbase Wallet"
  if (provider?.isMetaMask) return "MetaMask"
  if (provider?.isBraveWallet) return "Brave Wallet"
  if (provider?.isTrust) return "Trust Wallet"
  if (provider?.isPhantom) return "Phantom"
  if (provider?.isOKXWallet) return "OKX Wallet"
  return "Browser Wallet"
}

/** Every provider we can see, de-duplicated by identity and by object. */
export function detectWallets(): DetectedWallet[] {
  if (typeof window === "undefined") return []

  const found: DetectedWallet[] = []
  const seenNames = new Set<string>()
  const seenObjects = new Set<any>()

  const push = (provider: any, name?: string) => {
    if (!provider || typeof provider.request !== "function") return
    if (seenObjects.has(provider)) return
    seenObjects.add(provider)
    const identity = name ?? identityFor(provider)
    if (seenNames.has(identity)) return
    seenNames.add(identity)
    found.push({ id: identity, name: name ?? identity, provider })
  }

  // EIP 6963 announcements win, they are the standard way.
  for (const info of announced.values()) {
    push(info.provider, info.name ?? labelFor(info.provider))
  }

  // The multi provider array, when an extension keeps them apart.
  const list = window.ethereum?.providers
  if (Array.isArray(list)) {
    for (const provider of list) push(provider)
  }

  // The well known globals.
  if (window.rabby) push(window.rabby, "Rabby")
  if (window.ethereum) push(window.ethereum)

  return found
}

/** The provider the user picked, or the only one there is. */
export function defaultProvider(): DetectedWallet | null {
  const wallets = detectWallets()
  if (wallets.length === 0) return null
  if (wallets.length === 1) return wallets[0]
  return null
}

export { listenForAnnouncements }
