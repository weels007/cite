"use client"

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react"

import {
  defaultProvider,
  detectWallets,
  listenForAnnouncements,
  type DetectedWallet,
} from "@/lib/wallets"

const EXPECTED_CHAIN_ID = 61999

interface WalletContextValue {
  address: string | null
  provider: any | null
  chainId: number | null
  wrongChain: boolean
  loading: boolean
  available: DetectedWallet[]
  connectWallet: (wallet?: DetectedWallet) => Promise<boolean>
  disconnectWallet: () => void
}

const WalletContext = createContext<WalletContextValue>({
  address: null,
  provider: null,
  chainId: null,
  wrongChain: false,
  loading: true,
  available: [],
  connectWallet: async () => false,
  disconnectWallet: () => {},
})

export function useWallet() {
  return useContext(WalletContext)
}

export function WalletProvider({ children }: { children: ReactNode }) {
  const [address, setAddress] = useState<string | null>(null)
  const [provider, setProvider] = useState<any | null>(null)
  const [chainId, setChainId] = useState<number | null>(null)
  const [available, setAvailable] = useState<DetectedWallet[]>([])
  const [loading, setLoading] = useState(true)

  // The provider the user picked. We keep the object itself, so a second
  // extension cannot take the connection away from under us.
  const [locked, setLocked] = useState<DetectedWallet | null>(null)

  const refreshAvailable = useCallback(() => {
    setAvailable(detectWallets())
  }, [])

  useEffect(() => {
    listenForAnnouncements()
    refreshAvailable()
    // Some extensions announce themselves a moment after load.
    const timer = setTimeout(refreshAvailable, 600)
    const second = setTimeout(refreshAvailable, 1800)
    return () => {
      clearTimeout(timer)
      clearTimeout(second)
    }
  }, [refreshAvailable])

  const connectWallet = useCallback(
    async (wallet?: DetectedWallet): Promise<boolean> => {
      const target = wallet ?? defaultProvider()
      if (!target) {
        refreshAvailable()
        return false
      }
      try {
        const accounts: string[] = await target.provider.request({
          method: "eth_requestAccounts",
        })
        if (!accounts || accounts.length === 0) return false

        const idHex: string = await target.provider.request({
          method: "eth_chainId",
        })

        setLocked(target)
        setProvider(target.provider)
        setAddress(accounts[0])
        setChainId(Number(idHex))
        return true
      } catch (error) {
        console.error("Failed to connect the wallet:", error)
        return false
      }
    },
    [refreshAvailable]
  )

  const disconnectWallet = useCallback(() => {
    setLocked(null)
    setProvider(null)
    setAddress(null)
    setChainId(null)
  }, [])

  // Listen on the locked provider only, so another extension cannot switch
  // the account underneath the user.
  useEffect(() => {
    if (!locked?.provider?.on) return

    const onAccountsChanged = (accounts: string[]) => {
      if (!accounts || accounts.length === 0) {
        disconnectWallet()
        return
      }
      setAddress(accounts[0])
    }
    const onChainChanged = (id: string) => {
      setChainId(Number(id))
    }

    locked.provider.on("accountsChanged", onAccountsChanged)
    locked.provider.on("chainChanged", onChainChanged)

    return () => {
      locked.provider.removeListener?.("accountsChanged", onAccountsChanged)
      locked.provider.removeListener?.("chainChanged", onChainChanged)
    }
  }, [locked, disconnectWallet])

  // Reconnect silently on a reload, when there is exactly one wallet.
  useEffect(() => {
    let cancelled = false
    async function restore() {
      const candidate = defaultProvider()
      if (!candidate) {
        setLoading(false)
        return
      }
      try {
        const accounts: string[] = await candidate.provider.request({
          method: "eth_accounts",
        })
        if (cancelled) return
        if (accounts && accounts.length > 0) {
          const idHex: string = await candidate.provider.request({
            method: "eth_chainId",
          })
          if (cancelled) return
          setLocked(candidate)
          setProvider(candidate.provider)
          setAddress(accounts[0])
          setChainId(Number(idHex))
        }
      } catch {
        /* nothing to restore */
      } finally {
        if (!cancelled) setLoading(false)
      }
    }
    restore()
    return () => {
      cancelled = true
    }
  }, [])

  const value = useMemo(
    () => ({
      address,
      provider,
      chainId,
      wrongChain: chainId !== null && chainId !== EXPECTED_CHAIN_ID,
      loading,
      available,
      connectWallet,
      disconnectWallet,
    }),
    [address, provider, chainId, loading, available, connectWallet, disconnectWallet]
  )

  return (
    <WalletContext.Provider value={value}>{children}</WalletContext.Provider>
  )
}
