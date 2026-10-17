import { rmSync } from 'node:fs'
const path = process.env.DB_PATH?.trim() || './payments.db'
for (const f of [path, `${path}-wal`, `${path}-shm`]) rmSync(f, { force: true })
console.log('database removed')
