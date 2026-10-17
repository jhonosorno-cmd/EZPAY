import { useEffect, useState, type FormEvent } from "react"
import { ApiError, addContact, deleteContact, getContacts, messageFor } from "../api/client"
import type { Contact } from "../api/types"

// Agenda de contactos: la voz solo puede pagar a quien esté aquí (SEG-4). La billetera se valida
// en Python contra Open Payments al guardar; aquí solo se muestra el resultado.
export function Contacts({ onClose }: { onClose: () => void }) {
  const [contacts, setContacts] = useState<Contact[] | null>(null)
  const [name, setName] = useState("")
  const [wallet, setWallet] = useState("")
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)
  const [confirming, setConfirming] = useState<string | null>(null)

  const load = () =>
    getContacts().then((r) => setContacts(r.contacts)).catch((e) => {
      setContacts([])
      setError(messageFor(e instanceof ApiError ? e.code : "UNKNOWN"))
    })

  useEffect(() => { void load() }, [])

  const submit = async (e: FormEvent) => {
    e.preventDefault()
    if (!name.trim() || !wallet.trim() || busy) return
    setBusy(true)
    setError(null)
    setNotice(null)
    try {
      const c = await addContact(name.trim(), wallet.trim())
      setNotice(`Listo, agregué a ${c.name}. Ya puedes decir: “envíale veinte mil a ${c.name}”.`)
      setName("")
      setWallet("")
      await load()
    } catch (err) {
      setError(messageFor(err instanceof ApiError ? err.code : "UNKNOWN"))
    } finally {
      setBusy(false)
    }
  }

  const remove = async (alias: string) => {
    setBusy(true)
    setError(null)
    setNotice(null)
    try {
      await deleteContact(alias)
      setConfirming(null)
      await load()
    } catch (err) {
      setError(messageFor(err instanceof ApiError ? err.code : "UNKNOWN"))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="app">
      <header className="topbar enroll-top">
        <button className="back" aria-label="Volver" onClick={onClose}>←</button>
        <p className="brand">MIS CONTACTOS</p>
        <span />
      </header>

      <main className="content">
        <section className="panel" aria-labelledby="contacts-title">
          <h2 id="contacts-title">Personas a las que puedes enviar</h2>
          {contacts === null && <p className="muted">Cargando…</p>}
          {contacts?.length === 0 && <p className="muted">Todavía no tienes contactos. Agrega el primero abajo.</p>}
          {contacts && contacts.length > 0 && (
            <ul className="contact-list">
              {contacts.map((c) => (
                <li key={c.alias}>
                  <div className="contact-info">
                    <p className="contact-name">{c.name}</p>
                    <p className="contact-wallet">{c.walletAddress.replace(/^https:\/\//, "")}</p>
                  </div>
                  {confirming === c.alias ? (
                    <div className="contact-actions">
                      <button className="chip chip-danger" disabled={busy} onClick={() => remove(c.alias)}>Borrar</button>
                      <button className="chip" disabled={busy} onClick={() => setConfirming(null)}>No</button>
                    </div>
                  ) : (
                    <button className="chip" aria-label={`Borrar a ${c.name}`} disabled={busy}
                      onClick={() => setConfirming(c.alias)}>✕</button>
                  )}
                </li>
              ))}
            </ul>
          )}
        </section>

        <form className="panel" onSubmit={submit} aria-labelledby="add-title">
          <h2 id="add-title">Agregar contacto</h2>
          <label className="field">
            <span>Nombre</span>
            <input value={name} onChange={(e) => setName(e.target.value)} placeholder="Laura" autoComplete="off"
              maxLength={40} required />
          </label>
          <label className="field">
            <span>Dirección de su billetera</span>
            <input value={wallet} onChange={(e) => setWallet(e.target.value)} inputMode="url" autoComplete="off"
              placeholder="https://ilp.interledger-test.dev/laura" required />
          </label>
          {error && <p className="warn" role="alert">{error}</p>}
          {notice && <p className="ok-note" role="status">{notice}</p>}
          <button className="pill pill-primary" type="submit" disabled={busy || !name.trim() || !wallet.trim()}>
            {busy ? "Revisando la billetera…" : "Guardar contacto"}
          </button>
        </form>
      </main>
    </div>
  )
}
