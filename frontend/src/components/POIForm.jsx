import { useState } from 'react'

/**
 * POIForm — Modal form for naming a newly placed POI.
 * Shown when user double-clicks in the 3D scene while in "poi-select" mode.
 */
export default function POIForm({ position, onSubmit, onCancel }) {
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [saving, setSaving] = useState(false)

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!name.trim()) return
    setSaving(true)
    await onSubmit({
      name: name.trim(),
      description: description.trim() || null,
      x: position.x,
      y: position.y,
      z: position.z,
    })
    setSaving(false)
  }

  return (
    <div style={styles.overlay}>
      <div style={styles.modal}>
        <h3 style={styles.title}>📍 New Point of Interest</h3>

        <div style={styles.coords}>
          x: {position.x.toFixed(2)} &nbsp; y: {position.y.toFixed(2)} &nbsp; z: {position.z.toFixed(2)}
        </div>

        <form onSubmit={handleSubmit} style={styles.form}>
          <label style={styles.label}>Name *</label>
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="e.g. Main Entrance"
            style={styles.input}
            autoFocus
            required
          />

          <label style={styles.label}>Description</label>
          <textarea
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="Optional description…"
            rows={3}
            style={{ ...styles.input, resize: 'vertical' }}
          />

          <div style={styles.btnRow}>
            <button
              type="button"
              onClick={onCancel}
              style={{ ...styles.btn, ...styles.cancelBtn }}
              disabled={saving}
            >
              Cancel
            </button>
            <button
              type="submit"
              style={{ ...styles.btn, ...styles.saveBtn }}
              disabled={saving || !name.trim()}
            >
              {saving ? 'Saving…' : 'Save POI'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

const styles = {
  overlay: {
    position: 'fixed',
    inset: 0,
    background: 'rgba(0,0,0,0.7)',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    zIndex: 1000,
    backdropFilter: 'blur(4px)',
  },
  modal: {
    background: '#111827',
    border: '1px solid #1e4080',
    borderRadius: 12,
    padding: '24px 28px',
    minWidth: 340,
    maxWidth: 420,
    width: '90vw',
    boxShadow: '0 20px 60px rgba(0,0,0,0.8)',
  },
  title: {
    color: '#00bfff',
    fontSize: 18,
    fontWeight: 700,
    marginBottom: 8,
  },
  coords: {
    fontSize: 11,
    color: '#556',
    fontFamily: 'monospace',
    marginBottom: 16,
  },
  form: {
    display: 'flex',
    flexDirection: 'column',
    gap: 10,
  },
  label: {
    fontSize: 12,
    color: '#aaa',
    fontWeight: 600,
    marginBottom: -6,
  },
  input: {
    background: '#1a2233',
    border: '1px solid #2a3a5a',
    borderRadius: 6,
    color: '#e0e0e0',
    padding: '10px 12px',
    fontSize: 14,
    outline: 'none',
    width: '100%',
    boxSizing: 'border-box',
  },
  btnRow: {
    display: 'flex',
    gap: 10,
    marginTop: 8,
    justifyContent: 'flex-end',
  },
  btn: {
    padding: '9px 20px',
    borderRadius: 7,
    fontSize: 13,
    fontWeight: 600,
    cursor: 'pointer',
    border: 'none',
    transition: 'opacity 0.15s',
  },
  cancelBtn: {
    background: '#1a2233',
    color: '#888',
    border: '1px solid #2a3a5a',
  },
  saveBtn: {
    background: '#0d3060',
    color: '#00bfff',
    border: '1px solid #00bfff',
  },
}
