import type { Metadata } from "next"
import { Inter } from "next/font/google"

import "./globals.css"
import { Header } from "@/components/Header"
import { WalletProvider } from "@/lib/WalletContext"

const inter = Inter({ subsets: ["latin"], variable: "--font-inter" })

export const metadata: Metadata = {
  title: "Cite — prediction markets settled by evidence",
  description:
    "Weather prediction markets on GenLayer. Every settlement cites the web, and the contract verifies that the quote is really there.",
}

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" className="dark">
      <body className={`${inter.variable} min-h-screen bg-[#0A0C11] antialiased`}>
        <WalletProvider>
          <Header />
          <main className="relative z-10">{children}</main>
        </WalletProvider>
      </body>
    </html>
  )
}
