import { useState, useEffect } from 'react';
import { Plus, Trash2, Save, RefreshCw, Package, Map, Sliders } from 'lucide-react';

const getBase = () => {
  const origin = window.location.origin;
  const basePath = (import.meta.env.BASE_URL || '/');
  return origin + (basePath.endsWith('/') ? basePath.slice(0, -1) : basePath);
};

function CouriersSection({ token }) {
  const [couriers, setCouriers] = useState([]);
  const [newCourier, setNewCourier] = useState('');
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState('');

  useEffect(() => {
    loadCouriers();
  }, []);

  const loadCouriers = async () => {
    try {
      const r = await fetch(`${getBase()}/api/couriers`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      if (r.ok) setCouriers(await r.json());
    } catch {}
  };

  const persistCouriers = async (list) => {
    setSaving(true);
    setMsg('');
    try {
      const r = await fetch(`${getBase()}/api/couriers`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
        body: JSON.stringify(list),
      });
      if (r.ok) setMsg('Saved!');
      else setMsg('Save failed.');
    } catch (e) {
      setMsg('Error: ' + e.message);
    } finally {
      setSaving(false);
      setTimeout(() => setMsg(''), 3000);
    }
  };

  const addCourier = () => {
    const name = newCourier.trim();
    if (!name || couriers.includes(name)) return;
    const updated = [...couriers, name];
    setCouriers(updated);
    setNewCourier('');
    persistCouriers(updated);
  };

  const removeCourier = (name) => {
    const updated = couriers.filter(c => c !== name);
    setCouriers(updated);
    persistCouriers(updated);
  };

  return (
    <div className="settings-section">
      <h3><Package size={18} /> Standard Couriers</h3>
      <p className="text-sm text-muted mb-3">
        Manage the list of known courier partners. These are used during sheet-to-courier mapping.
      </p>
      <div className="inline-add mb-3">
        <input
          type="text"
          value={newCourier}
          onChange={(e) => setNewCourier(e.target.value)}
          placeholder="Enter courier name"
          onKeyDown={(e) => e.key === 'Enter' && addCourier()}
        />
        <button className="btn btn-sm btn-outline" onClick={addCourier} disabled={saving}>
          <Plus size={16} /> {saving ? 'Saving...' : 'Add'}
        </button>
        {msg && <span className="text-sm" style={{ color: msg === 'Saved!' ? 'var(--success)' : 'var(--danger)' }}>{msg}</span>}
      </div>
      <div className="table-wrap scrollable" style={{ maxHeight: 320 }}>
        <table>
          <thead>
            <tr>
              <th>#</th>
              <th>Courier Name</th>
              <th style={{ width: 80 }}>Action</th>
            </tr>
          </thead>
          <tbody>
            {couriers.map((c, i) => (
              <tr key={c}>
                <td>{i + 1}</td>
                <td>{c}</td>
                <td>
                  <button className="btn btn-xs btn-outline" style={{ color: 'var(--danger)' }} onClick={() => removeCourier(c)}>
                    <Trash2 size={14} />
                  </button>
                </td>
              </tr>
            ))}
            {couriers.length === 0 && (
              <tr><td colSpan={3} className="text-muted text-sm" style={{ textAlign: 'center', padding: 16 }}>No couriers added yet.</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function MappingSection({ token }) {
  const [mapping, setMapping] = useState([]);
  const [newSheet, setNewSheet] = useState('');
  const [newMode, setNewMode] = useState('');
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState('');
  const [editIdx, setEditIdx] = useState(-1);
  const [editSheet, setEditSheet] = useState('');
  const [editMode, setEditMode] = useState('');

  useEffect(() => {
    loadMapping();
  }, []);

  const loadMapping = async () => {
    try {
      const r = await fetch(`${getBase()}/api/mapping`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      if (r.ok) setMapping(await r.json());
    } catch {}
  };

  const persistMapping = async (list) => {
    setSaving(true);
    setMsg('');
    try {
      const r = await fetch(`${getBase()}/api/mapping`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
        body: JSON.stringify(list),
      });
      if (r.ok) setMsg('Saved!');
      else setMsg('Save failed.');
    } catch (e) {
      setMsg('Error: ' + e.message);
    } finally {
      setSaving(false);
      setTimeout(() => setMsg(''), 3000);
    }
  };

  const addRecord = () => {
    if (!newSheet.trim() || !newMode.trim()) return;
    const updated = [...mapping, { "Sheet Name": newSheet.trim(), "Mode": newMode.trim() }];
    setMapping(updated);
    setNewSheet('');
    setNewMode('');
    persistMapping(updated);
  };

  const removeRecord = (idx) => {
    const updated = mapping.filter((_, i) => i !== idx);
    setMapping(updated);
    persistMapping(updated);
  };

  const startEdit = (idx) => {
    setEditIdx(idx);
    setEditSheet(mapping[idx]["Sheet Name"]);
    setEditMode(mapping[idx]["Mode"]);
  };

  const saveEdit = () => {
    if (editIdx < 0) return;
    const updated = [...mapping];
    updated[editIdx] = { "Sheet Name": editSheet.trim(), "Mode": editMode.trim() };
    setMapping(updated);
    setEditIdx(-1);
    persistMapping(updated);
  };

  const cancelEdit = () => {
    setEditIdx(-1);
  };

  return (
    <div className="settings-section">
      <h3><Map size={18} /> Courier Modes Mapping</h3>
      <p className="text-sm text-muted mb-3">
        Each row maps an output sheet name to a mode. This controls how output sheets are named and generated.
      </p>
      <div className="inline-add mb-3" style={{ flexWrap: 'wrap' }}>
        <input type="text" value={newSheet} onChange={(e) => setNewSheet(e.target.value)} placeholder="Sheet Name" style={{ maxWidth: 220 }} />
        <input type="text" value={newMode} onChange={(e) => setNewMode(e.target.value)} placeholder="Mode (e.g. Surface)" style={{ maxWidth: 180 }}
          onKeyDown={(e) => e.key === 'Enter' && addRecord()}
        />
        <button className="btn btn-sm btn-outline" onClick={addRecord} disabled={saving}>
          <Plus size={16} /> {saving ? 'Saving...' : 'Add'}
        </button>
        {msg && <span className="text-sm" style={{ color: msg === 'Saved!' ? 'var(--success)' : 'var(--danger)' }}>{msg}</span>}
      </div>
      <div className="table-wrap scrollable" style={{ maxHeight: 400 }}>
        <table>
          <thead>
            <tr>
              <th>#</th>
              <th>Sheet Name</th>
              <th>Mode</th>
              <th style={{ width: 120 }}>Actions</th>
            </tr>
          </thead>
          <tbody>
            {mapping.map((rec, i) => (
              <tr key={i}>
                <td>{i + 1}</td>
                <td>
                  {editIdx === i ? (
                    <input type="text" value={editSheet} onChange={(e) => setEditSheet(e.target.value)} style={{ width: '100%' }} />
                  ) : rec["Sheet Name"]}
                </td>
                <td>
                  {editIdx === i ? (
                    <input type="text" value={editMode} onChange={(e) => setEditMode(e.target.value)} style={{ width: '100%' }} />
                  ) : rec["Mode"]}
                </td>
                <td>
                  {editIdx === i ? (
                    <div className="flex gap-2">
                      <button className="btn btn-xs btn-primary" onClick={saveEdit}>Save</button>
                      <button className="btn btn-xs btn-outline" onClick={cancelEdit}>Cancel</button>
                    </div>
                  ) : (
                    <div className="flex gap-2">
                      <button className="btn btn-xs btn-outline" onClick={() => startEdit(i)}>Edit</button>
                      <button className="btn btn-xs btn-outline" style={{ color: 'var(--danger)' }} onClick={() => removeRecord(i)}>
                        <Trash2 size={14} />
                      </button>
                    </div>
                  )}
                </td>
              </tr>
            ))}
            {mapping.length === 0 && (
              <tr><td colSpan={4} className="text-muted text-sm" style={{ textAlign: 'center', padding: 16 }}>No mapping records.</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function DefaultsSection({ token }) {
  const [defaults, setDefaults] = useState({
    volumetric_coefficient: 5000,
    tax_pct: 18,
    is_gst_inclusive: false,
    fuel_surcharge_pct: 0,
    docket_charge: 0,
    qc_charges: 0,
    cod_invoice_pct: 1.5,
    cod_operator: 'MAX',
    cod_fixed_charge: 30,
  });
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState('');

  useEffect(() => {
    loadDefaults();
  }, []);

  const loadDefaults = async () => {
    try {
      const r = await fetch(`${getBase()}/api/defaults`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      if (r.ok) {
        const data = await r.json();
        if (data && typeof data === 'object' && Object.keys(data).length > 0) {
          setDefaults(prev => ({ ...prev, ...data }));
        }
      }
    } catch {}
  };

  const updateField = (key, value) => {
    setDefaults(prev => ({ ...prev, [key]: value }));
  };

  const saveDefaults = async () => {
    setSaving(true);
    setMsg('');
    try {
      const r = await fetch(`${getBase()}/api/defaults`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
        body: JSON.stringify(defaults),
      });
      if (r.ok) setMsg('Saved!');
      else setMsg('Save failed.');
    } catch (e) {
      setMsg('Error: ' + e.message);
    } finally {
      setSaving(false);
      setTimeout(() => setMsg(''), 3000);
    }
  };

  const fields = [
    { key: 'volumetric_coefficient', label: 'Volumetric Coefficient', type: 'number' },
    { key: 'tax_pct', label: 'Tax (%)', type: 'number' },
    { key: 'is_gst_inclusive', label: 'Is GST Inclusive', type: 'bool' },
    { key: 'fuel_surcharge_pct', label: 'Fuel Surcharge (%)', type: 'number' },
    { key: 'docket_charge', label: 'Docket Charge', type: 'number' },
    { key: 'qc_charges', label: 'QC Charges (Rs)', type: 'number' },
    { key: 'cod_invoice_pct', label: 'Invoice % for COD', type: 'number' },
    { key: 'cod_operator', label: 'COD Operator (Min/Max)', type: 'select', options: ['MIN', 'MAX'] },
    { key: 'cod_fixed_charge', label: 'Fixed COD Charge', type: 'number' },
  ];

  return (
    <div className="settings-section">
      <h3><Sliders size={18} /> Default Values</h3>
      <p className="text-sm text-muted mb-3">
        Default values used when global parameters are missing from the base file.
      </p>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: 16 }}>
        {fields.map(f => (
          <div key={f.key}>
            <label>{f.label}</label>
            {f.type === 'number' && (
              <input
                type="number"
                step="any"
                value={defaults[f.key] ?? ''}
                onChange={(e) => updateField(f.key, e.target.value === '' ? 0 : parseFloat(e.target.value))}
              />
            )}
            {f.type === 'bool' && (
              <select
                value={defaults[f.key] ? 'true' : 'false'}
                onChange={(e) => updateField(f.key, e.target.value === 'true')}
              >
                <option value="false">FALSE</option>
                <option value="true">TRUE</option>
              </select>
            )}
            {f.type === 'select' && (
              <select
                value={defaults[f.key] || ''}
                onChange={(e) => updateField(f.key, e.target.value)}
              >
                {f.options.map(o => <option key={o} value={o}>{o}</option>)}
              </select>
            )}
          </div>
        ))}
      </div>
      <div className="flex gap-3 mt-4 items-center">
        <button className="btn btn-primary" onClick={saveDefaults} disabled={saving}>
          <Save size={16} /> {saving ? 'Saving...' : 'Save Defaults'}
        </button>
        {msg && <span className="text-sm" style={{ color: msg === 'Saved!' ? 'var(--success)' : 'var(--danger)' }}>{msg}</span>}
      </div>
    </div>
  );
}

export default function Settings({ token }) {
  const [subTab, setSubTab] = useState('couriers');

  return (
    <div className="card">
      <h2 style={{ fontSize: '1.15rem', marginTop: 0, marginBottom: 16 }}>Settings</h2>
      <div className="flex gap-3 mb-4" style={{ flexWrap: 'wrap' }}>
        {[
          { id: 'couriers', label: 'Couriers', icon: Package },
          { id: 'mapping', label: 'Courier Modes', icon: Map },
          { id: 'defaults', label: 'Default Values', icon: Sliders },
        ].map(t => (
          <button
            key={t.id}
            className={`tab-btn ${subTab === t.id ? 'active' : ''}`}
            style={{ fontSize: '0.82rem', padding: '8px 18px' }}
            onClick={() => setSubTab(t.id)}
          >
            <t.icon size={14} style={{ marginRight: 4 }} /> {t.label}
          </button>
        ))}
      </div>

      {subTab === 'couriers' && <CouriersSection token={token} />}
      {subTab === 'mapping' && <MappingSection token={token} />}
      {subTab === 'defaults' && <DefaultsSection token={token} />}
    </div>
  );
}
