# Cite — frontend

The web app for the Cite weather prediction markets.

## Stack

Next.js 14 (App Router) · React 18 · TypeScript · Tailwind CSS v3 · shadcn
conventions (`src/components/ui`) · `genlayer-js` for the chain.

## Run it

```bash
npm install
cp .env.example .env.local     # point it at the deployed contract
npm run dev
```

| route | what it shows |
|---|---|
| `/` | the animated backdrop, the open board and how the last market was settled |
| `/markets` | the whole board, grouped by status |
| `/markets/[id]` | the measurement spec, the event spec, the odds, the bet panel and the citation trail |
| `/settlements` | every settlement, with the quotes the committee relied on |

## The backdrop

`src/components/ui/modern-background-paths.tsx` draws four layers that rotate
every eleven seconds:

| layer | what it stands for |
|---|---|
| radar | the field the committee reads |
| committee | the validators that have to agree |
| pressure | the locked measurement |
| wind | how the evidence moves |

Every path comes from a fixed seed, so the server and the browser draw exactly
the same picture and React never sees a hydration mismatch. The component also
honours `prefers-reduced-motion`.

## Wiring it to a contract

`src/lib/cite.ts` is a typed one to one mapping onto the public methods of
`contracts/cite.py`. `src/lib/genlayer-client.ts` holds the studionet client
and strips the EIP 1559 fee fields, which the injected providers insist on
adding but GenLayer does not use.

`src/lib/WalletContext.tsx` connects the browser wallet. It is deliberately
thinner than the one in `betcle`: Cite has no user registry, so there is no
registration step.
